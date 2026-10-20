# T-profile checker

Standalone tool to sanity-check a candidate temperature profile against an
experimental pressure reading. Given a known mole count, a trusted volume
profile, and a temperature profile (currently: sparse points from a
SolidWorks thermal sim, fit with a cubic spline), it integrates

    P = n / sum(Vi / (Zi * R * Ti))

over the volume profile's slices and reports P_calc, optionally diffed
against a measured P_exp. Uses the same real-gas solver
(`_synth_compute_P`) as MolCalc's Pressure Trace Synthesizer, so results are
on the same physical footing as the rest of the app — any mismatch against
P_exp is attributable to the T profile, not a different gas model.

Not wired into the MolCalc notebook/GUI — run it directly:

```bash
python check_t_profile.py \
    --n-mol 0.0452 \
    --volume-csv volume_profile.csv \
    --temp-csv sw_temps_120min.csv \
    --p-exp 2.35 \
    --gas Nitrogen
```

## Inputs

- `--n-mol`: known mole count (mol) at this timestep.
- `--volume-csv`: MolCalc's own `volumeDF` columns, unchanged —
  `Axial Position` (mm) and `Total Volume` (mm^3, **per-slice**, not
  cumulative). `example_volume_profile.csv` shows the format. Export your
  real one straight from a run, no renaming needed:
  ```python
  volumeDF[['Axial Position', 'Total Volume']].to_csv('volume_profile.csv', index=False)
  ```
- `--temp-csv`: columns `z_mm, T_C` — sparse points (e.g. read off a
  SolidWorks thermal plot). Need at least 4 for a well-posed cubic spline.
  See `example_temp_profile.csv`.
- `--p-exp` (optional): measured pressure (MPa) at this timestep, to print
  the error against.
- `--gas` (default `Nitrogen`): looks up `<stem>_Z.npz` in the same
  Dropbox "File Dependencies" folder the rest of MolCalc uses. Falls back
  to ideal gas (Z=1) with a printed warning if the species isn't mapped or
  the file can't be found.

Volume-profile z points outside the T-profile's z-range are clamped to the
nearest known temperature (not extrapolated by the cubic) — the script
warns when this happens and how much of the volume profile it affects.

## Next step

Built for one timestep/profile at a time. Once there's a fuller T-profile
lookup table (multiple timesteps), this should take a timestep index/column
instead of a single `--temp-csv`.
