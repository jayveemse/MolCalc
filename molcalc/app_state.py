# Clears out any variables, just to be safe.

import tkinter as tk
from tkinter import * # Keep this for constants like HORIZONTAL, W, etc.
from tkinter import ttk
from tkinter import filedialog
from tkinter.ttk import Progressbar
import pandas as pd
import matplotlib.pyplot as plt
from  matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import plotly.graph_objects as go
import numpy as np
import math
import os
import re
import sys
import json
import ast
from time import perf_counter
from time import perf_counter_ns
import seaborn as sns
from scipy.optimize import curve_fit

# --- Global variables for file paths ---
data_filename = ""
temp_profile_file = ""
layout_file = ""
mating_table_file = ""
fur_file = ""
hps_file = ""
runData = [] # This will store all final data for plotting/export
runBool = False
imageViewer = None # For the main Moles/P/T plot
temp_viewer_window = None
baselineEdited = False
z_temp_cutoff_var = None
z_offset_var = None
p_calc_start_time_var = None
interpolate_temps_var = None
plot_fig = None      # Global figure reference for fit overlay
plot_ax2 = None      # Global pressure axis reference for fit overlay
plot_canvas = None   # Global canvas reference for fit overlay
fit_results_csv_path = ""   # Persistent path for appending fit results
dn_dt_start_var = None   # Widget var for dn/dt start time
dn_dt_end_var   = None   # Widget var for dn/dt end time
dn_dt_button    = None   # dn/dt Calculate button
dn_dt_csv_path = ""         # Persistent path for dn/dt results
dn_dt_csv_label = None      # Label widget showing dn/dt CSV path
dn_dt_interval_var = None  # Widget var for dn/dt interval width
run_id = ""             # RunID extracted from data file
calc_step_var = None       # Widget var for calculation step interval
output_dir = ""             # Output folder for auto-saved files
info_log = []               # Collects run info for the info window/file
info_window = None          # Toplevel for displaying run info
plot_ax4 = None            # 4th y-axis for dn/dt
dn_dt_results_label = None # Results label in dn/dt section
info_text_widget = None    # Direct ref to ScrolledText in info window
pcalc_button = None        # Calculate P_calc button
save_plot_button = None    # Save plot PNG/SVG button
export_fit_button = None   # Export fit CSV button
last_fit_result = None     # Stores most recent fit result for export
fit_csv_path = ""          # Persistent fit CSV path for this run
p_offset_var = None        # StringVar for P_calc pressure offset (MPa)
pcalc_info_label = None    # Label showing auto-calculated offset
p_calc_end_time_var = None   # End time for P_calc window
p_calc_step_var = None       # Step interval for P_calc loop
p_zero_start_var = None    # Vacuum window start time for P zero offset
p_zero_end_var   = None    # Vacuum window end time for P zero offset
p_zero_manual_var = None   # Manual P zero override (MPa)
line_thickness_var = None  # DoubleVar: curve linewidth

# --- Furniture table globals ---
fur_mass_entries    = {}    # UID -> StringVar (mass in grams)
fur_internal_checks = {}    # UID -> BooleanVar (is internal/subtractive)
fur_table_inner     = None  # Inner Frame holding table rows
_internal_uids_set  = set() # UIDs from MLD-FUR sheets
vol_info_label      = None  # Label showing vol before/after correction

# --- Chemical species globals ---
chem_species_var  = None  # StringVar: selected species
chem_mass_var     = None  # StringVar: mass in grams
chem_density_var  = None  # StringVar: custom density g/cm³

pressure_col_var  = None   # StringVar: selected PT pressure column


# --- Fit & Uncertainty Widgets ---
fit_start_time_var = None
fit_end_time_var = None
fit_results_label = None
calculateFitButton = None
sigma_p_var = None # <-- NEW
sigma_v_var = None # <-- NEW
sigma_t_var = None # <-- NEW
# ---

exportTempButton = None # Initialize button variables
tempViewButton = None
exportPlotButton = None
importTempButton = NoneexportHtmlButton = None  # Export HTML plot button
gas_species_var = None  # Gas species for Z lookup
texpansion_button = None

# fur_mass_var removed — replaced by fur_mass_entries table
_sorted_tc_idx   = None      # Pre-computed sorted TC index order for interpolation
_x_tc_sorted     = None      # Pre-computed sorted TC positions (mm)
_x_target_interp = None      # Pre-computed interp target array


# --- Pressure Trace Synthesizer globals ---
synth_p0_var         = None   # StringVar: initial pressure (MPa)
synth_t0_var         = None   # StringVar: initial temperature for n calc (degC)
synth_ambient_var    = None   # StringVar: ambient / cold-end temperature (degC)
synth_total_time_var = None   # StringVar: total simulation time (hr)
synth_dt_var         = None   # StringVar: time step (hr)
synth_profile_mode_var = None # StringVar: 'uniform' | 'gradient' | 'profile_csv' | 'loaded'
synth_spatial_file   = ''     # Path to 1-D spatial profile CSV (z_mm, T_C)
synth_spatial_label  = None   # Label widget showing spatial file name
synth_schedule_text  = None   # Text widget: furnace schedule (time, T pairs)
synth_n_label        = None   # Label showing derived n (mol)
synth_status_label   = None   # Status / results label
synth_run_button     = None   # Run Synthesizer button
synth_coarse_vol     = None   # Computed coarseVol (m3/bin) without raw data
synth_loaded_profile = None   # Tuple (z_arr, T_arr_K) for 'loaded' spatial mode
synth_vol_label      = None   # Label showing computed volume info
synth_lookup_table   = None   # pd.DataFrame: rows=TC setpoint (degC), cols=z_mm
synth_lookup_z_mm    = None   # np.array of z positions (mm) from CSV columns
synth_lookup_label   = None   # Label widget showing which profile CSV is loaded
