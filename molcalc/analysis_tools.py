# --- Calculate P_calc Function ---
def calculate_pcalc():
    global runData, graphLabel, plot_fig, plot_canvas, p_calc_start_time_var, p_offset_var, pcalc_info_label, p_calc_end_time_var, p_calc_step_var

    if not runData or len(runData) < 30:
        graphLabel.configure(text="Error: Run 'Generate Graph' first."); return

    # Pull required data from runData
    Time_Hours        = pd.Series(runData[0])
    n                 = runData[3]
    full_temp_profiles_K = runData[25]
    coarseVol         = runData[26]
    final_expected_len = len(runData[0])
    R = 8.3145

    # Total volume (m^3) from coarseVol
    V_total_m3 = sum(coarseVol) if coarseVol else 0.0

    # Z-offset from GUI
    try:
        z_off = z_offset_var.get().strip()
        z_offset_mm = int(float(z_off)) if z_off else 0
    except (ValueError, AttributeError):
        z_offset_mm = 0

    # P_calc start time from GUI
    try:
        start_input = p_calc_start_time_var.get().strip()
        if not start_input:
            graphLabel.configure(text="Error: Enter a P_calc Start Time (hr) first."); return
        p_calc_start_hr = float(start_input)
    except ValueError:
        graphLabel.configure(text="Error: P_calc Start Time must be numeric.")
        return

    # P_calc end time (optional)
    p_calc_end_hr = None
    try:
        end_input = p_calc_end_time_var.get().strip() if p_calc_end_time_var else ''
        if end_input:
            p_calc_end_hr = float(end_input)
            if p_calc_end_hr <= p_calc_start_hr:
                graphLabel.configure(text='Error: P_calc End Time must be after Start Time.')
                return
    except ValueError:
        graphLabel.configure(text='Error: P_calc End Time must be numeric.')
        return

    # P_calc step interval
    p_calc_step = 1
    try:
        step_in = p_calc_step_var.get().strip() if p_calc_step_var else ''
        if step_in:
            p_calc_step = max(1, int(float(step_in)))
    except (ValueError, AttributeError):
        pass
    _log_live(f'P_calc: step interval = every {p_calc_step} rows')

    graphLabel.configure(text='Calculating P_calc...')
    window.update_idletasks()

    try:
        n_start = np.nan
        P_calc_MPa_list = [np.nan] * final_expected_len
        molar_density = np.nan

        start_index_loc = (Time_Hours - p_calc_start_hr).abs().idxmin()
        if not (0 <= start_index_loc < len(n)):
            graphLabel.configure(text='Warn: P_calc start index out of range.'); return

        # n is in mmol — convert back to mol for molar density
        n_start = n[start_index_loc] / 1000.0
        actual_start_time = Time_Hours.iloc[start_index_loc]
        _log_live(f'P_calc: n_start = {n_start:.4e} mol at {actual_start_time:.3f} hr')

        if pd.isna(n_start):
            graphLabel.configure(text='Warn: n_start is NaN.'); return
        if V_total_m3 <= 0:
            graphLabel.configure(text='Warn: Total volume <= 0.'); return

        molar_density = n_start / V_total_m3
        _log_live(f'P_calc: molar density = {molar_density:.4e} mol/m³')

        P_calc_MPa_list = []
        # Determine index range for the P_calc window
        end_index_loc = final_expected_len
        if p_calc_end_hr is not None:
            end_index_loc = int((Time_Hours - p_calc_end_hr).abs().idxmin()) + 1
        _log_live(f'P_calc: computing from index {start_index_loc} to {end_index_loc-1}')

        # Sparse compute: only calculate at every p_calc_step-th index in window
        calc_indices = [i for i in range(start_index_loc, end_index_loc, p_calc_step)]
        if end_index_loc - 1 not in calc_indices:
            calc_indices.append(end_index_loc - 1)
        sparse_idx = []
        sparse_vals = []

        for i in calc_indices:
            if i >= len(full_temp_profiles_K): break
            temp_prof_K = full_temp_profiles_K[i]
            T_aligned = temp_prof_K
            V_aligned_ref = coarseVol
            if z_offset_mm > 0:
                T_aligned = temp_prof_K[z_offset_mm:] if z_offset_mm < len(temp_prof_K) else []
            elif z_offset_mm < 0:
                V_aligned_ref = coarseVol[abs(z_offset_mm):] if abs(z_offset_mm) < len(coarseVol) else []
            final_len_pcalc = min(len(T_aligned), len(V_aligned_ref))
            if final_len_pcalc == 0:
                sparse_idx.append(i); sparse_vals.append(np.nan); continue
            T_arr_pcalc = np.array(T_aligned[:final_len_pcalc])
            T_arr_pcalc[T_arr_pcalc <= 0] = 1e-6
            if np.isnan(T_arr_pcalc).any():
                sparse_idx.append(i); sparse_vals.append(np.nan); continue
            P_calc_Pa = np.nanmean(molar_density * R * T_arr_pcalc)
            sparse_idx.append(i)
            sparse_vals.append(np.nan if pd.isna(P_calc_Pa) else P_calc_Pa / 1e6)

        # Interpolate back to full resolution within the window
        if len(sparse_idx) >= 2:
            interp_vals = np.interp(
                np.arange(start_index_loc, end_index_loc),
                sparse_idx, sparse_vals
            )
            P_calc_MPa_list = ([np.nan] * start_index_loc +
                               interp_vals.tolist() +
                               [np.nan] * (final_expected_len - end_index_loc))
        elif len(sparse_idx) == 1:
            P_calc_MPa_list = [np.nan] * final_expected_len
            P_calc_MPa_list[sparse_idx[0]] = sparse_vals[0]
        else:
            P_calc_MPa_list = [np.nan] * final_expected_len

        _log_live('P_calc: calculation complete.')

        # ── Pressure offset ────────────────────────────────────────────
        # Auto-offset: difference at anchor point due to thermal gradient
        P_meas_at_start = runData[27]['Pressure_Meas_MPa'].iloc[start_index_loc]
        P_calc_at_start = P_calc_MPa_list[start_index_loc] if start_index_loc < len(P_calc_MPa_list) else np.nan
        auto_offset = (P_meas_at_start - P_calc_at_start
                       if not np.isnan(P_meas_at_start) and not np.isnan(P_calc_at_start)
                       else 0.0)

        # User offset (defaults to auto if field empty)
        user_offset = auto_offset
        try:
            ov = p_offset_var.get().strip() if p_offset_var else ''
            if ov: user_offset = float(ov)
        except ValueError:
            graphLabel.configure(text='Warning: Invalid P offset — using auto offset.')

        # Apply offset
        P_calc_MPa_list = [v + user_offset if not np.isnan(v) else np.nan
                           for v in P_calc_MPa_list]

        # Update info label
        info_txt = (f'Auto offset: {auto_offset:+.4f} MPa  |  '
                    f'Applied offset: {user_offset:+.4f} MPa  |  '
                    f'P_meas at t={actual_start_time:.3f} hr: {P_meas_at_start:.4f} MPa')
        _log_live(f'P_calc offset: {info_txt}')
        if pcalc_info_label:
            pcalc_info_label.configure(text=info_txt, fg='darkblue')
        # Pre-fill offset entry with auto value for user reference
        if p_offset_var and not p_offset_var.get().strip():
            p_offset_var.set(f'{auto_offset:.4f}')


        # Pad and update runData + plot_df
        P_calc_final = P_calc_MPa_list + [np.nan] * (final_expected_len - len(P_calc_MPa_list))
        if isinstance(runData[27], pd.DataFrame):
            runData[27]['Pressure_Calc_MPa'] = P_calc_final
        runData[24] = P_calc_final

        # Overlay on existing plot
        if plot_fig is not None and plot_canvas is not None:
            try:
                ax2_ref = plot_fig.axes[1]
                t_np  = np.array(runData[0])
                pc_np = np.array(P_calc_final)
                mask_pc = ~np.isnan(pc_np)
                if mask_pc.any():
                    for artist in ax2_ref.get_lines()[:]:
                        if artist.get_gid() == 'pcalc_line': artist.remove()
                    _lw_pc = float(line_thickness_var.get()) if line_thickness_var else 1.8
                    ax2_ref.plot(t_np[mask_pc], pc_np[mask_pc],
                                 color='darkorange', linestyle='--', linewidth=_lw_pc,
                                 label='P_calc (MPa)', gid='pcalc_line')
                    _rebuild_outside_legend(plot_fig)
                    plot_canvas.draw()
            except Exception as pe:
                print(f'Warning: could not overlay P_calc: {pe}')

        graphLabel.configure(text='P_calc complete.')

    except Exception as e:
        print(f'Error in calculate_pcalc: {e}')
        import traceback; traceback.print_exc()
        graphLabel.configure(text=f'Error in P_calc: {e}')


