# --- MAIN GUI ---
window = tk.Tk()
window.title('MoleGrapher 1.4.0')
window.geometry('760x880')
window.resizable(True, True)

# ── Status bar (always visible at bottom) ────────────────────────────────
statusFrame = tk.Frame(window, bd=1, relief=tk.SUNKEN)
statusFrame.pack(side=tk.BOTTOM, fill=tk.X, padx=6, pady=(0, 4))
graphLabel = tk.Label(statusFrame,
                       text="Press 'Generate Graph' or 'Import...' to begin.",
                       anchor=W, fg='navy')
graphLabel.pack(side=tk.LEFT, padx=4)

# ── Run-finder helpers ────────────────────────────────────────────────────
_PROCESSED_RUN_BASE = os.path.join(
    os.path.expanduser('~'),
    'Lehigh University Dropbox', 'ENG-MATSGroup', 'MATS', 'Data', 'Processed - Run'
)

def _open_run_folder(run_id, folder_path):
    files = sorted(f for f in os.listdir(folder_path)
                   if os.path.isfile(os.path.join(folder_path, f)))
    if not files:
        find_status_label.configure(text='No files found in that folder.')
        return
    win = tk.Toplevel(window)
    win.title(f'Run: {run_id}')
    win.geometry('520x380')
    win.lift()
    tk.Label(win, text=f'Run: {run_id}',
             font=('TkDefaultFont', 12, 'bold')).pack(pady=(12, 2))
    tk.Label(win, text=folder_path, fg='gray', wraplength=480,
             font=('TkDefaultFont', 8)).pack(pady=(0, 8))
    _lf = tk.Frame(win); _lf.pack(fill=tk.BOTH, expand=True, padx=10)
    _sb = tk.Scrollbar(_lf); _sb.pack(side=tk.RIGHT, fill=tk.Y)
    _lb = tk.Listbox(_lf, yscrollcommand=_sb.set, font=('TkDefaultFont', 10),
                     activestyle='dotbox', selectmode=tk.SINGLE)
    _lb.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    _sb.config(command=_lb.yview)
    for fname in files:
        _lb.insert(tk.END, fname)
    def _open_file(event=None):
        sel = _lb.curselection()
        if not sel:
            return
        fpath = os.path.join(folder_path, files[sel[0]])
        import subprocess, sys
        if sys.platform == 'darwin':
            subprocess.Popen(['open', fpath])
        elif sys.platform == 'win32':
            os.startfile(fpath)
        else:
            subprocess.Popen(['xdg-open', fpath])
    _lb.bind('<Double-Button-1>', _open_file)
    tk.Button(win, text='Open', command=_open_file).pack(pady=(6, 10))

def search_run_id():
    run_id = run_id_search_var.get().strip()
    find_status_label.configure(text='')
    if len(run_id) < 6:
        find_status_label.configure(text='Run ID must be at least 6 characters.')
        return
    folder_path = os.path.join(_PROCESSED_RUN_BASE, run_id[:2], run_id[2:4], run_id)
    if not os.path.isdir(folder_path):
        find_status_label.configure(text=f'Folder not found: ...{os.sep}{run_id[:2]}{os.sep}{run_id[2:4]}{os.sep}{run_id}')
        return
    _open_run_folder(run_id, folder_path)

def go_to_main():
    landing_frame.pack_forget()
    _outer.pack(fill=tk.BOTH, expand=True)
    window.update_idletasks()
    _rw = min(mainFrame.winfo_reqwidth() + 40, window.winfo_screenwidth() - 40)
    _rh = min(int(window.winfo_screenheight() * 0.85), window.winfo_screenheight() - 60)
    _rx = (window.winfo_screenwidth() - _rw) // 2
    _ry = (window.winfo_screenheight() - _rh) // 2
    window.geometry(f'{_rw}x{_rh}+{_rx}+{_ry}')

def go_to_landing():
    _outer.pack_forget()
    landing_frame.pack(fill=tk.BOTH, expand=True)
    window.update_idletasks()
    _lw, _lh = 500, 420
    _lx = (window.winfo_screenwidth() - _lw) // 2
    _ly = (window.winfo_screenheight() - _lh) // 2
    window.geometry(f'{_lw}x{_lh}+{_lx}+{_ly}')

# ── Landing page ──────────────────────────────────────────────────────────
landing_frame = tk.Frame(window, bg='white')
landing_frame.pack(fill=tk.BOTH, expand=True)

tk.Label(landing_frame, text='MolCalc',
         font=('TkDefaultFont', 28, 'bold'), bg='white').pack(pady=(70, 30))

tk.Button(landing_frame, text='Process a Run',
          font=('TkDefaultFont', 14), width=22,
          command=go_to_main).pack(pady=8)

tk.Frame(landing_frame, height=2, bg='#cccccc').pack(fill=tk.X, padx=80, pady=22)

