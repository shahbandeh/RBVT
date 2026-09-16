"""RTVT-style command-line entry point."""
import argparse
import math
import sys
from pathlib import Path
from . import __version__

FILTERS = {"F062": .62, "F087": .87, "F106": 1.06, "F129": 1.29,
           "F146": 1.46, "F158": 1.58, "F184": 1.84, "F213": 2.13,
           "Prism": 1.25, "Grism": 1.42}


def build_parser():
    p = argparse.ArgumentParser(description="Roman Background Visualization Tool")
    p.add_argument("--version", action="version", version=f"rbvt {__version__}")
    p.add_argument("--ra", "--lon", required=True, help="RA in degrees or sexagesimal hours; longitude in other frames")
    p.add_argument("--dec", "--lat", required=True, help="Dec in degrees or sexagesimal degrees; latitude in other frames")
    p.add_argument("--coordinate-system", "--coords", choices=["equatorial", "galactic", "ecliptic"], default="equatorial")
    selection = p.add_mutually_exclusive_group()
    selection.add_argument("--filter", choices=FILTERS, help="Representative wavelength (default: F184); not bandpass-integrated")
    selection.add_argument("--wavelength", type=float, help="Wavelength in microns")
    p.add_argument("--threshold", type=float, default=1.1, help="Multiplier of minimum background (>=1)")
    p.add_argument("--day", type=int, help="Spectrum day, 0–365 (Jan 1=0); default: first available day")
    p.add_argument("--target-name", help="Display label")
    p.add_argument("--write-csv", help="Save daily background components as CSV")
    p.add_argument("--write-spectrum", help="Save selected day's spectrum as CSV")
    p.add_argument("--write-plot", help="Save background and spectrum figure (PNG, PDF, SVG)")
    p.add_argument("--write-report", help="Save self-contained HTML report")
    p.add_argument("--show-plot", action="store_true")
    p.add_argument("--interactive", action="store_true", help="Launch the original interactive Bokeh viewer")
    p.add_argument("--port", type=int, default=5006, help="Interactive viewer port (default: 5006)")
    p.add_argument("--no-browser", action="store_true", help="Do not open the interactive viewer automatically")
    p.add_argument("--quiet", action="store_true", help="Suppress summary")
    return p


def parse_target(lon, lat, frame):
    from astropy.coordinates import SkyCoord, BarycentricTrueEcliptic
    from astropy import units as u
    if frame == "equatorial":
        unit = u.hourangle if any(c in lon.lower() for c in ':hms ') else u.deg
        target = SkyCoord(lon, lat, unit=(unit, u.deg), frame="icrs")
    else:
        target = SkyCoord(float(lon)*u.deg, float(lat)*u.deg,
                          frame="galactic" if frame == "galactic" else BarycentricTrueEcliptic())
    target = target.icrs
    if not all(math.isfinite(x) for x in (target.ra.deg, target.dec.deg)):
        raise ValueError("Coordinates must be finite")
    return target


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.threshold) or args.threshold < 1:
            raise ValueError("--threshold must be finite and >=1")
        if args.day is not None and not 0 <= args.day <= 365:
            raise ValueError("--day must be 0–365 (Jan 1=0)")
        if not 1 <= args.port <= 65535:
            raise ValueError("--port must be 1–65535")
        if args.interactive and (args.wavelength is not None or any((args.write_csv, args.write_spectrum, args.write_plot, args.write_report, args.show_plot))):
            raise ValueError("Use --interactive with --filter; run exports separately")
        target = parse_target(args.ra, args.dec, args.coordinate_system)
        if args.interactive:
            return serve(args, target)
        from .background import background
        from .products import daily_table, spectrum_table, summary, write_csv, render_products
        wave = args.wavelength if args.wavelength is not None else FILTERS[args.filter or "F184"]
        result = background(target.ra.deg, target.dec.deg, wave, args.threshold)
        calendar = result.bkg_data['calendar']
        day = int(calendar[0]) if args.day is None else args.day
        if day not in calendar:
            raise ValueError(f"Day {day} has no observable background data; omit --day to use the first available day")
        # Validate destinations before producing files.
        paths = [Path(p).expanduser().resolve() for p in (args.write_csv, args.write_spectrum, args.write_plot, args.write_report) if p]
        if len(set(paths)) != len(paths):
            raise ValueError("Output files must have distinct paths")
        if args.write_csv:
            write_csv(daily_table(result), args.write_csv)
        if args.write_spectrum:
            write_csv(spectrum_table(result, day), args.write_spectrum)
        if not args.quiet:
            print(summary(result, day, args.target_name))
        if args.write_plot or args.show_plot or args.write_report:
            render_products(result, day, args)
        return 0
    except (ValueError, OSError, ImportError) as exc:
        print(f"rbvt: error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


def serve(args, target):
    from bokeh.server.server import Server
    from .viewer import plot_rbt
    def app(doc):
        doc.title = "Roman Background Visualization Tool"
        plot_rbt(doc, ra=target.ra.deg, dec=target.dec.deg,
                 default_filter=args.filter or "F184", thresh=args.threshold,
                 thisday=args.day if args.day is not None else 100)
    server = Server(
        {'/': app}, address="127.0.0.1", port=args.port,
        allow_websocket_origin=[f"127.0.0.1:{args.port}", f"localhost:{args.port}"],
    )
    server.start()
    print(f"RBVT viewer: http://127.0.0.1:{args.port}/ (Ctrl+C to stop)")
    if not args.no_browser:
        server.io_loop.add_callback(server.show, "/")
    try:
        server.io_loop.start()
    finally:
        server.stop()
    return 0