# --- Export Plot Data Function ---
def export_plot_data():
    global runData, graphLabel, output_dir, run_id
    from datetime import datetime
    if not runData or len(runData) < 30: graphLabel.configure(text="Error: Run 'Generate Graph' first."); return
    plot_df = runData[27]
    if not isinstance(plot_df, pd.DataFrame): graphLabel.configure(text='Error: plot_df missing.'); return
    try:
        if output_dir and run_id:
            ts = datetime.now().strftime('%y%m%d_%H%M%S')
            file_path = os.path.join(output_dir, f'{run_id}_{ts}_PlotData.csv')
        else:
            file_path = filedialog.asksaveasfilename(title='Save Plot Data CSV',
                defaultextension='.csv', filetypes=(('CSV files', '*.csv'),))
        if not file_path: graphLabel.configure(text='Export cancelled.'); return
        plot_df.to_csv(file_path, index=False, float_format='%.6e')
        graphLabel.configure(text=f'Plot data exported: {os.path.basename(file_path)}')
    except Exception as e: print(f'Error exporting plot data: {e}'); graphLabel.configure(text=f'Error: {e}')


# --- Export Interactive HTML Plot ---
def export_html_plot():
    global runData, graphLabel, run_id
    import plotly.graph_objects as go
    from datetime import datetime

    if not runData or len(runData) < 30:
        graphLabel.configure(text="Error: Run 'Generate Graph' first.")
        return

    plot_df = runData[27]
    if not isinstance(plot_df, pd.DataFrame):
        graphLabel.configure(text='Error: plot_df missing.')
        return

    try:
        # ── Build filename from RunID + timestamp ────────────────────────────
        timestamp = datetime.now().strftime('%y%m%d_%H%M%S')
        safe_run_id = run_id if run_id else 'UnknownRun'
        default_name = f'{safe_run_id}_{timestamp}.html'

        if output_dir:
            file_path = os.path.join(output_dir, default_name)
        else:
            file_path = filedialog.asksaveasfilename(
                title='Export Interactive HTML Plot',
                defaultextension='.html',
                initialfile=default_name,
                filetypes=(('HTML files', '*.html'),)
            )
        if not file_path:
            graphLabel.configure(text='HTML export cancelled.')
            return

        # ── Extract data arrays ──────────────────────────────────────────────
        t   = plot_df['Time_Hours'].to_numpy()
        n   = plot_df['Moles_mmol'].to_numpy()
        n_e = plot_df['Moles_Uncertainty_mmol'].to_numpy()
        p_m = plot_df['Pressure_Meas_MPa'].to_numpy()
        p_c = plot_df['Pressure_Calc_MPa'].to_numpy()

        # Prefer control TC; fall back to average
        ctrl_ch = plot_df['Control_TC_Channel'].iloc[0] if not plot_df.empty else 'N/A'
        if ctrl_ch and ctrl_ch != 'N/A' and 'Temp_Control_C' in plot_df.columns:
            temp     = plot_df['Temp_Control_C'].to_numpy()
            temp_lbl = f'Control T ({ctrl_ch}) (°C)'
        else:
            temp     = plot_df['Temp_Avg_C'].to_numpy()
            temp_lbl = 'Avg T (°C)'

        hover_t = [f'{v:.4f} hr' if not np.isnan(v) else 'N/A' for v in t]

        # ── Build figure ─────────────────────────────────────────────────────
        fig = go.Figure()

        # Uncertainty band (filled area, drawn first so it sits behind)
        valid_e = ~(np.isnan(n) | np.isnan(n_e))
        if valid_e.any():
            fig.add_trace(go.Scatter(
                x=np.concatenate([t[valid_e], t[valid_e][::-1]]),
                y=np.concatenate([n[valid_e] + n_e[valid_e], (n[valid_e] - n_e[valid_e])[::-1]]),
                fill='toself', fillcolor='rgba(0,0,255,0.12)',
                line=dict(color='rgba(255,255,255,0)'),
                hoverinfo='skip', showlegend=True,
                name='n (1\u03c3 uncertainty)',
                yaxis='y1'
            ))

        # Moles
        valid_n = ~np.isnan(n)
        fig.add_trace(go.Scatter(
            x=t[valid_n], y=n[valid_n],
            mode='lines', name='n (mmol)',
            line=dict(color='blue', width=1.5),
            yaxis='y1',
            hovertemplate='<b>n</b>: %{y:.4f} mmol<br>Time: %{x:.4f} hr<extra></extra>'
        ))

        # Measured pressure
        valid_pm = ~np.isnan(p_m)
        fig.add_trace(go.Scatter(
            x=t[valid_pm], y=p_m[valid_pm],
            mode='lines', name='P_meas (MPa)',
            line=dict(color='red', width=1.5),
            yaxis='y2',
            hovertemplate='<b>P_meas</b>: %{y:.4f} MPa<br>Time: %{x:.4f} hr<extra></extra>'
        ))

        # Calculated pressure
        valid_pc = ~np.isnan(p_c)
        if valid_pc.any():
            fig.add_trace(go.Scatter(
                x=t[valid_pc], y=p_c[valid_pc],
                mode='lines', name='P_calc (MPa)',
                line=dict(color='darkorange', width=1.5, dash='dash'),
                yaxis='y2',
                hovertemplate='<b>P_calc</b>: %{y:.4f} MPa<br>Time: %{x:.4f} hr<extra></extra>'
            ))

        # Temperature
        valid_t = ~np.isnan(temp)
        if valid_t.any():
            fig.add_trace(go.Scatter(
                x=t[valid_t], y=temp[valid_t],
                mode='lines', name=temp_lbl,
                line=dict(color='green', width=1.5),
                yaxis='y3',
                hovertemplate='<b>T</b>: %{y:.2f} °C<br>Time: %{x:.4f} hr<extra></extra>'
            ))

        # ── Layout ───────────────────────────────────────────────────────────
        fig.update_layout(
            title=dict(
                text=f'MolCalc — {safe_run_id}',
                font=dict(size=16)
            ),
            xaxis=dict(title='Time (h)', domain=[0, 0.70],
                       showline=True, linewidth=1.2, linecolor='black',
                       mirror=True, ticks='inside', showgrid=True,
                       gridcolor='rgba(0,0,0,0.08)'),
            yaxis=dict(
                title=dict(text='<i>n</i> (mmol)', font=dict(color='#1f77b4')),
                tickfont=dict(color='#1f77b4'),
                showline=True, linewidth=1.2, linecolor='#1f77b4',
                ticks='inside', mirror=False,
            ),
            yaxis2=dict(
                title=dict(text='Pressure (MPa)', font=dict(color='#d62728')),
                tickfont=dict(color='#d62728'),
                anchor='x', overlaying='y', side='right',
                showline=True, linewidth=1.2, linecolor='#d62728',
                ticks='inside',
            ),
            yaxis3=dict(
                title=dict(text=temp_lbl, font=dict(color='#2ca02c')),
                tickfont=dict(color='#2ca02c'),
                anchor='free', overlaying='y', side='right', position=0.86,
                showline=True, linewidth=1.2, linecolor='#2ca02c',
                ticks='inside',
            ),
            legend=dict(x=1.04, y=1.0, xanchor='left', yanchor='top',
                        bgcolor='rgba(255,255,255,0.95)',
                        bordercolor='#aaa', borderwidth=1,
                        font=dict(size=13)),
            font=dict(family='Arial', size=13),
            hovermode='x unified',
            template='simple_white',
            plot_bgcolor='white',
            paper_bgcolor='white',
            autosize=True, height=800,
            margin=dict(l=60, r=220, t=70, b=60),
        )

        # ── Write self-contained HTML ─────────────────────────────────────────
        fig.write_html(file_path, include_plotlyjs='cdn', full_html=True, config={'responsive': True})
        graphLabel.configure(text=f'HTML plot exported: {os.path.basename(file_path)}')
        print(f'HTML plot saved to {file_path}')

    except Exception as e:
        print(f'Error exporting HTML: {e}')
        import traceback; traceback.print_exc()
        graphLabel.configure(text=f'Error exporting HTML: {e}')


