"""
volume_profile.py — standalone MolCalc volume profile + single-moment mole calc.

Run:  python volume_profile.py      (or  %run volume_profile.py  in Jupyter)
You will be prompted for:
  1. Autoclave Layout file (.xlsx)
  2. MLD - FUR (.xlsx)
  3. MLD - HPS (.xlsx)
  4. Surface Mating Table (.xlsx)
  5. (Mole calc window) z, T points along the system axis, a uniform pressure,
     and an optional z offset — or "Skip" for volume only
  6. Where to save the output Excel file

Mole calc:
  - T(z): natural cubic spline through your (z, T) points, evaluated at the
    centre of every 0.01 mm volume slice. Outside your z range T is held at the
    first/last value (no spline extrapolation).
  - Z(T, P): N2_Z.npz from generate_Z_table.py (Dropbox File Dependencies),
    same clamping as MolCalc v0_8 (T/P clamped to table range, Z clipped 0.5–2).
  - n = sum_i  P * V_i / (Z_i * R * T_i)

Output workbook:
  - "Mole Calc":      result + inputs (only if the mole calc was run)
  - "T Input":        your z, T points
  - "Volume Profile": volumeDF (0.01 mm slices; per-part volume mm^3/slice, Total Volume,
                      and T_C, T_K, Z, n_slice_mmol, n_cumulative_mmol if mole calc ran)
  - "Part Summary":   total volume per part (mm^3 and mL) + material
  Plus a .png of the V + T plot next to the .xlsx.

The geometry functions below are copied verbatim from MolCalc_v0_8.ipynb
(getPartVolProfile, safe_parse_profile, _build_profile_sequence,
_find_internal_alignment_position, getSystemVolumeProfile). If you change the
volume logic in the notebook, re-copy those functions here.
"""
import ast
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np
import pandas as pd

# ── Default folder for file dialogs ──────────────────────────────────────────
_DROPBOX_DEPS = os.path.join(
    os.path.expanduser('~'), 'Lehigh University Dropbox',
    'ENG-MATSGroup', 'MATS - Collaboration', 'Data', 'Parsers', 'MolCalc', 'File Dependencies')
_REPO_DEPS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dependencies')
DEFAULT_DIR = next((d for d in (_DROPBOX_DEPS, _REPO_DEPS) if os.path.isdir(d)),
                   os.path.expanduser('~'))


# ── Stand-ins for the notebook's GUI globals ─────────────────────────────────
class _ConsoleLabel:
    def configure(self, text='', **_):
        print(text)

class _NoWindow:
    def update_idletasks(self):
        pass

graphLabel = _ConsoleLabel()
window = _NoWindow()

def _log_live(text):
    print(str(text))


# =============================================================================
# Functions copied from MolCalc_v0_8.ipynb
# =============================================================================

def getPartVolProfile(data):
    APdata = data["Axial Position (mm)"]
    CSdata = data["Cross-Sectional Area (mm^2)"]
    TMdata = data["Transition Model"]
    
    areaProfile = []
    
    for i in range(len(APdata) - 1):
        # 1. Calculate the exact number of 0.1mm slices in this segment
        segment_length = APdata[i+1] - APdata[i]
        # Use round to handle float math like 0.700000000001
        num_slices = int(round(segment_length / 0.01))
        
        # 2. Create the x-array for the eval() functions
        # This creates exactly 'num_slices' points starting from the current position
        x = np.linspace(APdata[i], APdata[i+1], num_slices, endpoint=False)
        
        if TMdata[i] != 'Constant':
            try: 
                sectionAreaProfile = eval(TMdata[i])
                # Ensure the eval result matches our slice count
                if isinstance(sectionAreaProfile, np.ndarray):
                    if len(sectionAreaProfile) != num_slices:
                        # If eval returns the wrong size, force it to num_slices
                        sectionAreaProfile = np.resize(sectionAreaProfile, num_slices)
                else:
                    sectionAreaProfile = np.full(num_slices, sectionAreaProfile)
            except Exception as e: 
                print(f"Error eval TM '{TMdata[i]}': {e}")
                sectionAreaProfile = np.full(num_slices, CSdata[i])
        else: 
            # Constant area for the duration of this segment
            sectionAreaProfile = np.full(num_slices, CSdata[i])
            
        areaProfile.append(sectionAreaProfile)

    areaProfile = np.concatenate(areaProfile)
    
    # Each entry represents the volume of a 0.1mm thick slice
    volumeProfile = [0.01 * slice_area for slice_area in areaProfile]
    
    return volumeProfile


def safe_parse_profile(profile):
    if isinstance(profile, str): profile = profile.strip()
    if isinstance(profile, str) and (profile.endswith("'") or profile.endswith('"')): profile = profile[:-1]
    if isinstance(profile, str) and (profile.startswith("'") or profile.startswith('"')): profile = profile[1:]
    if isinstance(profile, str):
        try:
            parsed = ast.literal_eval(profile)
        except Exception as e:
            raise ValueError(f"Invalid profile string: {profile}") from e
        # Strip leading/trailing whitespace from all keys — guards against
        # accidental spaces in spreadsheet cells (e.g. ' Axial Position (mm)')
        if isinstance(parsed, dict):
            return {k.strip(): v for k, v in parsed.items()}
        return parsed
    # Already a dict (pre-parsed) — sanitise keys the same way
    if isinstance(profile, dict):
        return {k.strip(): v for k, v in profile.items()}
    return profile


