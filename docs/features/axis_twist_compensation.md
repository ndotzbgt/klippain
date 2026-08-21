# Axis twist compensation

The axis twist compensation is a Klipper module that corrects the probe's results when the X or Y axis of the machine is slightly twisted. This is common on machines where the gantry rails can twist a little, and it shows up as a small skew between what the probe measures and the actual first layer squish: the `[bed_mesh]`, `Z_TILT_ADJUST` or `SCREWS_TILT_CALCULATE` results look perfect, but the first layer is not even.

Klippain integrates the Klipper `[axis_twist_compensation]` module and adds a **dockable probe aware calibration wizard**, because the stock wizard is not compatible with dockable probes (see the [Klipper documentation warning](https://www.klipper3d.org/Axis_Twist_Compensation.html)): it keeps the probe attached during the manual "paper touch" measurement, so the paper touches the probe pin instead of the nozzle and the measured offsets are constant (the resulting compensation is silently zero).


## Description

The module measures the probe Z offset at several points along the axis (default 3 points, adjustable with `SAMPLE_COUNT=`). Each point is measured twice:

1. **Automatically** with the probe (the probe must give a reliable Z of the bed at that location).
2. **Manually** by jogging the nozzle down until a piece of paper just touches it.

The difference between the two measurements at each point is the probe location bias caused by the twisted axis. The calibration normalizes the offsets (they are made independent of the probe `z_offset`) and saves them through `SAVE_CONFIG`.

The Klippain wizard batches the measurements to minimize dock/attach cycles with a dockable probe:

1. `ACTIVATE_PROBE` (attach the klicky / Euclid probe).
2. Automatic probing of every point with the probe attached.
3. `DEACTIVATE_PROBE` (dock the probe).
4. Manual (paper touch on the **nozzle**) measurement of every point.
5. `ACTIVATE_PROBE` (re-attach the probe).
6. Compute and save the compensation values.

For non-dockable probes (inductive, Beacon, TAP, ...) the wizard works exactly like the stock one, without the attach/dock steps.


## Installation

In `printer.cfg`, uncomment the include that matches your machine size (select only one line):

```
# [include config/software/axis_twist_compensation/axis_twist_compensation_120mm.cfg]
# [include config/software/axis_twist_compensation/axis_twist_compensation_180mm.cfg]
# [include config/software/axis_twist_compensation/axis_twist_compensation_220mm.cfg]
# [include config/software/axis_twist_compensation/axis_twist_compensation_250mm.cfg]
# [include config/software/axis_twist_compensation/axis_twist_compensation_300mm.cfg]
# [include config/software/axis_twist_compensation/axis_twist_compensation_350mm.cfg]
```

The dockable probe aware wizard is a Klippain plugin (`scripts/axis_twist_compensation_dockable.py`) that the [install script](../../install.sh) symlinks into `klippy/extras`. If you installed Klippain before this feature, re-run the install script once so the plugin is installed.

The compensation values are **saved by `SAVE_CONFIG`** into the `[axis_twist_compensation]` section of your `printer.cfg` save block. Do **not** add `z_compensations`, `zy_compensations`, `compensation_start_x`/`compensation_end_x` or `compensation_start_y`/`compensation_end_y` to the included config files yourself: they must be saved by the calibration wizard, otherwise `SAVE_CONFIG` will refuse to run.


## Quick start

Before calibrating, make sure the machine is mechanically sound (the module explicitly recommends fixing a significantly twisted axis mechanically first) and that the probe X/Y offsets are correctly set, as they greatly influence the calibration.

The full calibration workflow (for a Voron-style CoreXY machine):

```
# 1. Home
G28

# 2. Level the bed
SCREWS_TILT_CALCULATE          # silicone spacer beds
Z_TILT_ADJUST                  # or QUAD_GANTRY_LEVEL on V2-style machines

# 3. Calibrate axis twist compensation (X axis by default)
CALIBRATE_AXIS_TWIST

# 4. Save and restart
SAVE_CONFIG

# 5. Recalibrate the bed mesh with the new compensation active
BED_MESH_CALIBRATE
```


## Macro reference

### CALIBRATE_AXIS_TWIST

Main entry point. Levels the bed first (`_TILT_CALIBRATE`), then runs the calibration wizard.

| Parameter | Default | Description |
|---|---|---|
| `AXIS` | `X` | Axis to calibrate: `X` or `Y` |
| `SAMPLE_COUNT` | `3` | Number of measurement points along the axis (minimum 2) |

**Examples:**

```
# Calibrate the X axis (default, 3 points)
CALIBRATE_AXIS_TWIST

# Calibrate the Y axis
CALIBRATE_AXIS_TWIST AXIS=Y

# Use 5 points for higher precision
CALIBRATE_AXIS_TWIST SAMPLE_COUNT=5

# Calibrate Y with 5 points
CALIBRATE_AXIS_TWIST AXIS=Y SAMPLE_COUNT=5
```

The wizard will guide you through each measurement point:

1. The probe automatically probes the bed at each point.
2. For the manual phase, place a piece of paper on the bed and jog the nozzle down until it just touches it.
3. Send `ACCEPT` to confirm each point.
4. After all points are measured, run `SAVE_CONFIG` to persist the compensation.

### QUERY_AXIS_TWIST_COMPENSATION

Displays the current compensation state: the saved `z_compensations` / `zy_compensations` values and the ranges over which they are applied.

```
QUERY_AXIS_TWIST_COMPENSATION
```

**Example output (in the console):**

```
Axis twist compensation X (z_compensations): 0.100000, -0.050000, 0.250000
Axis twist compensation X is applied from 25.0 to 325.0 mm
Axis twist compensation Y (zy_compensations):
Axis twist compensation is not calibrated yet. Run CALIBRATE_AXIS_TWIST to calibrate it.
```

### CLEAR_AXIS_TWIST_COMPENSATION

Removes the compensation from the current session. You must run `SAVE_CONFIG` afterward to persist the change.

| Parameter | Default | Description |
|---|---|---|
| `AXIS` | `BOTH` | Which axis to clear: `X`, `Y`, or `BOTH` |

**Examples:**

```
# Clear both axes
CLEAR_AXIS_TWIST_COMPENSATION
SAVE_CONFIG

# Clear only the X axis
CLEAR_AXIS_TWIST_COMPENSATION AXIS=X
SAVE_CONFIG
```

### SCREWS_TILT_CALCULATE

If you included a `screws_tilt_*mm.cfg` file, the `SCREWS_TILT_CALCULATE` command is automatically wrapped to support dockable probes (klicky, Euclid). It attaches the probe before running and docks it afterward, just like the other tilting overrides (`QUAD_GANTRY_LEVEL`, `Z_TILT_ADJUST`).

No extra configuration is needed -- just use `SCREWS_TILT_CALCULATE` as usual.


## When to re-run calibration

Re-run `CALIBRATE_AXIS_TWIST` after:

- Any mechanical work on the gantry, rails, or toolhead.
- Replacing the probe or changing probe X/Y offsets.
- If the first layer accuracy drifts and bed mesh / screws tilt / Z tilt look correct.


## Caveats

- **The compensation is applied to every probe result** (bed mesh, screws tilt, Z tilt, ...) through the `probe:update_results` Klipper hook.
- **Interpolation extrapolates outside the calibrated range.** The compensation is linearly interpolated between the calibration points and extrapolates beyond them. Keep `calibrate_start_x`/`calibrate_end_x` (and the Y variants) close to the edges of the area you probe, like the defaults do.
- The wizard needs a probe (the `_INIT_CHECKPROBECONF` startup check refuses to start if the axis twist compensation is enabled without one).
- On a Voron Trident, the bed homes **down** onto the bottom endstop (SexBolt). There is no Z max endstop and no Z max homing needed. The axis twist compensation corrects the probe along the XY plane; the Z reference remains the SexBolt at the bottom.