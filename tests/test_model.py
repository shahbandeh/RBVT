import io
import numpy as np
import pytest


def test_model_interpolation(offline):
    from rbvt.background import background
    b = background(180, 0, 1.84)
    days = b.bkg_data['calendar']
    # At 1.84 μm the NIRCam correction leaves a flat synthetic spectrum unchanged.
    expected_zodi = .5 + days/365
    np.testing.assert_allclose(b.bathtub['zodi_thiswave'], expected_zodi)
    np.testing.assert_allclose(b.bathtub['nonzodi_thiswave'], .2)
    np.testing.assert_allclose(b.bathtub['total_thiswave'], expected_zodi + .2 + b.bathtub['thermal_thiswave'])
    assert b.bathtub['themin'] == pytest.approx(np.min(b.bathtub['total_thiswave']))
    assert b.bkg_data['total_bg'].shape[0] == len(days)


def test_corrupt_mapping(monkeypatch, cache_bytes):
    import rbvt.background as model
    # Remove all packed spectra but preserve a valid header.
    from pathlib import Path
    n = len(np.loadtxt(Path(model.__file__).parent/'refdata/std_spectrum_wavelengths.txt'))
    header_length = 5*8 + n*8 + 366*4
    monkeypatch.setattr(model.urllib.request,'urlopen',lambda *a, **k: io.BytesIO(cache_bytes[:header_length]))
    with pytest.raises(ValueError, match='invalid day mapping'):
        model.background(180,0,1.84)


def test_empty_calendar(monkeypatch, cache_bytes):
    import rbvt.background as model
    from pathlib import Path
    n = len(np.loadtxt(Path(model.__file__).parent/'refdata/std_spectrum_wavelengths.txt'))
    payload = bytearray(cache_bytes)
    days = np.frombuffer(payload,dtype='i4',count=366,offset=5*8+n*8)
    days[:] = -1
    monkeypatch.setattr(model.urllib.request,'urlopen',lambda *a, **k: io.BytesIO(payload))
    with pytest.raises(ValueError, match='No observable days'):
        model.background(180,0,1.84)


def test_packaged_resources():
    from importlib.resources import files
    data = files('rbvt') / 'refdata'
    assert (data / 'std_spectrum_wavelengths.txt').is_file()
    assert (data / 'thermal_curve_roman_rryan_v1.0.csv').is_file()
