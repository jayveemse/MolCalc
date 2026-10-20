import numpy as np

# Pre-computed interpolation geometry (see processing.py). Left as None here
# so this module is directly importable/callable on its own — interpolateTempProfile
# falls back to computing from tc_positions_series when these aren't set.
_sorted_tc_idx = None
_x_tc_sorted = None
_x_target_interp = None


# --- interpolateTempProfile function ---
def interpolateTempProfile(current_temps, tc_positions_series):
    """
    Build a 1-mm-resolution temperature profile by linearly interpolating
    across ALL TC channels.

    Speed: sorted TC order, x_target, and _x_tc_sorted are pre-computed
    once before the main loop (_sorted_tc_idx, _x_tc_sorted, _x_target_interp)
    and reused every call.  Falls back to on-the-fly computation if those
    globals are not yet initialised (e.g. during unit testing).

    Previous behaviour used only three anchor points (min-pos / peak / max-pos),
    discarding all intermediate TCs.  This version uses every TC channel.
    """
    global _sorted_tc_idx, _x_tc_sorted, _x_target_interp
    try:
        y_raw = [float(t) for t in current_temps]
    except (ValueError, TypeError) as e:
        print(f"Error: Non-numeric temp reading in interpolateTempProfile: {e}"); return []

    # --- Use pre-computed arrays when available (normal run-time path) ---
    if _sorted_tc_idx is not None and _x_tc_sorted is not None and _x_target_interp is not None:
        if len(y_raw) != len(_sorted_tc_idx):
            print(f"Error: TC count mismatch in interpolateTempProfile "
                  f"({len(y_raw)} temps vs {len(_sorted_tc_idx)} positions)."); return []
        y_known = np.array(y_raw)[_sorted_tc_idx]
        return np.interp(_x_target_interp, _x_tc_sorted, y_known).tolist()

    # --- Fallback: compute on the fly (e.g. first call before pre-computation) ---
    try:
        x_known_values = tc_positions_series.astype(float).values
    except (AttributeError, ValueError) as e:
        print(f"Error: TC positions not convertible to float: {e}"); return []
    if len(y_raw) != len(x_known_values):
        print("Error: Temps/Positions length mismatch in interpolateTempProfile."); return []
    si = np.argsort(x_known_values)
    x_s = x_known_values[si]; y_s = np.array(y_raw)[si]
    if len(x_s) < 2:
        print(f"Warn: Only {len(x_s)} unique TC position(s) — cannot interpolate."); return []
    x_tgt = np.arange(int(x_s[0]), int(x_s[-1]) + 1)
    return np.interp(x_tgt, x_s, y_s).tolist()