def _build_profile_sequence(relevantParts, planeTable):

    isReversed = False
    previousIsReversed = False
    cumulativeOffset = 0
    maxAxialPosition = 100000
    
    # Dictionary to hold Part Volume Series before building the final volumeDF
    part_series_dict = {} 

    # Initialize the output DataFrame structure
    colNames = ["Axial Position"]
    dummyarray = np.empty((maxAxialPosition,))
    dummyarray[:] = np.nan
    volumeDF = pd.DataFrame(dummyarray, columns=colNames)

    mate_positions = []
    placement_summaries = []

    if relevantParts.empty:
        return volumeDF, mate_positions, placement_summaries, "Error: No parts to process in sequence."

    # Initial part setup (Part 0)
    uid0 = str(relevantParts["UID"].iloc[0])

    mate_positions.append({
        "Part": f"Part_0_{uid0}",
        "Previous Mate Position": None,
        "Next Mate Position": None  # filled in at i=0
    })

    # --- Main Mating and Volume Calculation Loop ---
    for i in range(len(relevantParts) - 1):
        try:
            previousPart = safe_parse_profile(relevantParts["Profile"].iloc[i])
            nextPart = safe_parse_profile(relevantParts["Profile"].iloc[i + 1])
            
            if not isinstance(previousPart, dict) or not isinstance(nextPart, dict):
                raise ValueError(f"Parsed profile is not a dictionary at index {i} or {i+1}")
            
            previousPartPlanes = previousPart.get('Contact Plane')
            nextPartPlanes = nextPart.get('Contact Plane')
            if previousPartPlanes is None or nextPartPlanes is None:
                raise KeyError(f"'Contact Plane' missing in profile at index {i} or {i+1}")
                
            
            # Calculate the reversed version of the next part's planes
            nextPartPlanesReversed = [
                ''.join([c if c!='^' and c!='v' else '^' if c=='v' else 'v' for c in p]) 
                for p in reversed(nextPartPlanes)
            ]
            
            
            previousPartAxialPositions = previousPart.get('Axial Position (mm)')
            nextPartAxialPositions = nextPart.get('Axial Position (mm)')
            if previousPartAxialPositions is None or nextPartAxialPositions is None:
                raise KeyError(f"'Axial Position (mm)' missing in profile at index {i} or {i+1}")
            
            previousPartVolumeProfile = getPartVolProfile(previousPart)

            # --- Initial Part Placement ---
            if i == 0:
                colName0 = f"Part_0_{uid0}"
                first_part_slice_idx = list(range(len(previousPartVolumeProfile)))
                
                if first_part_slice_idx:
                    part_series_dict[colName0] = pd.Series(previousPartVolumeProfile, index=first_part_slice_idx)
                    cumulativeOffset = (len(previousPartVolumeProfile)) / 100.0
                else:
                    cumulativeOffset = 0.0

            # Reverse the previous part's data if it was reversed in the previous step
            if isReversed:
                previousPartPlanes = [
                    ''.join([c if c!='^' and c!='v' else '^' if c=='v' else 'v' for c in p]) 
                    for p in reversed(previousPartPlanes)
                ]
                previousPartAxialPositions.reverse()
                previousPartVolumeProfile.reverse()
                previousIsReversed = True
            else:
                previousIsReversed = False


            # --- Mating Logic (Finding Valid Mates) ---
            mateList = []
            for plane in previousPartPlanes:
                matches = planeTable.loc[planeTable['Plane'] == plane]
                if not matches.empty and 'Valid Mates' in matches.columns:
                    mates_str = matches['Valid Mates'].iloc[-1]
                    mateList.append(mates_str.split(', ') if pd.notna(mates_str) else [])
                else:
                    mateList.append([])
                    

            normalMates = []
            reversedMates = []
            
            # Loop backwards through previous part's planes (higher index first for 'top-most' logic)
            for j in reversed(range(len(mateList))):
                # Find normal orientation mates
                for k in range(len(nextPartPlanes)):
                    if nextPartPlanes[k] in mateList[j]:
                        normalMates.append([previousPartPlanes[j], j, nextPartPlanes[k], k])

                # Find reversed orientation mates
                for k in range(len(nextPartPlanesReversed)):
                    if nextPartPlanesReversed[k] in mateList[j]:
                        reversedMates.append([previousPartPlanes[j], j, nextPartPlanesReversed[k], k])

                    # Optimization for REST mates (only keep if no non-REST mate is found)
                    is_rest = lambda s: "REST" in str(s).upper()
                    nn = [c for c in normalMates if not is_rest(c[0])]
                    rr = [c for c in reversedMates if not is_rest(c[0])]
                    if nn or rr:
                        normalMates, reversedMates = nn, rr
            
            # --- Mate Selection Logic (Corrected Priority Structure) ---
            
            validMateList = None
            isReversed = False
            
            # --- 1. Priority 1: LID Mates (Highest Priority with Reversed Preference) ---
            
            # Find LID Mates (Logic remains the same)
            find_mate = lambda mates, names: next((m for m in mates if any(n in str(m[0]).upper() or n in str(m[2]).upper() for n in names)), None)
            lid_normal_mate = find_mate(normalMates, ['LID'])
            lid_reversed_mate = find_mate(reversedMates, ['LID'])
            
            # Reset validMateList here to ensure clean selection
            validMateList = None
            isReversed = False
            
            # A. Check for the CRITICAL Reversed LID mate first
            if lid_reversed_mate:
                # If a reversed LID mate exists, select it immediately as highest priority
                if not lid_normal_mate:
                    # Unique reversed LID mate
                    validMateList = lid_reversed_mate
                    isReversed = True
                    print(f"Reversed (Unique LID priority): {relevantParts['UID'].iloc[i+1]}")
                else:
                    # Both exist (Tie-breaker). Since the reversed mate is required, 
                    # we explicitly check the 'topmost' plane index (j) or prefer reverse.
                    jn_lid = lid_normal_mate[1]
                    jr_lid = lid_reversed_mate[1]
                    
                    # Explicitly prefer reverse if the reversed mate is equal or better 
                    # in terms of 'topmost' index (jr_lid <= jn_lid)
                    if jr_lid <= jn_lid:
                        validMateList = lid_reversed_mate
                        isReversed = True
                        print(f"Reversed (LID tie-breaker preference): {relevantParts['UID'].iloc[i+1]}")
                    else:
                        # Only use normal if reversed is demonstrably lower priority by index
                        validMateList = lid_normal_mate
                        isReversed = False
            
            # B. Fallback to Unique Normal LID mate if no reversed LID mate was selected
            elif lid_normal_mate:
                # Only a normal LID mate exists
                validMateList = lid_normal_mate
                isReversed = False
                
            # If validMateList is still None, the code proceeds to the 'if validMateList is None:' block below.

            # --- 2. Priority 2: Standard Multi-Mate Checks (Runs ONLY if no LID mate was found) ---
            
            # Only proceed if we haven't selected a mate yet AND we have multi-mates
            elif len(normalMates) > 0 and len(reversedMates) > 0:
                jn, jr = normalMates[0][1], reversedMates[0][1]

                # Priority 2a: Specific part UIDs
                # if any(x in relevantParts["UID"].iloc[i+1] for x in ["AC","GKT","GPA"]):
                #     validMateList = normalMates[0]
                #     isReversed = False
                # Priority 2b: Same mate plane index (prefer normal)
                if jr == jn:
                    validMateList = normalMates[0]
                    print(f"Normal and reversed for {relevantParts['UID'].iloc[i+1]} have same index; resorting to normal")
                    isReversed = False
                # Priority 2c: Honor topmost plane 
                elif jr != jn:
                    if jr > jn:
                        validMateList = reversedMates[0]
                        isReversed = True
                        print(f"Reversed to honor top-most plane: {relevantParts['UID'].iloc[i+1]}")
                    else:
                        validMateList = normalMates[0]
                        isReversed = False
                # Priority 2d: GASK/ORING planes 
                elif find_mate(normalMates, ['GASK','ORING']):
                    validMateList = normalMates[0]
                    isReversed = False
                    print(f"Normal mate for GASK/ORING mate: {relevantParts['UID'].iloc[i+1]}")
                elif find_mate(reversedMates, ['GASK','ORING']):
                    validMateList = reversedMates[0]
                    isReversed = True
                    print(f"Reversed (gask/oring): {relevantParts['UID'].iloc[i+1]}")
                # Default to normal match
                else:
                    validMateList = normalMates[0]
                    isReversed = False
                    print(f"Nothing else hit, resorting to first normal: {relevantParts['UID'].iloc[i+1]}")

            # --- 3. Priority 3: Simple Mate Cases (Runs ONLY if previous checks failed) ---
            
            # Case 3a: Only Normal Mates exist
            elif len(normalMates) > 0 and len(reversedMates) == 0:
                validMateList = normalMates[0]
                isReversed = False
                print(f"Only normal mates exist: {relevantParts['UID'].iloc[i+1]}")
            # Case 3b: Only Reversed Mates exist
            elif len(reversedMates) > 0 and len(normalMates) == 0:
                validMateList = reversedMates[0]
                isReversed = True
                print(f"Reversed: {relevantParts['UID'].iloc[i+1]}")

            # Final check before placement
            if validMateList is None:
                raise ValueError(f"No valid mates for {relevantParts['UID'].iloc[i+1]} to {relevantParts['UID'].iloc[i]}.")

            # --- Volume Profile Placement ---
            nextPartVolumeProfile = getPartVolProfile(nextPart)
            
            # Reverse next part's profile and axial positions if reversed mate was selected
            if isReversed:
                nextPartAxialPositions.reverse()
                x_max = max(nextPartAxialPositions)
                nextPartAxialPositions = [x_max - x for x in nextPartAxialPositions]
                nextPartVolumeProfile.reverse()

            j = validMateList[1]  # Index of the mating plane on the previous part
            k = validMateList[3]  # Index of the mating plane on the next part

            prev_part_end = max(previousPartAxialPositions)
            next_start = min(nextPartAxialPositions)

            # Calculate the distance of the previous mate plane from the previous part's end
            if previousIsReversed:
                d_prev = previousPartAxialPositions[j]
            else:
                d_prev = prev_part_end - previousPartAxialPositions[j]

            # Calculate the distance of the next mate plane from the next part's start
            d_next = nextPartAxialPositions[k]

            # Calculate the axial overlap/gap (part_Offset)
            if previousPartAxialPositions[j] == prev_part_end and nextPartAxialPositions[k] == next_start:
                part_Offset = 0.0
            else:
                part_Offset = d_prev + d_next

            part_length = (len(nextPartVolumeProfile)) / 100.0
            start_pos = cumulativeOffset - part_Offset
            end_pos = start_pos + part_length
            #next_mate = round(start_pos + nextPartAxialPositions[k], 3)

            # Insert next part's volume data into the part_series_dict
            next_part_uid = relevantParts['UID'].iloc[i + 1]
            colName = f"Part_{i + 1}_{next_part_uid}"
            
            slice_start_idx = int(round(100 * start_pos))
            effective_start_mm = slice_start_idx / 100.0
            next_mate = round(effective_start_mm + nextPartAxialPositions[k], 3)
            slice_end_idx = slice_start_idx + len(nextPartVolumeProfile)
            
            part_series_dict[colName] = pd.Series(nextPartVolumeProfile, index=range(slice_start_idx, slice_end_idx))

            # Update placement summaries and mate positions (includes reversal status)
            reversal_status = "Reversed" if isReversed else "Normal"
            uid_prev = relevantParts['UID'].iloc[i]
            summary = [
                (f"{uid_prev} mated to {next_part_uid} at {next_mate} mm ({reversal_status})"),
                (f"{validMateList[0]} → {validMateList[2]}"),
                (f"Calculated Length of {next_part_uid}: {part_length}")
            ]
            placement_summaries.append(summary)

            # Update previous part's next mate and append new part with correct interface position
            mate_positions[i]["Next Mate Position"] = next_mate
            mate_positions.append({
                "Part": f"Part_{i + 1}_{next_part_uid}",
                "Previous Mate Position": next_mate,
                "Next Mate Position": None  # filled in next iteration
            })

            cumulativeOffset = start_pos + part_length

        except (ValueError, KeyError, IndexError, TypeError) as e:
            error_msg = (
                f"Error processing part {i + 1} ({relevantParts['UID'].iloc[i + 1]} "
                f"mating with {relevantParts['UID'].iloc[i]}): {e}"
            )
            return pd.DataFrame(), [], [], error_msg

    # --- Final calculations and DataFrame Assembly ---
    
    # Determine max length for the final DataFrame
    max_idx = max(idx for series in part_series_dict.values() for idx in series.index) if part_series_dict else 0
    
    # Ensure the final DataFrame size is sufficient
    final_size = max(max_idx + 1, int(maxAxialPosition)) 

    indexList = [round(0.01 * i, 2) for i in range(final_size)]
    volumeDF = pd.DataFrame({'Axial Position': indexList})

    # Add all collected part series
    for colName, series in part_series_dict.items():
        volumeDF[colName] = series.reindex(volumeDF.index)

    volumeDF["Total Volume"] = volumeDF.filter(like='Part_').sum(axis=1)
    
    return volumeDF, mate_positions, placement_summaries, None