_find_outer = tk.Frame(landing_frame, bg='white')
_find_outer.pack()
tk.Label(_find_outer, text='Find a Processed Run',
         font=('TkDefaultFont', 13, 'bold'), bg='white').pack(pady=(0, 12))
_find_row = tk.Frame(_find_outer, bg='white'); _find_row.pack()
tk.Label(_find_row, text='Run ID:', bg='white',
         font=('TkDefaultFont', 11)).pack(side=tk.LEFT, padx=(0, 6))
run_id_search_var = tk.StringVar()
_run_id_entry = tk.Entry(_find_row, textvariable=run_id_search_var, width=16,
                          font=('TkDefaultFont', 11))
_run_id_entry.pack(side=tk.LEFT, padx=(0, 6))
_run_id_entry.bind('<Return>', lambda e: search_run_id())
tk.Button(_find_row, text='Search', command=search_run_id,
          font=('TkDefaultFont', 11)).pack(side=tk.LEFT)
find_status_label = tk.Label(_find_outer, text='', fg='red', bg='white', wraplength=420)
find_status_label.pack(pady=(8, 0))

# ── Scrollable main area ──────────────────────────────────────────────────
_outer = tk.Frame(window)  # packed by go_to_main()

_vscroll = tk.Scrollbar(_outer, orient='vertical')
_vscroll.pack(side=tk.RIGHT, fill=tk.Y)
_hscroll = tk.Scrollbar(_outer, orient='horizontal')
_hscroll.pack(side=tk.BOTTOM, fill=tk.X)

_canvas_scroll = tk.Canvas(_outer, yscrollcommand=_vscroll.set,
                           xscrollcommand=_hscroll.set,
                           highlightthickness=0)
_canvas_scroll.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

_vscroll.config(command=_canvas_scroll.yview)
_hscroll.config(command=_canvas_scroll.xview)

mainFrame = tk.Frame(_canvas_scroll)
_canvas_scroll.create_window((0, 0), window=mainFrame, anchor='nw')

def _on_frame_configure(event):
    _canvas_scroll.configure(scrollregion=_canvas_scroll.bbox('all'))

mainFrame.bind('<Configure>', _on_frame_configure)

# ── Back button (top of main UI) ──────────────────────────────────────────
_back_row = tk.Frame(mainFrame)
_back_row.pack(fill=tk.X, padx=6, pady=(4, 0))
tk.Button(_back_row, text='← Back to MolCalc', command=go_to_landing,
          font=('TkDefaultFont', 9)).pack(side=tk.LEFT)

# Allow mousewheel scrolling
def _on_mousewheel(event):
    try:
        if event.widget.winfo_toplevel() is not window:
            return
    except Exception:
        return
    _canvas_scroll.yview_scroll(int(-1*(event.delta/120)), 'units')
window.bind_all('<MouseWheel>', _on_mousewheel)
# Linux mousewheel
window.bind_all('<Button-4>', lambda e: _canvas_scroll.yview_scroll(-1, 'units'))
window.bind_all('<Button-5>', lambda e: _canvas_scroll.yview_scroll( 1, 'units'))

PAD = dict(padx=6, pady=3)

# ── Section 1: File Selection ─────────────────────────────────────────────
fileFrame = tk.LabelFrame(mainFrame, text='File Selection', font=('TkDefaultFont', 9, 'bold'))
fileFrame.pack(fill=tk.X, **PAD)

row0 = tk.Frame(fileFrame); row0.pack(fill=tk.X, padx=4, pady=2)
fileBrowseButton = tk.Button(row0, text='Browse Data...', command=lambda: (browseFiles(), resolve_geometry_files()), width=16)
fileBrowseButton.pack(side=tk.LEFT, padx=(0,6))
fileLabel = tk.Label(row0, text='Data: (Not Selected)', anchor=W, fg='gray')
fileLabel.pack(side=tk.LEFT, fill=tk.X, expand=True)

# Pressure column selector (populated by _populate_pt_dropdown after Browse)
ptRow = tk.Frame(fileFrame); ptRow.pack(fill=tk.X, padx=4, pady=2)
ptLabel = tk.Label(ptRow, text='Pressure Col: (load data file first)',
                   anchor=W, fg='gray', width=34)
ptLabel.pack(side=tk.LEFT)
pressure_col_var = tk.StringVar(value='')
pt_menu = tk.OptionMenu(ptRow, pressure_col_var, '(load data first)')
pt_menu.config(width=26)
pt_menu.pack(side=tk.LEFT)

row1 = tk.Frame(fileFrame); row1.pack(fill=tk.X, padx=4, pady=2)
interpolate_temps_var = tk.BooleanVar(value=False)
interpolateCheckbox = tk.Checkbutton(row1, text='Interpolate Temps (No CSV)',
                                     variable=interpolate_temps_var,
                                     command=toggle_temp_file_selection)
