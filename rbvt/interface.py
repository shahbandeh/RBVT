"""Shared request validation and exports for the desktop and web interfaces."""
from dataclasses import dataclass
import io
import math
import shlex

from .cli import FILTERS, parse_target
from .background import background
from .products import daily_table, spectrum_table, plot_background, report_html


@dataclass(frozen=True)
class BackgroundRequest:
    longitude: str = '180'
    latitude: str = '0'
    coordinate_system: str = 'equatorial'
    optical_element: str = 'F184'
    wavelength: float = 1.84
    threshold: float = 1.1
    target_name: str = ''

    def parameters(self):
        if self.coordinate_system not in ('equatorial', 'galactic', 'ecliptic'):
            raise ValueError('Choose equatorial, galactic, or ecliptic coordinates')
        target = parse_target(self.longitude.strip(), self.latitude.strip(), self.coordinate_system)
        if self.optical_element == 'Custom wavelength':
            wave = float(self.wavelength)
        elif self.optical_element in FILTERS:
            wave = FILTERS[self.optical_element]
        else:
            raise ValueError('Choose an optical element or custom wavelength')
        threshold = float(self.threshold)
        if not math.isfinite(wave) or wave <= 0:
            raise ValueError('Wavelength must be a finite positive number')
        if not math.isfinite(threshold) or threshold < 1:
            raise ValueError('Threshold must be finite and at least 1')
        return target, wave, threshold

    def calculate(self):
        target, wave, threshold = self.parameters()
        return background(target.ra.deg, target.dec.deg, wave, threshold)

    def command(self, day=None):
        self.parameters()
        # Use --option=value so negative sexagesimal coordinates remain unambiguous.
        args = ['rbvt', f'--ra={self.longitude}', f'--dec={self.latitude}',
                '--coordinate-system', self.coordinate_system,
                '--threshold', str(self.threshold)]
        if self.optical_element == 'Custom wavelength':
            args.extend(['--wavelength', str(self.wavelength)])
        else:
            args.extend(['--filter', self.optical_element])
        if self.target_name:
            args.extend(['--target-name', self.target_name])
        if day is not None:
            args.extend(['--day', str(day)])
        return shlex.join(args)


def make_figure(result, day, name=''):
    # Object-oriented figures avoid global pyplot windows/backends in both UIs.
    from matplotlib.figure import Figure
    fig = Figure(figsize=(13, 5), constrained_layout=True)
    return plot_background(result, day, name or None, figure=fig)


def export_products(result, day, name=''):
    fig = make_figure(result, day, name)
    image = io.BytesIO()
    fig.savefig(image, format='png', dpi=150)
    png = image.getvalue()
    return {
        'daily.csv': daily_table(result).to_csv(index=False).encode('utf-8'),
        'spectrum.csv': spectrum_table(result, day).to_csv(index=False).encode('utf-8'),
        'background.png': png,
        'report.html': report_html(result, day, name, png).encode('utf-8'),
    }