def _find_internal_alignment_position(relevantParts_df, safe_parse_profile, df_label="Unknown"):
    """
    Searches through all parts for 'MP-INTERNAL' planes.
    Reports findings to console for debugging.
    """
    print(f"\n--- Searching for MP-INTERNAL in {df_label} Sequence ---")
    
    for index, row in relevantParts_df.iterrows():
        uid = row['UID']
        try:
            profile_data = safe_parse_profile(row['Profile'])
            planes = profile_data.get('Contact Plane', [])
            positions = profile_data.get('Axial Position (mm)', [])
            
            # Debug: Log that we are checking this part
            # print(f"  Checking Part: {uid} (found {len(planes)} planes)")

            for plane_index, plane_name in enumerate(planes):
                # Ensure we have a string to check against
                p_name_str = str(plane_name).upper() if plane_name else ""
                
                if 'MP-INTERNAL' in p_name_str:
                    if plane_index < len(positions):
                        alignment_pos_mm = positions[plane_index]
                        
                        # --- THE DEBUG PRINT YOU REQUESTED ---
                        print(f"  [FOUND] '{plane_name}' on Part: {uid}")
                        print(f"  [INFO] Axial position: {alignment_pos_mm} mm (local to part)")
                        
                        return alignment_pos_mm
                    else:
                        print(f"  [ERROR] Found '{plane_name}' on {uid} but no axial position index {plane_index} exists.")
        
        except Exception as e:
            print(f"  [WARNING] Error parsing profile for part {uid}: {e}")
            continue
            
    print(f"  [RESULT] No 'MP-INTERNAL' plane found in {df_label} sequence.")
    return None


