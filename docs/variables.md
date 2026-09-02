# Variables Configuration

The `variables.cfg` file allows you to customize macro behavior without modifying Klippain files directly. This file is safe to edit and will be preserved during updates.

## General Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_verbose` | `True` | Enable verbose output for debugging |

## Speeds and Accelerations

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_homing_travel_speed` | `350` | Travel speed during homing (mm/s) |
| `variable_travel_speed` | `350` | General travel speed (mm/s) |
| `variable_z_drop_speed` | `15` | Z axis drop speed (mm/s) |
| `variable_brush_clean_speed` | `100` | Speed during brush cleaning (mm/s) |
| `variable_probe_dock_speed` | `60` | Speed for probe dock operations (mm/s) |
| `variable_homing_travel_accel` | `3000` | Acceleration during homing (mm/s²) |
| `variable_tilting_travel_accel` | `3000` | Acceleration during tilt adjustments (mm/s²) |
| `variable_brush_clean_accel` | `1500` | Acceleration during brush cleaning (mm/s²) |
| `variable_probe_dock_accel` | `2000` | Acceleration for probe dock operations (mm/s²) |

## Homing and Start/End Print

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_zendstop_position` | `-1, -1` | Physical Z endstop pin position (only if not using auto z_calibration plugin) |
| `variable_force_homing_in_start_print` | `False` | Force full homing and QGL/Z_TILT during START_PRINT |
| `variable_homing_zhop` | `5` | Z hop before homing to avoid bed grinding (mm) |
| `variable_homing_first` | `"X"` | Axis to home first (`"X"` or `"Y"`) |
| `variable_homing_backoff_distance_xy` | `-5, -5` | Backoff distance after touching endstops (mm) |
| `variable_sensorless_current_factor` | `75` | Percentage of run_current used during sensorless homing |
| `variable_probe_dock_margin_xy` | `0, 0` | Margin to avoid probe dock when homing (mm) |
| `variable_safe_extruder_temp` | `150` | Extruder temperature for chamber preheating and START_PRINT actions (°C) |

## Prime Line

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_prime_line_adaptive_mode` | `True` | Use adaptive primeline for automatic start point and direction |
| `variable_prime_line_xy` | `5, 2.5` | Starting point of the prime line (mm) |
| `variable_prime_line_direction` | `"X"` | Direction of the prime line (`"X"` or `"Y"`) |
| `variable_prime_line_length` | `40` | Length of the prime line on the bed (mm) |
| `variable_prime_line_purge_distance` | `30` | Length of filament to purge (mm) |
| `variable_prime_line_flowrate` | `10` | Flow rate for the prime line (mm³/s) |
| `variable_prime_line_height` | `0.6` | Height of the prime line (mm) |
| `variable_prime_line_margin` | `5` | Distance of purge line from fl_size rectangle (mm) |
| `variable_prime_line_wipe` | `False` | Enable wipe after completing the prime line |

## Retraction

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_retract_length` | `20` | Filament retract length to prevent heatcreep and oozing (mm) |
| `variable_unretract_length` | `23` | Filament unretract length to prime nozzle (mm, recommended 10-20% more than retract) |

## Park Position

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_park_position_xy` | `-1, -1` | Park position for pause, end_print, etc. (mm) |
| `variable_park_lift_z` | `50` | Z height to lift to when parking (mm) |

## Pause and End Print Behavior

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_idle_timeout_on_pause` | `0` | Idle timeout duration when print is paused (0 = no change) |
| `variable_turn_off_extruder_on_pause` | `False` | Automatically turn off extruder when paused |
| `variable_disable_motors_in_end_print` | `False` | Automatically disable motors in END_PRINT |
| `variable_turn_off_heaters_in_end_print` | `True` | Automatically turn off heaters in END_PRINT |
| `variable_reset_velocity_limits_in_end_print` | `True` | Reset velocity limits to configured values in END_PRINT |
| `variable_reset_extrude_factor_in_end_print` | `True` | Reset extrude factor to 100% in END_PRINT |
| `variable_reset_speed_factor_in_end_print` | `True` | Reset speed factor to 100% in END_PRINT |

## Dockable Probe

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_min_bed_xy` | `0, 0` | Minimum bed size for safety checks (mm) |
| `variable_max_bed_xy` | `9999, 9999` | Maximum bed size for safety checks (mm) |
| `variable_probe_min_z_travel` | `20` | Minimum safe Z height to attach/detach probe (mm) |
| `variable_probe_stow_z_height` | `None` | Z height to move to when detaching probe (None = no movement) |
| `variable_probe_dock_location_xy` | `-1, -1` | Position of the probe dock (mm) |
| `variable_probe_servo_angle_retracted` | `0` | Servo angle for retracted position (if applicable) |
| `variable_probe_servo_angle_deployed` | `90` | Servo angle for deployed position (if applicable) |
| `variable_probe_before_attach_position` | `"front"` | Toolhead position before attaching probe |
| `variable_probe_after_attach_position` | `"front"` | Toolhead position after attaching probe |
| `variable_probe_before_dock_position` | `"front"` | Toolhead position before docking probe |
| `variable_probe_after_dock_position` | `"left"` | Toolhead position after docking probe |
| `variable_probe_move_attach_length` | `30` | Length of move to attach probe (mm) |
| `variable_probe_move_dock_length` | `30` | Length of move to dock probe (mm) |
| `variable_autodock_on_probe_error` | `True` | Automatically dock probe on QGL/Z_TILT/BED_MESH errors |

## Virtual Z Contact Probe

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_probe_contact_max_temp` | `150` | Maximum temperature for contact probing (°C) |
| `variable_probe_contact_deactivation_zhop` | `5` | Z hop before restoring temperature after contact probing (mm) |
| `variable_probe_unsupported_contact_action_policy` | `"warn"` | Policy for unsupported contact actions (`"warn"` or `"error"`) |

