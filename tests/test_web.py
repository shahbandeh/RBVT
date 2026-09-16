from pathlib import Path
import pytest
pytest.importorskip('streamlit')
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / 'streamlit_app.py'


def test_web_calculate_day_and_exports(offline, monkeypatch):
    from rbvt.interface import BackgroundRequest
    original = BackgroundRequest.calculate
    calls = []
    def counted(request):
        calls.append(request)
        return original(request)
    monkeypatch.setattr(BackgroundRequest, 'calculate', counted)
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not app.exception
    assert len(calls) == 0
    app.button(key='calculate').click().run()
    assert not app.exception
    assert len(app.metric) == 3
    assert len(app.dataframe) == 2
    assert len(calls) == 1
    _, result = app.session_state['calculation']
    new_day = int(result.bkg_data['calendar'][1])
    app.selectbox(key='day').set_value(new_day).run()
    assert not app.exception
    assert len(calls) == 1
    assert app.dataframe[1].value.day.unique().tolist() == [new_day]
    assert len(app.get('download_button')) == 4
    app.text_input(key='lon').set_value('90').run()
    assert app.warning
    assert len(calls) == 1
    app.text_input(key='lat').set_value('100').run()
    app.button(key='calculate').click().run()
    assert not app.exception
    assert app.error
    assert not app.metric
    assert not app.get('download_button')


def test_web_custom_wave_and_network_error(offline, monkeypatch):
    from rbvt.interface import BackgroundRequest
    app = AppTest.from_file(str(APP), default_timeout=30).run()
    app.selectbox(key='element').select('Custom wavelength').run()
    app.number_input(key='wave').set_value(1.58).run()
    app.button(key='calculate').click().run()
    assert not app.exception
    assert app.session_state['calculation'][1].wavelength == 1.58
    def fail(_):
        raise OSError('Cache is unavailable')
    monkeypatch.setattr(BackgroundRequest, 'calculate', fail)
    app.button(key='calculate').click().run()
    assert not app.exception
    assert 'Cache is unavailable' in app.error[0].value
    assert not app.get('download_button')