def getSystemVolumeProfile(partList, mating_table_path, fur_path, hps_path):
    global graphLabel
    
    # --- 1. File Reading and Part Profile Preparation ---
    # Authoritative sheet lists — only these contain valid UID/Profile geometry
    FUR_SHEETS = ['CRU', 'LID', 'PLU', 'VRE']
    HPS_SHEETS = ['AC', 'GKT', 'NZ', 'TU']

    def _load_sheets(path, sheet_names, label, material_col=None):
        """Load only the sheets that exist in the file; warn about any missing ones.
        If material_col is given, also returns a uid->material dict."""
        try:
            all_sheets = pd.ExcelFile(path).sheet_names
        except Exception as e:
            raise IOError(f'Cannot open {label}: {e}')
        available = [s for s in sheet_names if s in all_sheets]
        missing   = [s for s in sheet_names if s not in all_sheets]
        if missing:
            print(f'  Warning: {label} missing expected sheets: {missing} — skipped')
        if not available:
            raise ValueError(f'{label} contains none of the expected sheets: {sheet_names}')
        frames = []
        uid_mat = {}
        for s in available:
            df_s = pd.read_excel(path, sheet_name=s)
            if 'UID' in df_s.columns and 'Profile' in df_s.columns:
                frames.append(df_s[['UID', 'Profile']].dropna())
            else:
                print(f'  Warning: {label} sheet "{s}" missing UID/Profile columns — skipped')
            if material_col and material_col in df_s.columns and 'UID' in df_s.columns:
                for _, row in df_s[['UID', material_col]].dropna().iterrows():
                    uid_mat[str(row['UID'])] = str(row[material_col])
        if not frames:
            raise ValueError(f'{label}: no valid UID/Profile data found in sheets {available}')
        return pd.concat(frames, ignore_index=True), uid_mat

    try:
        planeTable   = pd.read_excel(mating_table_path)
        partsDF_Internal, uid_mat_fur = _load_sheets(fur_path, FUR_SHEETS, 'MLD-FUR', material_col='Chemicals')
        partsDF_External, uid_mat_hps = _load_sheets(hps_path, HPS_SHEETS, 'MLD-HPS', material_col='Material')
        uid_to_material = {**uid_mat_fur, **uid_mat_hps}
        _log_live(f'MLD-FUR: loaded {len(partsDF_Internal)} parts')
        _log_live(f'MLD-HPS: loaded {len(partsDF_External)} parts')

    except FileNotFoundError as e:
        print(f'Error: Could not find required geometry file: {e.filename}')
        graphLabel.configure(text=f'Error: File not found: {os.path.basename(e.filename)}')
        window.update_idletasks()
        return None
    except Exception as e:
        print(f'Error reading geometry files: {e}')
        graphLabel.configure(text=f'Error reading geometry files: {e}')
        window.update_idletasks()
        return None

    partsDF_All = pd.concat([partsDF_Internal, partsDF_External], ignore_index=True)



    # --- 2. Filter Input List to Create Master relevantParts List ---
    partList = partList.dropna()
    relevantParts = pd.DataFrame(columns=['UID', 'Profile'])

    for index, row in partList.iterrows():
        partProfile = partsDF_All.loc[partsDF_All['UID'] == row['UID']]
        if not partProfile.empty:
            relevantParts=pd.concat([relevantParts, partProfile], ignore_index=True)

    if relevantParts.empty:
        graphLabel.configure(text="Error: No relevant parts found based on Layout file.")
        return None

    # --- 3. Split Master List into Internal and External Sequences ---
    internal_uids = partsDF_Internal['UID'].tolist()
    
    relevantParts_Internal = relevantParts[relevantParts['UID'].isin(internal_uids)].reset_index(drop=True)
    relevantParts_External = relevantParts[~relevantParts['UID'].isin(internal_uids)].reset_index(drop=True)

    # --- 4. Generate Two Profiles using _build_profile_sequence ---

    _log_live("--- Building External Profile Sequence ---")
    external_volumeDF, external_mate_positions, external_placement_summaries, error_ext = \
        _build_profile_sequence(relevantParts_External, planeTable)
    
    if error_ext:
        error_msg = f"External Profile Error: {error_ext}"
        print(error_msg)
        graphLabel.configure(text=error_msg)
        window.update_idletasks()
        return None

    # Only attempt to build internal sequence if internal parts exist
    internal_volumeDF = None
    internal_mate_positions = []
    internal_placement_summaries = []
    if not relevantParts_Internal.empty:
        _log_live("--- Building Internal Profile Sequence ---")
        (internal_volumeDF, internal_mate_positions,
         internal_placement_summaries, error_int) = _build_profile_sequence(
            relevantParts_Internal, planeTable)
        if error_int:
            error_msg = f"Internal Profile Error: {error_int}"
            print(error_msg)
            graphLabel.configure(text=error_msg)
            window.update_idletasks()
            return None
    else:
        _log_live("--- No internal parts in layout, skipping internal profile sequence ---")

    # --- 5. Merge/Overlay Profiles based on MP-INTERNAL Alignment ---
    
    # Initialize variables for the final DataFrame
    volumeDF = None
    mate_positionsDF = pd.DataFrame()
    placement_summaries = []
    mate_positions = []
    
    if not relevantParts_Internal.empty:
        
        # Calculate alignment based on MP-INTERNAL plane
        external_alignment_pos = _find_internal_alignment_position(relevantParts_External, safe_parse_profile)
        internal_alignment_pos = _find_internal_alignment_position(relevantParts_Internal, safe_parse_profile)
        
        if external_alignment_pos is None or internal_alignment_pos is None:
            error_msg = "Error: Could not find 'MP-INTERNAL' plane in both external and internal part lists for alignment."
            print(error_msg)
            graphLabel.configure(text=error_msg)
            window.update_idletasks()
            return None
        
        # Calculate the required offset
        alignment_offset_mm = external_alignment_pos - internal_alignment_pos
        alignment_offset_slices = int(round(alignment_offset_mm * 100))
        
        _log_live(f"Alignment calculated: External pos={external_alignment_pos}mm, Internal pos={internal_alignment_pos}mm. Offset={alignment_offset_mm}mm.")

        # Determine the maximum length required for the final combined DataFrame.
        # `shift` re-anchors the combined coordinate system so whichever
        # profile (External or Internal) physically starts first lands at
        # index 0. Previously External always started at index 0, so a
        # negative alignment_offset_slices placed Internal at negative
        # indices — pandas Series assignment then silently dropped that
        # volume (no index overlap with volumeDF's 0..max_len-1 range).
        shift = max(0, -alignment_offset_slices)
        external_start = shift
        internal_start = shift + alignment_offset_slices
        max_idx_external = external_start + len(external_volumeDF)
        max_idx_internal = internal_start + len(internal_volumeDF)
        max_len = max(max_idx_external, max_idx_internal)
        if shift > 0:
            _log_live(f"Volume alignment: Internal starts {shift/100:.2f}mm before "
                       f"External — shifting combined profile so x=0mm is the true "
                       f"start (previously this volume was silently dropped).")
        
        # Initialize final volumeDF
        volumeDF = pd.DataFrame(index=range(max_len))
        volumeDF["Axial Position"] = [round(0.01*i, 2) for i in range(max_len)]
        
        # Copy External Profile (starts at index `external_start`)
        for col in external_volumeDF.columns:
            if col.startswith("Part_"):
                 col_data = pd.Series(
                     external_volumeDF[col].values,
                     index=range(external_start, external_start + len(external_volumeDF))
                 )
                 volumeDF[f"External_{col}"] = col_data
        
        # Copy Internal Profile (starts at index `internal_start`)
        for col in internal_volumeDF.columns:
            if col.startswith("Part_"):
                 col_data = pd.Series(
                     internal_volumeDF[col].values, 
                     index=range(internal_start, internal_start + len(internal_volumeDF))
                 )
                 volumeDF[f"Internal_{col}"] = col_data
        
        # Fill NaN with 0 for summation and calculate Total Volume
        volumeDF = volumeDF.fillna(0)
        volumeDF["Total Volume"] = volumeDF.filter(like='Part_').sum(axis=1)
        
        # Combine summaries and adjust mate positions for plotting
        placement_summaries = external_placement_summaries + internal_placement_summaries
        
        # Adjust internal mate positions by the alignment offset
        adjusted_internal_mates = []
        for mate in internal_mate_positions:
            adjusted_mate = mate.copy()
            if adjusted_mate["Previous Mate Position"] is not None:
                adjusted_mate["Previous Mate Position"] = round(adjusted_mate["Previous Mate Position"] + alignment_offset_mm, 3)
            if adjusted_mate["Next Mate Position"] is not None:
                adjusted_mate["Next Mate Position"] = round(adjusted_mate["Next Mate Position"] + alignment_offset_mm, 3)
            adjusted_internal_mates.append(adjusted_mate)
            
        mate_positions = external_mate_positions + adjusted_internal_mates
        mate_positionsDF = pd.DataFrame(mate_positions).reset_index(drop=True)
        
    else:
        # If there are only external parts, use the external profile as the final result
        volumeDF = external_volumeDF
        mate_positionsDF = pd.DataFrame(external_mate_positions).reset_index(drop=True)
        placement_summaries = external_placement_summaries
        mate_positions = external_mate_positions


    # --- 6. Output and Plotting (Adjusted for combined/split profiles) ---

    print("\nPLACEMENT SUMMARY:")
    _log_live("-" * 60)
    # Ensure placement_summaries is a list of tuples (pos_str, mate_str) for printing
    for pos, mates_summary, length in placement_summaries:
        print(pos)
        print(mates_summary)
        print(length)
        _log_live("-" * 60)

    _log_live("\nMate Positions")
    _log_live(mate_positionsDF)

    _log_live("\nVolume per part (mL):")
    for col in volumeDF.columns:
        if col.startswith("External_Part_") or col.startswith("Internal_Part_"):
            v_mm3 = volumeDF[col].sum(skipna=True)
            _log_live(f"{col}: {v_mm3/1000:.3f} mL")


    print('\npartList:', partList)

    return volumeDF, uid_to_material