# --- Import Data Function ---
def import_data():
    global runData, graphLabel, tempViewButton, exportTempButton, exportPlotButton, calculateFitButton
    try:
        file_path = filedialog.askopenfilename(title="Import Plot Data CSV", filetypes=(("CSV files", "*.csv"),))
        if not file_path: graphLabel.configure(text="Import cancelled."); return
        imported_df = pd.read_csv(file_path)
        required_cols = ['Time_Hours', 'Moles_mmol', 'Moles_Uncertainty_mmol', 'Pressure_Meas_MPa', 'Pressure_Calc_MPa', 'Temp_Avg_C', 'Temp_Control_C', 'Control_TC_Channel']
        if not all(col in imported_df.columns for col in required_cols): graphLabel.configure(text=f"Error: Imported CSV missing columns."); print(f"Missing: {[c for c in required_cols if c not in imported_df.columns]}"); return
        Time_Hours_final = imported_df['Time_Hours'].tolist(); n_final = imported_df['Moles_mmol'].tolist()
        P_MPa_final = imported_df['Pressure_Meas_MPa'].tolist(); P_calc_MPa_final = imported_df['Pressure_Calc_MPa'].tolist()
        avgTempList_final = imported_df['Temp_Avg_C'].tolist(); control_temp_final = imported_df['Temp_Control_C'].tolist()
        n_error_final = imported_df['Moles_Uncertainty_mmol'].tolist() # <-- Import uncertainty
        control_tc_channel = imported_df['Control_TC_Channel'].iloc[0] if not imported_df.empty else "N/A"
        mock_runDF = pd.DataFrame({control_tc_channel: control_temp_final}) if control_tc_channel != "N/A" else pd.DataFrame()
        mock_TC_df = pd.DataFrame({'NI LV Channel': [control_tc_channel], 'IO Type': ['Control']}) if control_tc_channel != "N/A" else pd.DataFrame()
        mock_runData = [Time_Hours_final,None,None,n_final,P_MPa_final,avgTempList_final,mock_runDF,mock_TC_df,None,None,None,None,None,None,None,None,None,None,file_path,None,None,None,None,None,P_calc_MPa_final,None,None,imported_df,n_error_final] # <-- Add error to list
        runData = mock_runData
        if tempViewButton: tempViewButton.configure(state='disabled')
        if exportTempButton: exportTempButton.configure(state='disabled')
        if exportPlotButton: exportPlotButton.configure(state='normal')
        if exportHtmlButton: exportHtmlButton.configure(state='normal')
        if calculateFitButton: calculateFitButton.configure(state='normal')
        if dn_dt_button: dn_dt_button.configure(state='normal')
        moleGraph(mock_runData)
        graphLabel.configure(text=f"Imported & plotted: {os.path.basename(file_path)}")
    except Exception as e: print(f"Error importing data: {e}"); import traceback; traceback.print_exc(); graphLabel.configure(text=f"Error importing data: {e}")

