# --- Temperature Profile Viewer Functions ---
def open_temp_viewer():
    global runData, temp_viewer_window, graphLabel
    if not runData or len(runData) < 27:
        graphLabel.configure(text="Error: Run 'Generate Graph' first."); return
    if runData[25] is None or runData[26] is None:
        graphLabel.configure(text="Error: Temp profiles N/A."); return
    if temp_viewer_window and temp_viewer_window.winfo_exists():
        temp_viewer_window.lift(); return

    time_hours_list = runData[0]      # list/Series of float hours, one per data row
    full_profiles   = runData[25]     # list of 1-mm T arrays (K), len == len(runDF)
    coarse_vol      = runData[26]     # list of floats (m³), 1-mm bins, AC coords

    # coarseVol is already 1-mm resolution (each bin = 100 x 0.01 mm volumeDF rows).
    # x_V_mm[j] = j mm in AC coordinates.
    vol_arr = np.array(coarse_vol, dtype=float)   # m³ per 1-mm slice
    x_V_mm  = np.arange(len(vol_arr), dtype=float)

    # Recover z_min_cal (start of T-profile in AC mm)
    _z_min_cal = 0
    try:
        _lut = runData[8]
        if _lut is not None and hasattr(_lut, 'columns') and len(_lut.columns) > 1:
            _z_min_cal = int(float(_lut.columns[1]))
        elif runData[7] is not None and 'X Position' in runData[7].columns:
            _tc_pos = pd.to_numeric(runData[7]['X Position'], errors='coerce').dropna()
            if not _tc_pos.empty:
                _z_min_cal = int(_tc_pos.min())
    except Exception:
        _z_min_cal = 0

    # Sample position (absolute AC mm) from GUI
    _sample_z_abs = None
    if sample_pos_var:
        try:
            _sz = sample_pos_var.get().strip()
            _sample_z_abs = float(_sz) if _sz else None
        except Exception:
            _sample_z_abs = None

    # Read z_offset so viewer shows the same T/V alignment used in the calculation
    _z_off = 0
    try:
        _zos = z_offset_var.get().strip()
        _z_off = int(float(_zos)) if _zos else 0
    except Exception:
        _z_off = 0

    t_max_hr  = max(time_hours_list) if time_hours_list else 0
    n_steps   = len(full_profiles)
    time_arr  = np.array(time_hours_list, dtype=float)

    temp_viewer_window = tk.Toplevel(window)
    temp_viewer_window.title("Temperature Profile Viewer")
    temp_viewer_window.geometry("860x640")

    # ── Control bar ────────────────────────────────────────────────────────
    ctrl = tk.Frame(temp_viewer_window); ctrl.pack(side=tk.TOP, fill=tk.X, pady=4, padx=6)

    tk.Label(ctrl, text=f'Time (h)  [0 – {t_max_hr:.3f}]:').pack(side=tk.LEFT, padx=(0,4))
    time_entry_var = tk.StringVar(value='0')
    time_entry = tk.Entry(ctrl, textvariable=time_entry_var, width=9)
    time_entry.pack(side=tk.LEFT, padx=(0,6))

    slider_var = tk.IntVar(value=0)
    _slide = ttk.Scale(ctrl, from_=0, to=max(n_steps-1,1), orient=tk.HORIZONTAL,
                       variable=slider_var, length=300)
    _slide.pack(side=tk.LEFT, padx=(0,8))

    idx_label = tk.Label(ctrl, text=f'Row index: 0 / {n_steps-1}', width=22, anchor=W)
    idx_label.pack(side=tk.LEFT)

    # ── Plot area ──────────────────────────────────────────────────────────
    plot_frame = tk.Frame(temp_viewer_window); plot_frame.pack(fill=tk.BOTH, expand=True)
    plt.rcParams.update({
        'font.family':           'DejaVu Sans',
        'font.size':             13,
        'axes.linewidth':        1.4,
        'axes.titlesize':        14,
        'axes.labelsize':        14,
        'xtick.labelsize':       12,
        'ytick.labelsize':       12,
        'xtick.direction':       'in',
        'ytick.direction':       'in',
        'xtick.minor.visible':   True,
        'ytick.minor.visible':   True,
        'xtick.major.size':      6,
        'xtick.minor.size':      3,
        'ytick.major.size':      6,
        'ytick.minor.size':      3,
        'xtick.top':             True,
        'ytick.right':           True,
        'legend.fontsize':       11,
        'legend.framealpha':     0.95,
        'legend.edgecolor':      '0.6',
        'lines.linewidth':       1.8,
        'figure.facecolor':      'white',
        'axes.facecolor':        'white',
        'axes.grid':             False,
        'axes.spines.top':       True,
        'axes.spines.right':     True,
    })
    fig_tv  = plt.figure(figsize=(8, 8))
    can_tv  = FigureCanvasTkAgg(fig_tv, master=plot_frame)
    tb_tv   = NavigationToolbar2Tk(can_tv, plot_frame)
    tb_tv.update(); tb_tv.pack(side=tk.BOTTOM, fill=tk.X)
    can_tv.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    # ── Core plot function ─────────────────────────────────────────────────
    def _draw(idx):
        idx = int(np.clip(idx, 0, n_steps-1))
        _lw = float(line_thickness_var.get()) if line_thickness_var else 1.8
        profile_K = full_profiles[idx]
        t_hr      = float(time_arr[idx]) if idx < len(time_arr) else float('nan')
        idx_label.configure(text=f'Row index: {idx} / {n_steps-1}')
        time_entry_var.set(f'{t_hr:.4f}')
        slider_var.set(idx)

        if not profile_K:
            return

        # T profile stays fixed at its calibrated AC coordinates.
        # V profile shifts by z_off so the user can see how the alignment moves.
        #   z_off > 0 → V shifts right (hot-zone moves toward sample)
        #   z_off < 0 → V shifts left
        T_use   = np.array(profile_K, dtype=float)
        if apply_smoothing_var and apply_smoothing_var.get() and len(T_use) > 4:
            from scipy.signal import savgol_filter as _sgf
            _win = min(201, len(T_use))
            if _win % 2 == 0: _win -= 1
            if _win >= 5:
                T_use = _sgf(T_use, window_length=_win, polyorder=2)
        x_T_mm  = _z_min_cal + np.arange(len(T_use), dtype=float)

        x_V_all = _z_off + np.arange(len(vol_arr), dtype=float)  # shifted V x-axis
        v_all   = vol_arr * 1e6                                    # m³/mm → mL/mm

        # Only plot the V range that overlaps with T for a clean comparison
        x_lo = max(x_T_mm[0],  x_V_all[0])
        x_hi = min(x_T_mm[-1], x_V_all[-1])
        if x_lo < x_hi:
            v_mask   = (x_V_all >= x_lo) & (x_V_all <= x_hi)
            x_V_plot = x_V_all[v_mask]
            v_plot   = v_all[v_mask]
        else:
            x_V_plot = x_V_all
            v_plot   = v_all

        fig_tv.clear()
        axT = fig_tv.add_subplot(111)
        axV = axT.twinx()

        pT, = axT.plot(x_T_mm, T_use,
                       color='steelblue', lw=_lw, label='T (K)')
        axV.fill_between(x_V_plot, v_plot, color='tomato', alpha=0.15)
        pV_line, = axV.plot(x_V_plot, v_plot,
                            color='tomato', lw=_lw, linestyle='--', alpha=0.80,
                            label='V (mL / 1-mm slice)')

        # Sample position vertical line
        _handles = [pT, pV_line]
        _labels  = ['T (K)', 'V (mL / 1-mm slice)']
        if _sample_z_abs is not None:
            _vl = axT.axvline(_sample_z_abs, color='#e6550d', lw=_lw,
                              linestyle=':', label=f'Sample @ {_sample_z_abs:.0f} mm')
            _handles.append(_vl)
            _labels.append(f'Sample @ {_sample_z_abs:.0f} mm')

        axT.set_xlabel('Axial Position (mm, AC coordinates)', labelpad=6)
        axT.set_ylabel('Temperature (K)', color='steelblue', labelpad=4)
        axT.tick_params(axis='x', direction='in', which='both')
        axT.tick_params(axis='y', labelcolor='steelblue', direction='in', which='both')
        axT.yaxis.set_tick_params(which='both', direction='in')
        _t_lo, _t_hi = axT.get_ylim()
        if _t_hi - _t_lo < 100:
            axT.set_ylim(_t_lo - 10, _t_lo + 90)
        axV.set_ylabel('Volume (mL / 1-mm slice)', color='tomato', labelpad=4)
        axV.tick_params(axis='y', labelcolor='tomato', direction='in', which='both')
        axV.spines['right'].set_edgecolor('tomato')
        _samp_info = f'  |  Sample @ {_sample_z_abs:.0f} mm' if _sample_z_abs is not None else ''
        _zoff_info = f'  |  z_off = {_z_off} mm' if _z_off != 0 else ''
        axT.set_title(
            f'T & V Profiles  |  t = {t_hr:.4f} h  |  z_min_cal = {_z_min_cal} mm{_zoff_info}{_samp_info}',
            fontsize=9)
        fig_tv.legend(handles=_handles, labels=_labels,
                      loc='upper left',
                      bbox_to_anchor=(0.76, 0.92),
                      bbox_transform=fig_tv.transFigure,
                      framealpha=0.95, edgecolor='0.6',
                      fontsize=11, borderaxespad=0,
                      handlelength=2.0, labelspacing=0.6)
        fig_tv.subplots_adjust(left=0.10, right=0.78, top=0.93, bottom=0.10)
        can_tv.draw()

    # ── Event handlers ─────────────────────────────────────────────────────
    def _on_time_entry(event=None):
        try:
            t_req = float(time_entry_var.get())
        except ValueError:
            return
        idx = int(np.argmin(np.abs(time_arr - t_req)))
        _draw(idx)

    def _on_slider(val):
        _draw(int(float(val)))

    time_entry.bind('<Return>', _on_time_entry)
    time_entry.bind('<FocusOut>', _on_time_entry)
    _slide.configure(command=_on_slider)

    tk.Button(ctrl, text='Export HTML',
              command=lambda: export_temp_profile_html(
                  full_profiles, coarse_vol, time_arr, _z_min_cal, _z_off, _sample_z_abs),
              width=12).pack(side=tk.LEFT, padx=(12, 0))

    _draw(0)