# =============================================================================
# Single-moment mole calculation
# =============================================================================

R_GAS = 8.3145          # J/(mol K) — same value MolCalc uses
SLICE_MM = 0.01         # volumeDF resolution (mm per row)
P_UNITS_TO_MPA = {'MPa': 1.0, 'psi': 0.00689475729, 'bar': 0.1}

Z_TABLE_NAME = 'N2_Z.npz'   # produced by generate_Z_table.py


def find_z_table():
    """Look for the Z table in Dropbox File Dependencies, then repo dependencies/,
    then ask. Returns a path, or None to fall back to ideal gas (Z = 1)."""
    for d in (_DROPBOX_DEPS, _REPO_DEPS, os.path.dirname(os.path.abspath(__file__))):
        p = os.path.join(d, Z_TABLE_NAME)
        if os.path.isfile(p):
            return p
    if messagebox.askyesno('Z Table Not Found',
                           f'{Z_TABLE_NAME} was not found in:\n{_DROPBOX_DEPS}\nor\n{_REPO_DEPS}\n\n'
                           'Locate it manually?\n(No = use ideal gas, Z = 1)'):
        p = filedialog.askopenfilename(title=f'Select {Z_TABLE_NAME}', initialdir=DEFAULT_DIR,
                                       filetypes=(('NumPy archive', '*.npz'), ('All files', '*.*')))
        return p or None
    return None


