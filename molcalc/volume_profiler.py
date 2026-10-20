import ast
import os

import numpy as np
import pandas as pd


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
    # graphLabel/window/_log_live are optional GUI hooks supplied by gui.py via
    # the shared notebook namespace. Reading them through globals() (rather than
    # `global`) means this function still works — minus the live status updates —
    # when the module is imported and called on its own, outside the GUI.
    def _report_error(msg):
        print(msg)
        label = globals().get('graphLabel')
        win = globals().get('window')
        if label is not None:
            label.configure(text=msg)
        if win is not None:
            win.update_idletasks()

    def _log(msg):
        globals().get('_log_live', print)(msg)

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
        _log(f'MLD-FUR: loaded {len(partsDF_Internal)} parts')
        _log(f'MLD-HPS: loaded {len(partsDF_External)} parts')

    except FileNotFoundError as e:
        _report_error(f'Error: File not found: {os.path.basename(e.filename)}')
        return None
    except Exception as e:
        _report_error(f'Error reading geometry files: {e}')
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
        _report_error("Error: No relevant parts found based on Layout file.")
        return None

    # --- 3. Split Master List into Internal and External Sequences ---
    internal_uids = partsDF_Internal['UID'].tolist()
    
    relevantParts_Internal = relevantParts[relevantParts['UID'].isin(internal_uids)].reset_index(drop=True)
    relevantParts_External = relevantParts[~relevantParts['UID'].isin(internal_uids)].reset_index(drop=True)

    # --- 4. Generate Two Profiles using _build_profile_sequence ---

    _log("--- Building External Profile Sequence ---")
    external_volumeDF, external_mate_positions, external_placement_summaries, error_ext = \
        _build_profile_sequence(relevantParts_External, planeTable)
    
    if error_ext:
        _report_error(f"External Profile Error: {error_ext}")
        return None

    # Only attempt to build internal sequence if internal parts exist
    internal_volumeDF = None
    internal_mate_positions = []
    internal_placement_summaries = []
    if not relevantParts_Internal.empty:
        _log("--- Building Internal Profile Sequence ---")
        (internal_volumeDF, internal_mate_positions,
         internal_placement_summaries, error_int) = _build_profile_sequence(
            relevantParts_Internal, planeTable)
        if error_int:
            _report_error(f"Internal Profile Error: {error_int}")
            return None
    else:
        _log("--- No internal parts in layout, skipping internal profile sequence ---")

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
            _report_error("Error: Could not find 'MP-INTERNAL' plane in both external and internal part lists for alignment.")
            return None
        
        # Calculate the required offset
        alignment_offset_mm = external_alignment_pos - internal_alignment_pos
        alignment_offset_slices = int(round(alignment_offset_mm * 100))
        
        _log(f"Alignment calculated: External pos={external_alignment_pos}mm, Internal pos={internal_alignment_pos}mm. Offset={alignment_offset_mm}mm.")

        # Determine the maximum length required for the final combined DataFrame
        max_idx_external = len(external_volumeDF)
        max_idx_internal = alignment_offset_slices + len(internal_volumeDF)
        max_len = max(max_idx_external, max_idx_internal)
        
        # Initialize final volumeDF
        volumeDF = pd.DataFrame(index=range(max_len))
        volumeDF["Axial Position"] = [round(0.01*i, 2) for i in range(max_len)]
        
        # Copy External Profile (starts at index 0)
        for col in external_volumeDF.columns:
            if col.startswith("Part_"):
                 volumeDF[f"External_{col}"] = external_volumeDF[col]
        
        # Copy Internal Profile (offset it by alignment_offset_slices)
        for col in internal_volumeDF.columns:
            if col.startswith("Part_"):
                 col_data = pd.Series(
                     internal_volumeDF[col].values, 
                     index=range(alignment_offset_slices, alignment_offset_slices + len(internal_volumeDF))
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
    _log("-" * 60)
    # Ensure placement_summaries is a list of tuples (pos_str, mate_str) for printing
    for pos, mates_summary, length in placement_summaries:
        print(pos)
        print(mates_summary)
        print(length)
        _log("-" * 60)

    _log("\nMate Positions")
    _log(mate_positionsDF)

    _log("\nVolume per part (mL):")
    for col in volumeDF.columns:
        if col.startswith("External_Part_") or col.startswith("Internal_Part_"):
            v_mm3 = volumeDF[col].sum(skipna=True)
            _log(f"{col}: {v_mm3/1000:.3f} mL")


    print('\npartList:', partList)

    return volumeDF, uid_to_material
