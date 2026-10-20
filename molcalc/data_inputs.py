# --- browseFiles: data + temp CSV only ---
def browseFiles():
    global data_filename, temp_profile_file, interpolate_temps_var

    data_filename = filedialog.askopenfilename(
        initialdir=os.path.expanduser(r'~\Lehigh University Dropbox'),
        title='1. Select Data CSV File',
        filetypes=(('CSV files', '*.csv*'), ('all files', '*.*'))
    )
    if data_filename:
        fileLabel.configure(text=f'Data: {os.path.basename(data_filename)}', fg='black')
        _populate_pt_dropdown(data_filename)
    else:
        fileLabel.configure(text='Data: (Not Selected)', fg='gray')

    start_dir = os.path.dirname(data_filename) if data_filename else os.path.expanduser('~')

    if not interpolate_temps_var.get():
        temp_profile_file = filedialog.askopenfilename(
            initialdir=start_dir,
            title='2. Select Temperature Profile CSV',
            filetypes=(('CSV files', '*.csv*'),)
        )
        if temp_profile_file:
            tempLabel.configure(text=f'Temp Profile: {os.path.basename(temp_profile_file)}',
                                state='normal', fg='black')
        else:
            tempLabel.configure(text='Temp Profile: (Not Selected)', state='normal', fg='gray')
    else:
        temp_profile_file = ''
        tempLabel.configure(text='Temp Profile: (Using Interpolation)', state='disabled', fg='gray')

    window.update_idletasks()


# --- PT column helper ---
def _populate_pt_dropdown(csv_path):
    """Read CSV headers, filter columns containing 'PT', update the pressure dropdown."""
    global pressure_col_var
    try:
        header = pd.read_csv(csv_path, nrows=0)
        pt_cols = [c for c in header.columns if 'PT' in c.upper()]
    except Exception as e:
        print(f'Warning: could not read PT columns: {e}')
        pt_cols = []

    if not pt_cols:
        pt_cols = ['(none found)']
        print('Warning: no PT columns found in data file.')
    else:
        print(f'PT columns found: {pt_cols}')

    if pressure_col_var is None:
        return   # GUI not yet built

    # Update OptionMenu choices — prefer A2 column if present
    _a2 = [c for c in pt_cols if 'A2' in c.upper()]
    pressure_col_var.set(_a2[0] if _a2 else pt_cols[0])
    menu = pt_menu['menu']
    menu.delete(0, 'end')
    for col in pt_cols:
        menu.add_command(label=col, command=lambda v=col: pressure_col_var.set(v))
    ptRow.configure(bg='white')
    ptLabel.configure(text=f'Pressure Col: ({len(pt_cols)} PT channel{"s" if len(pt_cols)>1 else ""} found)',
                      fg='black')


# --- Canonical geometry file paths ---
DROPBOX           = os.path.join(os.path.expanduser('~'), 'Lehigh University Dropbox')
CANON_MLD_DIR     = os.path.join(DROPBOX, r'ENG-MATSGroup/MATS - Collaboration/Data/Parsers/MolCalc/File Dependencies')
CANON_MOLCALC_DIR = os.path.join(DROPBOX, r'ENG-MATSGroup/MATS - Collaboration/Data\Parsers/MolCalc/File Dependencies')
CANON_LAYOUT_DIR  = CANON_MLD_DIR  # Layouts also live in File Dependencies

def _find_xlsx(directory, exact_stem):
    """Return the path to <exact_stem>.xlsx in directory (case-insensitive stem match),
    or None if the directory doesn't exist or the file isn't found."""
    if not os.path.isdir(directory):
        return None
    target = exact_stem.lower() + '.xlsx'
    for fname in os.listdir(directory):
        if fname.lower() == target:
            return os.path.join(directory, fname)
    return None

def _find_mating_table(directory):
    """Return the first .xlsx whose name contains 'mating', 'surface', or 'mate'."""
    if not os.path.isdir(directory):
        return None
    for kw in ['mating', 'surface', 'mate']:
        for fname in os.listdir(directory):
            if fname.lower().endswith('.xlsx') and kw in fname.lower():
                return os.path.join(directory, fname)
    return None