class ZLookup:
    """Z(T [K], P [MPa]) from the generate_Z_table.py .npz — same clamping as MolCalc v0_8."""
    def __init__(self, path):
        from scipy.interpolate import RegularGridInterpolator
        self.path = path
        if path is None:
            self.interp = None
            return
        d = np.load(path)
        self.interp = RegularGridInterpolator((d['T_K'], d['P_MPa']), d['Z'],
                                              bounds_error=False, fill_value=None)
        self.T_min, self.T_max = float(d['T_K'].min()), float(d['T_K'].max())
        self.P_min, self.P_max = float(d['P_MPa'].min()), float(d['P_MPa'].max())

    def __call__(self, T_K, P_MPa):
        T_K = np.asarray(T_K, dtype=float)
        if self.interp is None:
            return np.ones_like(T_K)
        P = np.clip(P_MPa, self.P_min, self.P_max)
        T = np.clip(T_K, self.T_min, self.T_max)
        Z = self.interp(np.column_stack([T, np.full(T.size, P)]))
        return np.clip(Z, 0.5, 2.0)


def parse_zT_text(text):
    """Parse 'z, T' pairs (comma / tab / space separated, one per line).
    Lines that don't start with a number (headers, comments) are skipped."""
    z, T = [], []
    for line in text.splitlines():
        parts = [p for p in line.replace(',', ' ').replace('\t', ' ').replace(';', ' ').split() if p]
        if len(parts) < 2:
            continue
        try:
            zi, Ti = float(parts[0]), float(parts[1])
        except ValueError:
            continue
        z.append(zi)
        T.append(Ti)
    if len(z) < 2:
        raise ValueError('Need at least 2 (z, T) points.')
    z, T = np.array(z), np.array(T)
    order = np.argsort(z)
    z, T = z[order], T[order]
    if np.any(np.diff(z) == 0):
        dup = z[:-1][np.diff(z) == 0]
        raise ValueError(f'Duplicate z values: {sorted(set(dup.tolist()))}')
    return z, T


def build_T_profile(z_pts, T_pts_C, z_slices):
    """Natural cubic spline through the points, evaluated at z_slices.
    Outside [z_min, z_max] T is held at the end value (no spline extrapolation)."""
    from scipy.interpolate import CubicSpline
    cs = CubicSpline(z_pts, T_pts_C, bc_type='natural')
    zc = np.clip(z_slices, z_pts[0], z_pts[-1])
    return cs(zc), cs


