# =============================================================================
# PRESSURE TRACE SYNTHESIZER
# Forward-calculates P(t) from user-defined T schedule + AC geometry.
# No raw LabVIEW data required.
# =============================================================================

import numpy as np

def _synth_compute_volume():
    """Compute coarseVol from loaded geometry files without needing raw data."""
    global synth_coarse_vol, synth_vol_label
    global fur_file, hps_file, layout_file, mating_table_file
    global fur_mass_entries, fur_internal_checks
    global chem_species_var, chem_mass_var, chem_density_var

    if not layout_file:
        msg = 'Error: Layout file not loaded. Use Resolve Geometry or browse manually.'
        print('Synth:', msg)
        if synth_vol_label: synth_vol_label.configure(text=msg, fg='red')
        return
    if not mating_table_file or not fur_file or not hps_file:
        msg = 'Error: Geometry files missing. Use Resolve Geometry first.'
        print('Synth:', msg)
        if synth_vol_label: synth_vol_label.configure(text=msg, fg='red')
        return

    DENSITY_MAP = {
        "TZM B387 Type 364":      10.22,
        "304SS":                   7.93,
        "Molybdenum":             10.28,
        "Zr":                      6.52,
        "SS 316":                  8.00,
        "TZM B387-19, Type 364":  10.22,
    }
    CHEMICAL_PROPS = {
        'Li3BN2':  1.85,
        'Li3N':    1.27,
        'Li3AlN2': 2.31,
        'Li3GaN2': 4.10,
        'GaN':     6.15,
    }

    try:
        partList = pd.read_excel(layout_file)
    except Exception as e:
        print(f'Synth: Error reading layout: {e}')
        if synth_vol_label: synth_vol_label.configure(text=f'Error: {e}', fg='red')
        return

    volumeDF, uid_to_material = getSystemVolumeProfile(
        partList, mating_table_file, fur_file, hps_file)
    if volumeDF is None:
        print('Synth: getSystemVolumeProfile returned None.')
        if synth_vol_label: synth_vol_label.configure(text='Error: volume calc failed.', fg='red')
        return

    # --- Furniture mass correction (reuse fur_mass_entries from main UI) ---
    _any_fur = False
    for _uid, _mass_sv in fur_mass_entries.items():
        _mstr = _mass_sv.get().strip()
        if not _mstr: continue
        try:
            _mass_g = float(_mstr)
        except ValueError:
            continue
        _is_int     = fur_internal_checks.get(_uid, tk.BooleanVar(value=False)).get()
        _col_prefix = 'Internal_' if _is_int else 'External_'
        _mat  = uid_to_material.get(_uid)
        _dens = DENSITY_MAP.get(_mat) if _mat else None
        if not _dens: continue
        _V_mass_mm3 = (_mass_g / _dens) * 1000.0
        for _col in volumeDF.columns:
            if _col.startswith(_col_prefix) and _col.endswith(f'_{_uid}'):
                _V_cad = float(volumeDF[_col].sum())
                if abs(_V_cad) < 1e-9: break
                _scale = _V_mass_mm3 / abs(_V_cad)
                volumeDF[_col] = volumeDF[_col] * _scale
                _any_fur = True
                break
    if _any_fur:
        volumeDF['Total Volume'] = volumeDF.filter(like='Part_').fillna(0).sum(axis=1)

    # --- Chemical species volume ---
    _chem_sp = chem_species_var.get() if chem_species_var else 'None'
    _chem_ms = chem_mass_var.get().strip() if chem_mass_var else ''
    if _chem_sp not in ('None', '') and _chem_ms:
        try:
            _chem_g = float(_chem_ms)
            _chem_dens = (float(chem_density_var.get().strip())
                          if chem_density_var and chem_density_var.get().strip()
                          else None) if _chem_sp == 'Custom' else CHEMICAL_PROPS.get(_chem_sp)
            if _chem_dens and _chem_g > 0:
                _V_chem_mm3 = (_chem_g / _chem_dens) * 1000.0
                _cru_col = next((c for c in volumeDF.columns
                                 if c.startswith('Internal_') and 'CRU' in c.upper()), None)
                if _cru_col:
                    _nz = volumeDF[_cru_col][volumeDF[_cru_col] != 0]
                    if len(_nz) > 0:
                        _cru_s = int(_nz.index[0]); _cru_e = int(_nz.index[-1])
                        _n_sl  = _cru_e - _cru_s + 1
                        volumeDF[f'Chem_{_chem_sp}'] = pd.Series(
                            [-_V_chem_mm3 / _n_sl] * _n_sl,
                            index=range(_cru_s, _cru_e + 1))
                        _extra = volumeDF.filter(regex='^Chem_').fillna(0).sum(axis=1)
                        volumeDF['Total Volume'] = (
                            volumeDF.filter(like='Part_').fillna(0).sum(axis=1) + _extra)
        except Exception as _ce:
            print(f'Synth: chemical volume warning: {_ce}')

    # --- Coarsen to 100-mm bins -> m3 ---
    coarseVol_series = volumeDF['Total Volume']
    remainder = len(coarseVol_series) % 100
    if remainder:
        padding = pd.Series([0] * (100 - remainder),
                            index=range(len(coarseVol_series),
                                        len(coarseVol_series) + 100 - remainder))
        coarseVol_series = pd.concat([coarseVol_series, padding])
    raw = coarseVol_series.tolist()
    coarseVol = [sum(raw[100 * i:100 * (i + 1)]) / 1e9   # mm3 -> m3
                 for i in range(len(raw) // 100)]

    synth_coarse_vol = coarseVol
    V_tot_mL = sum(coarseVol) * 1e6
    vol_str = f'V = {V_tot_mL:.3f} mL  ({len(coarseVol)} bins x 100 mm)'
    if synth_vol_label:
        synth_vol_label.configure(text=vol_str, fg='darkgreen')
    print(f'Synth volume computed: {vol_str}')


# ---------------------------------------------------------------------------
# Temp-profile CSV lookup helpers
# ---------------------------------------------------------------------------

def _synth_load_lookup_table(path):
    """
    Load a MolCalc temp profile CSV as a lookup table for the synthesizer.
    Format: rows indexed by TC setpoint temperature (degC),
            columns are z positions in mm.
    Returns (lookup_table_df, z_positions_mm_array) or (None, None) on error.
    """
    global synth_lookup_table, synth_lookup_z_mm
    try:
        tbl = pd.read_csv(path, index_col=0)
        # Normalise column names to integer mm strings (same as processData)
        tbl.columns = [str(int(float(c))) for c in tbl.columns]
        # Row index should be numeric TC setpoint temperatures
        tbl.index = pd.to_numeric(tbl.index, errors='coerce')
        tbl = tbl[~tbl.index.isna()].sort_index()
        if tbl.empty:
            print('Synth: temp profile CSV is empty after parsing.')
            return None, None
        z_mm = np.array([int(c) for c in tbl.columns], dtype=float)
        synth_lookup_table = tbl
        synth_lookup_z_mm  = z_mm
        print(f'Synth: temp profile CSV loaded — '
              f'{len(tbl)} setpoint rows, z range {z_mm.min():.0f}–{z_mm.max():.0f} mm')
        return tbl, z_mm
    except Exception as e:
        print(f'Synth: error loading temp profile CSV: {e}')
        return None, None


def _synth_get_T_from_lookup(T_setpoint_C, n_bins, ambient_K):
    """
    Query the loaded temp profile lookup table at T_setpoint_C.
    Finds the closest row (TC setpoint), reads the full T(z) spatial profile,
    and resamples it to n_bins of 100 mm each (matching coarseVol resolution).
    Returns T array in K of length n_bins.
    """
    if synth_lookup_table is None or synth_lookup_z_mm is None:
        print('Synth: lookup table not loaded — falling back to uniform.')
        return np.full(n_bins, T_setpoint_C + 273.15)

    tbl  = synth_lookup_table
    z_mm = synth_lookup_z_mm

    # Find the closest row to T_setpoint_C (binary search on sorted index)
    idx = tbl.index.searchsorted(T_setpoint_C)
    idx = int(np.clip(idx, 0, len(tbl) - 1))
    T_z_C = tbl.iloc[idx].values.astype(float)

    # Resample from CSV z-positions to 100-mm bin centres used by coarseVol
    z_bin_centres = np.arange(n_bins) * 100.0 + 50.0   # mm centres
    T_resampled_C = np.interp(z_bin_centres, z_mm, T_z_C,
                               left=float(T_z_C[0]),
                               right=float(T_z_C[-1]))
    T_K = T_resampled_C + 273.15
    return np.clip(T_K, ambient_K, None)


def browse_synth_lookup_table():
    """Browse for a temp profile CSV to use in the synthesizer."""
    global synth_lookup_label
    p = filedialog.askopenfilename(
        initialdir=(os.path.dirname(temp_profile_file)
                    if temp_profile_file else os.path.expanduser('~')),
        title='Select Temp Profile CSV for Synthesizer',
        filetypes=(('CSV files', '*.csv'),))
    if not p:
        return
    tbl, z_mm = _synth_load_lookup_table(p)
    if tbl is not None and synth_lookup_label:
        synth_lookup_label.configure(
            text=f'{os.path.basename(p)}  '
                 f'({len(tbl)} setpoint rows, '
                 f'z {z_mm.min():.0f}–{z_mm.max():.0f} mm)',
            fg='black')
    elif synth_lookup_label:
        synth_lookup_label.configure(text='Error loading file.', fg='red')


def synth_use_loaded_temp_profile():
    """Load the temp profile CSV that is already selected in the File Selection section."""
    global synth_lookup_label
    if not temp_profile_file:
        if synth_lookup_label:
            synth_lookup_label.configure(
                text='No temp profile loaded in File Selection — browse below.',
                fg='darkorange')
        return
    tbl, z_mm = _synth_load_lookup_table(temp_profile_file)
    if tbl is not None and synth_lookup_label:
        synth_lookup_label.configure(
            text=f'{os.path.basename(temp_profile_file)}  '
                 f'({len(tbl)} setpoint rows, '
                 f'z {z_mm.min():.0f}–{z_mm.max():.0f} mm)',
            fg='darkgreen')
    elif synth_lookup_label:
        synth_lookup_label.configure(text='Error loading temp profile.', fg='red')


# ---------------------------------------------------------------------------
# Core T-profile builder
# ---------------------------------------------------------------------------

def _synth_build_T_profile(T_set_K, n_bins, mode, ambient_K, loaded_profile):
    """
    Return a numpy array of temperatures (K) of length n_bins for a given setpoint.

    mode == 'uniform'     : all bins at T_set_K
    mode == 'gradient'    : linear from ambient_K (z=0) to T_set_K (z=end)
    mode == 'profile_csv' : query synth_lookup_table at T_set_K-273.15
    mode == 'loaded'      : scale a loaded (z_arr, T_arr_K) shape proportionally
    """
    T_set_K = max(T_set_K, ambient_K)

    if mode == 'uniform':
        return np.full(n_bins, T_set_K)

    elif mode == 'gradient':
        return np.linspace(ambient_K, T_set_K, n_bins)

    elif mode == 'profile_csv':
        return _synth_get_T_from_lookup(T_set_K - 273.15, n_bins, ambient_K)

    elif mode == 'loaded' and loaded_profile is not None:
        z_ref, T_ref_K = loaded_profile
        src_idx  = np.linspace(0, len(T_ref_K) - 1, n_bins)
        T_interp = np.interp(src_idx, np.arange(len(T_ref_K)), T_ref_K)
        T_max    = float(np.max(T_interp))
        T_min_r  = float(np.min(T_interp))
        span     = T_max - T_min_r
        if span > 1.0:
            scale = (T_set_K - ambient_K) / span
            T_out = ambient_K + scale * (T_interp - T_min_r)
        else:
            T_out = np.full(n_bins, T_set_K)
        return np.clip(T_out, ambient_K, None)

    else:
        return np.full(n_bins, T_set_K)  # fallback


# ---------------------------------------------------------------------------
# Equilibrium pressure solver
# ---------------------------------------------------------------------------

def _synth_compute_P(n_mol, T_arr_K, coarse_vol, z_interp=None,
                     z_T_min=250, z_T_max=2000, z_P_min=0.1, z_P_max=50, R=8.3145):
    """
    Compute equilibrium pressure (Pa) for fixed n_mol using real-gas iteration.
    P = n / sum(Vi / (Zi * R * Ti))
    Converges in typically < 10 iterations.
    """
    V_arr = np.array(coarse_vol, dtype=float)
    n_b   = len(V_arr)
    T_in  = np.array(T_arr_K, dtype=float)
    if len(T_in) >= n_b:
        T_use = T_in[:n_b]
    else:
        T_use = np.concatenate([T_in, np.full(n_b - len(T_in),
                                               T_in[-1] if len(T_in) else 298.15)])
    T_use = np.clip(T_use, 1e-6, None)

    # Ideal-gas first guess
    P_guess = n_mol * R * float(np.mean(T_use)) / float(np.sum(V_arr))
    if not np.isfinite(P_guess) or P_guess <= 0:
        P_guess = 1e5

    for _ in range(20):
        if z_interp is not None:
            P_MPa_g = float(np.clip(P_guess / 1e6, z_P_min, z_P_max))
            T_cl    = np.clip(T_use, z_T_min, z_T_max)
            Z_arr   = z_interp(np.column_stack([T_cl, np.full(n_b, P_MPa_g)]))
            Z_arr   = np.clip(Z_arr, 0.5, 2.0)
        else:
            Z_arr = np.ones(n_b)
        denom = float(np.sum(V_arr / (Z_arr * R * T_use)))
        if denom <= 0:
            return np.nan
        P_new = n_mol / denom
        if not np.isfinite(P_new):
            return np.nan
        if abs(P_new - P_guess) / max(abs(P_guess), 1e-12) < 1e-8:
            break
        P_guess = P_new
    return P_new   # Pa


# ---------------------------------------------------------------------------
# Standalone plot window
# ---------------------------------------------------------------------------

def _synth_plot_standalone(time_arr, P_synth, sched_t, sched_T,
                           gas_name, T_amb_K, mode):
    """Open a standalone Toplevel window with the synthesized P(t) plot."""
    win = tk.Toplevel(window)
    win.title('Pressure Trace Synthesizer - Result')
    win.geometry('960x480')

    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 13, 'axes.linewidth': 1.4,
        'axes.labelsize': 13, 'xtick.labelsize': 12, 'ytick.labelsize': 12,
        'legend.fontsize': 11,
        'axes.grid': True, 'grid.color': '0.88', 'grid.linewidth': 0.5,
        'xtick.direction': 'in', 'ytick.direction': 'in',
        'xtick.minor.visible': True, 'ytick.minor.visible': True,
        'figure.facecolor': 'white', 'axes.facecolor': 'white',
    })
    fig, ax_p = plt.subplots(figsize=(8, 8))
    ax_p.set_box_aspect(1)
    fig.subplots_adjust(left=0.10, right=0.88, top=0.91, bottom=0.18)

    C_P = '#d62728'
    C_T = '#ff7f0e'

    mask = ~np.isnan(P_synth)
    ax_p.plot(time_arr[mask], P_synth[mask], color=C_P, linewidth=1.8,
              label='P_synth (MPa)')
    ax_p.set_xlabel('Time (h)', labelpad=4)
    ax_p.set_ylabel('Pressure (MPa)', color=C_P, labelpad=4)
    ax_p.tick_params(axis='y', labelcolor=C_P, direction='in', which='both')
    ax_p.tick_params(axis='x', direction='in', which='both')
    ax_p.spines['top'].set_visible(False)

    ax_t = ax_p.twinx()
    ax_t.plot(sched_t, sched_T, color=C_T, linestyle='--', linewidth=1.4,
              marker='o', markersize=4, label='T setpoint (degC)')
    ax_t.set_ylabel('T setpoint (degC)', color=C_T, labelpad=4)
    ax_t.tick_params(axis='y', labelcolor=C_T, direction='in', which='both')
    ax_t.spines['top'].set_visible(False)

    T_amb_C = T_amb_K - 273.15
    ax_p.set_title(
        f'Synthesized Pressure Trace  |  Gas: {gas_name}  |  Mode: {mode}  |  '
        f'T_amb = {T_amb_C:.0f} degC',
        fontsize=9, pad=5)

    lines1, labs1 = ax_p.get_legend_handles_labels()
    lines2, labs2 = ax_t.get_legend_handles_labels()
    fig.legend(lines1 + lines2, labs1 + labs2,
               loc='upper center', bbox_to_anchor=(0.5, 0.06),
               ncol=2, fontsize=9, framealpha=0.95, edgecolor='0.6',
               bbox_transform=fig.transFigure)

    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)
    NavigationToolbar2Tk(canvas, win)