interpolateCheckbox.pack(side=tk.LEFT, padx=(0,6))
tempLabel = tk.Label(row1, text='Temp Profile: (Select via Browse)', anchor=W, fg='gray')
tempLabel.pack(side=tk.LEFT, fill=tk.X, expand=True)

row2 = tk.Frame(fileFrame); row2.pack(fill=tk.X, padx=4, pady=2)
importPlotButton = tk.Button(row2, text='Import Plot CSV', command=import_data, width=16)
importPlotButton.pack(side=tk.LEFT, padx=(0,6))
importTempButton = tk.Button(row2, text='Import Temp CSV',
                             command=import_temp_profile_viewer, width=16)
importTempButton.pack(side=tk.LEFT)

outDirRow = tk.Frame(fileFrame); outDirRow.pack(fill=tk.X, padx=4, pady=2)
tk.Button(outDirRow, text='Set Output Folder...', command=set_output_dir,
          width=18).pack(side=tk.LEFT, padx=(0,8))
outputDirLabel = tk.Label(outDirRow, text='Output: (NOT SET — required)',
                          anchor=W, fg='red')
outputDirLabel.pack(side=tk.LEFT, fill=tk.X, expand=True)

# ── Section 2: Geometry Files ─────────────────────────────────────────────
geoFrame = tk.LabelFrame(mainFrame, text='Geometry Files', font=('TkDefaultFont', 9, 'bold'))
geoFrame.pack(fill=tk.X, **PAD)

def _geo_row(parent, label_text, browse_cmd):
    f = tk.Frame(parent); f.pack(fill=tk.X, padx=4, pady=2)
    btn = tk.Button(f, text='Browse...', command=browse_cmd, width=10)
    btn.pack(side=tk.RIGHT, padx=(4, 0))
    lbl = tk.Label(f, text=label_text, anchor=W, fg='gray')
    lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
    return lbl

layoutLabel  = _geo_row(geoFrame, 'Layout:       (Not Selected)', browse_layout)
matingLabel  = _geo_row(geoFrame, 'Mating Table: (Not Selected)', browse_mating)
furLabel     = _geo_row(geoFrame, 'MLD-FUR:      (Not Selected)', browse_fur)
hpsLabel     = _geo_row(geoFrame, 'MLD-HPS:      (Not Selected)', browse_hps)


# ── Section 3: Calc Parameters + Uncertainty (side by side) ──────────────
midRow = tk.Frame(mainFrame); midRow.pack(fill=tk.X, **PAD)

calcFrame = tk.LabelFrame(midRow, text='Calculation Parameters',
                          font=('TkDefaultFont', 9, 'bold'))
calcFrame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0,4))

def _param_row(parent, label_text, default=''):
    f = tk.Frame(parent); f.pack(fill=tk.X, padx=4, pady=2)
    tk.Label(f, text=label_text, width=24, anchor=W).pack(side=tk.LEFT)
    sv = tk.StringVar(value=default)
    tk.Entry(f, textvariable=sv, width=10).pack(side=tk.LEFT)
    return sv

z_temp_cutoff_var   = _param_row(calcFrame, 'Z-Temp Cutoff (mm):')
z_offset_var        = _param_row(calcFrame, 'Z-Offset (mm):')
sample_pos_var      = _param_row(calcFrame, 'Sample Position (mm):', '')
calc_step_var       = _param_row(calcFrame, 'Calc Step (every N rows):', '1')

# Gas species dropdown
_gas_row = tk.Frame(calcFrame); _gas_row.pack(fill=tk.X, padx=4, pady=2)
tk.Label(_gas_row, text='Gas Species:', width=24, anchor=W).pack(side=tk.LEFT)
gas_species_var = tk.StringVar(value='Nitrogen')
tk.OptionMenu(_gas_row, gas_species_var, 'Nitrogen').pack(side=tk.LEFT)

sigmaFrame = tk.LabelFrame(midRow, text='Uncertainty Inputs',
                           font=('TkDefaultFont', 9, 'bold'))
sigmaFrame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

sigma_p_var = _param_row(sigmaFrame, 'σ_P (% Error):', '0.25')
sigma_v_var = _param_row(sigmaFrame, 'σ_V (% Error):', '5.0')
sigma_t_var = _param_row(sigmaFrame, 'σ_T (K Error):', '2.2')

# ── Section 3b: Furniture Masses & Chemical Sample ─────────────────────
furChemFrame = tk.LabelFrame(mainFrame, text='Furniture Masses & Chemical Sample',
                              font=('TkDefaultFont', 9, 'bold'))
furChemFrame.pack(fill=tk.X, **PAD)

# Top row: build-table button + volume info label
_fcTopRow = tk.Frame(furChemFrame); _fcTopRow.pack(fill=tk.X, padx=4, pady=(4,0))
tk.Button(_fcTopRow, text='Build Table from Layout',
          command=build_fur_table_from_layout, width=24).pack(side=tk.LEFT)
vol_info_label = tk.Label(_fcTopRow, text='',
                           fg='darkblue', font=('TkDefaultFont', 8), anchor=W)
