# MolCalc source modules

`MolCalc_v0_6.ipynb` remains the launch point. Run its first cell to load the
files below in order into the notebook's shared namespace.

The functions currently rely on shared notebook globals for GUI controls and
run state. Executing the files in one namespace preserves those connections
while keeping the extracted v6 code unchanged. Run the notebook rather than an
individual module file.

| File | Responsibility |
| --- | --- |
| `app_state.py` | Imports and shared state |
| `data_inputs.py` | Data, geometry, and furniture inputs |
| `temperature_interpolation.py` | Temperature interpolation |
| `volume_profiler.py` | Geometry-based volume profile |
| `processing.py` | Run processing and calculated profiles |
| `plotting.py` | Main mole, pressure, and temperature graph |
| `temperature_viewer.py` | Temperature profile viewing and export |
| `run_info.py` | Run information window |
| `analysis_tools.py` | Fits, pressure calculations, exports, and dn/dt |
| `pressure_trace_synthesizer.py` | Forward pressure-trace calculation and UI |
| `gui.py` | Main application interface |

This is a behavior-preserving first split. Replacing the shared globals with
explicit inputs and outputs would make the calculation modules independently
testable, but should be done as a separate, incrementally validated change.

## Standalone use

`temperature_interpolation.py` and `volume_profiler.py` carry their own
imports and no longer require the exec chain — they can be imported and run
on their own, e.g. from a plain script or a test:

```python
from molcalc.temperature_interpolation import interpolateTempProfile
from molcalc.volume_profiler import getPartVolProfile, getSystemVolumeProfile

interpolateTempProfile(current_temps, tc_positions_series)   # pure, no deps
getPartVolProfile(part_profile_dict)                          # pure, no deps
getSystemVolumeProfile(partList, mating_table_path, fur_path, hps_path)
# ^ reads the geometry .xlsx files and returns (volumeDF, uid_to_material);
#   prints status/errors to the console when run outside the GUI instead of
#   updating the main window's label.
```

The other modules (`processing.py`, `plotting.py`, `gui.py`, etc.) still rely
on shared notebook globals and should be run through the notebook.