# --- Import Temp Profile Viewer Function ---
def import_temp_profile_viewer():
    global graphLabel, temp_viewer_window
    try:
        file_path = filedialog.askopenfilename(title="Import Temperature Profile CSV", filetypes=(("CSV files", "*.csv"),))
        if not file_path: graphLabel.configure(text="Import cancelled."); return
        df = pd.read_csv(file_path)
        if 'Time_Hours' not in df.columns: graphLabel.configure(text="Error: Imported CSV missing 'Time_Hours'."); return
        z_cols = [col for col in df.columns if col.startswith('Z_') and col.endswith('_mm')]
        if not z_cols: graphLabel.configure(text="Error: Imported CSV missing 'Z_..._mm' cols."); return
        y_axis_time = df['Time_Hours']
        z_col_nums = sorted([(int(re.findall(r'\d+', col)[0]), col) for col in z_cols]); x_axis_z_positions = [z[0] for z in z_col_nums]; sorted_z_cols = [z[1] for z in z_col_nums]
        z_data_temps = df[sorted_z_cols].values
        
        if temp_viewer_window and temp_viewer_window.winfo_exists(): temp_viewer_window.destroy()
        temp_viewer_window = tk.Toplevel(window); temp_viewer_window.title(f"Imported Profile: {os.path.basename(file_path)}"); temp_viewer_window.geometry("800x600")
        
        fig_temp = plt.figure(); ax = fig_temp.add_subplot(111)
        im = ax.imshow(z_data_temps, aspect='auto', cmap='jet', extent=[min(x_axis_z_positions), max(x_axis_z_positions), y_axis_time.max(), y_axis_time.min()])
        ax.set_title(f"Temperature Profile (T vs. Z vs. Time)"); ax.set_xlabel("Z Position (mm)"); ax.set_ylabel("Time (Hours)")
        fig_temp.colorbar(im, ax=ax, label="Temp (K?)")
        
        plot_frame = tk.Frame(temp_viewer_window); plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        canvas_temp = FigureCanvasTkAgg(fig_temp, master=plot_frame); canvas_temp.draw(); canvas_temp.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        toolbar_temp = NavigationToolbar2Tk(canvas_temp, plot_frame); toolbar_temp.update(); toolbar_temp.pack(side=tk.BOTTOM, fill=tk.X)
        graphLabel.configure(text=f"Temp profile viewer opened for {os.path.basename(file_path)}")
    except Exception as e: print(f"Error importing temp profile: {e}"); import traceback; traceback.print_exc(); graphLabel.configure(text=f"Error importing temp profile: {e}")