def ask_moment_inputs(root, z_lo, z_hi):
    """Modal window: paste/load (z, T) points, enter pressure + z offset.
    Returns dict, or None if the user skips the mole calc."""
    result = {}
    win = tk.Toplevel(root)
    win.title('Single-Moment Mole Calc — Inputs')
    win.attributes('-topmost', True)
    win.geometry('520x620')

    tk.Label(win, text=f'Volume profile spans {z_lo:.2f} – {z_hi:.2f} mm (system axis, x = 0 at bottom of stack)',
             fg='navy', wraplength=490, justify='left').pack(anchor='w', padx=10, pady=(10, 4))
    tk.Label(win, text='T profile points — one "z_mm, T_C" pair per line\n'
                       '(comma, tab or space separated; header lines ignored; paste from Excel OK)',
             justify='left').pack(anchor='w', padx=10)

    txt_frame = tk.Frame(win)
    txt_frame.pack(fill='both', expand=True, padx=10, pady=4)
    txt = tk.Text(txt_frame, height=16, font=('Menlo', 12))
    sb = tk.Scrollbar(txt_frame, command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    txt.pack(side='left', fill='both', expand=True)
    sb.pack(side='right', fill='y')
    txt.insert('1.0', '# z_mm, T_C\n')

    def load_csv():
        p = filedialog.askopenfilename(parent=win, title='Load z, T CSV',
                                       filetypes=(('CSV / text', '*.csv *.txt *.tsv'), ('Excel', '*.xlsx'),
                                                  ('All files', '*.*')))
        if not p:
            return
        try:
            if p.lower().endswith(('.xlsx', '.xls')):
                df = pd.read_excel(p, header=None)
                content = '\n'.join(f'{a}, {b}' for a, b in df.iloc[:, :2].itertuples(index=False))
            else:
                with open(p) as f:
                    content = f.read()
            txt.delete('1.0', 'end')
            txt.insert('1.0', content)
        except Exception as e:
            messagebox.showerror('Load Error', str(e), parent=win)

    tk.Button(win, text='Load z, T from file…', command=load_csv).pack(anchor='w', padx=10)

    form = tk.Frame(win)
    form.pack(fill='x', padx=10, pady=8)
    tk.Label(form, text='Pressure (uniform):').grid(row=0, column=0, sticky='w')
    p_var = tk.StringVar()
    tk.Entry(form, textvariable=p_var, width=12).grid(row=0, column=1, sticky='w')
    unit_var = tk.StringVar(value='MPa')
    tk.OptionMenu(form, unit_var, *P_UNITS_TO_MPA.keys()).grid(row=0, column=2, sticky='w')
    tk.Label(form, text='z offset (mm, added to your z):').grid(row=1, column=0, sticky='w', pady=(6, 0))
    off_var = tk.StringVar(value='0')
    tk.Entry(form, textvariable=off_var, width=12).grid(row=1, column=1, sticky='w', pady=(6, 0))

    btns = tk.Frame(win)
    btns.pack(fill='x', padx=10, pady=(0, 10))

    def ok():
        try:
            z, T = parse_zT_text(txt.get('1.0', 'end'))
            P_raw = float(p_var.get())
            off = float(off_var.get() or 0)
        except ValueError as e:
            messagebox.showerror('Input Error', str(e) if 'z' in str(e) or 'point' in str(e)
                                 else 'Pressure and z offset must be numbers.', parent=win)
            return
        if P_raw <= 0:
            messagebox.showerror('Input Error', 'Pressure must be > 0.', parent=win)
            return
        result.update(z=z + off, T_C=T, z_offset=off, P_input=P_raw, P_unit=unit_var.get(),
                      P_MPa=P_raw * P_UNITS_TO_MPA[unit_var.get()],
                      raw_text=txt.get('1.0', 'end'))
        win.destroy()

    def skip():
        win.destroy()

    tk.Button(btns, text='Calculate Moles', command=ok, default='active').pack(side='right')
    tk.Button(btns, text='Skip (volume only)', command=skip).pack(side='right', padx=6)
    win.protocol('WM_DELETE_WINDOW', skip)
    win.grab_set()
    root.wait_window(win)
    return result or None


def calc_moles(volumeDF, inputs, zlookup):
    """Adds per-slice T, Z and n columns to volumeDF; returns (volumeDF, summary dict)."""
    z_start = volumeDF['Axial Position'].to_numpy(dtype=float)
    z_mid = z_start + SLICE_MM / 2                      # evaluate T at slice centre
    V_mm3 = volumeDF['Total Volume'].fillna(0).to_numpy(dtype=float)

    T_C, _ = build_T_profile(inputs['z'], inputs['T_C'], z_mid)
    T_K = T_C + 273.15
    if np.any(T_K <= 0):
        raise ValueError('Spline produced T <= 0 K — check your T points.')
    P_MPa = inputs['P_MPa']
    Z = zlookup(T_K, P_MPa)
    V_m3 = V_mm3 * 1e-9
    n_slice = (P_MPa * 1e6 * V_m3) / (Z * R_GAS * T_K)

    volumeDF = volumeDF.copy()
    volumeDF['T_C'] = T_C
    volumeDF['T_K'] = T_K
    volumeDF['Z'] = Z
    volumeDF['n_slice_mmol'] = n_slice * 1e3
    volumeDF['n_cumulative_mmol'] = np.cumsum(n_slice) * 1e3

    n_tot = n_slice.sum()
    V_tot = V_m3.sum()
    outside = (z_mid < inputs['z'][0]) | (z_mid > inputs['z'][-1])
    V_out = V_m3[outside].sum()
    n_ideal = (P_MPa * 1e6 * V_m3 / (R_GAS * T_K)).sum()
    summary = {
        'n_total_mol': n_tot,
        'n_total_mmol': n_tot * 1e3,
        'n_ideal_gas_mmol (Z=1)': n_ideal * 1e3,
        'V_total_mL': V_tot * 1e6,
        'P_input': inputs['P_input'],
        'P_unit': inputs['P_unit'],
        'P_MPa': P_MPa,
        'z_offset_mm': inputs['z_offset'],
        'T_points': len(inputs['z']),
        'T_input_z_range_mm (after offset)': f"{inputs['z'][0]:.2f} – {inputs['z'][-1]:.2f}",
        'Volume-weighted mean T_C': float((T_C * V_m3).sum() / V_tot) if V_tot else np.nan,
        'Gas-weighted mean T_C (V/sum(V/T))': float(V_tot / (V_m3 / T_K).sum() - 273.15) if V_tot else np.nan,
        'Volume outside T-point range (mL, T held at end value)': V_out * 1e6,
        'Volume outside T-point range (%)': 100 * V_out / V_tot if V_tot else np.nan,
        'Z range': f'{Z.min():.5f} – {Z.max():.5f}',
        'Z table': zlookup.path or 'NONE — ideal gas (Z = 1)',
        'Spline': 'Natural cubic (scipy CubicSpline), evaluated at 0.01 mm slice centres',
    }
    return volumeDF, summary


def plot_profiles(volumeDF, inputs, summary, title, save_path=None):
    import matplotlib.pyplot as plt
    z = volumeDF['Axial Position'].to_numpy(dtype=float) + SLICE_MM / 2
    V_per_mm = volumeDF['Total Volume'].fillna(0).to_numpy(dtype=float) / SLICE_MM   # mm^3 per mm (= mm^2)

    fig, axV = plt.subplots(figsize=(12, 5.5))
    axV.fill_between(z, V_per_mm, step='mid', color='tab:blue', alpha=0.25, lw=0)
    axV.plot(z, V_per_mm, color='tab:blue', lw=0.8, label='Volume (mm³ per mm)')
    axV.set_xlabel('Axial position z (mm)')
    axV.set_ylabel('Volume per mm (mm³/mm)', color='tab:blue')
    axV.tick_params(axis='y', labelcolor='tab:blue')
    axV.set_xlim(z[0], z[-1])

    axT = axV.twinx()
    axT.plot(z, volumeDF['T_C'], color='tab:red', lw=1.8, label='T (cubic spline)')
    axT.plot(inputs['z'], inputs['T_C'], 'o', color='black', ms=5, label='T input points')
    axT.set_ylabel('Temperature (°C)', color='tab:red')
    axT.tick_params(axis='y', labelcolor='tab:red')

    lines = axV.get_legend_handles_labels()[0] + axT.get_legend_handles_labels()[0]
    labels = axV.get_legend_handles_labels()[1] + axT.get_legend_handles_labels()[1]
    axV.legend(lines, labels, loc='upper left')
    axV.set_title(f"{title}\nn = {summary['n_total_mmol']:.4f} mmol   |   "
                  f"P = {summary['P_input']:g} {summary['P_unit']}   |   V = {summary['V_total_mL']:.3f} mL")
    axV.grid(alpha=0.3)
    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=200)
    return fig


# =============================================================================
# Standalone driver
# =============================================================================

def _ask(title, initialdir):
    path = filedialog.askopenfilename(
        title=title, initialdir=initialdir,
        filetypes=(('Excel files', '*.xlsx *.xlsm'), ('All files', '*.*')))
    if not path:
        messagebox.showinfo('Volume Profile', f'Cancelled at: {title}')
        sys.exit(0)
    print(f'{title}: {path}')
    return path