# ---------------------------------------------------------------------------
# Browse for simple 2-col spatial profile (legacy mode)
# ---------------------------------------------------------------------------

def browse_synth_spatial_profile():
    """Browse for a 1-D spatial profile CSV (columns: z_mm, T_C) — legacy mode."""
    global synth_spatial_file, synth_loaded_profile, synth_spatial_label
    p = filedialog.askopenfilename(
        initialdir=os.path.expanduser('~'),
        title='Select Spatial Profile CSV  (columns: z_mm, T_C)',
        filetypes=(('CSV files', '*.csv'),))
    if not p:
        return
    try:
        df_sp = pd.read_csv(p)
        num_cols = [c for c in df_sp.columns
                    if pd.api.types.is_numeric_dtype(df_sp[c])]
        if len(num_cols) < 2:
            print(f'Synth spatial CSV: need >= 2 numeric cols; got {df_sp.columns.tolist()}')
            return
        z_arr   = df_sp[num_cols[0]].values.astype(float)
        T_arr_C = df_sp[num_cols[1]].values.astype(float)
        T_arr_K = T_arr_C + 273.15
        synth_loaded_profile = (z_arr, T_arr_K)
        synth_spatial_file   = p
        if synth_spatial_label:
            synth_spatial_label.configure(
                text=f'{os.path.basename(p)}  ({len(z_arr)} pts, '
                     f'T range {T_arr_C.min():.0f}-{T_arr_C.max():.0f} degC)',
                fg='black')
        print(f'Synth spatial profile loaded: {p}  ({len(z_arr)} pts)')
    except Exception as e:
        print(f'Error loading spatial profile: {e}')
        if synth_spatial_label:
            synth_spatial_label.configure(text=f'Error: {e}', fg='red')