# --- Calculate Exponential Fit Function ---
def exp_fit_func(t, a, b, c):
    """Exponential decay function: a * exp(-b * t) + c"""
    return a * np.exp(-b * t) + c

def calculate_exponential_fit():
    global runData, fit_start_time_var, fit_end_time_var, fit_results_label
    
    if not runData or len(runData) < 30: # Check for 30 items
        fit_results_label.configure(text="Error: Must 'Generate Graph' or 'Import' data first.", fg='red')
        return
        
    plot_df = runData[27] # plot_df is at index 27
    if not isinstance(plot_df, pd.DataFrame) or 'Moles_Uncertainty_mmol' not in plot_df.columns:
        fit_results_label.configure(text="Error: Plot data/Uncertainty is missing. Re-run/Re-import.", fg='red')
        return
        
    try:
        start_h = float(fit_start_time_var.get())
        end_h = float(fit_end_time_var.get())
        if start_h >= end_h:
            fit_results_label.configure(text="Error: Start time must be before end time.", fg='red')
            return
    except ValueError:
        fit_results_label.configure(text="Error: Fit times must be numeric (e.g., 1.5).", fg='red')
        return

    try:
        df_fit = plot_df[(plot_df['Time_Hours'] >= start_h) & (plot_df['Time_Hours'] <= end_h)].copy()
        df_fit.dropna(subset=['Time_Hours', 'Pressure_Meas_MPa', 'Temp_Control_C', 'Moles_mmol', 'Moles_Uncertainty_mmol'], inplace=True)
        
        if len(df_fit) < 3:
            fit_results_label.configure(text="Error: Not enough valid data points in selected range.", fg='red')
            return

        t_data = df_fit['Time_Hours']; t_data_rel = t_data - t_data.iloc[0]; p_data = df_fit['Pressure_Meas_MPa']; t_control_data = df_fit['Temp_Control_C']
        t_sample_data = df_fit['Temp_Sample_C'] if 'Temp_Sample_C' in df_fit.columns else pd.Series([np.nan]*len(df_fit), index=df_fit.index)
        sample_temp_at_end = np.nan   # initialise; assigned after successful fit
        p0 = [p_data.iloc[0] - p_data.iloc[-1], 1.0, p_data.iloc[-1]]
        
        print(f"Fitting {len(t_data_rel)} points between {start_h} and {end_h} Hr..."); print(f"Initial guesses (a, b, c): {p0}")
        popt, pcov = curve_fit(exp_fit_func, t_data_rel, p_data, p0=p0, maxfev=5000)
        
        asymptote_c = popt[2]; temp_at_end = t_control_data.iloc[-1]
        _s_valid = t_sample_data.dropna()
        sample_temp_at_end = float(_s_valid.iloc[-1]) if not _s_valid.empty else np.nan
        
        # --- NEW: LOD Calculation ---
        delta_n_measured = df_fit['Moles_mmol'].iloc[-1] - df_fit['Moles_mmol'].iloc[0]
        sigma_n_start = df_fit['Moles_Uncertainty_mmol'].iloc[0]
        sigma_n_end = df_fit['Moles_Uncertainty_mmol'].iloc[-1]
        
        sigma_delta_n = np.sqrt(sigma_n_start**2 + sigma_n_end**2)
        LOD_3sigma_mol = 3 * sigma_delta_n
        # --- END NEW ---

        # --- Plot fit curve and asymptote onto the main pressure axis ---
        if plot_fig is not None and plot_ax2 is not None and plot_canvas is not None:
            try:
                t_fit_rel = np.linspace(0, float(t_data_rel.iloc[-1]), 500)
                p_fit_vals = exp_fit_func(t_fit_rel, *popt)
                t_fit_abs = t_fit_rel + float(t_data.iloc[0])
                # Remove any previous fit lines (tagged with gid='exp_fit')
                for artist in plot_ax2.get_lines():
                    if artist.get_gid() in ('exp_fit_curve', 'exp_fit_asymptote'):
                        artist.remove()
                _lw_fit = float(line_thickness_var.get()) if line_thickness_var else 1.8
                plot_ax2.plot(t_fit_abs, p_fit_vals, color='purple', linestyle='--',
                              linewidth=_lw_fit, label='Exp Fit', gid='exp_fit_curve')
                plot_ax2.axhline(y=asymptote_c, color='darkviolet', linestyle=':',
                                 linewidth=_lw_fit, label=f'Asymptote ({asymptote_c:.4e} MPa)',
                                 gid='exp_fit_asymptote')
                _rebuild_outside_legend(plot_fig)
                plot_canvas.draw()
                print('Fit curve and asymptote plotted on main graph.')
            except Exception as plot_err:
                print(f'Warning: Could not overlay fit on plot: {plot_err}')
        else:
            print('Warning: Main plot not available for fit overlay. Run Generate Graph first.')


        _spos_lbl = sample_pos_var.get().strip() if sample_pos_var else ""
        _samp_str = (f"Sample T @ {_spos_lbl} mm: {sample_temp_at_end:.2f} C" if (not np.isnan(sample_temp_at_end) and _spos_lbl) else ("Sample T: N/A" if np.isnan(sample_temp_at_end) else f"Sample T: {sample_temp_at_end:.2f} C"))
        result_text = f"Fit Asymptote: {asymptote_c:.4e} MPa | Control T @ {end_h:.2f} Hr: {temp_at_end:.2f} C  |  {_samp_str}\n"
        result_text += f"Measured $\Delta n$: {delta_n_measured:.3e} mol | LOD (3$\sigma$): {LOD_3sigma_mol:.3e} mol"
        
        fit_results_label.configure(text=result_text, fg='black')
        print(result_text)

        # Store fit result for manual export via 'Export Fit CSV' button
        # Write fit result directly to the run's fit CSV
        fit_row = {
            'Fit_Start_Time_hr':     start_h,
            'Fit_End_Time_hr':       end_h,
            'Fit_Param_a_MPa':       popt[0],
            'Fit_Param_b_per_hr':    popt[1],
            'Fit_Param_c_MPa':       popt[2],
            'Asymptote_MPa':         asymptote_c,
            'Control_Temp_at_End_C': temp_at_end,
            'Sample_Temp_at_End_C':  sample_temp_at_end,
            'Delta_n_mmol':          delta_n_measured,
            'Sigma_delta_n_mmol':    sigma_delta_n,
            'LOD_3sigma_mmol':       LOD_3sigma_mol,
        }
        if fit_csv_path and os.path.isdir(os.path.dirname(fit_csv_path)):
            try:
                write_header = not os.path.exists(fit_csv_path)
                pd.DataFrame([fit_row]).to_csv(
                    fit_csv_path, mode='a', index=False,
                    header=write_header, float_format='%.6e')
                graphLabel.configure(
                    text=f'Fit saved to {os.path.basename(fit_csv_path)}')
            except Exception as _csv_e:
                graphLabel.configure(text=f'Warning: fit CSV write failed: {_csv_e}')
        else:
            graphLabel.configure(
                text='Warning: Output folder not set — fit result not saved to CSV.')



    except RuntimeError:
        fit_results_label.configure(text="Error: Exponential fit failed to converge.", fg='red')
        print("Error: Exponential fit failed to converge.")
    except Exception as e:
        fit_results_label.configure(text=f"Error: {e}", fg='red')
        print(f"Error during fitting: {e}")
        import traceback; traceback.print_exc()