vol_info_label.pack(side=tk.LEFT, padx=(10, 0))

# Column headers
_fcHdr = tk.Frame(furChemFrame); _fcHdr.pack(fill=tk.X, padx=4, pady=(3,0))
for _ht, _hw in [('UID', 16), ('Material', 16), ('Internal', 9), ('Mass (g)', 9)]:
    tk.Label(_fcHdr, text=_ht, width=_hw, anchor=W,
             font=('TkDefaultFont', 8, 'bold')).pack(side=tk.LEFT)
tk.Label(_fcHdr, text='  ← enter measured part mass; Internal = subtracts from gas volume',
         font=('TkDefaultFont', 7), fg='gray').pack(side=tk.LEFT)

# Scrollable table body
_fcCanvasFrame = tk.Frame(furChemFrame); _fcCanvasFrame.pack(fill=tk.X, padx=4, pady=2)
_fcCanvas  = tk.Canvas(_fcCanvasFrame, height=130, bg='#f5f5f5', highlightthickness=0)
_fcScrollb = ttk.Scrollbar(_fcCanvasFrame, orient=tk.VERTICAL, command=_fcCanvas.yview)
fur_table_inner = tk.Frame(_fcCanvas, bg='#f5f5f5')
fur_table_inner.bind('<Configure>',
    lambda e: _fcCanvas.configure(scrollregion=_fcCanvas.bbox('all')))
_fcCanvas.create_window((0, 0), window=fur_table_inner, anchor='nw')
_fcCanvas.configure(yscrollcommand=_fcScrollb.set)
_fcCanvas.pack(side=tk.LEFT, fill=tk.X, expand=True)
_fcScrollb.pack(side=tk.RIGHT, fill=tk.Y)
_fcCanvas.bind('<Enter>',
    lambda e: _fcCanvas.bind_all('<MouseWheel>',
        lambda ev: _fcCanvas.yview_scroll(-1*(1 if ev.delta>0 else -1), 'units')))
_fcCanvas.bind('<Leave>', lambda e: window.bind_all('<MouseWheel>', _on_mousewheel))

