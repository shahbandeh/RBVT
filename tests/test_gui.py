import time
import pytest


def test_desktop_calculate_select_export(offline, monkeypatch, tmp_path):
    tk = pytest.importorskip('tkinter')
    from rbvt.gui import RBVTGui
    try:
        app = RBVTGui()
    except tk.TclError:
        pytest.skip('Desktop display unavailable (use xvfb-run on Linux)')
    app.withdraw()
    errors = []
    monkeypatch.setattr('rbvt.gui.messagebox.showerror', lambda *a, **k: errors.append(a))
    try:
        app.calculate()
        deadline = time.monotonic() + 20
        while app.busy and time.monotonic() < deadline:
            app.update()
            time.sleep(.02)
        assert not app.busy
        assert not errors
        assert app.result is not None
        assert len(app.tables['daily'].get_children()) == len(app.result.bkg_data['calendar'])
        day = int(app.result.bkg_data['calendar'][1])
        app.day.set(str(day))
        app.refresh()
        assert f'Spectrum day: {day}' in app.summary_text.get('1.0','end')
        path = tmp_path / 'daily.csv'
        monkeypatch.setattr('rbvt.gui.filedialog.asksaveasfilename', lambda **k: str(path))
        app.save('daily.csv')
        assert 'total_MJy_sr' in path.read_text()
        app.copy_command()
        assert f'--day {day}' in app.clipboard_get()
        app.vars['latitude'].set('100')
        app.calculate()
        assert errors
        assert not app.busy
    finally:
        app.destroy()