## Voron TAP Probe

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_tap_max_probing_temp` | `150` | Maximum temperature for TAP probing (°C) |
| `variable_tap_deactivation_zhop` | `5` | Z hop before restoring temperature after TAP probing (mm) |

## Beacon Probe

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_beacon_max_probing_temp` | `150` | Maximum temperature for Beacon probing (°C) |
| `variable_beacon_deactivation_zhop` | `5` | Z hop before restoring temperature after Beacon probing (mm) |

## Material Parameters

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_print_default_bed_temp` | `105` | Default bed temperature (°C) |
| `variable_print_default_extruder_temp` | `240` | Default extruder temperature (°C) |
| `variable_print_default_chamber_temp` | `0` | Default chamber temperature (°C) |
| `variable_print_default_chamber_max_heating_time` | `15` | Maximum chamber heating time (minutes) |
| `variable_print_default_chamber_temp_tolerance` | `0.0` | Chamber temperature tolerance (°C) |
| `variable_print_default_soak` | `8` | Default soak time (minutes) |
| `variable_print_default_material` | `"XXX"` | Default material type |

### Material Configuration Dictionary

The `variable_material_parameters` dictionary defines per-material settings:

```python
variable_material_parameters: {
    'PLA': {
        'pressure_advance': 0.0525,
        'retract_length': 0.75,
        'unretract_extra_length': 0,
        'retract_speed': 40,
        'unretract_speed': 30,
        'filter_speed': 0,
        'additional_z_offset': 0,
        'filament_sensor': 1
    },
    # ... additional materials
}
```

Each material can have:
- `pressure_advance` - Pressure advance value
- `retract_length` - Firmware retraction length (mm)
- `unretract_extra_length` - Extra unretract length (mm)
- `retract_speed` - Retraction speed (mm/s)
- `unretract_speed` - Unretract speed (mm/s)
- `filter_speed` - Filter speed percentage (0-100)
- `additional_z_offset` - Additional Z offset during print (mm)
- `filament_sensor` - Filament sensor state (0=disabled, 1=enabled)

## MMU/ERCF Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_mmu_force_homing_in_start_print` | `False` | Force homing during START_PRINT with MMU |
| `variable_mmu_unload_on_cancel_print` | `False` | Unload filament on cancel print |
| `variable_mmu_unload_on_end_print` | `True` | Unload filament on end print |
| `variable_mmu_check_gates_on_start_print` | `False` | Check gates at start of print (recommended: True with TOOLS_USED in slicer) |
| `variable_mmu_check_errors_on_start_print` | `False` | Early check of MMU errors during START_PRINT |

## Filter Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_filter_default_time_on_end_print` | `600` | Filter run time after print ends (seconds) |

## Auxiliary Fan Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_aux_fan_speed_on_end_print` | `100` | Aux fan speed after print ends (percent) |
| `variable_aux_fan_time_on_end_print` | `300` | Aux fan run time after print ends (seconds) |
| `variable_aux_fan_soak_speed` | `0` | Aux fan speed during heatsoak (percent, 0=disabled) |
| `variable_aux_fan_vent_temp` | `0` | Chamber temp threshold for venting at print start (°C, 0=disabled) |
| `variable_aux_fan_vent_speed` | `100` | Aux fan speed during chamber vent (percent) |
| `variable_aux_fan_vent_time` | `120` | Aux fan vent duration at print start (seconds) |

## Brush and Purge Bucket

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_purge_and_brush_enabled` | `False` | Enable purge bucket and brush system |
| `variable_force_homing_before_brush` | `False` | Home Z axis before brush cleaning |
| `variable_brush_over_y_axis` | `True` | Cleanup moves along Y axis then X axis (False = X only) |
| `variable_brush_xyz` | `-1, -1, -1` | Brush center position (mm) |
| `variable_brush_width_x` | `40` | Brush width in X direction (mm) |
| `variable_brush_center_offset` | `0` | Offset of brush center to start brushing (mm, + towards max X) |
| `variable_brushes` | `6` | Number of brush passes |
| `variable_purge_bucket_xyz` | `-1, -1, -1` | Purge bucket position (mm) |
| `variable_purge_distance` | `30` | Amount to purge (mm) |
| `variable_purge_ooze_time` | `10` | Wait time after purge for nozzle ooze (seconds) |
| `variable_purgeclean_servo_angle_retracted` | `0` | Servo angle for retracted position (if applicable) |
| `variable_purgeclean_servo_angle_deployed` | `90` | Servo angle for deployed position (if applicable) |

## Caselight

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_caselight_on_at_startup` | `False` | Turn on caselight LEDs at startup |
| `variable_light_intensity_startup` | `100` | Light intensity at startup (percent) |
| `variable_light_intensity_start_print` | `100` | Light intensity during start print (percent) |
| `variable_light_intensity_printing` | `30` | Light intensity during printing (percent) |
| `variable_light_intensity_end_print` | `0` | Light intensity at end print (percent) |

## Other Hardware Options

| Variable | Default | Description |
|----------|---------|-------------|
| `variable_fix_heaters_temperature_settle` | `False` | Patch M190/M109 to avoid wait time on low thermal latency devices |
| `variable_resonnance_test_point_xy` | `-1, -1` | Resonance test position (mm, -1,-1 = bed center at 50mm height) |
| `variable_resonnance_test_z_clearance` | `50` | Z clearance for resonance testing (mm) |

## START_PRINT and END_PRINT Actions

The `variable_startprint_actions` and `variable_endprint_actions` lists define the sequence of actions during print start and end. See [overrides.md](./overrides.md#custom-start_print-and-end_print-actions) for details on customizing these lists.