# Chemical species row
_chemRow = tk.Frame(furChemFrame); _chemRow.pack(fill=tk.X, padx=4, pady=(6,2))
tk.Label(_chemRow, text='Chemical Species:', width=18, anchor=W).pack(side=tk.LEFT)
chem_species_var = tk.StringVar(value='None')
_chem_opts = ['None','Li3BN2','Li3N','Li3AlN2','Li3GaN2','GaN','Custom']
tk.OptionMenu(_chemRow, chem_species_var, *_chem_opts).pack(side=tk.LEFT, padx=(0,8))
tk.Label(_chemRow, text='Mass (g):', width=9, anchor=W).pack(side=tk.LEFT)
chem_mass_var = tk.StringVar(value='')
tk.Entry(_chemRow, textvariable=chem_mass_var, width=8).pack(side=tk.LEFT, padx=(0,10))
tk.Label(_chemRow, text='Custom Density (g/cm³):', width=22, anchor=W).pack(side=tk.LEFT)
chem_density_var = tk.StringVar(value='')
tk.Entry(_chemRow, textvariable=chem_density_var, width=8).pack(side=tk.LEFT)
tk.Label(_chemRow, text='(Custom species only)',
         fg='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(4,0))

# ── Section 3c: Pressure Zero Offset ────────────────────────────────────
pzeroFrame = tk.LabelFrame(mainFrame, text='Pressure Zero Offset',
                           font=('TkDefaultFont', 9, 'bold'))
pzeroFrame.pack(fill=tk.X, **PAD)

pzeroRow1 = tk.Frame(pzeroFrame); pzeroRow1.pack(fill=tk.X, padx=4, pady=2)
tk.Label(pzeroRow1, text='Vacuum Window Start (hr):', width=26, anchor=W).pack(side=tk.LEFT)
p_zero_start_var = tk.StringVar(value='')
tk.Entry(pzeroRow1, textvariable=p_zero_start_var, width=8).pack(side=tk.LEFT, padx=(0,16))
tk.Label(pzeroRow1, text='End (hr):', width=10, anchor=W).pack(side=tk.LEFT)
p_zero_end_var = tk.StringVar(value='')
tk.Entry(pzeroRow1, textvariable=p_zero_end_var, width=8).pack(side=tk.LEFT)

pzeroRow2 = tk.Frame(pzeroFrame); pzeroRow2.pack(fill=tk.X, padx=4, pady=2)
tk.Label(pzeroRow2, text='Manual Override (MPa):', width=26, anchor=W).pack(side=tk.LEFT)
p_zero_manual_var = tk.StringVar(value='')
tk.Entry(pzeroRow2, textvariable=p_zero_manual_var, width=8).pack(side=tk.LEFT, padx=(0,10))
tk.Label(pzeroRow2,
         text='Override takes priority over vacuum window. Leave both blank for no offset.',
         anchor=W, fg='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

# ── Section 4: Action Buttons ─────────────────────────────────────────────
actFrame = tk.LabelFrame(mainFrame, text='Actions', font=('TkDefaultFont', 9, 'bold'))
actFrame.pack(fill=tk.X, **PAD)

actRow = tk.Frame(actFrame); actRow.pack(fill=tk.X, padx=4, pady=4)
graphButton = tk.Button(actRow, text='Generate Graph', command=lambda: processData(), width=16)
graphButton.pack(side=tk.LEFT, padx=(0,4))
tempViewButton = tk.Button(actRow, text='View Temp Profiles', command=open_temp_viewer,
                           width=16, state='disabled')
tempViewButton.pack(side=tk.LEFT, padx=(0,4))
texpansion_button = tk.Button(actRow, text='T Expansion', command=open_texpansion_viewer,
                              width=12, state='disabled')
texpansion_button.pack(side=tk.LEFT, padx=(0,4))
exportPlotButton = tk.Button(actRow, text='Export Plot Data', command=export_plot_data,
                             width=16, state='disabled')
exportPlotButton.pack(side=tk.LEFT, padx=(0,4))
exportTempButton = tk.Button(actRow, text='Export Temp Profiles', command=export_temp_profiles,
                             width=18, state='disabled')
exportTempButton.pack(side=tk.LEFT)
exportHtmlButton = tk.Button(actRow, text='Export HTML Plot', command=export_html_plot,
                             width=16, state='disabled')
exportHtmlButton.pack(side=tk.LEFT, padx=(4,0))


save_plot_button = tk.Button(actRow, text='Save Plot',
                             command=save_plot_image, width=12, state='disabled')
save_plot_button.pack(side=tk.LEFT, padx=(4,0))


# ── Section 5: P_calc ───────────────────────────────────────────────────
pcalcFrame = tk.LabelFrame(mainFrame, text='Back-Calculated Pressure  P_calc',
                           font=('TkDefaultFont', 9, 'bold'))
pcalcFrame.pack(fill=tk.X, **PAD)

pcalcTimeRow = tk.Frame(pcalcFrame); pcalcTimeRow.pack(fill=tk.X, padx=4, pady=2)
tk.Label(pcalcTimeRow, text='Start Time (hr):', width=18, anchor=W).pack(side=tk.LEFT)
p_calc_start_time_var = tk.StringVar(value='')
tk.Entry(pcalcTimeRow, textvariable=p_calc_start_time_var, width=8).pack(side=tk.LEFT, padx=(0,12))
tk.Label(pcalcTimeRow, text='End Time (hr):', width=14, anchor=W).pack(side=tk.LEFT)
p_calc_end_time_var = tk.StringVar(value='')
tk.Entry(pcalcTimeRow, textvariable=p_calc_end_time_var, width=8).pack(side=tk.LEFT)
tk.Label(pcalcTimeRow,
         text='  (leave End blank to calculate over full run)',
         anchor=W, fg='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)
tk.Label(pcalcTimeRow, text='  Step (every N rows):', width=20, anchor=W).pack(side=tk.LEFT)
p_calc_step_var = tk.StringVar(value='1')
tk.Entry(pcalcTimeRow, textvariable=p_calc_step_var, width=6).pack(side=tk.LEFT)

pcalcRow = tk.Frame(pcalcFrame); pcalcRow.pack(fill=tk.X, padx=4, pady=4)
pcalc_button = tk.Button(pcalcRow, text='Calculate P_calc',
                         command=calculate_pcalc, width=18, state='disabled')
pcalc_button.pack(side=tk.LEFT, padx=(0,6))
tk.Button(pcalcRow, text='Clear P_calc', command=clear_pcalc,
          width=12).pack(side=tk.LEFT)

pcalcOffsetRow = tk.Frame(pcalcFrame); pcalcOffsetRow.pack(fill=tk.X, padx=4, pady=2)
tk.Label(pcalcOffsetRow, text='P Offset (MPa):', width=18, anchor=W).pack(side=tk.LEFT)
p_offset_var = tk.StringVar(value='')
tk.Entry(pcalcOffsetRow, textvariable=p_offset_var, width=10).pack(side=tk.LEFT, padx=(0,8))
tk.Label(pcalcOffsetRow,
         text='Leave blank to use auto offset. Re-run Calculate P_calc after changing.',
         anchor=W, fg='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

pcalc_info_label = tk.Label(pcalcFrame, text='', anchor=W, justify=LEFT,
                             fg='darkblue', wraplength=680,
                             font=('TkDefaultFont', 8))
pcalc_info_label.pack(fill=tk.X, padx=6, pady=(0,4))


# ── Section 5: Exponential Fit ────────────────────────────────────────────
fitFrame = tk.LabelFrame(mainFrame, text='Exponential Fit', font=('TkDefaultFont', 9, 'bold'))
fitFrame.pack(fill=tk.X, **PAD)

fitRow1 = tk.Frame(fitFrame); fitRow1.pack(fill=tk.X, padx=4, pady=2)
tk.Label(fitRow1, text='Fit Start Time (hr):', width=20, anchor=W).pack(side=tk.LEFT)
fit_start_time_var = tk.StringVar(value='')
tk.Entry(fitRow1, textvariable=fit_start_time_var, width=10).pack(side=tk.LEFT, padx=(0,20))
tk.Label(fitRow1, text='Fit End Time (hr):', width=18, anchor=W).pack(side=tk.LEFT)
fit_end_time_var = tk.StringVar(value='')
tk.Entry(fitRow1, textvariable=fit_end_time_var, width=10).pack(side=tk.LEFT)

fitRow2 = tk.Frame(fitFrame); fitRow2.pack(fill=tk.X, padx=4, pady=2)
export_fit_button = tk.Button(fitRow2, text='Export Fit CSV',
    command=export_fit_csv, width=16, state='disabled')
export_fit_button.pack(side=tk.LEFT)

fitRow3 = tk.Frame(fitFrame); fitRow3.pack(fill=tk.X, padx=4, pady=2)
calculateFitButton = tk.Button(fitRow3, text='Calculate Fit',
                               command=calculate_exponential_fit, width=14, state='disabled')
calculateFitButton.pack(side=tk.LEFT)
tk.Button(fitRow3, text='Clear Fit', command=clear_fit,
          width=10).pack(side=tk.LEFT, padx=(6,0))

fit_results_label = tk.Label(fitFrame, text='', anchor=W, justify=LEFT,
                             fg='darkgreen', wraplength=680)
fit_results_label.pack(fill=tk.X, padx=6, pady=(0,4))

# ── Section 5b: Plot Options ─────────────────────────────────────────────
plotOptFrame = tk.LabelFrame(mainFrame, text='Plot Options',
                              font=('TkDefaultFont', 9, 'bold'))
plotOptFrame.pack(fill=tk.X, **PAD)

thicknessRow = tk.Frame(plotOptFrame); thicknessRow.pack(fill=tk.X, padx=4, pady=4)
tk.Label(thicknessRow, text='Curve Thickness:', width=18, anchor='w').pack(side=tk.LEFT)
line_thickness_var = tk.DoubleVar(value=1.8)
tk.Scale(thicknessRow, from_=0.5, to=5.0, resolution=0.25,
         orient=tk.HORIZONTAL, variable=line_thickness_var,
         length=220, showvalue=True).pack(side=tk.LEFT)
tk.Label(thicknessRow, text='pt  (applies to all curves on next Generate Graph / overlay)',
         fg='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(6,0))


# ── Section 5c: Apply Smoothing ──────────────────────────────────────────
smoothFrame = tk.LabelFrame(mainFrame, text='Apply Smoothing',
                             font=('TkDefaultFont', 9, 'bold'))
smoothFrame.pack(fill=tk.X, **PAD)
_smRow = tk.Frame(smoothFrame); _smRow.pack(fill=tk.X, padx=4, pady=4)
apply_smoothing_var = tk.BooleanVar(value=False)
tk.Checkbutton(_smRow,
               text='Smooth temperature profile  (2nd-degree polynomial, 200 mm window)',
               variable=apply_smoothing_var).pack(side=tk.LEFT)

# ── Section 6: dn/dt Calculator ─────────────────────────────────────────
dndtFrame = tk.LabelFrame(mainFrame, text='Rate of Change  dn/dt',
                          font=('TkDefaultFont', 9, 'bold'))
dndtFrame.pack(fill=tk.X, **PAD)

dndtRow1 = tk.Frame(dndtFrame); dndtRow1.pack(fill=tk.X, padx=4, pady=2)
tk.Label(dndtRow1, text='Period Start (hr):', width=18, anchor=W).pack(side=tk.LEFT)
dn_dt_start_var = tk.StringVar(value='')
tk.Entry(dndtRow1, textvariable=dn_dt_start_var, width=8).pack(side=tk.LEFT, padx=(0,12))
tk.Label(dndtRow1, text='Period End (hr):', width=16, anchor=W).pack(side=tk.LEFT)
dn_dt_end_var = tk.StringVar(value='')
tk.Entry(dndtRow1, textvariable=dn_dt_end_var, width=8).pack(side=tk.LEFT, padx=(0,12))
tk.Label(dndtRow1, text='Interval (hr):', width=13, anchor=W).pack(side=tk.LEFT)
dn_dt_interval_var = tk.StringVar(value='')
tk.Entry(dndtRow1, textvariable=dn_dt_interval_var, width=8).pack(side=tk.LEFT)



dndtRow2 = tk.Frame(dndtFrame); dndtRow2.pack(fill=tk.X, padx=4, pady=2)
dn_dt_button = tk.Button(dndtRow2, text='Calculate dn/dt',
                         command=calculate_dn_dt, width=16, state='disabled')
dn_dt_button.pack(side=tk.LEFT)
tk.Button(dndtRow2, text='Clear dn/dt', command=clear_dndt,
          width=12).pack(side=tk.LEFT, padx=(6,0))

dn_dt_results_label = tk.Label(dndtFrame, text='', anchor=W,
                               justify=LEFT, fg='darkorchid',
                               wraplength=680)
dn_dt_results_label.pack(fill=tk.X, padx=6, pady=(0,4))


# ── Progress Bars ─────────────────────────────────────────────────────────
progFrame = tk.Frame(mainFrame); progFrame.pack(fill=tk.X, padx=6, pady=2)
tk.Label(progFrame, text='File:', anchor=W, width=5).pack(side=tk.LEFT)
fileProgress = Progressbar(progFrame, orient=HORIZONTAL, length=150, mode='determinate')
fileProgress.pack(side=tk.LEFT, padx=(0,16))
tk.Label(progFrame, text='Graph:', anchor=W, width=6).pack(side=tk.LEFT)
graphProgress = Progressbar(progFrame, orient=HORIZONTAL, length=250, mode='determinate')
graphProgress.pack(side=tk.LEFT)

window.attributes('-topmost', False)

# == Section 8: Pressure Trace Synthesizer ====================================
synthFrame = tk.LabelFrame(mainFrame, text='Pressure Trace Synthesizer',
                            font=('TkDefaultFont', 9, 'bold'))
synthFrame.pack(fill=tk.X, **PAD)

tk.Label(synthFrame,
         text='Compute a forward P(t) trace from AC geometry + temperature '
              'schedule.  No raw data file required.',
         anchor=W, fg='#444', font=('TkDefaultFont', 8),
         wraplength=680).pack(fill=tk.X, padx=6, pady=(2, 0))

# -- Volume computation row ---------------------------------------------------
synthVolRow = tk.Frame(synthFrame); synthVolRow.pack(fill=tk.X, padx=4, pady=2)
tk.Button(synthVolRow, text='Compute Volume Profile',
          command=_synth_compute_volume, width=22).pack(side=tk.LEFT)
synth_vol_label = tk.Label(synthVolRow,
                            text='(click after loading geometry files)',
                            anchor=W, fg='gray', font=('TkDefaultFont', 8))
synth_vol_label.pack(side=tk.LEFT, padx=(8, 0))

# -- Initial conditions -------------------------------------------------------
synthIC = tk.Frame(synthFrame); synthIC.pack(fill=tk.X, padx=4, pady=2)
tk.Label(synthIC, text='P0 (MPa):', width=10, anchor=W).pack(side=tk.LEFT)
synth_p0_var = tk.StringVar(value='')
tk.Entry(synthIC, textvariable=synth_p0_var, width=8).pack(side=tk.LEFT, padx=(0, 10))
tk.Label(synthIC, text='T0 (degC):', width=10, anchor=W).pack(side=tk.LEFT)
synth_t0_var = tk.StringVar(value='25')
tk.Entry(synthIC, textvariable=synth_t0_var, width=7).pack(side=tk.LEFT, padx=(0, 10))
tk.Label(synthIC, text='T_ambient (degC):', width=17, anchor=W).pack(side=tk.LEFT)
synth_ambient_var = tk.StringVar(value='25')
tk.Entry(synthIC, textvariable=synth_ambient_var, width=7).pack(side=tk.LEFT, padx=(0, 10))

# -- Time parameters ----------------------------------------------------------
synthTimeRow = tk.Frame(synthFrame); synthTimeRow.pack(fill=tk.X, padx=4, pady=2)
tk.Label(synthTimeRow, text='Total time (hr):', width=15, anchor=W).pack(side=tk.LEFT)
synth_total_time_var = tk.StringVar(value='')
tk.Entry(synthTimeRow, textvariable=synth_total_time_var,
         width=8).pack(side=tk.LEFT, padx=(0, 12))
tk.Label(synthTimeRow, text='Time step (hr):', width=14, anchor=W).pack(side=tk.LEFT)
synth_dt_var = tk.StringVar(value='0.05')
tk.Entry(synthTimeRow, textvariable=synth_dt_var, width=8).pack(side=tk.LEFT)

# -- Furnace schedule text widget ---------------------------------------------
synthSchedOuter = tk.LabelFrame(
    synthFrame,
    text='Furnace Schedule  (one breakpoint per line:  time_hr, T_setpoint_degC)',
    font=('TkDefaultFont', 8))
synthSchedOuter.pack(fill=tk.X, padx=6, pady=(4, 2))
synth_schedule_text = tk.Text(synthSchedOuter, height=5, width=32,
                               font=('Courier New', 9), relief='sunken', bd=1)
synth_schedule_text.pack(side=tk.LEFT, padx=(4, 6), pady=4)
synth_schedule_text.insert('1.0',
    '# time_hr, T_setpoint_degC\n'
    '0.0, 25\n'
    '0.5, 25\n'
    '1.5, 700\n'
    '5.0, 700\n'
    '6.0, 25\n')
tk.Label(synthSchedOuter,
         text='Linear interpolation between breakpoints.\n'
              'Lines starting with # are ignored.',
         anchor=W, justify=tk.LEFT, fg='gray',
         font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(0, 6))

# -- Spatial temperature distribution mode ------------------------------------
synthModeFrame = tk.LabelFrame(
    synthFrame,
    text='Spatial Temperature Distribution along Autoclave',
    font=('TkDefaultFont', 8))
synthModeFrame.pack(fill=tk.X, padx=6, pady=(4, 2))
synth_profile_mode_var = tk.StringVar(value='profile_csv')

# Option 1: Uniform
tk.Radiobutton(synthModeFrame,
               text='Uniform  (entire gas volume at T_setpoint)',
               variable=synth_profile_mode_var,
               value='uniform').pack(anchor=W, padx=6)

# Option 2: Gradient
tk.Radiobutton(synthModeFrame,
               text='Gradient  (linear: T_ambient at z=0  to  T_setpoint at z=end)',
               variable=synth_profile_mode_var,
               value='gradient').pack(anchor=W, padx=6)

# Option 3: Temp Profile CSV (the proper calibrated spatial shape)
synthCsvRow = tk.Frame(synthModeFrame); synthCsvRow.pack(anchor=W, padx=6, pady=(0, 2))
tk.Radiobutton(synthCsvRow,
               text='Temp Profile CSV  (calibrated T(z) lookup — same format as File Selection)',
               variable=synth_profile_mode_var,
               value='profile_csv').pack(side=tk.LEFT)

synthCsvBtnRow = tk.Frame(synthModeFrame); synthCsvBtnRow.pack(anchor=W, padx=22, pady=(0, 4))
tk.Button(synthCsvBtnRow, text='Use Loaded Profile',
          command=synth_use_loaded_temp_profile,
          width=18).pack(side=tk.LEFT, padx=(0, 4))
tk.Button(synthCsvBtnRow, text='Browse Different File...',
          command=browse_synth_lookup_table,
          width=22).pack(side=tk.LEFT, padx=(0, 6))
synth_lookup_label = tk.Label(synthCsvBtnRow,
                               text='(no profile CSV loaded for synthesizer)',
                               anchor=W, fg='gray',
                               font=('TkDefaultFont', 8))
synth_lookup_label.pack(side=tk.LEFT)

# Option 4: Simple 2-col shape CSV (legacy)
synthLoadedRow = tk.Frame(synthModeFrame); synthLoadedRow.pack(anchor=W, padx=6, pady=(0, 4))
tk.Radiobutton(synthLoadedRow,
               text='Simple shape CSV  (z_mm, T_C — scaled proportionally)',
               variable=synth_profile_mode_var,
               value='loaded').pack(side=tk.LEFT)
tk.Button(synthLoadedRow, text='Browse...',
          command=browse_synth_spatial_profile,
          width=10).pack(side=tk.LEFT, padx=(6, 4))
synth_spatial_label = tk.Label(synthLoadedRow, text='(none loaded)',
                                anchor=W, fg='gray', font=('TkDefaultFont', 8))
synth_spatial_label.pack(side=tk.LEFT)

# -- n readout ----------------------------------------------------------------
synthNRow = tk.Frame(synthFrame); synthNRow.pack(fill=tk.X, padx=4, pady=(0, 2))
synth_n_label = tk.Label(synthNRow, text='', anchor=W, fg='#004080',
                          font=('TkDefaultFont', 8))
synth_n_label.pack(side=tk.LEFT)

# -- Action buttons -----------------------------------------------------------
synthActRow = tk.Frame(synthFrame); synthActRow.pack(fill=tk.X, padx=4, pady=4)
synth_run_button = tk.Button(synthActRow, text='Run Synthesizer',
                              command=synthesize_pressure_trace, width=18)
synth_run_button.pack(side=tk.LEFT, padx=(0, 6))
tk.Button(synthActRow, text='Clear Synth Trace',
          command=clear_synth_trace, width=16).pack(side=tk.LEFT)

# -- Status label -------------------------------------------------------------
synth_status_label = tk.Label(synthFrame, text='', anchor=W, justify=tk.LEFT,
                               fg='darkgreen', wraplength=680,
                               font=('TkDefaultFont', 8))
synth_status_label.pack(fill=tk.X, padx=6, pady=(0, 4))
# Size window for landing page
window.update_idletasks()
_lw, _lh = 500, 420
_lx = (window.winfo_screenwidth() - _lw) // 2
_ly = (window.winfo_screenheight() - _lh) // 2
window.geometry(f'{_lw}x{_lh}+{_lx}+{_ly}')
window.mainloop()