# --- Export Fit CSV & Save Plot Image ---
def export_fit_csv():
    global last_fit_result, output_dir, run_id, graphLabel, fit_csv_path
    if not last_fit_result:
        graphLabel.configure(text='No fit result to export. Run Calculate Fit first.')
        return
    if not output_dir or not run_id:
        graphLabel.configure(text='Set Output Folder before exporting.')
        return
    try:
        # Use a single persistent file for the whole run (append each fit)
        if not fit_csv_path:
            from datetime import datetime
            ts = datetime.now().strftime('%y%m%d_%H%M%S')
            fit_csv_path = os.path.join(output_dir, f'{run_id}_{ts}_FitResults.csv')
        write_header = not os.path.exists(fit_csv_path)
        pd.DataFrame([last_fit_result]).to_csv(
            fit_csv_path, mode='a', index=False,
            header=write_header, float_format='%.6e')
        graphLabel.configure(text=f'Fit appended to {os.path.basename(fit_csv_path)}')
    except Exception as e:
        graphLabel.configure(text=f'Error exporting fit: {e}')

def save_plot_image():
    global plot_fig, output_dir, run_id, graphLabel
    from datetime import datetime
    if plot_fig is None:
        graphLabel.configure(text="No plot to save. Run 'Generate Graph' first.")
        return
    if not output_dir or not run_id:
        graphLabel.configure(text='Set Output Folder before saving plot.')
        return
    try:
        ts = datetime.now().strftime('%y%m%d_%H%M%S')
        base = os.path.join(output_dir, f'{run_id}_{ts}_Plot')
        plot_fig.savefig(base + '.png', dpi=300, bbox_inches='tight', facecolor='white')
        plot_fig.savefig(base + '.svg', bbox_inches='tight', facecolor='white')
        graphLabel.configure(text=f'Plot saved: {os.path.basename(base)}.png/.svg')
    except Exception as e:
        graphLabel.configure(text=f'Error saving plot: {e}')


# --- Legend rebuild helper ---
def _rebuild_outside_legend(fig, canvas=None):
    """Collect all labeled artists from every axis and place legend outside the plot area."""
    seen = set()
    handles = []
    labels = []
    for ax in fig.axes:
        for h, l in zip(*ax.get_legend_handles_labels()):
            if l and not l.startswith('_') and l not in seen:
                seen.add(l)
                handles.append(h)
                labels.append(l)
    for leg in list(fig.legends):
        leg.remove()
    if handles:
        fig.legend(handles=handles, labels=labels,
                   loc='upper left',
                   bbox_to_anchor=(0.745, 0.92),
                   bbox_transform=fig.transFigure,
                   framealpha=0.95, edgecolor='0.6',
                   fontsize=11, borderaxespad=0,
                   handlelength=2.0, labelspacing=0.6)
    if canvas is not None:
        canvas.draw()

# --- Clear Overlay Functions ---
def clear_dndt():
    global plot_ax4, plot_canvas, dn_dt_results_label
    if plot_ax4 is not None:
        plot_ax4.cla()
        plot_ax4.set_ylabel('dn/dt (mmol/hr)', color='darkorchid')
        plot_ax4.tick_params(axis='y', labelcolor='darkorchid', direction='in', which='both')
        plot_ax4.spines['right'].set_position(('outward', 120))
        plot_ax4.yaxis.set_label_position('right')
        plot_ax4.yaxis.tick_right()
        plot_ax4.set_visible(False)
        if plot_canvas: plot_canvas.draw()
    if dn_dt_results_label: dn_dt_results_label.configure(text='')