# --- Export Temperature Profile HTML ---
def export_temp_profile_html(full_profiles, coarse_vol, time_arr,
                              z_min_cal=0, z_off=0, sample_z_abs=None):
    """
    Export an interactive Plotly HTML showing T(z) and V(z) at every sampled
    time step — matching the GUI viewer exactly:
      - T stays fixed at z_min_cal + j AC mm
      - V shifts by z_off mm
      - Sample position shown as vertical line if set
      - Slider only (no play/pause)
    """
    import plotly.graph_objects as go
    from datetime import datetime

    global run_id, output_dir, graphLabel

    if not full_profiles or time_arr is None or len(time_arr) == 0:
        graphLabel.configure(text='Error: no profile data to export.'); return

    MAX_FRAMES = 500
    n_total = len(full_profiles)
    step    = max(1, n_total // MAX_FRAMES)
    indices = list(range(0, n_total, step))
    if indices[-1] != n_total - 1:
        indices.append(n_total - 1)
    print(f'Temp HTML export: {len(indices)} frames from {n_total} steps (step={step})')

    # coarse_vol is 1-mm resolution (m³/mm); V shifts by z_off, T fixed at z_min_cal
    vol_arr = np.array(coarse_vol, dtype=float)
    x_V_all = z_off + np.arange(len(vol_arr), dtype=float)

    # Global axis ranges
    all_T = [float(v) for i in indices for v in (full_profiles[i] or [])]
    T_min = float(np.nanmin(all_T)) if all_T else 0
    T_max = float(np.nanmax(all_T)) if all_T else 1
    V_min = float(np.nanmin(vol_arr * 1e6))
    V_max = float(np.nanmax(vol_arr * 1e6))
    T_pad = (T_max - T_min) * 0.05 or 1
    V_pad = (V_max - V_min) * 0.05 or 1e-10

    def _frame_traces(idx):
        prof  = full_profiles[idx] or []
        t_hr  = float(time_arr[idx])
        x_T   = (z_min_cal + np.arange(len(prof), dtype=float)).tolist()

        # Overlap region
        x_lo = max(x_T[0]  if x_T  else 0, float(x_V_all[0]))
        x_hi = min(x_T[-1] if x_T  else 0, float(x_V_all[-1]))
        if x_lo < x_hi:
            v_mask   = (x_V_all >= x_lo) & (x_V_all <= x_hi)
            x_V_plot = x_V_all[v_mask].tolist()
            v_plot   = (vol_arr[v_mask] * 1e6).tolist()
        else:
            x_V_plot = x_V_all.tolist()
            v_plot   = (vol_arr * 1e6).tolist()

        traces = [
            go.Scatter(x=x_T, y=[float(v) for v in prof],
                       mode='lines', name='T (K)', yaxis='y1',
                       line=dict(color='steelblue', width=1.5)),
            go.Scatter(x=x_V_plot, y=v_plot,
                       mode='lines', name='V (mL/mm)', yaxis='y2',
                       line=dict(color='tomato', width=1.1, dash='dash'),
                       fill='tozeroy', fillcolor='rgba(255,99,71,0.12)'),
        ]
        if sample_z_abs is not None:
            traces.append(go.Scatter(
                x=[sample_z_abs, sample_z_abs],
                y=[T_min - T_pad, T_max + T_pad],
                mode='lines', name=f'Sample @ {sample_z_abs:.0f} mm',
                yaxis='y1',
                line=dict(color='#e6550d', width=1.8, dash='dot'),
            ))
        return traces, f'{t_hr:.4f}'

    # Build frames
    frames = []
    slider_steps = []
    for fi, idx in enumerate(indices):
        traces, frame_name = _frame_traces(idx)
        frames.append(go.Frame(name=frame_name, data=traces))
        slider_steps.append(dict(
            args=[[frame_name],
                  dict(frame=dict(duration=0, redraw=True),
                       mode='immediate',
                       transition=dict(duration=0))],
            label=f'{float(time_arr[idx]):.3f}',
            method='animate'
        ))

    init_traces, _ = _frame_traces(indices[0])
    fig = go.Figure(data=init_traces, frames=frames)

    zoff_str   = f'z_off = {z_off} mm' if z_off != 0 else 'z_off = 0'
    samp_str   = f'  |  Sample @ {sample_z_abs:.0f} mm' if sample_z_abs is not None else ''
    fig.update_layout(
        title=dict(
            text=f'Temperature Profile — {run_id or ""}  |  z_min_cal = {z_min_cal} mm'
                 f'  |  {zoff_str}{samp_str}',
            font=dict(size=14)),
        xaxis=dict(title='Axial Position (mm, AC coordinates)', domain=[0, 0.76],
                   showline=True, linewidth=1.2, linecolor='black',
                   mirror=False, ticks='inside',
                   showgrid=False),
        yaxis=dict(
            title=dict(text='Temperature (K)', font=dict(color='steelblue')),
            tickfont=dict(color='steelblue'),
            showline=True, linewidth=1.2, linecolor='steelblue', ticks='inside',
            range=[T_min - T_pad, T_max + T_pad]
        ),
        yaxis2=dict(
            title=dict(text='Volume (mL / 1-mm slice)', font=dict(color='tomato')),
            tickfont=dict(color='tomato'),
            anchor='x', overlaying='y', side='right',
            showline=True, linewidth=1.2, linecolor='tomato', ticks='inside',
            range=[V_min - V_pad, V_max + V_pad]
        ),
        legend=dict(x=1.04, y=1.0, xanchor='left', yanchor='top',
                    bgcolor='rgba(255,255,255,0.95)',
                    bordercolor='#aaa', borderwidth=1, font=dict(size=13)),
        font=dict(family='Arial', size=13),
        template='simple_white',
        plot_bgcolor='white', paper_bgcolor='white',
        autosize=True, height=800,
        margin=dict(l=60, r=200, t=70, b=80),
        sliders=[dict(
            active=0,
            currentvalue=dict(prefix='Time: ', suffix=' h',
                              font=dict(size=13), xanchor='center'),
            pad=dict(t=50, b=10),
            steps=slider_steps,
            x=0.0, len=1.0
        )]
    )

    ts      = datetime.now().strftime('%y%m%d_%H%M%S')
    safe_id = run_id if run_id else 'UnknownRun'
    fname   = f'{safe_id}_{ts}_TempProfile.html'
    if output_dir:
        fpath = os.path.join(output_dir, fname)
    else:
        fpath = filedialog.asksaveasfilename(
            title='Export Temperature Profile HTML',
            defaultextension='.html',
            initialfile=fname,
            filetypes=(('HTML files', '*.html'),)
        )
    if not fpath:
        graphLabel.configure(text='Temp profile HTML export cancelled.'); return

    fig.write_html(fpath, include_plotlyjs='cdn', full_html=True, config={'responsive': True})
    graphLabel.configure(text=f'Temp profile HTML saved: {os.path.basename(fpath)}')
    print(f'Temp profile HTML saved to {fpath}')


# --- Thermal Expansion Viewer ---
def open_texpansion_viewer():
    global runData, graphLabel
    if not runData or len(runData) < 30:
        graphLabel.configure(text="Error: Run 'Generate Graph' first."); return
    delta_V_pct = runData[29]
    time_hours  = runData[0]
    if delta_V_pct is None:
        graphLabel.configure(text="Error: Thermal expansion data N/A."); return

    win = Toplevel(window)
    win.title('Thermal Expansion — ΔV (%)')
    win.geometry('900x400')

    plt.rcParams.update({
        'font.family': 'DejaVu Sans', 'font.size': 13, 'axes.linewidth': 1.4,
        'axes.labelsize': 13, 'xtick.labelsize': 12, 'ytick.labelsize': 12,
        'legend.fontsize': 11,
        'axes.grid': True, 'grid.color': '0.88', 'grid.linewidth': 0.5,
        'xtick.direction': 'in', 'ytick.direction': 'in',
        'xtick.minor.visible': True, 'ytick.minor.visible': True,
        'figure.facecolor': 'white', 'axes.facecolor': 'white',
    })
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_box_aspect(1)
    fig.subplots_adjust(left=0.11, right=0.95, top=0.90, bottom=0.16)

    C_DV = '#17becf'
    time_np = np.array(time_hours, dtype=float)
    dv_np   = np.array(delta_V_pct, dtype=float)
    mask    = ~np.isnan(dv_np) & ~np.isnan(time_np)

    if np.any(mask):
        ax.plot(time_np[mask], dv_np[mask], color=C_DV, linewidth=1.5)
    ax.axhline(0, color='0.5', linewidth=0.8, linestyle='--')
    ax.set_xlabel('Time (h)', labelpad=4)
    ax.set_ylabel('ΔV (%)', color=C_DV, labelpad=4)
    ax.set_title('Thermal Expansion — Volume Change (%)')
    ax.tick_params(axis='y', labelcolor=C_DV, direction='in', which='both')
    ax.tick_params(axis='x', direction='in', which='both')
    ax.spines['right'].set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.grid(True, color='0.88', linewidth=0.6)

    canvas = FigureCanvasTkAgg(fig, master=win)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)
    NavigationToolbar2Tk(canvas, win)