def _part_summary(volumeDF, uid_to_material):
    rows = []
    for col in volumeDF.columns:
        if 'Part_' in col:
            uid = col.split('_', 3)[-1] if col.startswith(('External_', 'Internal_')) else col.split('_', 2)[-1]
            v = volumeDF[col].sum(skipna=True)
            rows.append({'Column': col, 'UID': uid,
                         'Material': uid_to_material.get(str(uid), ''),
                         'Volume (mm^3)': v, 'Volume (mL)': v / 1000})
    total = volumeDF['Total Volume'].sum()
    rows.append({'Column': 'Total Volume', 'Volume (mm^3)': total, 'Volume (mL)': total / 1000})
    return pd.DataFrame(rows)


def main():
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)  # keep dialogs in front

    layout_file  = _ask('1/4  Select Autoclave Layout File', DEFAULT_DIR)
    fur_file     = _ask('2/4  Select MLD - FUR File', DEFAULT_DIR)
    hps_file     = _ask('3/4  Select MLD - HPS File', DEFAULT_DIR)
    mating_file  = _ask('4/4  Select Surface Mating Table', DEFAULT_DIR)

    try:
        partList = pd.read_excel(layout_file)
    except Exception as e:
        messagebox.showerror('Volume Profile', f'Could not read layout file:\n{e}')
        sys.exit(1)

    result = getSystemVolumeProfile(partList, mating_file, fur_file, hps_file)
    if result is None:
        messagebox.showerror('Volume Profile',
                             'Volume profile failed — see the console output for the error.')
        sys.exit(1)
    volumeDF, uid_to_material = result

    # Trim the empty tail (the builder pads to 1000 mm)
    nonzero = volumeDF.index[volumeDF['Total Volume'].fillna(0) > 0]
    if len(nonzero):
        volumeDF = volumeDF.loc[:nonzero[-1]]
    volumeDF = volumeDF.reset_index(drop=True)
    summaryDF = _part_summary(volumeDF, uid_to_material)
    total = volumeDF['Total Volume'].sum()
    layout_stem = os.path.splitext(os.path.basename(layout_file))[0]

    # ── Single-moment mole calc ──────────────────────────────────────────
    z_lo = float(volumeDF['Axial Position'].iloc[0])
    z_hi = float(volumeDF['Axial Position'].iloc[-1]) + SLICE_MM
    inputs = ask_moment_inputs(root, z_lo, z_hi)
    mole_summary = None
    fig = None
    if inputs:
        zlookup = ZLookup(find_z_table())
        print(f"\nZ table: {zlookup.path or 'NONE — ideal gas (Z = 1)'}")
        try:
            volumeDF, mole_summary = calc_moles(volumeDF, inputs, zlookup)
        except Exception as e:
            messagebox.showerror('Mole Calc', f'Mole calculation failed:\n{e}')
            sys.exit(1)

        print('\nMOLE CALC RESULT')
        for k, v in mole_summary.items():
            print(f'  {k}: {v}')
        fig = plot_profiles(volumeDF, inputs, mole_summary, layout_stem)

        warn = ''
        if mole_summary['Volume outside T-point range (%)'] > 0.5:
            warn = (f"\n\n⚠ {mole_summary['Volume outside T-point range (%)']:.1f}% of the volume lies outside "
                    f"your T-point z range — T was held at the end values there.")
        if zlookup.path is None:
            warn += '\n\n⚠ No Z table — ideal gas (Z = 1) used.'
        messagebox.showinfo('Mole Calc Result',
                            f"n = {mole_summary['n_total_mmol']:.4f} mmol\n"
                            f"   ({mole_summary['n_total_mol']:.6f} mol)\n\n"
                            f"P = {inputs['P_input']:g} {inputs['P_unit']} ({inputs['P_MPa']:.4f} MPa)\n"
                            f"V = {mole_summary['V_total_mL']:.3f} mL\n"
                            f"Gas-weighted mean T = {mole_summary['Gas-weighted mean T_C (V/sum(V/T))']:.1f} °C"
                            f"{warn}")

    # ── Save ─────────────────────────────────────────────────────────────
    out_path = filedialog.asksaveasfilename(
        title='Save Volume Profile As',
        initialdir=os.path.dirname(layout_file),
        initialfile=f"{'MoleCalc' if mole_summary else 'volumeDF'}_{layout_stem}.xlsx",
        defaultextension='.xlsx',
        filetypes=(('Excel files', '*.xlsx'),))
    if not out_path:
        print('Save cancelled — nothing written.')
    else:
        print(f'\nWriting {len(volumeDF):,} rows to {out_path} ...')
        with pd.ExcelWriter(out_path, engine='openpyxl') as xw:
            if mole_summary:
                ms = pd.DataFrame(list(mole_summary.items()), columns=['Quantity', 'Value'])
                ms = pd.concat([ms, pd.DataFrame([
                    {'Quantity': 'Layout', 'Value': layout_file},
                    {'Quantity': 'MLD - FUR', 'Value': fur_file},
                    {'Quantity': 'MLD - HPS', 'Value': hps_file},
                    {'Quantity': 'Mating Table', 'Value': mating_file}])], ignore_index=True)
                ms.to_excel(xw, sheet_name='Mole Calc', index=False)
                pd.DataFrame({'z_input_mm': inputs['z'] - inputs['z_offset'],
                              'z_system_mm (after offset)': inputs['z'],
                              'T_C': inputs['T_C']}).to_excel(xw, sheet_name='T Input', index=False)
            volumeDF.to_excel(xw, sheet_name='Volume Profile', index=False)
            summaryDF.to_excel(xw, sheet_name='Part Summary', index=False)
        if fig is not None:
            png = os.path.splitext(out_path)[0] + '.png'
            fig.savefig(png, dpi=200)
            print(f'Plot saved: {png}')
        print('Done.')
        if messagebox.askyesno('Volume Profile', f'Saved:\n{out_path}\n\nOpen it now?'):
            if sys.platform == 'darwin':
                os.system(f'open "{out_path}"')
            elif os.name == 'nt':
                os.startfile(out_path)
            else:
                os.system(f'xdg-open "{out_path}"')

    root.destroy()
    if fig is not None:
        import matplotlib.pyplot as plt
        plt.show()


if __name__ == '__main__':
    main()
