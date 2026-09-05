# Dockable Probe Automation

Klippain automates the attach/dock lifecycle for physical dockable probes (Klicky, Clicky, EUclid, etc.). The framework handles probe attachment before probing operations and docking afterward, so you don't need manual `ACTIVATE_PROBE`/`DEACTIVATE_PROBE` calls in your slicer start G-code.

## Probe Profiles

Use one of the dockable probe includes in your `printer.cfg`:

```ini
[include config/hardware/probes/dockable.cfg]          # Standard dockable probe
[include config/hardware/probes/dockable_virtual.cfg]   # Dockable used as virtual Z endstop
```

`dockable.cfg` sets `probe_type_enabled: "dockable"` — the probe is a physical endstop switch mounted on a magnetic dock.
`dockable_virtual.cfg` sets `probe_type_enabled: "dockable_virtual"` — same physical probe but used as a virtual Z endstop (no separate Z endstop pin required).


## Dock Location and Movement

These variables control where the dock is and how the toolhead moves to attach/dock the probe.

```ini
variable_probe_dock_location_xy: -1, -1        # X,Y position of the probe dock
variable_probe_min_z_travel: 20                 # Minimum Z height for attach/dock moves
variable_probe_stow_z_height: None              # Z height after detaching (None = no move)
```

Movement positions use named directions relative to the dock:

```ini
variable_probe_before_attach_position: "front"  # Approach direction before attaching
variable_probe_after_attach_position: "front"   # Retract direction after attaching
variable_probe_before_dock_position: "front"    # Approach direction before docking
variable_probe_after_dock_position: "left"      # Retract direction after docking
variable_probe_move_attach_length: 30           # Distance of approach/retract moves
variable_probe_move_dock_length: 30             # Distance of approach/retract moves
```

Direction diagram:

```
    Y
    ^ 
    |          back
    |           ^
    |   left  < O >  right
    |           v
    |         front
    |_ _ _ _ _ _ _ _ _ _ _ _> X
```


## Speeds and Acceleration

```ini
variable_probe_dock_speed: 60       # Speed for probe dock/attach movements (mm/s)
variable_probe_dock_accel: 2000     # Acceleration for probe dock/attach movements (mm/s^2)
```


## Servo Support (Optional)

If your dock uses a servo to deploy/retract:

```ini
variable_probe_servo_angle_retracted: 0
variable_probe_servo_angle_deployed: 90
```

These only take effect if a `[servo]` section is included in your probe config.


## Error Handling

When QGL, Z_TILT_ADJUST, or BED_MESH_CALIBRATE fails, the probe could be left attached near a hot bed. Enable automatic docking on error:

```ini
variable_autodock_on_probe_error: True    # Dock probe if probing operation fails
```

When enabled, if a probing operation raises an error (e.g. QGL fails to converge), the framework automatically docks the probe before the machine stops, protecting the probe microswitch from heat damage.


## Keep Probe Attached Between Operations

By default (`False`), the probe is docked after each probing operation during `START_PRINT`. This means for a typical print with QGL + bed mesh, the probe is attached and docked twice.

Enable keep-attached mode to leave the probe attached between consecutive operations, only docking once after all probing is complete:

```ini
variable_probe_keep_attached: False    # Default: dock after each operation
```

When set to `True`:

1. **QGL/Z_TILT**: Probe stays attached after calibration
2. **BED_MESH**: Probe stays attached after meshing
3. **Cleanup**: Probe is docked once after all `START_PRINT` actions complete
4. **Z homing**: Probe stays attached after G28 Z (if using `dockable_virtual`)

This reduces print start time by avoiding unnecessary attach/dock cycles. The probe is always docked at the end of `START_PRINT`, so there is no risk of starting a print with the probe still attached.

### When to use `True`

- Multiple consecutive probing operations (QGL → bed mesh → Z calibration)
- Minimizing print start time
- Reducing mechanical wear on the dock mechanism

### When to leave as `False`

- Single probing operation per print
- Prefer the safety of docking between each operation
- Standard configuration (no changes needed)


## How It Works

The framework hooks into Klippain's macro overrides. When you call `QUAD_GANTRY_LEVEL`, `Z_TILT_ADJUST`, or `BED_MESH_CALIBRATE`, the override macros automatically:

1. Call `ACTIVATE_PROBE` before the operation (attaches the probe if dockable)
2. Run the underlying Klipper command
3. Call `DEACTIVATE_PROBE` after the operation (docks the probe, or keeps it attached if `probe_keep_attached` is enabled)

You do not need to add `ACTIVATE_PROBE` or `DEACTIVATE_PROBE` to your slicer start G-code — Klippain handles the full lifecycle.
