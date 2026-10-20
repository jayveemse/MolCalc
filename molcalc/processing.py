# --- processData function ---
def processData():
    global runData, baselineEdited, graphLabel, fileProgress, graphProgress, calc_step_var, output_dir, info_log, fit_csv_path, p_zero_start_var, p_zero_end_var, p_zero_manual_var
    global data_filename, temp_profile_file, layout_file, mating_table_file, fur_file, hps_file
    global z_temp_cutoff_var, z_offset_var, p_calc_start_time_var, interpolate_temps_var
    global _sorted_tc_idx, _x_tc_sorted, _x_target_interp
    global exportTempButton, tempViewButton, exportPlotButton, calculateFitButton, fit_results_label, texpansion_button
    global sigma_p_var, sigma_v_var, sigma_t_var # <-- NEW
    global gas_species_var

    info_log = []  # Reset for new run
    fit_csv_path = ""  # Reset — will be created after output_dir check
    _log = _log_live
    open_info_window(clear=True)  # Open/clear info window for new run
    if exportPlotButton: exportPlotButton.configure(state='disabled')
    if exportTempButton: exportTempButton.configure(state='disabled')
    if tempViewButton: tempViewButton.configure(state='disabled')
    if texpansion_button: texpansion_button.configure(state='disabled')
    if calculateFitButton: calculateFitButton.configure(state='disabled')
    if fit_results_label: fit_results_label.configure(text="")

    if not data_filename: graphLabel.configure(text="Error: Select Data File."); return
    use_interpolation = interpolate_temps_var.get()
    if not use_interpolation and not temp_profile_file: graphLabel.configure(text="Error: Select Temp Profile or check Interpolate."); return
    if not layout_file: graphLabel.configure(text="Error: Select Layout File."); return
    if not mating_table_file: graphLabel.configure(text="Error: Select Mating Table."); return
    if not fur_file: graphLabel.configure(text="Error: Select MLD-FUR File."); return
    if not hps_file: graphLabel.configure(text="Error: Select MLD-HPS File."); return
    if not output_dir:
        graphLabel.configure(text='Error: Set Output Folder before running.')
        return

    z_temp_cutoff_mm = None
    # Create the fit CSV path once for this run
    from datetime import datetime as _dt
    _ts_run = _dt.now().strftime('%y%m%d_%H%M%S')
    # Placeholder — will be finalised with run_id after getData
    _fit_csv_pending = True
    try: 
        z_cutoff_input = z_temp_cutoff_var.get();
        if z_cutoff_input: z_temp_cutoff_mm = int(float(z_cutoff_input)); print(f"Using Z-Temp Cutoff: {z_temp_cutoff_mm} mm")
    except ValueError: 
        graphLabel.configure(text="Error: Invalid Z-Temp Cutoff."); return

    z_offset_mm = 0
    try: 
        z_offset_input = z_offset_var.get();
        if z_offset_input: z_offset_mm = int(float(z_offset_input)); print(f"Applying Z-Offset: {z_offset_mm} mm")
    except ValueError: 
        graphLabel.configure(text="Error: Invalid Z-Offset."); return
    if z_offset_mm < 0:
        _log(f"Warning: Negative Z-Offset ({z_offset_mm} mm) not allowed — clamped to 0.")
        z_offset_mm = 0

    p_calc_start_hr = None
    try: 
        start_time_input = p_calc_start_time_var.get();
        if start_time_input: p_calc_start_hr = float(start_time_input); print(f"Using P_calc Start Time: {p_calc_start_hr} Hours")
        else: print("P_calc Start Time not provided.")
    except ValueError: 
        graphLabel.configure(text=f"Error: Invalid P_calc Start Time '{start_time_input}'."); return

    # --- NEW: Get Uncertainty Inputs ---
    try:
        sigma_p_percent = float(sigma_p_var.get()) / 100.0 # Convert from % to fraction
        sigma_v_percent = float(sigma_v_var.get()) / 100.0 # Convert from % to fraction
        sigma_t_base_K = float(sigma_t_var.get()) # Absolute K


        _log(f"Uncertainty Assumptions: P={sigma_p_percent*100}%, V={sigma_v_percent*100}%, T={sigma_t_base_K} K")
    except ValueError:
        graphLabel.configure(text="Error: Invalid uncertainty values. Must be numbers."); return
    # --- END NEW ---

    # --- Calculation Step Interval ---
    calc_step = 1  # default: compute every row
    try:
        step_input = calc_step_var.get().strip()
        if step_input:
            calc_step = max(1, int(float(step_input)))
        _log(f'Calculation step interval: every {calc_step} rows')
    except (ValueError, AttributeError):
        graphLabel.configure(text='Error: Invalid calc step interval.'); return



    fileProgress['value'] = 0; window.update_idletasks()

    try: df = pd.read_csv(data_filename, low_memory=False)
    except Exception as e: graphLabel.configure(text=f"Error reading Data: {e}"); return
    fileProgress['value'] = 10; window.update_idletasks()

    if df.shape[0] <= 12 or df.shape[1] <= 20: graphLabel.configure(text="Error: Data format unexpected."); return
    runID = df.iloc[12,10]; EXP_ID = df.iloc[6, 20]
    global run_id; run_id = str(runID).strip()
    if output_dir:
        from datetime import datetime as _dt2
        fit_csv_path = os.path.join(
            output_dir,
            f'{run_id}_{_dt2.now().strftime("%y%m%d_%H%M%S")}_FitResults.csv'
        )
        _log_live(f'Fit CSV: {os.path.basename(fit_csv_path)}')
    _log(f"Run ID: {runID}, EXP ID: {EXP_ID}")

    runDF_filtered, TC_df, TC_positions = getData(df.copy(), EXP_ID)
    if runDF_filtered is None: return

    print("Resetting runDF index..."); runDF = runDF_filtered.reset_index(drop=True); print("Index reset.")
    fileProgress['value'] = 20; window.update_idletasks()

    # Pressure Processing — column chosen in UI dropdown (populated from CSV headers)
    pressure_col = None; P_MPa = []; P_MPa_series = None
    _sel = pressure_col_var.get().strip() if pressure_col_var else ''
    if _sel and _sel not in ('', '(load data first)', '(none found)'):
        if _sel in df.columns:
            pressure_col = _sel
        else:
            graphLabel.configure(
                text=f'Error: Selected pressure column "{_sel}" not in data file.')
            return
    else:
        # Fallback: auto-detect first column whose name contains 'PT'
        for _c in df.columns:
            if 'PT' in _c.upper():
                pressure_col = _c
                _log(f'Auto-selected pressure column: {pressure_col}')
                break
    if pressure_col is None:
        graphLabel.configure(text='Error: No pressure (PT) column found — select one manually.')
        return
    try:
        _log(f"Using pressure column: {pressure_col}")
        P_MPa_series = df.loc[runDF_filtered.index, pressure_col].astype(float)
        if P_MPa_series.isna().all(): graphLabel.configure(text=f"Error: All pressure data is invalid."); return
        P_MPa = P_MPa_series.tolist()

    except Exception as e: graphLabel.configure(text=f"Error processing pressure: {e}"); return

    # ── Pressure zero offset ─────────────────────────────────────────────
    p_zero_offset = 0.0
    _zero_method = 'none'
    try:
        manual_in = p_zero_manual_var.get().strip() if p_zero_manual_var else ''
        zs_in     = p_zero_start_var.get().strip()  if p_zero_start_var  else ''
        ze_in     = p_zero_end_var.get().strip()    if p_zero_end_var    else ''

        if manual_in:
            # Manual override takes priority
            p_zero_offset = float(manual_in)
            _zero_method  = f'manual ({p_zero_offset:.6f} MPa)'

        elif zs_in and ze_in:
            # Auto: mean of P_meas over the vacuum window
            zs_hr = float(zs_in); ze_hr = float(ze_in)
            if zs_hr >= ze_hr:
                graphLabel.configure(text='Error: P zero window start must be before end.')
                return
            # Time series aligned with P_MPa (same index as runDF_filtered)
            time_series_tmp = df['Relative.2'].loc[runDF_filtered.index].astype(float) / 60.0
            mask_window = (time_series_tmp >= zs_hr) & (time_series_tmp <= ze_hr)
            p_window = P_MPa_series[mask_window].dropna()
            if len(p_window) < 2:
                graphLabel.configure(text='Warning: P zero window has < 2 points — offset not applied.')
            else:
                p_zero_offset = float(p_window.mean())
                p_zero_sigma  = float(p_window.std())
                _zero_method  = (
                    f'auto-vacuum window {zs_hr:.3f}–{ze_hr:.3f} hr '
                    f'(n={len(p_window)}, mean={p_zero_offset:.6f} MPa, '
                    f'sigma={p_zero_sigma:.4e} MPa)'
                )

        if p_zero_offset != 0.0:
            P_MPa = [v - p_zero_offset if pd.notna(v) else v for v in P_MPa]
            _log_live(f'Pressure zero offset applied: {_zero_method}')
        else:
            _log_live('Pressure zero offset: none applied')

    except Exception as _ze:
        _log_live(f'Warning: P zero offset error — {_ze}. Continuing without offset.')
    # ── End pressure zero offset ─────────────────────────────────────────

    _log(f"Pressure points: {len(P_MPa)}"); P_Pa=[float(p)*1e6 for p in P_MPa if pd.notna(p)]; fileProgress['value'] = 30; window.update_idletasks()

    # Time Processing (Aligned with runDF)
    if 'Relative.2' not in df.columns: graphLabel.configure(text="Error: Time column 'Relative.2' missing."); return
    Time_Minutes = []; Time_Seconds = pd.Series([], dtype=float); Time_Hours = pd.Series([], dtype=float)
    try:
        time_series_full = df['Relative.2']
        Time_Minutes_series = time_series_full.loc[runDF_filtered.index]
        if len(Time_Minutes_series) != len(runDF): graphLabel.configure(text="Error: Time/runDF length mismatch."); return
        Time_Minutes = Time_Minutes_series.tolist()
        Time_Seconds= pd.Series([float(min)*60 for min in Time_Minutes], index=runDF.index)
        Time_Hours= pd.Series([float(min)/60 for min in Time_Minutes], index=runDF.index)
        _log(f"Time points: {len(Time_Minutes)}")
    except Exception as e: graphLabel.configure(text=f"Error processing time: {e}"); return
    if not Time_Minutes: graphLabel.configure(text="Error: No time data after alignment."); return
    fileProgress['value'] = 40; window.update_idletasks()


    # Volume Profile Processing
    try: partList=pd.read_excel(layout_file)
    except Exception as e: graphLabel.configure(text=f"Error reading Layout: {e}"); return
    volumeDF, uid_to_material = getSystemVolumeProfile(partList, mating_table_file, fur_file, hps_file)
    if volumeDF is None: return

    # Material densities (g/cm³) keyed by material string from MLD files
    DENSITY_MAP = {
        "TZM B387 Type 364":      10.22,
        "304SS":                   7.93,
        "Molybdenum":             10.28,
        "Zr":                      6.52,
        "SS 316":                  8.00,
        "TZM B387-19, Type 364":  10.22,
    }

    # --- Capture volume before any correction ---
    _V_before_mL = volumeDF['Total Volume'].sum() / 1000.0

    # --- Furniture mass-based volume correction (from table) ---
    _any_fur = False
    for _uid, _mass_sv in fur_mass_entries.items():
        _mstr = _mass_sv.get().strip()
        if not _mstr: continue
        try: _mass_g = float(_mstr)
        except ValueError: _log(f'Warning: invalid mass for {_uid}: "{_mstr}" — skipped'); continue
        _is_int     = fur_internal_checks.get(_uid, tk.BooleanVar(value=False)).get()
        _col_prefix = 'Internal_' if _is_int else 'External_'
        _mat = uid_to_material.get(_uid)
        if not _mat: _log(f'Warning: no material for UID "{_uid}" — skipped'); continue
        _dens = DENSITY_MAP.get(_mat)
        if _dens is None: _log(f'Warning: no density for "{_mat}" (UID {_uid}) — add to DENSITY_MAP'); continue
        _V_mass_mm3 = (_mass_g / _dens) * 1000.0
        _found = False
        for _col in volumeDF.columns:
            if _col.startswith(_col_prefix) and _col.endswith(f'_{_uid}'):
                _V_cad = float(volumeDF[_col].sum())
                if abs(_V_cad) < 1e-9: _log(f'Warning: CAD vol ~0 for {_uid}'); _found = True; break
                _scale = _V_mass_mm3 / abs(_V_cad)
                volumeDF[_col] = volumeDF[_col] * _scale
                _V_corr = (_V_cad * _scale) / 1000.0  # preserves sign
                _delta  = _V_corr - _V_cad / 1000.0
                _log(f'Furniture: {_uid} ({_mat}, {"int" if _is_int else "ext"}): '
                     f'CAD={_V_cad/1000:.4f} mL → mass={_V_corr:.4f} mL '
                     f'(Δ={_delta:+.5f} mL, scale={_scale:.5f})')
                _found = True; _any_fur = True; break
        if not _found:
            _log(f'Warning: no {_col_prefix}Part_ col for UID "{_uid}" — check MLD file')
    if _any_fur:
        volumeDF['Total Volume'] = volumeDF.filter(like='Part_').fillna(0).sum(axis=1)
        _log('Total Volume recomputed after furniture corrections.')
    _V_after_fur_mL = volumeDF['Total Volume'].sum() / 1000.0

    # --- Chemical species volume (placed uniformly within CRU) ---
    # Densities (g/cm³) from literature / crystallographic data
    CHEMICAL_PROPS = {
        'Li3BN2':  1.85,   # lithium boron nitride (β-phase)
        'Li3N':    1.27,   # lithium nitride
        'Li3AlN2': 2.31,   # lithium aluminum nitride
        'Li3GaN2': 4.10,   # lithium gallium nitride
        'GaN':     6.15,   # gallium nitride (wurtzite)
    }
    _V_after_chem_mL = _V_after_fur_mL
    _chem_sp   = chem_species_var.get() if chem_species_var else 'None'
    _chem_ms   = chem_mass_var.get().strip() if chem_mass_var else ''
    if _chem_sp not in ('None', '') and _chem_ms:
        try:
            _chem_g = float(_chem_ms)
            _chem_dens = (float(chem_density_var.get().strip()) if chem_density_var and chem_density_var.get().strip() else None)\
                         if _chem_sp == 'Custom' else CHEMICAL_PROPS.get(_chem_sp)
            if _chem_dens and _chem_g > 0:
                _V_chem_mm3 = (_chem_g / _chem_dens) * 1000.0
                _cru_col = next((c for c in volumeDF.columns
                                 if c.startswith('Internal_') and 'CRU' in c.upper()), None)
                if _cru_col:
                    _nz = volumeDF[_cru_col][volumeDF[_cru_col] != 0]
                    if len(_nz) > 0:
                        _cru_s = int(_nz.index[0]); _cru_e = int(_nz.index[-1])
                        _n_sl  = _cru_e - _cru_s + 1
                        _vps   = -_V_chem_mm3 / _n_sl
                        volumeDF[f'Chem_{_chem_sp}'] = pd.Series([_vps]*_n_sl, index=range(_cru_s, _cru_e+1))
                        _chem_extra = volumeDF.filter(regex='^Chem_').fillna(0).sum(axis=1)
                        volumeDF['Total Volume'] = volumeDF.filter(like='Part_').fillna(0).sum(axis=1) + _chem_extra
                        _V_after_chem_mL = volumeDF['Total Volume'].sum() / 1000.0
                        _log(f'Chemical {_chem_sp}: {_chem_g:.3f} g, ρ={_chem_dens} g/cm³, '
                             f'V_chem={_V_chem_mm3/1000:.4f} mL (CRU slices {_cru_s}–{_cru_e})')
                    else: _log('Warning: CRU column all-zero — chemical not placed.')
                else: _log('Warning: no CRU Internal column found — chemical not placed.')
            else: _log(f'Warning: density not found for "{_chem_sp}" or mass≤0 — skipped.')
        except (ValueError, TypeError) as _ce:
            _log(f'Warning: chemical volume error: {_ce}')

    # --- Volume summary ---
    _vol_str = f'CAD vol: {_V_before_mL:.3f} mL'
    if _any_fur:
        _vol_str += f'  →  fur-corrected: {_V_after_fur_mL:.3f} mL  (Δ{_V_after_fur_mL-_V_before_mL:+.4f} mL)'
    if _chem_sp not in ('None','') and _chem_ms:
        _vol_str += f'  →  +chem: {_V_after_chem_mL:.3f} mL  (Δ{_V_after_chem_mL-_V_after_fur_mL:+.4f} mL)'
    _log(_vol_str)
    if vol_info_label: vol_info_label.configure(text=_vol_str)

    if 'Total Volume' not in volumeDF or volumeDF['Total Volume'].isna().all():
        graphLabel.configure(text='Error: Total Volume calc failed.'); return
    coarseVol_series = volumeDF['Total Volume']; remainder = len(coarseVol_series) % 100
    if remainder != 0: padding = pd.Series([0]*(100-remainder), index=range(len(coarseVol_series), len(coarseVol_series)+100-remainder)); coarseVol_series=pd.concat([coarseVol_series,padding])
    coarseVol = []; volumeProfile_padded = coarseVol_series.tolist()
    for i in range(int(len(volumeProfile_padded) / 100)): coarseVol.append(sum(volumeProfile_padded[100*i : 100*(i+1)]))
    if not coarseVol: graphLabel.configure(text="Error: Coarse volume calc failed."); return
    coarseVol = [vol / 1e9 for vol in coarseVol]; coarseVol_mL = [v*1e6 for v in coarseVol]
    V_total_m3 = sum(coarseVol)
    
    # Plot Coarse Volume Profile ---
    try:
        # Create an axial position array in mm (1mm steps)
        axial_coords_mm = np.arange(len(coarseVol))
        coarseVol_plot = [v * 1e9 for v in coarseVol]

        fig_vol = go.Figure()
        fig_vol.add_trace(go.Scatter(
            x=axial_coords_mm, 
            y=coarseVol_plot, 
            mode='lines',
            name='Coarse Volume',
            line=dict(color='darkgreen', width=2),
            fill='tozeroy'
        ))

        fig_vol.update_layout(
            title="System Volume Profile (1mm Resolution)",
            xaxis_title="Axial Position (mm)",
            yaxis_title="Volume (mm^3) per 1mm Slice",
            template='plotly_white',
            hovermode='x unified',
            width=1300,
            height=600
        )
        fig_vol.show()

    except Exception as e:
        print(f"Error plotting coarse volume: {e}")
    
    
    _log(f"\nTotal Vol (mL): {volumeDF['Total Volume'].sum()/1000:.3f} (DF), {sum(coarseVol_mL):.3f} (Coarse), Total Vol (m^3): {V_total_m3:.3e}")
    
    
    
    # --- Material property maps ---
    # Thermal expansion coefficients (m/m/K) keyed by material string from MLD files
    CTE_MAP = {
        "TZM B387 Type 364":     6.1e-6,
        "304SS":                 18e-6,
        "Molybdenum":            5.5e-6,
        "Zr":                    7e-6,
        "SS 316":                18e-6,
        "TZM B387-19, Type 364": 6.1e-6, 
    }

    T_ROOM_K = 295.15  # 22°C reference (temperature at which part profiles were measured)
    cte_sensitivity = np.zeros(len(coarseVol))
    for col in volumeDF.columns:
        if not (col.startswith("External_Part_") or col.startswith("Internal_Part_")):
            continue
        parts_split = col.split('_', 3)
        if len(parts_split) < 4:
            continue
        uid = parts_split[3]
        material = uid_to_material.get(uid)
        if not material:
            continue
        cte = CTE_MAP.get(material)
        if cte is None:
            continue
        part_vals = volumeDF[col].fillna(0).values
        remainder = len(part_vals) % 100
        if remainder:
            part_vals = np.concatenate([part_vals, np.zeros(100 - remainder)])
        part_coarse_m3 = part_vals.reshape(-1, 100).sum(axis=1) / 1e9  # mm³ -> m³
        n_contrib = min(500, len(part_coarse_m3), len(cte_sensitivity))
        cte_sensitivity[:n_contrib] += cte * part_coarse_m3[:n_contrib]
    print(f"Thermal expansion sensitivity built: {np.count_nonzero(cte_sensitivity)} nonzero 1mm positions in 0-500mm range")
    
    fileProgress['value'] = 50; window.update_idletasks()

    # Temperature Profile Setup (Conditional)
    lookupTable = None; central_tc_col = None; z_min_cal = None; z_max_cal = None
    if not use_interpolation:
        _log("Using Temperature Profile CSV...")
        try: lookupTable = pd.read_csv(temp_profile_file, index_col=0)
        except Exception as e: graphLabel.configure(text=f"Error reading Temp Profile: {e}"); return
        try: lookupTable.columns = [str(int(float(c))) for c in lookupTable.columns]
        except ValueError: graphLabel.configure(text="Error: Temp Profile columns not numbers."); return
        try:
            if len(lookupTable.columns) < 1: raise IndexError("Temp Profile has no position columns.")
            z_min_cal = int(lookupTable.columns[0]); z_max_cal = int(lookupTable.columns[-1])
            _log(f"Temp profile range: {z_min_cal}mm to {z_max_cal}mm")
        except (IndexError, ValueError) as e: graphLabel.configure(text=f"Error reading Temp Profile range: {e}"); return
        central_tc_row = TC_df[TC_df['Shorthand Tag'].str.contains('157', na=False)]
        if central_tc_row.empty: graphLabel.configure(text="Error: No TC with '157' in tag found."); return
        central_tc_col = central_tc_row.iloc[0]['NI LV Channel']
        _log(f"Central TC: {central_tc_row.iloc[0]['Shorthand Tag']} → channel {central_tc_col}")
    else:
        _log("Using Linear Interpolation for Temperature Profile...")
        if TC_positions.empty: graphLabel.configure(text="Error: No TC positions for interpolation."); return
        z_min_cal = int(TC_positions.min()); z_max_cal = int(TC_positions.max())
        _log(f"Interpolation range: {z_min_cal}mm to {z_max_cal}mm")
    fileProgress['value'] = 60; window.update_idletasks()

    # Main Calculation Loop
    graphProgress['value'] = 0; window.update_idletasks()
    n=[]; avgTempList = []; full_temp_profiles_K = []; n_error_list = [] # <-- NEW: Init error list
    R = 8.3145

    # Load Z (compressibility factor) lookup table for selected gas
    from scipy.interpolate import RegularGridInterpolator as _RGI
    _Z_TABLE_DIR = CANON_MLD_DIR
    _gas_file_map = {'Nitrogen': 'N2_Z.npz'}
    _gas_name = gas_species_var.get() if gas_species_var else 'Nitrogen'
    _gas_stem = _gas_file_map.get(_gas_name, 'N2_Z.npz')
    _z_interp = None; _z_T_min = 250.0; _z_T_max = 2000.0; _z_P_min = 0.1; _z_P_max = 50.0
    try:
        _zd = np.load(os.path.join(_Z_TABLE_DIR, _gas_stem))
        _z_interp = _RGI((_zd['T_K'], _zd['P_MPa']), _zd['Z'], bounds_error=False, fill_value=None)
        _z_T_min, _z_T_max = float(_zd['T_K'].min()), float(_zd['T_K'].max())
        _z_P_min, _z_P_max = float(_zd['P_MPa'].min()), float(_zd['P_MPa'].max())
        _log(f"Z table loaded: {_gas_name}")
    except Exception as _ze:
        _log(f"Warning: Z table not found ({_ze}). Using ideal gas Z=1.")

    required_tc_channels = TC_df['NI LV Channel'].tolist()
    runTempsDF = runDF[required_tc_channels]
    if runTempsDF.empty: graphLabel.configure(text="Error: No temperature data."); return

    # --- Pre-compute interpolation arrays (used by interpolateTempProfile) ---
    if use_interpolation:
        _sorted_tc_idx   = np.argsort(TC_positions.values.astype(float))
        _x_tc_sorted     = TC_positions.values.astype(float)[_sorted_tc_idx]
        _x_target_interp = np.arange(int(_x_tc_sorted[0]), int(_x_tc_sorted[-1]) + 1)
        _log(f'Interp pre-computation: {len(_x_tc_sorted)} TCs, '
             f'range {int(_x_tc_sorted[0])}–{int(_x_tc_sorted[-1])} mm '
             f'({len(_x_target_interp)} target points)')
    else:
        _sorted_tc_idx = _x_tc_sorted = _x_target_interp = None

    _log("Starting main calculation loop...")
    # Compute at every calc_step-th row; interp fills the rest
    calc_indices = list(range(0, len(runDF), calc_step))
    # Always include the last index so the full time range is covered
    if calc_indices[-1] != len(runDF) - 1:
        calc_indices.append(len(runDF) - 1)
    all_indices = list(range(len(runDF)))

    n_sparse = [];  avg_sparse = []; err_sparse = []; prof_sparse = []; t_sparse = []; dv_sparse = []
    sample_T_sparse = []   # temperature (degC) at user-specified sample z-position

    _sample_z_mm = None
    if sample_pos_var:
        try:
            _sz = sample_pos_var.get().strip()
            _sample_z_mm = int(float(_sz)) if _sz else None
        except (ValueError, AttributeError):
            _sample_z_mm = None
    _profile_start_z = z_min_cal if z_min_cal is not None else 0

    for i in calc_indices:
        t_sparse.append(i)
        try:
            temps = runTempsDF.iloc[i].tolist() # Already float
            if use_interpolation:
                tempProfile_raw = interpolateTempProfile(temps, TC_positions)
            else:
                central_val = float(runTempsDF[central_tc_col].iloc[i])
                if pd.isna(central_val): print(f"Warn: Central TC NaN at step {i}."); avg_sparse.append(np.nan); n_sparse.append(np.nan); prof_sparse.append([]); err_sparse.append(np.nan); dv_sparse.append(np.nan); sample_T_sparse.append(np.nan); continue
                row_idx = min(lookupTable.index.searchsorted(central_val), len(lookupTable) - 1)
                tempProfile_raw = lookupTable.iloc[row_idx].tolist()
            if not tempProfile_raw: print(f"Warn: Temp profile empty step {i}."); avg_sparse.append(np.nan); n_sparse.append(np.nan); prof_sparse.append([]); err_sparse.append(np.nan); dv_sparse.append(np.nan); sample_T_sparse.append(np.nan); continue # Append NaN to all
            if len(tempProfile_raw) > 0: avg_sparse.append(sum(tempProfile_raw)/len(tempProfile_raw))
            else: avg_sparse.append(np.nan)
            if _sample_z_mm is not None and tempProfile_raw:
                _si = max(0, min(_sample_z_mm - _profile_start_z, len(tempProfile_raw) - 1))
                sample_T_sparse.append(float(tempProfile_raw[_si]))
            else:
                sample_T_sparse.append(np.nan)
            tempProfile = [temp + 273.15 for temp in tempProfile_raw] # To Kelvin

            ambient_val = runDF["CV1-TC-Ambient"].iloc[i] # Already float/NaN
            ambient_temp = ambient_val + 273.15 if pd.notna(ambient_val) else 298.15

            tempProfile_cutoff = tempProfile[:]
            if z_temp_cutoff_mm is not None:
                profile_start_z = 0 if not use_interpolation else z_min_cal
                # z_temp_cutoff_mm is in V-coordinates.  When z_offset_mm > 0,
                # T is shifted forward by z_offset_mm relative to V, so the
                # cutoff in the T-array is at (z_temp_cutoff_mm + z_offset_mm).
                # For z_offset_mm <= 0 it is V that is trimmed, so no adjustment
                # to the T-array cutoff is needed.
                _zoff_corr = z_offset_mm if z_offset_mm > 0 else 0
                cutoff_index = z_temp_cutoff_mm + _zoff_corr - profile_start_z
                if cutoff_index < 0: cutoff_index = 0
                if cutoff_index < len(tempProfile_cutoff): tempProfile_cutoff = tempProfile_cutoff[:cutoff_index]
                elif cutoff_index > len(tempProfile_cutoff):
                    if tempProfile_cutoff: fill_needed = cutoff_index - len(tempProfile_cutoff); tempProfile_cutoff.extend([tempProfile_cutoff[-1]] * fill_needed)

            if not tempProfile_cutoff: last_cal_temp = ambient_temp
            else: last_cal_temp = float(tempProfile_cutoff[-1])
            temp_gradient = np.linspace(last_cal_temp, ambient_temp, 50); tempProfile_cutoff.extend(temp_gradient)
            _target_len = len(coarseVol) + z_offset_mm
            if _target_len > len(tempProfile_cutoff): tempProfile_cutoff += [ambient_temp] * (_target_len - len(tempProfile_cutoff))
            prof_sparse.append(tempProfile_cutoff[:])

            V_aligned = coarseVol
            T_aligned = tempProfile_cutoff[z_offset_mm:z_offset_mm + len(coarseVol)]
            if len(T_aligned) == 0: n_sparse.append(np.nan); err_sparse.append(np.nan); dv_sparse.append(np.nan); sample_T_sparse.append(np.nan); continue

            V_base = np.array(V_aligned); T_arr = np.array(T_aligned)
            if apply_smoothing_var and apply_smoothing_var.get() and len(T_arr) > 4:
                from scipy.signal import savgol_filter as _sgf
                _win = min(201, len(T_arr))
                if _win % 2 == 0: _win -= 1
                if _win >= 5:
                    T_arr = _sgf(T_arr, window_length=_win, polyorder=2)
            # Apply thermal expansion for axial positions 0-500mm
            _n_vol = len(coarseVol)
            cte_end = min(_n_vol, len(cte_sensitivity))
            cte_slice = cte_sensitivity[:cte_end]
            if len(cte_slice) < _n_vol:
                cte_slice = np.concatenate([cte_slice, np.zeros(_n_vol - len(cte_slice))])
            n_expand = min(500, _n_vol)
            V_arr = V_base.copy()
            V_arr[:n_expand] += 3.0 * cte_slice[:n_expand] * (T_arr[:n_expand] - T_ROOM_K)
            if i >= len(P_Pa): n_sparse.append(np.nan); err_sparse.append(np.nan); dv_sparse.append(np.nan); continue
            P = P_Pa[i]
            if np.any(T_arr <= 0): T_arr[T_arr <= 0] = 1e-6
            if np.isnan(P) or np.isnan(V_arr).any() or np.isnan(T_arr).any(): n_sparse.append(np.nan); err_sparse.append(np.nan); dv_sparse.append(np.nan); continue
            
            # --- Mole Calculation ---
            if _z_interp is not None:
                _P_clamp = np.clip(P / 1e6, _z_P_min, _z_P_max)
                _T_clamp = np.clip(T_arr, _z_T_min, _z_T_max)
                Z_arr = _z_interp(np.column_stack([_T_clamp, np.full(len(T_arr), _P_clamp)]))
                Z_arr = np.clip(Z_arr, 0.5, 2.0)
            else:
                Z_arr = np.ones(len(T_arr))
            nList = (P * V_arr) / (Z_arr * R * T_arr)
            n_total_step = np.sum(nList)
            n_sparse.append(n_total_step * 1000.0)
            
            # --- NEW: Uncertainty Calculation ---
            sigma_P = P * sigma_p_percent
            sigma_V_arr = V_arr * sigma_v_percent
            # Simple T uncertainty model: constant value
            # (A better model would increase error away from TCs if interpolating)
            sigma_T_arr = np.full_like(T_arr, sigma_t_base_K) 
            
            term_P_sq = ((n_total_step / P)**2) * (sigma_P**2)
            term_V_sq_sum = np.sum( (P / (Z_arr * R * T_arr))**2 * (sigma_V_arr**2) )
            term_T_sq_sum = np.sum( (P * V_arr / (Z_arr * R * T_arr**2))**2 * (sigma_T_arr**2) )
            
            total_variance = term_P_sq + term_V_sq_sum + term_T_sq_sum
            sigma_n = np.sqrt(total_variance)
            err_sparse.append(sigma_n * 1000.0)
            dv_sparse.append((np.sum(V_arr) - np.sum(V_base)) / V_total_m3 * 100.0)  # % of base volume
            # --- END NEW ---

            if i%1000 == 0:
                #print(f"Step {i}, Time: {Time_Hours.iloc[i]:.2f} hr, n: {n_total_step:.3e} ± {sigma_n:.2e} mol")
                graphProgress['value'] = int(100*i/len(runDF)); window.update_idletasks()
        except Exception as e: print(f"Error loop step {i}: {e}"); graphLabel.configure(text=f"Error step {i}: {e}"); n_sparse.append(np.nan); avg_sparse.append(np.nan); prof_sparse.append([]); err_sparse.append(np.nan); dv_sparse.append(np.nan); sample_T_sparse.append(np.nan)
    _log("Finished main calculation loop.")

    # ── Interpolate sparse results back to full resolution ──────────────
    _log('Interpolating sparse results to full resolution...')
    if len(t_sparse) >= 2:
        t_sp = np.array(t_sparse, dtype=float)
        n_sp  = np.array(n_sparse,   dtype=float)
        err_sp = np.array(err_sparse, dtype=float)
        avg_sp = np.array(avg_sparse, dtype=float)
        all_t  = np.array(all_indices, dtype=float)
        n           = list(np.interp(all_t, t_sp, n_sp))
        n_error_list = list(np.interp(all_t, t_sp, err_sp))
        avgTempList  = list(np.interp(all_t, t_sp, avg_sp))
        sample_temp_list = list(np.interp(all_t, t_sp, np.array(sample_T_sparse, dtype=float)))
        dv_sp = np.array(dv_sparse, dtype=float)
        delta_V_interp = list(np.interp(all_t, t_sp, dv_sp))
        # For full_temp_profiles_K: repeat nearest computed profile for gaps
        prof_map = {idx: prof for idx, prof in zip(calc_indices, prof_sparse)}
        full_temp_profiles_K = []
        last_prof = []
        for idx in all_indices:
            if idx in prof_map:
                last_prof = prof_map[idx]
            full_temp_profiles_K.append(last_prof)
    else:
        # Only one point computed — fill everything with it
        n            = n_sparse * len(all_indices)
        n_error_list = err_sparse * len(all_indices)
        avgTempList  = avg_sparse * len(all_indices)
        sample_temp_list = sample_T_sparse * len(all_indices)
        delta_V_interp = dv_sparse * len(all_indices)
        full_temp_profiles_K = [prof_sparse[0] if prof_sparse else []] * len(all_indices)
    _log(f'Interpolation complete. Total points: {len(n)}')

    

    # P_calc deferred — run via 'Calculate P_calc' button after plot
    P_calc_MPa_list = [np.nan] * len(runDF)

    # Show Moles Plot
    try: n_array=np.array(n); time_h_array=np.array(Time_Hours); mask_n_plot=~np.isnan(n_array); fig_n=go.Figure(); fig_n.add_trace(go.Scatter(x=time_h_array[mask_n_plot], y=n_array[mask_n_plot], name='Moles')); fig_n.update_layout(title="Moles vs Time", xaxis_title="Time (Hr)"); fig_n.show()
    except Exception as e: print(f"Plotly plot error: {e}")

    # Prepare Final Data
    rawData, baseline, baselineRange, baselineUnit, movingAvg, movingAvgRange, movingAvgUnit, tempRange, pressureRange, timeRange, nRange, dn_dtRange = (None,)*12
    final_expected_len = len(runDF)
    n_final = n + [np.nan] * (final_expected_len - len(n)); n_error_final = n_error_list + [np.nan] * (final_expected_len - len(n_error_list))
    delta_V_final = delta_V_interp + [np.nan] * (final_expected_len - len(delta_V_interp)) # <-- Pad errors
    avgTempList_final = avgTempList + [np.nan] * (final_expected_len - len(avgTempList))
    sample_temp_final = sample_temp_list + [np.nan] * (final_expected_len - len(sample_temp_list))
    P_MPa_final = P_MPa + [np.nan] * (final_expected_len - len(P_MPa)); P_calc_MPa_final = P_calc_MPa_list + [np.nan] * (final_expected_len - len(P_calc_MPa_list))
    Time_Seconds_final = Time_Seconds.tolist() + [np.nan] * (final_expected_len - len(Time_Seconds)); Time_Minutes_final = Time_Minutes + [np.nan] * (final_expected_len - len(Time_Minutes)); Time_Hours_final = Time_Hours.tolist() + [np.nan] * (final_expected_len - len(Time_Hours))
    control_tc_channel = "N/A"; control_temp_final = [np.nan] * final_expected_len
    if TC_df is not None and 'IO Type' in TC_df.columns:
        control_row = TC_df[TC_df['IO Type'].astype(str).str.strip().str.lower() == 'control']
        if not control_row.empty:
            control_tc_channel = control_row['NI LV Channel'].iloc[0]
            if runDF is not None and control_tc_channel in runDF.columns:
                control_data_raw = runDF[control_tc_channel]; control_data_numeric = pd.to_numeric(control_data_raw, errors='coerce').tolist(); control_temp_final = control_data_numeric + [np.nan] * (final_expected_len - len(control_data_numeric))
    plot_df = pd.DataFrame({'Time_Hours': Time_Hours_final,'Moles_mmol': n_final,'Moles_Uncertainty_mmol': n_error_final, 'Pressure_Meas_MPa': P_MPa_final,'Pressure_Calc_MPa': P_calc_MPa_final,'Temp_Avg_C': avgTempList_final,'Temp_Control_C': control_temp_final,'Control_TC_Channel': control_tc_channel,'Delta_V_pct': delta_V_final,'Temp_Sample_C': sample_temp_final}) # <-- Added Uncertainty
    if not (len(Time_Hours_final) == len(n_final) == len(P_MPa_final) == len(avgTempList_final) == len(P_calc_MPa_final) == len(n_error_final)): # <-- Added error length check
         print("Error: Length mismatch FINAL."); graphLabel.configure(text="Error: Final length mismatch."); return
    runData = [Time_Hours_final, Time_Minutes_final, Time_Seconds_final, n_final, P_MPa_final, avgTempList_final, runDF, TC_df, lookupTable, rawData, baseline, baselineRange, baselineUnit, baselineEdited, movingAvg, movingAvgRange, movingAvgUnit, df, data_filename, tempRange, pressureRange, timeRange, nRange, dn_dtRange, P_calc_MPa_final, full_temp_profiles_K, coarseVol, plot_df, n_error_final, delta_V_final] # item 29: thermal ΔV per timestep (% of base volume)

    # Call moleGraph

    try: moleGraph(runData)
    except Exception as e: graphLabel.configure(text=f"Error plotting: {e}"); print(f"Error moleGraph: {e}"); import traceback; traceback.print_exc(); return
    fileProgress['value'] = 100; graphProgress['value'] = 100

    # P_calc is run separately via 'Calculate P_calc' button
    if pcalc_button: pcalc_button.configure(state='normal')

    # ── Auto-save info file ────────────────────────────────────────────
    from datetime import datetime
    _ts = datetime.now().strftime('%y%m%d_%H%M%S')
    _safe_id = run_id if run_id else 'UnknownRun'
    if output_dir:
        _info_path = os.path.join(output_dir, f'{_safe_id}_{_ts}_Info.txt')
        try:
            with open(_info_path, 'w', encoding='utf-8') as _f:
                _f.write(f'MolCalc Run Info\n{"="*60}\n')
                _f.write('\n'.join(info_log))
            _log_live(f'Info saved: {os.path.basename(_info_path)}')
        except Exception as _e:
            print(f'Warning: could not save info file: {_e}')

    # ── Auto-save HTML plot ───────────────────────────────────────────────
    if output_dir:
        try:
            export_html_plot()
        except Exception as _e:
            print(f'Warning: auto HTML export failed: {_e}')

    graphLabel.configure(text="Graph Generated Successfully")
    if exportPlotButton: exportPlotButton.configure(state='normal')
    if exportHtmlButton: exportHtmlButton.configure(state='normal')
    if exportTempButton: exportTempButton.configure(state='normal')
    if tempViewButton: tempViewButton.configure(state='normal')
    if texpansion_button: texpansion_button.configure(state='normal')
    if calculateFitButton: calculateFitButton.configure(state='normal')
    if dn_dt_button: dn_dt_button.configure(state='normal')
    if save_plot_button: save_plot_button.configure(state='normal')
    window.update_idletasks()
