"""Tables and plots of the existing Roman background model."""
import base64
import html
import io
from pathlib import Path
import numpy as np
import pandas as pd


def daily_table(result):
    b = result.bathtub
    return pd.DataFrame({"day": result.bkg_data['calendar'],
                         "wavelength_um": result.wavelength,
                         "total_MJy_sr": b['total_thiswave'],
                         "zodi_MJy_sr": b['zodi_thiswave'],
                         "thermal_MJy_sr": float(b['thermal_thiswave']),
                         "ism_cib_MJy_sr": float(b['nonzodi_thiswave']),
                         "below_threshold": b['total_thiswave'] < b['themin'] * result.thresh})


def spectrum_table(result, day):
    b = result.bkg_data
    indices = np.flatnonzero(b['calendar'] == day)
    if not len(indices):
        raise ValueError(f"Day {day} has no observable background data")
    idx = indices[0]
    return pd.DataFrame({"day": day, "wavelength_um": b['wave_array'],
                         "total_MJy_sr": b['total_bg'][idx],
                         "zodi_MJy_sr": b['zodi_bg'][idx],
                         "thermal_MJy_sr": b['thermal_bg'],
                         "ism_cib_MJy_sr": b['nonzodi_bg']})


def output_path(path):
    path = Path(path).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def write_csv(table, path):
    table.to_csv(output_path(path), index=False)


def summary(result, day, name=None):
    return (f"{name or 'Roman background'}\n"
            f"ICRS RA={result.ra:.6f} deg, Dec={result.dec:.6f} deg\n"
            f"Wavelength: {result.wavelength:g} microns (monochromatic)\n"
            f"Observable days with cache data: {len(result.bkg_data['calendar'])}\n"
            f"Minimum background: {result.bathtub['themin']:.6g} MJy/sr\n"
            f"Days below {result.thresh:g} × minimum: {result.bathtub['good_days']}\n"
            f"Spectrum day: {day} (Jan 1=0; reference year 2024)\n"
            f"Background cache version: {result.cache_version}")


def plot_background(result, day, name=None, figure=None):
    if figure is None:
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(13, 5), constrained_layout=True)
    else:
        fig = figure
        axes = fig.subplots(1, 2)
    tables = [daily_table(result).set_index('day').reindex(range(366)), spectrum_table(result, day).set_index('wavelength_um')]
    for ax, table in zip(axes, tables):
        for column, label, color in [('total_MJy_sr', 'Total', 'black'), ('zodi_MJy_sr', 'Zodi', 'orange'), ('thermal_MJy_sr', 'Thermal', 'red'), ('ism_cib_MJy_sr', 'ISM+CIB', 'blue')]:
            ax.plot(table.index, table[column], label=label, color=color)
        ax.set_yscale('log')
        ax.set_ylabel('Background (MJy/sr)')
        ax.legend()
    axes[0].axhline(result.bathtub['themin'] * result.thresh, color='gray', linestyle=':', label='Threshold')
    axes[0].legend()
    axes[0].set(xlabel='Day of year (Jan 1=0)', title=f'{result.wavelength:g} μm', xlim=(0, 365))
    axes[1].set(xlabel='Wavelength (μm)', title=f'Spectrum on day {day}', xlim=(.5, 2.5), ylim=(1e-5, 100))
    fig.suptitle(name or f'Roman background: RA={result.ra:.3f}°, Dec={result.dec:.3f}°')
    return fig


def render_products(result, day, args):
    import matplotlib
    if not args.show_plot:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig = plot_background(result, day, args.target_name)
    try:
        if args.write_plot:
            fig.savefig(output_path(args.write_plot), dpi=150)
        if args.write_report:
            data = io.BytesIO()
            fig.savefig(data, format='png', dpi=150)
            output_path(args.write_report).write_text(
                report_html(result, day, args.target_name, data.getvalue()), encoding='utf-8'
            )
        if args.show_plot:
            plt.show()
    finally:
        plt.close(fig)


def report_html(result, day, name, png):
    """Build the same self-contained report for CLI, desktop, and web exports."""
    encoded = base64.b64encode(png).decode('ascii')
    title = html.escape(name or 'Roman Background Visualization Tool')
    return (f'<!doctype html><html lang="en"><meta charset="utf-8"><title>{title}</title>'
            f'<h1>{title}</h1><pre>{html.escape(summary(result, day, name))}</pre>'
            f'<img style="max-width:100%" alt="Daily background and spectrum" '
            f'src="data:image/png;base64,{encoded}">'
            '<p>Monochromatic backgrounds; filter names denote representative wavelengths. '
            'Gaps indicate unavailable or unobservable days. Visibility uses the original '
            '2024 reference year.</p></html>')