def _set_label_resolved(label, prefix, path):
    if path:
        label.configure(text=f'{prefix}: {os.path.basename(path)} (auto)', fg='darkgreen')
    else:
        label.configure(text=f'{prefix}: NOT FOUND — select manually', fg='red')
        from tkinter import messagebox
        messagebox.showwarning(
            'File Not Found',
            f'{prefix} was not found at the expected location:\n'
            f'{CANON_MLD_DIR}\n\n'
            f'Please use the Browse... button to locate the file manually.'
        )

def resolve_geometry_files():
    """Auto-resolve all geometry files from canonical paths; update globals + labels."""
    global fur_file, hps_file, mating_table_file, layout_file

    # MLD-FUR: look for exactly 'MLD-FUR.xlsx'
    fur_file = _find_xlsx(CANON_MLD_DIR, 'MLD - FUR')
    _set_label_resolved(furLabel, 'MLD-FUR', fur_file)
    global _internal_uids_set
    _internal_uids_set = set()
    if fur_file and os.path.isfile(fur_file):
        try:
            _xf2 = pd.ExcelFile(fur_file)
            for _sh2 in ['CRU', 'LID', 'PLU', 'VRE']:
                if _sh2 in _xf2.sheet_names:
                    _df2 = pd.read_excel(fur_file, sheet_name=_sh2, usecols=['UID'])
                    _internal_uids_set.update(_df2['UID'].dropna().astype(str).tolist())
            print(f'Internal UIDs detected: {_internal_uids_set}')
        except Exception as _e2:
            print(f'Warning: could not extract internal UIDs: {_e2}')

    # MLD-HPS: look for exactly 'MLD-HPS.xlsx'
    hps_file = _find_xlsx(CANON_MLD_DIR, 'MLD - HPS')
    _set_label_resolved(hpsLabel, 'MLD-HPS', hps_file)

    # Mating Table: search MolCalc root for any xlsx with 'mating', 'surface', or 'mate'
    mating_table_file = _find_mating_table(CANON_MOLCALC_DIR)
    _set_label_resolved(matingLabel, 'Mating Table', mating_table_file)

    # Layout — point dialog at the layouts folder; user always picks the file
    layout_dir = CANON_LAYOUT_DIR if os.path.isdir(CANON_LAYOUT_DIR) else os.path.expanduser('~')
    layout_file = filedialog.askopenfilename(
        initialdir=layout_dir,
        title='Select Autoclave Layout File',
        filetypes=(('Excel files', '*.xlsx*'),)
    )
    if layout_file:
        layoutLabel.configure(text=f'Layout: {os.path.basename(layout_file)}', fg='black')
    else:
        layoutLabel.configure(text='Layout: (Not Selected)', fg='gray')

    window.update_idletasks()
    if fur_table_inner is not None and layout_file:
        build_fur_table_from_layout()
    print(f'FUR:     {fur_file}')
    print(f'HPS:     {hps_file}')
    print(f'Mating:  {mating_table_file}')
    print(f'Layout:  {layout_file}')

# Individual override functions
def browse_fur():
    global fur_file
    p = filedialog.askopenfilename(
        initialdir=CANON_MLD_DIR if os.path.isdir(CANON_MLD_DIR) else os.path.expanduser('~'),
        title='Select MLD-FUR File', filetypes=(('Excel files', '*.xlsx*'),))
    if p:
        fur_file = p
        furLabel.configure(text=f'MLD-FUR: {os.path.basename(p)}', fg='black')
    window.update_idletasks()

def browse_hps():
    global hps_file
    p = filedialog.askopenfilename(
        initialdir=CANON_MLD_DIR if os.path.isdir(CANON_MLD_DIR) else os.path.expanduser('~'),
        title='Select MLD-HPS File', filetypes=(('Excel files', '*.xlsx*'),))
    if p:
        hps_file = p
        hpsLabel.configure(text=f'MLD-HPS: {os.path.basename(p)}', fg='black')
    window.update_idletasks()

