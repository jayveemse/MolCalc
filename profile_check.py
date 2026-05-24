"""
profile_check.py

Run this script, paste a MolCalc part profile string into the text box,
then click Go to plot area vs axial position.
"""

import ast
import tkinter as tk
from tkinter import font as tkfont
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


def parse_profile(profile_str):
    s = profile_str.strip().strip("'\"")
    parsed = ast.literal_eval(s)
    if isinstance(parsed, dict):
        return {k.strip(): v for k, v in parsed.items()}
    return parsed


def build_area_profile(data):
    ap = data['Axial Position (mm)']
    cs = data['Cross-Sectional Area (mm^2)']
    tm = data['Transition Model']

    x_segments    = []
    area_segments = []

    for i in range(len(ap) - 1):
        segment_length = ap[i + 1] - ap[i]
        num_slices     = int(round(segment_length / 0.01))
        x              = np.linspace(ap[i], ap[i + 1], num_slices, endpoint=False)

        if tm[i] != 'Constant':
            try:
                section = eval(tm[i])
                if isinstance(section, np.ndarray):
                    if len(section) != num_slices:
                        section = np.resize(section, num_slices)
                else:
                    section = np.full(num_slices, float(section))
            except Exception as e:
                raise RuntimeError(f"Transition model eval failed at segment {i} ('{tm[i]}'): {e}")
        else:
            section = np.full(num_slices, float(cs[i]))

        x_segments.append(x)
        area_segments.append(section)

    return np.concatenate(x_segments), np.concatenate(area_segments)


def plot_profile(data, ax, canvas):
    ap     = data.get('Axial Position (mm)', [])
    cs     = data.get('Cross-Sectional Area (mm^2)', [])
    planes = data.get('Contact Plane', [])

    x, area = build_area_profile(data)

    ax.clear()
    ax.plot(x, area, color='steelblue', lw=1.5)
    ax.fill_between(x, area, alpha=0.15, color='steelblue')

    y_top = max(area) * 1.08
    ax.set_ylim(bottom=0, top=y_top)

    span = ap[-1] - ap[0] if len(ap) > 1 else 1
    for j, pos in enumerate(ap):
        ax.axvline(pos, color='gray', lw=0.8, linestyle='--', alpha=0.6)
        label = planes[j] if j < len(planes) else ''
        if label:
            ax.text(pos + span * 0.005, y_top * 0.97,
                    label, fontsize=8, va='top', color='dimgray', rotation=90)

    ax.set_xlabel('Axial Position (mm)')
    ax.set_ylabel('Cross-Sectional Area (mm²)')
    ax.set_title('Part Profile — Area vs Axial Position')
    ax.grid(True, linestyle='--', alpha=0.35)
    canvas.figure.tight_layout()
    canvas.draw()


def main():
    root = tk.Tk()
    root.title('Profile Check')
    root.resizable(True, True)

    # ── Top: paste area ───────────────────────────────────────────────────
    top = tk.Frame(root, padx=10, pady=8)
    top.pack(fill=tk.X)

    tk.Label(top, text='Paste profile string:', font=('TkDefaultFont', 10, 'bold')).pack(anchor='w')

    text_frame = tk.Frame(top)
    text_frame.pack(fill=tk.X, pady=(4, 0))

    mono = tkfont.Font(family='Courier', size=10)
    text_scroll = tk.Scrollbar(text_frame, orient=tk.VERTICAL)
    text_box = tk.Text(text_frame, height=10, font=mono, wrap=tk.NONE,
                       yscrollcommand=text_scroll.set, relief=tk.SOLID, bd=1)
    text_scroll.config(command=text_box.yview)
    text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
    text_box.pack(fill=tk.X, expand=True)

    status_var = tk.StringVar()
    status_label = tk.Label(top, textvariable=status_var, fg='red', anchor='w',
                            font=('TkDefaultFont', 9))
    status_label.pack(fill=tk.X, pady=(4, 0))

    # ── Plot area ─────────────────────────────────────────────────────────
    plot_frame = tk.Frame(root)
    plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

    fig, ax = plt.subplots(figsize=(11, 4))
    fig.patch.set_facecolor('white')
    canvas = FigureCanvasTkAgg(fig, master=plot_frame)
    toolbar = NavigationToolbar2Tk(canvas, plot_frame)
    toolbar.update()
    toolbar.pack(side=tk.BOTTOM, fill=tk.X)
    canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ── Go button ─────────────────────────────────────────────────────────
    def on_go():
        status_var.set('')
        raw = text_box.get('1.0', tk.END).strip()
        if not raw:
            status_var.set('Paste a profile string first.')
            return
        try:
            data = parse_profile(raw)
        except Exception as e:
            status_var.set(f'Parse error: {e}')
            return
        if 'Axial Position (mm)' not in data or 'Cross-Sectional Area (mm^2)' not in data:
            status_var.set("Profile must have 'Axial Position (mm)' and 'Cross-Sectional Area (mm^2)'.")
            return
        try:
            plot_profile(data, ax, canvas)
            status_var.set('')
        except Exception as e:
            status_var.set(f'Plot error: {e}')

    tk.Button(top, text='Go', command=on_go, width=10,
              font=('TkDefaultFont', 11, 'bold')).pack(anchor='e', pady=(6, 0))

    # ── Size and center ───────────────────────────────────────────────────
    root.update_idletasks()
    w, h = 900, 700
    x = (root.winfo_screenwidth()  - w) // 2
    y = (root.winfo_screenheight() - h) // 2
    root.geometry(f'{w}x{h}+{x}+{y}')

    root.mainloop()


if __name__ == '__main__':
    main()
