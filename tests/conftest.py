"""Deterministic cache fixture, exercising the real model and visibility mask."""
import io
import os
import tempfile
os.environ.setdefault('MPLCONFIGDIR', tempfile.mkdtemp(prefix='rbvt-mpl-'))

import numpy as np
import pytest

@pytest.fixture
def cache_bytes():
    from rbvt.background import background
    from pathlib import Path
    import rbvt.background as model
    n = len(np.loadtxt(Path(model.__file__).parent / 'refdata/std_spectrum_wavelengths.txt'))
    header = np.zeros(1, dtype=[('ra','f8'), ('dec','f8'), ('pos','f8',(3,)), ('nonzodi','f8',(n,)), ('days','i4',(366,))])
    header['ra'] = 180
    header['nonzodi'] = .2
    header['days'] = np.arange(366)
    spectra = np.zeros(366, dtype=[('zodi','f8',(n,)), ('stray','f8',(n,))])
    spectra['zodi'] = np.linspace(.5, 1.5, 366)[:, None]
    return header.tobytes() + spectra.tobytes()

@pytest.fixture
def offline(monkeypatch, cache_bytes):
    import rbvt.background as model
    monkeypatch.setattr(model.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(cache_bytes))

@pytest.fixture(autouse=True)
def no_iers_download():
    from astropy.utils import iers
    with iers.conf.set_temp('auto_download', False):
        yield