def clear_fit():
    global plot_ax2, plot_canvas, fit_results_label, last_fit_result, plot_fig
    if plot_ax2 is not None:
        for artist in plot_ax2.get_lines()[:]:
            if artist.get_gid() in ('exp_fit_curve', 'exp_fit_asymptote'):
                artist.remove()
        for coll in plot_ax2.collections[:]:
            if getattr(coll, '_gid', None) in ('exp_fit_curve', 'exp_fit_asymptote'):
                coll.remove()
        if plot_fig is not None:
            _rebuild_outside_legend(plot_fig)
        if plot_canvas: plot_canvas.draw()
    last_fit_result = None
    if fit_results_label: fit_results_label.configure(text='')

def clear_pcalc():
    global plot_ax2, plot_canvas, runData
    if plot_ax2 is not None:
        for artist in plot_ax2.get_lines()[:]:
            if artist.get_gid() == 'pcalc_line': artist.remove()
        if plot_canvas:
            _rebuild_outside_legend(plot_fig)
            plot_canvas.draw()()
    if runData and len(runData) >= 30 and isinstance(runData[27], pd.DataFrame):
        runData[27]['Pressure_Calc_MPa'] = np.nan
        runData[24] = [np.nan] * len(runData[0])
    graphLabel.configure(text='P_calc cleared.')


# --- Set Fit CSV Path Function ---
def set_fit_csv():
    global fit_results_csv_path, fitCsvLabel
    path = filedialog.asksaveasfilename(
        title='Choose / Create Fit Results CSV',
        defaultextension='.csv',
        filetypes=(('CSV files', '*.csv'),)
    )
    if path:
        fit_results_csv_path = path
        fitCsvLabel.configure(text=f'CSV: {os.path.basename(path)}')
        print(f'Fit results CSV set to: {path}')
    else:
        fitCsvLabel.configure(text='CSV: (not set)')

# --- Set dn/dt CSV Path Function ---
def set_dndt_csv():
    global dn_dt_csv_path, dn_dt_csv_label
    path = filedialog.asksaveasfilename(
        title='Choose / Create dn/dt Results CSV',
        defaultextension='.csv',
        filetypes=(('CSV files', '*.csv'),)
    )
    if path:
        dn_dt_csv_path = path
        if dn_dt_csv_label:
            dn_dt_csv_label.configure(text=f'CSV: {os.path.basename(path)}')
        print(f'dn/dt CSV set to: {path}')
    else:
        if dn_dt_csv_label:
            dn_dt_csv_label.configure(text='CSV: (not set)')