# --- Export Temp Profiles Function ---
def export_temp_profiles():
    global runData, graphLabel
    if not runData or len(runData) < 30: graphLabel.configure(text="Error: Run 'Generate Graph' first."); return
    if runData[25] is None: graphLabel.configure(text="Error: Temp profiles N/A."); return
    try:
        time_hours_list = runData[0]; full_profiles = runData[25]
        use_interpolation = runData[8] is None
        tc_positions = runData[7]['X Position'] if runData[7] is not None else None
        if not time_hours_list or not full_profiles: graphLabel.configure(text="Error: Time/profile data empty."); return
        max_len = 0; start_z = 0
        if full_profiles: max_len = max(len(p) for p in full_profiles if p)
        if use_interpolation and tc_positions is not None and not tc_positions.empty: start_z = int(tc_positions.min())
        elif not use_interpolation and runData[8] is not None:
            try: start_z = int(runData[8].columns[1])
            except (IndexError, ValueError): start_z = 0
        if max_len == 0: graphLabel.configure(text="Error: Profiles empty."); return
        file_path = filedialog.asksaveasfilename(title="Save Temp Profiles CSV", defaultextension=".csv", filetypes=(("CSV files", "*.csv"),))
        if not file_path: graphLabel.configure(text="Export cancelled."); return
        headers = ["Time_Hours"] + [f"Z_{start_z + z}_mm" for z in range(max_len)]
        data_to_export = []
        for i in range(len(time_hours_list)):
            time_val = time_hours_list[i]; profile = full_profiles[i] if i < len(full_profiles) else []
            padded_profile = profile + [np.nan] * (max_len - len(profile)); data_to_export.append([time_val] + padded_profile)
        export_df = pd.DataFrame(data_to_export, columns=headers)
        export_df.to_csv(file_path, index=False, float_format='%.3f')
        graphLabel.configure(text=f"Temp profiles exported.")
    except Exception as e: print(f"Error exporting profiles: {e}"); graphLabel.configure(text=f"Error exporting profiles: {e}")
