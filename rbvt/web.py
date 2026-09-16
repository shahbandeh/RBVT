"""Streamlit application and installed launcher."""
from pathlib import Path
import subprocess
import sys


def run_app():
    import streamlit as st
    from rbvt.cli import FILTERS
    from rbvt.interface import BackgroundRequest, export_products
    from rbvt.products import daily_table, spectrum_table, summary

    st.set_page_config(page_title='RBVT · Roman backgrounds', page_icon='🔭', layout='wide')
    st.title('Roman Background Visualization Tool')
    st.caption('Explore sky backgrounds, choose an observing day, and export your results.')
    with st.sidebar:
        st.header('Target & background')
        # Controls outside a form update coordinate labels and custom-wave availability immediately.
        frame = st.selectbox('Coordinate system', ['equatorial', 'galactic', 'ecliptic'], key='frame')
        name = st.text_input('Target label (optional)', key='name')
        lon_label, lat_label = {'equatorial': ('RA', 'Dec'), 'galactic': ('Galactic longitude', 'Galactic latitude'),
                               'ecliptic': ('Ecliptic longitude', 'Ecliptic latitude')}[frame]
        lon = st.text_input(lon_label, '180', key='lon')
        lat = st.text_input(lat_label, '0', key='lat')
        st.caption('Equatorial: degrees or sexagesimal RA hours / Dec degrees. Other frames: decimal degrees.')
        element = st.selectbox('Optical element', list(FILTERS) + ['Custom wavelength'], index=6, key='element')
        wave = st.number_input('Custom wavelength (μm)', min_value=0.001, value=1.84, format='%.3f',
                               disabled=element != 'Custom wavelength', key='wave')
        threshold = st.number_input('Threshold × minimum', min_value=1.0, value=1.1, step=0.05, key='threshold')
        compute = st.button('Calculate background', type='primary', key='calculate')
        st.caption('Filter names select representative wavelengths, not bandpass integrals. Calendar days use reference year 2024, with January 1 = 0.')
    request = BackgroundRequest(lon, lat, frame, element, wave, threshold, name)
    if compute:
        try:
            with st.spinner('Loading background from STScI…'):
                result = request.calculate()
            st.session_state['calculation'] = (request, result)
            st.session_state['day'] = int(result.bkg_data['calendar'][0])
            st.session_state.pop('exports', None)
        except Exception as exc:
            st.error(f'Unable to calculate background: {exc}')
            # Do not leave a previous target available for download after a failed submission.
            st.session_state.pop('calculation', None)
            st.session_state.pop('exports', None)
    if 'calculation' not in st.session_state:
        st.info('Enter your target at left and select Calculate background to begin.')
        return
    saved_request, result = st.session_state['calculation']
    if request != saved_request:
        st.warning('Inputs have changed. Results below belong to the last calculation; select Calculate background to update.')
    st.subheader(saved_request.target_name or 'Background results')
    st.caption(f'ICRS RA {result.ra:.6f}°, Dec {result.dec:.6f}° · {result.wavelength:g} μm · threshold {result.thresh:g} × minimum')
    cols = st.columns(3)
    cols[0].metric('Observable days with data', len(result.bkg_data['calendar']))
    cols[1].metric('Days below threshold', result.bathtub['good_days'])
    cols[2].metric('Minimum background (MJy/sr)', f"{result.bathtub['themin']:.5g}")
    days = [int(d) for d in result.bkg_data['calendar']]
    day = st.selectbox('Spectrum day (Jan 1 = 0)', days, key='day')
    # Rendering and downloads share a snapshot; selecting a day never downloads model data.
    export_key = (saved_request, day)
    cached = st.session_state.get('exports')
    if cached is None or cached[0] != export_key:
        products = export_products(result, day, saved_request.target_name)
        st.session_state['exports'] = (export_key, products)
    else:
        products = cached[1]
    plots, tables, report = st.tabs(['Background & spectrum', 'Data tables', 'Summary & command'])
    with plots:
        st.image(products['background.png'], use_container_width=True)
        st.caption('Gaps mark unavailable or unobservable days. Spectrum display: 0.5–2.5 μm, 10⁻⁵–100 MJy/sr; CSV includes the full model grid.')
    with tables:
        st.subheader('Daily background')
        st.dataframe(daily_table(result), use_container_width=True, hide_index=True)
        st.subheader('Selected-day spectrum')
        st.dataframe(spectrum_table(result, day), use_container_width=True, hide_index=True)
    with report:
        st.text(summary(result, day, saved_request.target_name))
        st.code(saved_request.command(day), language='bash')
    st.subheader('Download results')
    labels = [('daily.csv', 'Daily CSV', 'text/csv'), ('spectrum.csv', 'Spectrum CSV', 'text/csv'),
              ('background.png', 'Plot PNG', 'image/png'), ('report.html', 'HTML report', 'text/html')]
    for col, (filename, label, mime) in zip(st.columns(4), labels):
        col.download_button(label, products[filename], file_name=filename, mime=mime, key=filename)


def main():
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print('Install the web dependencies with: python -m pip install "rbvt[web]"', file=sys.stderr)
        return 2
    command = [sys.executable, '-m', 'streamlit', 'run', str(Path(__file__).resolve()), *sys.argv[1:]]
    try:
        return subprocess.call(command)
    except KeyboardInterrupt:
        return 130


if __name__ == '__main__':
    run_app()