# --- Calculate dn/dt Function (interval sweep) ---
def calculate_dn_dt():
    global runData, dn_dt_start_var, dn_dt_end_var, dn_dt_interval_var
    global output_dir, run_id, graphLabel, dn_dt_results_label
    global plot_fig, plot_canvas, plot_ax4

    if not runData or len(runData) < 30:
        if dn_dt_results_label: dn_dt_results_label.configure(
            text="Error: Run 'Generate Graph' or 'Import' first.", fg='red')
        return

    plot_df = runData[27]
    if not isinstance(plot_df, pd.DataFrame):
        if dn_dt_results_label: dn_dt_results_label.configure(
            text='Error: No plot data available.', fg='red')
        return

    # ── Parse inputs ────────────────────────────────────────────────────────
    try:
        period_start = float(dn_dt_start_var.get())
        period_end   = float(dn_dt_end_var.get())
        interval_h   = float(dn_dt_interval_var.get())
        if period_start >= period_end:
            dn_dt_results_label.configure(
                text='Error: Start time must be before end time.', fg='red'); return
        if interval_h <= 0:
            dn_dt_results_label.configure(
                text='Error: Interval must be a positive number.', fg='red'); return
        if interval_h > (period_end - period_start):
            dn_dt_results_label.configure(
                text='Error: Interval is larger than the total period.', fg='red'); return
    except ValueError:
        dn_dt_results_label.configure(
            text='Error: Start, End, and Interval must all be numeric.', fg='red')
        return

    try:
        sigma_n_col = 'Moles_Uncertainty_mmol'
        results = []
        window_starts = np.arange(period_start, period_end, interval_h)

        # ── Clear previous dn/dt overlays ───────────────────────────────────
        if plot_fig is not None and plot_ax4 is not None:
            plot_ax4.cla()
            plot_ax4.yaxis.set_label_position('right')
            plot_ax4.yaxis.tick_right()
            plot_ax4.set_ylabel('dn/dt (mmol/hr)', color='darkorchid')
            plot_ax4.tick_params(axis='y', labelcolor='darkorchid')
            plot_ax4.spines['right'].set_position(('outward', 120))

        midpoints  = []
        rates      = []
        rate_errs  = []

        for idx, win_start in enumerate(window_starts):
            win_end = win_start + interval_h
            df_w = plot_df[
                (plot_df['Time_Hours'] >= win_start) &
                (plot_df['Time_Hours'] <= win_end)
            ].dropna(subset=['Time_Hours', 'Moles_mmol']).copy()

            if len(df_w) < 2:
                print(f'  Skipping interval [{win_start:.3f}, {win_end:.3f}]: < 2 points')
                continue

            t_arr = df_w['Time_Hours'].to_numpy()
            n_arr = df_w['Moles_mmol'].to_numpy()

            # Linear regression slope = dn/dt for this interval
            coeffs    = np.polyfit(t_arr, n_arr, 1)
            dn_dt_hr  = coeffs[0]          # mmol/hr
            dn_dt_s   = dn_dt_hr / 3600.0  # mmol/s
            delta_n   = n_arr[-1] - n_arr[0]
            delta_t_h = t_arr[-1] - t_arr[0]
            midpt     = (win_start + win_end) / 2.0

            # Uncertainty
            if sigma_n_col in df_w.columns:
                sig_s = df_w[sigma_n_col].iloc[0]
                sig_e = df_w[sigma_n_col].iloc[-1]
                sigma_dn_dt_hr = (np.sqrt(sig_s**2 + sig_e**2) / delta_t_h
                                  if delta_t_h > 0 else np.nan)
                sigma_dn_dt_s  = sigma_dn_dt_hr / 3600.0
            else:
                sigma_dn_dt_hr = np.nan
                sigma_dn_dt_s  = np.nan

            # Control temperature at midpoint
            temp_mid = np.nan
            if 'Temp_Control_C' in df_w.columns:
                vt = df_w['Temp_Control_C'].dropna()
                if not vt.empty: temp_mid = vt.iloc[len(vt)//2]

            midpoints.append(midpt)
            rates.append(dn_dt_hr)
            rate_errs.append(sigma_dn_dt_hr if not np.isnan(sigma_dn_dt_hr) else 0)

            results.append({
                'Window_Index':            idx + 1,
                'Start_Time_hr':           win_start,
                'End_Time_hr':             win_end,
                'Midpoint_Time_hr':        midpt,
                'dn_dt_mmol_per_hr':       dn_dt_hr,
                'dn_dt_mmol_per_s':        dn_dt_s,
                'sigma_dn_dt_mmol_per_hr': sigma_dn_dt_hr,
                'sigma_dn_dt_mmol_per_s':  sigma_dn_dt_s,
                'Delta_n_mmol':            delta_n,
                'Delta_t_hr':              delta_t_h,
                'Control_Temp_mid_C':      temp_mid,
            })

        if not results:
            dn_dt_results_label.configure(
                text='Error: No valid intervals found in the specified period.', fg='red')
            return

        # ── Plot dn/dt on dedicated 4th y-axis ──────────────────────────────
        if plot_fig is not None and plot_ax4 is not None and plot_canvas is not None:
            try:
                mid_arr  = np.array(midpoints)
                rate_arr = np.array(rates)
                err_arr  = np.array(rate_errs)
                _lw_dn = float(line_thickness_var.get()) if line_thickness_var else 1.8
                plot_ax4.errorbar(
                    mid_arr, rate_arr, yerr=err_arr,
                    fmt='o-', color='darkorchid', linewidth=_lw_dn,
                    markersize=5, capsize=3, label='dn/dt (mmol/hr)',
                    gid='dndt_axis'
                )
                plot_ax4.axhline(0, color='darkorchid', linewidth=0.6,
                                  linestyle=':', alpha=0.5)
                plot_ax4.set_visible(True)
                plot_ax4.relim()
                plot_ax4.autoscale_view()
                plot_fig.canvas.toolbar.update()  # reset home stack
                _rebuild_outside_legend(plot_fig)
                plot_canvas.draw()
            except Exception as plot_err:
                print(f'Warning: Could not plot dn/dt axis: {plot_err}')

        # ── Summary label (in dn/dt section) ────────────────────────────────
        mean_rate = np.mean(rates)
        min_rate  = np.min(rates)
        max_rate  = np.max(rates)
        result_text = (
            f"{len(results)} intervals  |  "
            f"Mean dn/dt: {mean_rate:.4e} mmol/hr  |  "
            f"Range: [{min_rate:.3e}, {max_rate:.3e}] mmol/hr\n"
            f"Period: {period_start:.3f}\u2013{period_end:.3f} hr  |  "
            f"Interval: {interval_h:.3f} hr"
        )
        dn_dt_results_label.configure(text=result_text, fg='darkorchid')
        print(result_text)

        # ── Auto-save to output_dir (new file each run) ───────────────
        from datetime import datetime
        if output_dir and run_id:
            ts = datetime.now().strftime('%y%m%d_%H%M%S')
            dndt_path = os.path.join(output_dir, f'{run_id}_{ts}_dndt.csv')
            try:
                pd.DataFrame(results).to_csv(dndt_path, index=False, float_format='%.6e')
                graphLabel.configure(text=f'dn/dt saved: {os.path.basename(dndt_path)}')
                _log_live(f'dn/dt: {len(results)} intervals saved to {os.path.basename(dndt_path)}')
            except Exception as csv_err:
                graphLabel.configure(text=f'Warning: dn/dt save failed: {csv_err}')
        else:
            graphLabel.configure(text='Warning: Set Output Folder before running dn/dt.')

    except Exception as e:
        dn_dt_results_label.configure(text=f'Error: {e}', fg='red')
        print(f'Error in calculate_dn_dt: {e}')
        import traceback; traceback.print_exc()


# --- Set Output Directory ---
def set_output_dir():
    global output_dir, outputDirLabel
    default = os.path.join(os.path.expanduser('~'),
        'Lehigh University Dropbox', 'ENG-MATSGroup',
        'MATS', 'Data', 'Processed - Run')
    start = default if os.path.isdir(default) else os.path.expanduser('~')
    path = filedialog.askdirectory(title='Select Output Folder', initialdir=start)
    if path:
        output_dir = path
        outputDirLabel.configure(
            text=f'Output: ...{os.sep}{os.path.basename(path)}', fg='darkgreen')
        print(f'Output directory set: {path}')
    else:
        outputDirLabel.configure(text='Output: (not set)', fg='gray')