def browse_mating():
    global mating_table_file
    p = filedialog.askopenfilename(
        initialdir=CANON_MOLCALC_DIR if os.path.isdir(CANON_MOLCALC_DIR) else os.path.expanduser('~'),
        title='Select Mating Table File', filetypes=(('Excel files', '*.xlsx*'),))
    if p:
        mating_table_file = p
        matingLabel.configure(text=f'Mating Table: {os.path.basename(p)}', fg='black')
    window.update_idletasks()

def browse_layout():
    global layout_file
    layout_dir = CANON_LAYOUT_DIR if os.path.isdir(CANON_LAYOUT_DIR) else os.path.expanduser('~')
    p = filedialog.askopenfilename(
        initialdir=layout_dir,
        title='Select Layout File', filetypes=(('Excel files', '*.xlsx*'),))
    if p:
        layout_file = p
        layoutLabel.configure(text=f'Layout: {os.path.basename(p)}', fg='black')
    window.update_idletasks()
    if fur_table_inner is not None and layout_file:
        build_fur_table_from_layout()


# --- Build Furniture Table from Layout ---
def build_fur_table_from_layout():
    """
    Populate the per-part furniture mass table from the currently loaded layout.
    Reads UIDs, marks internal parts (from _internal_uids_set), and creates
    one row per part with: UID label | material | Internal checkbox | mass entry.
    Safe to call repeatedly — clears and rebuilds each time.
    """
    global fur_mass_entries, fur_internal_checks, fur_table_inner

    if fur_table_inner is None:
        print('Warning: fur_table_inner not yet created — GUI not ready.'); return
    if not layout_file:
        from tkinter import messagebox
        messagebox.showwarning('No Layout', 'Load a Layout file first (via Resolve Geometry).'); return

    # Build UID → material map from whichever geometry files are available
    _uid_mat = {}
    for _path, _sheets, _mcol in [
        (fur_file, ['CRU','LID','PLU','VRE'], 'Chemicals'),
        (hps_file, ['AC','GKT','NZ','TU'],    'Material')
    ]:
        if _path and os.path.isfile(_path):
            try:
                _xf = pd.ExcelFile(_path)
                for _sh in _sheets:
                    if _sh in _xf.sheet_names:
                        _df = pd.read_excel(_path, sheet_name=_sh)
                        if 'UID' in _df.columns and _mcol in _df.columns:
                            for _, _r in _df[['UID', _mcol]].dropna().iterrows():
                                _uid_mat[str(_r['UID'])] = str(_r[_mcol])
            except Exception as _e:
                print(f'Warning: material read error from {os.path.basename(_path)}: {_e}')

    # Clear existing rows
    for w in fur_table_inner.winfo_children():
        w.destroy()
    fur_mass_entries.clear()
    fur_internal_checks.clear()

    try:
        _pl = pd.read_excel(layout_file)
    except Exception as _e:
        from tkinter import messagebox
        messagebox.showerror('Layout Error', f'Could not read layout: {_e}'); return

    _ROW_BG = ('#eef2f7', '#ffffff')
    _row_idx = 0
    for _, _row in _pl.iterrows():
        _uid = str(_row.get('UID', '')).strip()
        if not _uid or _uid.lower() == 'nan':
            continue
        _is_int  = _uid in _internal_uids_set
        _mat     = _uid_mat.get(_uid, '—')
        _bg      = _ROW_BG[_row_idx % 2]
        _row_idx += 1

        _f = tk.Frame(fur_table_inner, bg=_bg)
        _f.pack(fill=tk.X, padx=0, pady=0)

        tk.Label(_f, text=_uid,  width=16, anchor=W, bg=_bg,
                 font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=(3,0))
        tk.Label(_f, text=_mat,  width=16, anchor=W, bg=_bg,
                 font=('TkDefaultFont', 8), fg='#555').pack(side=tk.LEFT)
        _int_var = tk.BooleanVar(value=_is_int)
        fur_internal_checks[_uid] = _int_var
        tk.Checkbutton(_f, variable=_int_var, bg=_bg).pack(side=tk.LEFT, padx=(2,6))
        _mass_sv = tk.StringVar(value='')
        fur_mass_entries[_uid] = _mass_sv
        tk.Entry(_f, textvariable=_mass_sv, width=9,
                 font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

    fur_table_inner.update_idletasks()
    _n_int = sum(v.get() for v in fur_internal_checks.values())
    print(f'Furniture table: {len(fur_mass_entries)} parts ({_n_int} marked internal)')


# --- Toggle Temp File Label State ---
def toggle_temp_file_selection():
    global interpolate_temps_var, tempLabel, temp_profile_file
    if interpolate_temps_var.get():
        tempLabel.configure(text="Temp Profile: (Using Interpolation)", state='disabled')
        temp_profile_file = ""
    else:
        tempLabel.configure(text="Temp Profile: (Select Below)", state='normal')

# --- getData function ---
def getData(runDF_raw, EXP_ID):
    global graphLabel
    print("running getData")
    config_path = os.path.expanduser(r"~\Lehigh University Dropbox\ENG-MATSGroup\MATS\cRIO\RunConfig\EXPs\\") + EXP_ID + '.csv'
    print(config_path)
    try:
        TC_df = pd.read_csv(config_path, usecols=['Device Type', 'NI LV Channel','Shorthand Tag', 'IO Type'])
    except FileNotFoundError: graphLabel.configure(text=f"Error: TC config file not found for {EXP_ID}.csv"); return None, None, None
    except ValueError as e: graphLabel.configure(text=f"Error: Check columns in {EXP_ID}.csv"); return None, None, None
    original_rows = len(TC_df); TC_df.drop_duplicates(subset=['NI LV Channel'], keep='first', inplace=True)
    if len(TC_df) < original_rows: print(f"Removed {original_rows - len(TC_df)} duplicate NI LV Channels.")
    positions = []
    for name, type in zip(TC_df['Shorthand Tag'], TC_df['Device Type']):
        if type == 'TC':
            numbers_found = re.findall(r"\d+", str(name))
            if len(numbers_found) >= 2:
                try: positions.append(int(numbers_found[1]))
                except (ValueError, IndexError): print(f"Warn: Bad TC tag num: '{name}'."); positions.append(np.nan)
            else: print(f"Warn: <2 nums in TC tag: '{name}'."); positions.append(np.nan)
        else: positions.append(np.nan)
    TC_df['X Position'] = positions; TC_df = TC_df.dropna(subset=['X Position'])
    try: TC_df['X Position'] = TC_df['X Position'].astype(int)
    except ValueError: print("Warn: X Pos not int.")
    TC_df = TC_df.sort_values(by='X Position'); TC_positions=TC_df['X Position']
    print("TC_positions (valid & sorted):", TC_positions.tolist()); print("TC_df (valid TCs, unique channels):"); print(TC_df[['NI LV Channel', 'Shorthand Tag', 'X Position', 'IO Type']])
    RelevantColumns = TC_df['NI LV Channel'].to_list()
    if not RelevantColumns: graphLabel.configure(text=f"Error: No valid TCs in config."); return None, None, None
    unique_required_cols = list(dict.fromkeys(RelevantColumns + ["CV1-TC-Ambient"]))
    missing_cols = [col for col in unique_required_cols if col not in runDF_raw.columns]
    if missing_cols: graphLabel.configure(text=f"Error: Data missing cols: {missing_cols}"); return None, None, None
    try:
        runDF_selected = runDF_raw[unique_required_cols].iloc[8:]
        print("Converting temperature columns to numeric...")
        runDF_selected = runDF_selected.apply(pd.to_numeric, errors='coerce')
        # Use how='all' so only fully-empty rows are dropped.
        # how='any' (the default) discards every row that has a NaN in even
        # one TC channel, which empties the dataset if a single TC is missing.
        runDF_filtered = runDF_selected.dropna(how='all')
        n_dropped = len(runDF_selected) - len(runDF_filtered)
        if n_dropped: print(f'getData: dropped {n_dropped} fully-empty rows.')
        if runDF_filtered.empty: graphLabel.configure(text="Error: No valid data rows found after filtering & coercion."); return None, None, None
        print(f"Data rows remaining after filtering: {len(runDF_filtered)}")
        return runDF_filtered, TC_df, TC_positions
    except Exception as e: graphLabel.configure(text=f"Error filtering data: {e}"); return None, None, None
