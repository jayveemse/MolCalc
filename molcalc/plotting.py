# --- moleGraph function ---
def moleGraph(runData):
    global runBool, imageViewer, baselineEdited
    global plot_fig, plot_ax2, plot_canvas, plot_ax4
    [Time_Hours, Time_Minutes, Time_Seconds, n, P_MPa, avgTempList, runDF, TC_df, lookupTable,
     rawData, baseline, baselineRange, baselineUnit, baselineEdited, movingAvg, movingAvgRange,
     movingAvgUnit, df, fileName, tempRange, pressureRange, timeRange, nRange, dn_dtRange,
     P_calc_MPa, full_temp_profiles_K, coarseVol, plot_df, n_error, delta_V_pct] = runData  # 30 items
    if runBool==True:
        if imageViewer and imageViewer.winfo_exists(): imageViewer.destroy()
    runBool=True
    imageViewer = Toplevel(window); imageViewer.title(str(fileName))
    _iw, _ih = 1060, int(window.winfo_screenheight()*0.8)
    _ix = (window.winfo_screenwidth() - _iw) // 2
    _iy = max(0, (window.winfo_screenheight() - _ih) // 2)
    imageViewer.geometry(f"{_iw}x{_ih}+{_ix}+{_iy}")
    # ── Scientific plot styling ─────────────────────────────────────
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

    fig = plt.figure(figsize=(10, 10))
    ax1 = fig.add_subplot(1, 1, 1)
    fig.subplots_adjust(left=0.09, right=0.82, top=0.88, bottom=0.09)
    plot_fig = fig

    n_error_np = None

    if plot_df is not None and isinstance(plot_df, pd.DataFrame):
        time_h_np = plot_df['Time_Hours'].to_numpy()
        n_np = plot_df['Moles_mmol'].to_numpy()
        p_mpa_np = plot_df['Pressure_Meas_MPa'].to_numpy()
        p_calc_mpa_np = plot_df['Pressure_Calc_MPa'].to_numpy()
        avg_temp_np = plot_df['Temp_Avg_C'].to_numpy()
        control_tc_data_numeric = plot_df['Temp_Control_C'].to_numpy()
        sample_tc_data_numeric = plot_df['Temp_Sample_C'].to_numpy() if 'Temp_Sample_C' in plot_df.columns else np.full(len(plot_df), np.nan)
        n_error_np = plot_df['Moles_Uncertainty_mmol'].to_numpy()
        control_tc_channel = plot_df['Control_TC_Channel'].iloc[0] if not plot_df.empty else 'N/A'
        mask_n = ~np.isnan(n_np); mask_p = ~np.isnan(p_mpa_np)
        mask_t = ~np.isnan(avg_temp_np); mask_p_calc = ~np.isnan(p_calc_mpa_np)
        mask_control_t = ~np.isnan(control_tc_data_numeric)
        time_control_t = time_h_np[mask_control_t] if np.any(mask_control_t) else np.array([])
    else:
        time_h_np = np.array(Time_Hours); n_np = np.array(n)
        p_mpa_np = np.array(P_MPa); avg_temp_np = np.array(avgTempList)
        p_calc_mpa_np = np.array(P_calc_MPa); n_error_np = np.array(n_error)
        control_tc_channel = None; control_tc_data_numeric = None
        sample_tc_data_numeric = np.full(len(time_h_np), np.nan)
        mask_control_t = np.array([False]*len(time_h_np)); time_control_t = np.array([])
        if TC_df is not None and 'IO Type' in TC_df.columns:
            ctrl = TC_df[TC_df['IO Type'].astype(str).str.strip().str.lower() == 'control']
            if not ctrl.empty:
                control_tc_channel = ctrl['NI LV Channel'].iloc[0]
                if runDF is not None and control_tc_channel in runDF.columns:
                    ctd = pd.to_numeric(runDF[control_tc_channel], errors='coerce').to_numpy()
                    control_tc_data_numeric = ctd
                    cl = min(len(ctd), len(time_h_np))
                    mask_control_t = ~np.isnan(ctd[:cl])
                    if np.any(mask_control_t): time_control_t = time_h_np[:cl][mask_control_t]
        mask_n = ~np.isnan(n_np); mask_p = ~np.isnan(p_mpa_np)
        mask_t = ~np.isnan(avg_temp_np); mask_p_calc = ~np.isnan(p_calc_mpa_np)

    mask_err = ~np.isnan(n_error_np)
    mask_n_with_err = mask_n & mask_err
    time_h_n   = time_h_np[mask_n]   if np.any(mask_n)   else np.array([])
    time_h_p   = time_h_np[mask_p]   if np.any(mask_p)   else np.array([])
    time_h_t   = time_h_np[mask_t]   if np.any(mask_t)   else np.array([])
    time_h_err = time_h_np[mask_n_with_err] if np.any(mask_n_with_err) else np.array([])

    # ── Axis 1: Moles (left) ─────────────────────────────────────────────
    handles = []; labels = []
    C_MOLES = '#1f77b4'   # blue
    C_PRES  = '#d62728'   # red
    C_TEMP  = '#2ca02c'   # green
    C_PCALC = '#ff7f0e'   # orange
    C_DNDT  = '#9467bd'   # purple
    _lw = float(line_thickness_var.get()) if line_thickness_var else 1.8

    if time_h_n.size > 0:
        p1, = ax1.plot(time_h_n, n_np[mask_n], color=C_MOLES,
                       linewidth=_lw, label='$n$ (mmol)')
        handles.append(p1); labels.append('$n$ (mmol)')
        if time_h_err.size > 0:
            _fb = ax1.fill_between(time_h_err,
                             n_np[mask_n_with_err] - n_error_np[mask_n_with_err],
                             n_np[mask_n_with_err] + n_error_np[mask_n_with_err],
                             color=C_MOLES, alpha=0.15, zorder=1,
                             label=r'$\pm1\sigma$ uncertainty')
            handles.append(_fb)
            labels.append(r'$\pm1\sigma$ uncertainty')
    ax1.set_ylabel('$n$ (mmol)', color=C_MOLES, labelpad=4)
    ax1.tick_params(axis='y', labelcolor=C_MOLES)
    ax1.yaxis.set_tick_params(which='both', direction='in')

    # ── Axis 2: Pressure (right 1) ───────────────────────────────────────
    ax2 = ax1.twinx(); plot_ax2 = ax2
    if time_h_p.size > 0:
        p2, = ax2.plot(time_h_p, p_mpa_np[mask_p], color=C_PRES,
                       linewidth=_lw, label='$P_{\\mathrm{meas}}$ (MPa)')
        handles.append(p2); labels.append('$P_{\\mathrm{meas}}$ (MPa)')
    ax2.set_ylabel('Pressure (MPa)', color=C_PRES, labelpad=4)
    ax2.tick_params(axis='y', labelcolor=C_PRES, direction='in', which='both')
    ax2.spines['right'].set_edgecolor(C_PRES)

    # ── Axis 3: Temperature (right 2) ────────────────────────────────────
    ax3 = ax1.twinx(); temp_label_text = 'Avg. $T$ (°C)'
    ax3.spines['right'].set_position(('outward', 60))
    ax3.spines['right'].set_edgecolor(C_TEMP)
    safe_mask_control_t = (mask_control_t[:len(control_tc_data_numeric)]
                           if control_tc_data_numeric is not None else mask_control_t)
    if (control_tc_channel and control_tc_channel != 'N/A'
            and control_tc_data_numeric is not None and time_control_t.size > 0):
        safe_len = min(len(control_tc_data_numeric), len(safe_mask_control_t))
        p3, = ax3.plot(time_control_t,
                       control_tc_data_numeric[:safe_len][safe_mask_control_t],
                       color=C_TEMP, linewidth=_lw,
                       label=f'$T_{{\\mathrm{{ctrl}}}}$ ({control_tc_channel}) (°C)')
        temp_label_text = f'$T_{{\\mathrm{{ctrl}}}}$ (°C)'
        handles.append(p3); labels.append(f'$T_{{\\mathrm{{ctrl}}}}$ (°C)')
    elif time_h_t.size > 0:
        p3a, = ax3.plot(time_h_t, avg_temp_np[mask_t], color=C_TEMP,
                        linewidth=_lw, linestyle='--', label='Avg. $T$ (°C)')
        handles.append(p3a); labels.append('Avg. $T$ (°C)')
    ax3.set_ylabel(temp_label_text, color=C_TEMP, labelpad=4)
    ax3.tick_params(axis='y', labelcolor=C_TEMP, direction='in', which='both')
    ax3.set_navigate(False)

    # ── Sample position temperature (second T trace on ax3) ───────────────
    C_SAMPLE = '#e6550d'   # burnt orange
    _spos_str = ''
    if sample_pos_var:
        try: _spos_str = sample_pos_var.get().strip()
        except Exception: pass
    if (sample_tc_data_numeric is not None
            and not np.all(np.isnan(sample_tc_data_numeric))):
        _safe_len_s = min(len(sample_tc_data_numeric), len(time_h_np))
        mask_sample_t = ~np.isnan(sample_tc_data_numeric[:_safe_len_s])
        if np.any(mask_sample_t):
            _lbl_s = (f'$T_{{\\mathrm{{sample}}}}$ @ {_spos_str} mm (°C)'
                      if _spos_str else '$T_{{\\mathrm{{sample}}}}$ (°C)')
            p3s, = ax3.plot(time_h_np[:_safe_len_s][mask_sample_t],
                            sample_tc_data_numeric[:_safe_len_s][mask_sample_t],
                            color=C_SAMPLE, linewidth=_lw, linestyle='--',
                            label=_lbl_s)
            handles.append(p3s)
            labels.append(_lbl_s)

    # ── Axis 4: dn/dt (right 3, hidden until used) ───────────────────────
    ax4 = ax1.twinx(); plot_ax4 = ax4
    ax4.yaxis.set_label_position('right')
    ax4.yaxis.tick_right()
    ax4.spines['right'].set_position(('outward', 120))
    ax4.spines['right'].set_edgecolor(C_DNDT)
    ax4.set_ylabel('d$n$/d$t$ (mmol h$^{-1}$)', color=C_DNDT, labelpad=4)
    ax4.tick_params(axis='y', labelcolor=C_DNDT, direction='in', which='both')
    ax4.set_visible(False)

    # ── Title & legend ────────────────────────────────────────────────────
    title_str = run_id if run_id else str(fileName)
    fig.suptitle(title_str, fontsize=14, fontweight='bold', x=0.455, y=0.97)
    if handles:
        ax1.legend(handles=handles, labels=labels,
                   loc='upper right',
                   framealpha=0.95, edgecolor='0.6',
                   fontsize=11, borderaxespad=1.0,
                   handlelength=2.0, labelspacing=0.5)

    ax1.tick_params(axis='x', direction='in', which='both')
    ax1.set_xlabel('Time (h)', labelpad=6)


    # ── Embed in Tkinter ──────────────────────────────────────────────────
    imageViewer.columnconfigure(1, weight=1)
    imageViewer.rowconfigure(2, weight=1)

    toolbarFrame = Frame(imageViewer)
    toolbarFrame.grid(row=1, column=1, sticky='ew')
    imageFrame = Frame(imageViewer)
    imageFrame.grid(row=2, column=1, sticky='nsew')

    canvas = FigureCanvasTkAgg(fig, master=imageFrame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill='both', expand=True)
    plot_canvas = canvas
    NavigationToolbar2Tk(canvas, toolbarFrame)

    # ── Independent y-axis scrolling via mouse wheel over each axis ─────
    def _scroll_y(event):
        """Scroll/zoom the y-axis the cursor is currently over."""
        if event.inaxes is None: return
        ax = event.inaxes
        scale = 1.1 if event.button == 'down' else (1/1.1)
        y_min, y_max = ax.get_ylim()
        y_mid = event.ydata if event.ydata else (y_min + y_max) / 2
        ax.set_ylim(y_mid - (y_mid - y_min)*scale,
                    y_mid + (y_max - y_mid)*scale)
        canvas.draw_idle()

    def _scroll_x(event):
        """Shift x-axis on Shift+scroll."""
        if event.inaxes is None: return
        x_min, x_max = ax1.get_xlim()
        shift = (x_max - x_min) * 0.1
        if event.button == 'down':
            ax1.set_xlim(x_min + shift, x_max + shift)
        else:
            ax1.set_xlim(x_min - shift, x_max - shift)
        canvas.draw_idle()

    def _on_scroll(event):
        if event.key == 'shift':
            _scroll_x(event)
        else:
            _scroll_y(event)

    canvas.mpl_connect('scroll_event', _on_scroll)

    # ── Hint label ──────────────────────────────────────────────────────
    hintFrame = Frame(imageViewer)
    hintFrame.grid(row=3, column=1, sticky='ew')
    tk.Label(hintFrame,
             text='Scroll over an axis to zoom it independently  |  Shift+Scroll to pan X',
             font=('TkDefaultFont', 7), fg='gray', anchor='w').pack(side='left', padx=4)

    baselineEdited = False
