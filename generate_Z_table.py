"""
Generate compressibility factor (Z) lookup tables using CoolProp Span-Wagner EOS.

Produces one .npz file per gas species saved to the MolCalc File Dependencies folder.
Load in processData with:
    data = np.load('N2_Z.npz')
    interp = RegularGridInterpolator((data['T_K'], data['P_MPa']), data['Z'])
    Z = interp(np.column_stack([T_arr, P_arr_MPa]))
"""

import numpy as np
import os

try:
    from CoolProp.CoolProp import PropsSI
except ImportError:
    raise ImportError("CoolProp not installed. Run: pip install CoolProp")

SAVE_DIR = "/Users/henryknight/Lehigh University Dropbox/ENG-MATSGroup/MATS - Collaboration/Data/Parsers/MolCalc/File Dependencies"

# Grid definition
T_MIN_K   = 250.0    # K  (below N2 boiling point to be safe)
T_MAX_K   = 2000.0   # K
T_STEP_K  = 0.5      # K

P_MIN_MPA = 0.1      # MPa (avoid 0 — CoolProp is unstable at vacuum)
P_MAX_MPA = 50.0     # MPa
P_STEP_MPA = 0.1     # MPa

# Gas species to generate tables for.
# Key = filename stem, value = CoolProp fluid name.
GASES = {
    "N2": "Nitrogen",
    # "Ar": "Argon",
    # "He": "Helium",
}


def generate_table(coolprop_name: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    T_arr = np.arange(T_MIN_K, T_MAX_K + T_STEP_K / 2, T_STEP_K)
    P_arr = np.arange(P_MIN_MPA, P_MAX_MPA + P_STEP_MPA / 2, P_STEP_MPA)
    P_Pa  = P_arr * 1e6

    Z_grid = np.empty((len(T_arr), len(P_arr)), dtype=np.float64)

    print(f"  Grid: {len(T_arr)} T points × {len(P_arr)} P points = {len(T_arr)*len(P_arr):,} values")

    for j, P in enumerate(P_Pa):
        if j % 50 == 0:
            print(f"  P step {j}/{len(P_Pa)} ({P/1e6:.1f} MPa)...", flush=True)
        try:
            Z_grid[:, j] = PropsSI("Z", "T", T_arr, "P", P, coolprop_name)
        except Exception as e:
            print(f"  Warning at P={P/1e6:.2f} MPa: {e} — filling with 1.0")
            Z_grid[:, j] = 1.0

    return T_arr, P_arr, Z_grid


def main():
    os.makedirs(SAVE_DIR, exist_ok=True)

    for stem, fluid in GASES.items():
        print(f"\nGenerating Z table for {fluid} ({stem})...")
        T_arr, P_arr, Z_grid = generate_table(fluid)

        out_path = os.path.join(SAVE_DIR, f"{stem}_Z.npz")
        np.savez_compressed(out_path, T_K=T_arr, P_MPa=P_arr, Z=Z_grid)

        size_mb = os.path.getsize(out_path) / 1e6
        print(f"  Saved: {out_path}  ({size_mb:.1f} MB)")
        print(f"  Z range: {Z_grid.min():.4f} – {Z_grid.max():.4f}")
        print(f"  Sample: Z(300 K, 10 MPa) = {Z_grid[np.searchsorted(T_arr, 300), np.searchsorted(P_arr, 10.0)]:.5f}")


if __name__ == "__main__":
    main()
