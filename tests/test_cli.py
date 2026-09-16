from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from rbvt.cli import main, parse_target


def test_help_and_version(capsys):
    for flag in ['--help', '--version']:
        with pytest.raises(SystemExit) as exc:
            main([flag])
        assert exc.value.code == 0
    assert '0.1.0' in capsys.readouterr().out


def test_coordinates():
    t = parse_target('12:00:00', '-10:30:00', 'equatorial')
    assert t.ra.deg == pytest.approx(180)
    assert t.dec.deg == pytest.approx(-10.5)
    t = parse_target('0', '0', 'galactic')
    assert t.ra.deg == pytest.approx(266.40499, abs=.001)
    assert t.dec.deg == pytest.approx(-28.93618, abs=.001)
    assert np.isfinite(parse_target('90', '10', 'ecliptic').ra.deg)


@pytest.mark.parametrize('extra', [
    ['--threshold', 'nan'], ['--threshold', '.9'], ['--day', '366'],
    ['--wavelength', 'nan'], ['--wavelength', '-1'], ['--dec', '91'],
    ['--ra', 'nan'], ['--interactive', '--wavelength', '1.5'],
    ['--interactive', '--write-csv', 'unused.csv']])
def test_invalid_inputs(extra, monkeypatch, capsys):
    import urllib.request
    def unexpected(*a, **k):
        pytest.fail('Invalid inputs should not download data')
    monkeypatch.setattr(urllib.request, 'urlopen', unexpected)
    assert main(['--ra', '180', '--dec', '0'] + extra) == 2
    assert 'error:' in capsys.readouterr().err


def test_outputs(offline, tmp_path, capsys):
    paths = {flag: tmp_path / 'nested' / name for flag, name in [
        ('--write-csv', 'daily.csv'), ('--write-spectrum', 'spectrum.csv'),
        ('--write-plot', 'background.png'), ('--write-report', 'report.html')]}
    args = ['--ra','180','--dec','0','--target-name','<Test>']
    for flag, path in paths.items():
        args.extend([flag, str(path)])
    assert main(args) == 0
    assert 'Observable days' in capsys.readouterr().out
    daily = pd.read_csv(paths['--write-csv'])
    assert daily.day.is_unique
    assert ((daily.day >= 0) & (daily.day <= 365)).all()
    assert 0 < len(daily) < 366
    assert np.array_equal(daily.below_threshold, daily.total_MJy_sr < daily.total_MJy_sr.min()*1.1)
    spectrum = pd.read_csv(paths['--write-spectrum'])
    assert spectrum.day.unique() == [daily.day.iloc[0]]
    assert paths['--write-plot'].read_bytes().startswith(b'\x89PNG')
    report = paths['--write-report'].read_text()
    assert '&lt;Test&gt;' in report and 'data:image/png;base64,' in report


def test_unavailable_day_and_duplicate_paths(offline, tmp_path, capsys):
    from rbvt.background import background
    b = background(180, 0, 1.84)
    missing = next(d for d in range(366) if d not in b.bkg_data['calendar'])
    path = tmp_path/'out.csv'
    assert main(['--ra','180','--dec','0','--day',str(missing),'--write-csv',str(path)]) == 2
    assert not path.exists()
    assert main(['--ra','180','--dec','0','--write-csv',str(path),'--write-spectrum',str(path)]) == 2
    assert not path.exists()


def test_quiet(offline, capsys):
    assert main(['--ra','180','--dec','0','--quiet']) == 0
    assert capsys.readouterr().out == ''


def test_network_error(monkeypatch, capsys):
    import urllib.request
    from urllib.error import URLError
    def fail(*a, **k):
        raise URLError('offline')
    monkeypatch.setattr(urllib.request,'urlopen',fail)
    assert main(['--ra','180','--dec','0']) == 2
    assert 'offline' in capsys.readouterr().err


def test_viewer(offline):
    from bokeh.document import Document
    from rbvt.viewer import plot_rbt
    from bokeh.models import Slider
    doc = Document()
    plot_rbt(doc, ra=180, dec=0, default_filter='F158', thresh=1.2)
    assert len(doc.roots) == 1
    sliders = {s.title: s for s in doc.select({'type': Slider})}
    assert sliders['Threshold (× min bkg)'].value == 1.2
    sliders['Calendar Day'].value = 0
    doc.validate()
    doc.to_json()
