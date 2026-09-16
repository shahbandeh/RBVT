"""Desktop GUI: run ``rbvt-gui``."""
import argparse
import queue
import sys
import threading
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .cli import FILTERS
from .interface import BackgroundRequest, export_products, make_figure
from .products import daily_table, spectrum_table, summary


class RBVTGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Roman Background Visualization Tool')
        self.geometry('1360x820')
        self.minsize(1000, 650)
        self.result = None
        self.request = None
        self.canvas = None
        self.messages = queue.Queue()
        self.busy = False
        self.vars = {key: tk.StringVar(value=value) for key, value in {
            'target_name': '', 'coordinate_system': 'equatorial',
            'longitude': '180', 'latitude': '0', 'optical_element': 'F184',
            'wavelength': '1.84', 'threshold': '1.1',
        }.items()}
        self.day = tk.StringVar()
        self.status = tk.StringVar(value='Enter a target, then calculate its background.')
        self._build_ui()
        self.after(100, self._poll)

    def _build_ui(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # check Tk backend early
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        controls = ttk.Frame(self, padding=18)
        controls.grid(row=0, column=0, sticky='ns')
        ttk.Label(controls, text='RBVT', font=('TkDefaultFont', 24, 'bold')).pack(anchor='w')
        ttk.Label(controls, text='Roman background explorer').pack(anchor='w', pady=(0,18))
        self.entries = {}
        options = {'coordinate_system': ('equatorial', 'galactic', 'ecliptic'),
                   'optical_element': tuple(FILTERS) + ('Custom wavelength',)}
        fields = [('target_name', 'Target label (optional)'), ('coordinate_system', 'Coordinates'),
                  ('longitude', 'RA / longitude'), ('latitude', 'Dec / latitude'),
                  ('optical_element', 'Optical element'), ('wavelength', 'Custom wavelength (μm)'),
                  ('threshold', 'Threshold × minimum')]
        for key, label in fields:
            field = ttk.Frame(controls)
            field.pack(fill='x', pady=5)
            ttk.Label(field, text=label, width=23).pack(side='left')
            if key in options:
                entry = ttk.Combobox(field, textvariable=self.vars[key], values=options[key], state='readonly', width=25)
            else:
                entry = ttk.Entry(field, textvariable=self.vars[key], width=28)
            entry.pack(side='right', fill='x', expand=True)
            self.entries[key] = entry
        self.vars['optical_element'].trace_add('write', lambda *_: self._wave_state())
        self._wave_state()
        self.calculate_button = ttk.Button(controls, text='Calculate background', command=self.calculate)
        self.calculate_button.pack(fill='x', pady=(20,8))
        self.progress = ttk.Progressbar(controls, mode='indeterminate')
        self.progress.pack(fill='x')
        ttk.Label(controls, text='Spectrum day (Jan 1 = 0)').pack(anchor='w', pady=(18,4))
        self.day_box = ttk.Combobox(controls, textvariable=self.day, state='disabled', width=25)
        self.day_box.pack(fill='x')
        self.day_box.bind('<<ComboboxSelected>>', lambda _: self.refresh())
        self.export_buttons = []
        for label, action in [('Save daily CSV', lambda: self.save('daily.csv')),
                              ('Save spectrum CSV', lambda: self.save('spectrum.csv')),
                              ('Save plot', lambda: self.save('background.png')),
                              ('Save HTML report', lambda: self.save('report.html')),
                              ('Copy CLI command', self.copy_command)]:
            button = ttk.Button(controls, text=label, command=action, state='disabled')
            button.pack(fill='x', pady=(7,0))
            self.export_buttons.append(button)
        ttk.Label(controls, wraplength=350, text='Equatorial RA accepts degrees or hours (12:00:00); Dec accepts degrees or sexagesimal. Other frames use degrees.\n\nFilter values are monochromatic. Visibility uses reference year 2024.').pack(anchor='w', pady=(16,0))
        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=0, column=1, sticky='nsew', padx=(0,15), pady=15)
        self.plot_frame = ttk.Frame(self.tabs)
        self.tabs.add(self.plot_frame, text='Background & spectrum')
        self.summary_text = tk.Text(self.tabs, wrap='word', padx=16, pady=16, state='disabled')
        self.tabs.add(self.summary_text, text='Summary')
        self.tables = {}
        for key, label in [('daily', 'Daily data'), ('spectrum', 'Spectrum data')]:
            frame = ttk.Frame(self.tabs)
            self.tabs.add(frame, text=label)
            frame.columnconfigure(0, weight=1)
            frame.rowconfigure(0, weight=1)
            tree = ttk.Treeview(frame, show='headings')
            tree.grid(row=0, column=0, sticky='nsew')
            scroll = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
            scroll.grid(row=0, column=1, sticky='ns')
            horizontal = ttk.Scrollbar(frame, orient='horizontal', command=tree.xview)
            horizontal.grid(row=1, column=0, sticky='ew')
            tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
            self.tables[key] = tree
        ttk.Label(self, textvariable=self.status, padding=(15,8)).grid(row=1, column=0, columnspan=2, sticky='ew')

    def _wave_state(self):
        state = 'normal' if self.vars['optical_element'].get() == 'Custom wavelength' else 'disabled'
        self.entries['wavelength'].configure(state=state)

    def calculate(self):
        if self.busy:
            return
        try:
            request = BackgroundRequest(**{key: var.get() for key, var in self.vars.items()})
            request.parameters()
        except ValueError as exc:
            messagebox.showerror('Check your inputs', str(exc), parent=self)
            return
        self.busy = True
        self.calculate_button.configure(state='disabled')
        self.day_box.configure(state='disabled')
        for button in self.export_buttons:
            button.configure(state='disabled')
        self.progress.start()
        self.status.set('Loading background from STScI…')
        # The worker never touches Tk widgets; the UI polls a queue on its own thread.
        def work():
            try:
                self.messages.put((request, request.calculate(), None))
            except Exception as exc:
                self.messages.put((request, None, str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            request, result, error = self.messages.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.progress.stop()
            self.calculate_button.configure(state='normal')
            if error:
                self.status.set('Calculation failed. Previous result remains displayed.' if self.result else 'Calculation failed.')
                messagebox.showerror('Background unavailable', error, parent=self)
            else:
                self.request, self.result = request, result
                days = [str(int(d)) for d in result.bkg_data['calendar']]
                self.day_box.configure(values=days)
                self.day.set(days[0])
                self.refresh()
            if self.result is not None:
                self.day_box.configure(state='readonly')
                for button in self.export_buttons:
                    button.configure(state='normal')
        self.after(100, self._poll)

    def refresh(self):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
        if self.result is None:
            return
        day = int(self.day.get())
        # Destroy old Tk widgets and release the old figure before drawing the new day.
        if self.canvas is not None:
            self.canvas.figure.clear()
        for child in self.plot_frame.winfo_children():
            child.destroy()
        figure = make_figure(self.result, day, self.request.target_name)
        self.canvas = FigureCanvasTkAgg(figure, master=self.plot_frame)
        toolbar = NavigationToolbar2Tk(self.canvas, self.plot_frame, pack_toolbar=False)
        toolbar.update()
        toolbar.pack(side='bottom', fill='x')
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.canvas.draw()
        self.summary_text.configure(state='normal')
        self.summary_text.delete('1.0', 'end')
        self.summary_text.insert('1.0', summary(self.result, day, self.request.target_name))
        self.summary_text.configure(state='disabled')
        for key, table in [('daily', daily_table(self.result)), ('spectrum', spectrum_table(self.result, day))]:
            tree = self.tables[key]
            tree.delete(*tree.get_children())
            tree.configure(columns=list(table.columns))
            for col in table.columns:
                tree.heading(col, text=col)
                tree.column(col, width=130, anchor='e')
            for row in table.itertuples(index=False, name=None):
                tree.insert('', 'end', values=[f'{v:.6g}' if isinstance(v, float) else v for v in row])
        self.status.set('Showing the last completed calculation. Edit inputs and Calculate to update.')

    def save(self, filename):
        if self.result is None:
            return
        suffix = Path(filename).suffix
        path = filedialog.asksaveasfilename(parent=self, initialfile=filename,
                   defaultextension=suffix, filetypes=[(suffix.upper()[1:] + ' file', '*' + suffix)])
        if not path:
            return
        try:
            data = export_products(self.result, int(self.day.get()), self.request.target_name)
            Path(path).write_bytes(data[filename])
            self.status.set(f'Saved {path}')
        except (ValueError, OSError) as exc:
            messagebox.showerror('Unable to save', str(exc), parent=self)

    def copy_command(self):
        if self.request is not None:
            self.clipboard_clear()
            self.clipboard_append(self.request.command(int(self.day.get())))
            self.status.set('Copied the CLI command for the displayed result.')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Roman Background Visualization Tool desktop GUI')
    parser.parse_args(argv)
    try:
        app = RBVTGui()
        app.mainloop()
    except tk.TclError as exc:
        print(f'rbvt-gui: {exc}. A desktop display and Python with Tk support are required.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