# ---------------------------------------------------------------------------
# Main synthesizer
# ---------------------------------------------------------------------------

def synthesize_pressure_trace():
    """
    Forward-calculate a synthetic pressure trace P(t) from:
      - AC geometry (layout + MLD files already loaded)
      - User-defined furnace temperature schedule
      - Initial conditions P0 (MPa), T0 (degC)
      - Gas species
    No raw LabVIEW data needed.
    """
    global synth_coarse_vol, synth_status_label, synth_n_label
    global gas_species_var, plot_fig, plot_ax2, plot_canvas, output_dir

    # -- 1. Parse scalar inputs -----------------------------------------------
    try:
        P0_MPa   = float(synth_p0_var.get())
        T0_C     = float(synth_t0_var.get())
        T_amb_C  = float(synth_ambient_var.get().strip() or '25')
        total_hr = float(synth_total_time_var.get())
        dt_hr    = float(synth_dt_var.get())
    except (ValueError, AttributeError) as e:
        if synth_status_label:
            synth_status_label.configure(text=f'Input error: {e}', fg='red')
        return

    if dt_hr <= 0 or total_hr <= 0:
        synth_status_label.configure(
            text='Error: Total time and time step must be > 0.', fg='red')
        return

    # -- 2. Parse furnace schedule ---------------------------------------------
    try:
        raw_sched = synth_schedule_text.get('1.0', 'end').strip()
        sched_t_list, sched_T_list = [], []
        for line in raw_sched.splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.replace(';', ',').split(',')
            if len(parts) < 2:
                continue
            sched_t_list.append(float(parts[0].strip()))
            sched_T_list.append(float(parts[1].strip()))
        if not sched_t_list:
            synth_status_label.configure(
                text='Error: Enter at least one schedule line (time_hr, T_degC).',
                fg='red')
            return
        sched_t = np.array(sched_t_list, dtype=float)
        sched_T = np.array(sched_T_list, dtype=float)
    except (ValueError, AttributeError) as e:
        synth_status_label.configure(text=f'Schedule parse error: {e}', fg='red')
        return

    # -- 3. Ensure volume profile is available --------------------------------
    if synth_coarse_vol is None:
        synth_status_label.configure(text='Computing volume profile...', fg='darkorange')
        synth_status_label.update_idletasks()
        _synth_compute_volume()
        if synth_coarse_vol is None:
            synth_status_label.configure(
                text='Error: Volume not computed. Load geometry files then click '
                     '"Compute Volume Profile".', fg='red')
            return
    coarse_vol = synth_coarse_vol
    n_bins = len(coarse_vol)
    V_arr  = np.array(coarse_vol, dtype=float)
    if V_arr.sum() <= 0:
        synth_status_label.configure(text='Error: Total volume is zero.', fg='red')
        return

    # -- 4. Load Z table -------------------------------------------------------
    from scipy.interpolate import RegularGridInterpolator as _RGI
    _z_interp = None
    _z_T_min, _z_T_max, _z_P_min, _z_P_max = 250.0, 2000.0, 0.1, 50.0
    _gas_name = gas_species_var.get() if gas_species_var else 'Nitrogen'
    _gas_file_map = {'Nitrogen': 'N2_Z.npz'}
    _gas_stem = _gas_file_map.get(_gas_name, 'N2_Z.npz')
    try:
        _zd = np.load(os.path.join(CANON_MLD_DIR, _gas_stem))
        _z_interp = _RGI((_zd['T_K'], _zd['P_MPa']), _zd['Z'],
                          bounds_error=False, fill_value=None)
        _z_T_min = float(_zd['T_K'].min())
        _z_T_max = float(_zd['T_K'].max())
        _z_P_min = float(_zd['P_MPa'].min())
        _z_P_max = float(_zd['P_MPa'].max())
        print(f'Synth: Z table loaded ({_gas_name})')
    except Exception as _ze:
        print(f'Synth: Z table not found ({_ze}) -- using ideal gas Z=1.')

    R       = 8.3145
    T0_K    = T0_C + 273.15
    T_amb_K = T_amb_C + 273.15
    mode    = synth_profile_mode_var.get() if synth_profile_mode_var else 'uniform'

    # -- 5. Validate profile_csv mode is ready --------------------------------
    if mode == 'profile_csv' and synth_lookup_table is None:
        synth_status_label.configure(
            text='Error: No temp profile CSV loaded for Synthesizer. '
                 'Use "Use Loaded Profile" or browse for a file.',
            fg='red')
        return

    # -- 6. Derive n from initial conditions ----------------------------------
    T0_profile = _synth_build_T_profile(T0_K, n_bins, mode, T_amb_K, synth_loaded_profile)
    P0_Pa = P0_MPa * 1e6
    if _z_interp is not None:
        Z0_arr = _z_interp(np.column_stack([
            np.clip(T0_profile, _z_T_min, _z_T_max),
            np.full(n_bins, float(np.clip(P0_Pa / 1e6, _z_P_min, _z_P_max)))]))
        Z0_arr = np.clip(Z0_arr, 0.5, 2.0)
    else:
        Z0_arr = np.ones(n_bins)
    n_mol = P0_Pa * float(np.sum(V_arr / (Z0_arr * R * T0_profile)))

    if synth_n_label:
        synth_n_label.configure(
            text=f'n = {n_mol * 1000:.4f} mmol  ({n_mol:.4e} mol)  |  '
                 f'V_total = {V_arr.sum() * 1e6:.3f} mL')
    print(f'Synth: n={n_mol:.4e} mol  P0={P0_MPa} MPa  T0={T0_C} degC  '
          f'V={V_arr.sum()*1e6:.3f} mL  mode={mode}')

    # -- 7. Main time loop ----------------------------------------------------
    synth_status_label.configure(text='Running synthesizer...', fg='darkorange')
    synth_status_label.update_idletasks()

    time_arr = np.arange(0.0, total_hr + dt_hr / 2, dt_hr)
    P_synth  = np.empty(len(time_arr))

    for idx, t_hr in enumerate(time_arr):
        T_set_C = float(np.interp(t_hr, sched_t, sched_T,
                                   left=float(sched_T[0]),
                                   right=float(sched_T[-1])))
        T_set_K  = T_set_C + 273.15
        T_prof_K = _synth_build_T_profile(
            T_set_K, n_bins, mode, T_amb_K, synth_loaded_profile)
        P_Pa = _synth_compute_P(
            n_mol, T_prof_K, coarse_vol,
            z_interp=_z_interp,
            z_T_min=_z_T_min, z_T_max=_z_T_max,
            z_P_min=_z_P_min, z_P_max=_z_P_max, R=R)
        P_synth[idx] = P_Pa / 1e6 if np.isfinite(P_Pa) else np.nan

    P_valid = P_synth[~np.isnan(P_synth)]
    result_str = (f'{len(time_arr)} steps  |  '
                  f'P range [{P_valid.min():.3f}, {P_valid.max():.3f}] MPa'
                  if len(P_valid) else 'No valid P values.')
    print(f'Synth complete: {result_str}')

    # -- 8. Plot --------------------------------------------------------------
    _pf = globals().get('plot_fig')
    _pa = globals().get('plot_ax2')
    _pc = globals().get('plot_canvas')
    if _pf is not None and _pa is not None and _pc is not None:
        for artist in _pa.get_lines()[:]:
            if artist.get_gid() == 'synth_P_line':
                artist.remove()
        _lw_sy = float(line_thickness_var.get()) if line_thickness_var else 1.8
        _pa.plot(time_arr, P_synth,
                      color='#9467bd', linestyle='-.', linewidth=_lw_sy,
                      label='P_synth (MPa)', gid='synth_P_line')
        _rebuild_outside_legend(_pf)
        _pc.draw()
    else:
        _synth_plot_standalone(time_arr, P_synth, sched_t, sched_T,
                               _gas_name, T_amb_K, mode)

    # -- 9. Auto-export CSV ---------------------------------------------------
    if output_dir:
        from datetime import datetime
        ts = datetime.now().strftime('%y%m%d_%H%M%S')
        csv_path = os.path.join(output_dir, f'Synth_{ts}.csv')
        try:
            pd.DataFrame({
                'Time_Hours':   time_arr,
                'P_Synth_MPa':  P_synth
            }).to_csv(csv_path, index=False, float_format='%.6f')
            result_str += f'  |  Saved: {os.path.basename(csv_path)}'
            print(f'Synth CSV saved: {csv_path}')
        except Exception as _e:
            print(f'Warning: synth CSV save failed: {_e}')

    synth_status_label.configure(text=result_str, fg='darkgreen')


def clear_synth_trace():
    """Remove synthesizer overlay from the main plot."""
    global plot_ax2, plot_canvas, plot_fig, synth_status_label, synth_n_label
    if plot_fig is not None and plot_ax2 is not None:
        for artist in plot_ax2.get_lines()[:]:
            if artist.get_gid() == 'synth_P_line':
                artist.remove()
        if plot_canvas:
            ax1_ref = _pf.axes[0]
            h, lb = [], []
            for ax in plot_fig.axes:
                for line in ax.get_lines():
                    lbl = line.get_label()
                    if lbl and not lbl.startswith('_') and 'P_synth' not in lbl:
                        h.append(line); lb.append(lbl)
            ax1_ref.legend(handles=h, labels=lb, loc='upper left',
                           bbox_to_anchor=(0.01, 0.99), framealpha=0.85,
                           edgecolor='0.7', fontsize=8)
            plot_canvas.draw()
    if synth_status_label:
        synth_status_label.configure(text='Synth trace cleared.', fg='gray')
    if synth_n_label:
        synth_n_label.configure(text='')
