# Roman Background Visualization Tool (RBVT)

An installable CLI and interactive viewer for the Roman background model,
with a command-line workflow similar to [RTVT](https://github.com/shahbandeh/RTVT).

## Install

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
rbvt --help
rbvt --version
```

Python 3.9 or newer is required. Calculations download the selected sky pixel
from the STScI background cache and require internet access. The wavelength grid
and thermal curve are included in the package. No local cache is maintained.

Once this repository is available on GitHub:

```bash
python -m pip install "git+https://github.com/shahbandeh/RBVT.git"
```

## CLI examples

```bash
rbvt --ra 180 --dec 0
rbvt --ra '12:00:00' --dec=-10:30:00 --filter F158 --threshold 1.2
rbvt --coordinate-system galactic --lon 0 --lat 0 --wavelength 1.84
rbvt --ra 180 --dec 0 --filter F184 --target-name 'Example target' \
  --write-csv results/daily.csv \
  --write-spectrum results/spectrum.csv \
  --write-plot results/background.png \
  --write-report results/report.html
rbvt --ra 180 --dec 0 --show-plot
```

`roman_bvt` and `python -m rbvt` provide the same interface. Equatorial inputs
accept degrees or sexagesimal RA (hours) and Dec (degrees). Use `--dec=-10:30:00`
for negative sexagesimal values. Galactic and ecliptic inputs are decimal degrees;
ecliptic coordinates use Astropy's barycentric true ecliptic frame at J2000.

`--filter` accepts F062, F087, F106, F129, F146, F158, F184 (default), F213,
Prism, or Grism. These select the original viewer's representative wavelengths,
**not bandpass-integrated backgrounds**. `--wavelength` selects a wavelength
in microns instead. `--threshold` is a multiplier of the minimum daily total
background; good days satisfy the strict condition `total < threshold * minimum`.

`--day` selects a spectrum day in the original zero-based calendar (0–365,
January 1 = 0). By default, the first observable day with cache data is used.
Unavailable days produce an error. The original visibility calculation uses
**2024 as its reference year** and a 54–126 degree Sun-angle constraint. This CLI
does not extrapolate the cache to arbitrary observing dates. Daily tables only
contain observable days with data, and plots leave gaps between visibility windows.
The spectrum plot displays 0.5–2.5 microns and 1e-5–100 MJy/sr, matching
the original viewer; spectrum CSV files retain the full model grid.
CSV column names include units: wavelengths in microns, backgrounds in MJy/sr.
Outputs replace existing files at the requested paths; missing parent directories
are created. Errors exit with status 2 and `--quiet` suppresses the summary.

## Interactive viewer

Launch the original three-panel Bokeh visualization from a terminal:

```bash
rbvt --ra 180 --dec 0 --filter F184 --interactive
rbvt --ra 180 --dec 0 --interactive --no-browser --port 5007
```

The viewer provides daily backgrounds, spectra, distributions by optical element,
coordinate controls, thresholds, and component overlays. It runs on localhost;
keep the terminal running and press Ctrl+C to stop. Viewer save buttons write CSV
files to the terminal’s working directory. If the initial day is unavailable,
the viewer selects a visible day, as in the original notebook. Interactive mode
uses filter selections; run custom-wavelength calculations and file exports separately.

## Python and notebooks

```python
from rbvt.background import background
from rbvt.products import daily_table, spectrum_table

result = background(180, 0, wavelength=1.84, thresh=1.1)
daily = daily_table(result)
spectrum = spectrum_table(result, int(result.bkg_data['calendar'][0]))
```

The Bokeh document builder is available as `rbvt.viewer.plot_rbt`.

## Development

```bash
python -m pip install -e '.[test]'
python -m pytest
python -m pip wheel . --no-deps -w dist
```

Tests use synthetic cache files and do not require the remote service. They check
coordinate handling, scientific-model equivalence, cache mappings, command errors,
exports, packaging resources, and the Bokeh document.

## Provenance

Adapted from `notebooks/background_visualization_tool` in
[roman_notebooks](https://github.com/shahbandeh/roman_notebooks), retaining its
background model, NIRCam-informed correction, thermal reference data, and interactive
visualization. The upstream BSD 3-Clause license is included in `LICENSE`.
The visibility helper retains its attribution to Jeff Kruk and
`spacetelescope/roman-technical-information`. The scientific model is preserved;
the package adds validation, bounded network timeouts, and clear errors for absent
or inconsistent cache data. The model modifies total and component spectra
separately, following the source implementation.
