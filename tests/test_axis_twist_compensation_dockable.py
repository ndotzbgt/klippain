#!/usr/bin/env python3
"""Behavioral tests for the axis_twist_compensation_dockable plugin.

Covers the calibration wizard flow, cancellation, probe cleanup (state
machine), result calculation/normalization, CLEAR command, and Klipper
internal API usage.

Run with:
    python3 -m unittest tests.test_axis_twist_compensation_dockable -v
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest
from unittest.mock import ANY, MagicMock, patch

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, "scripts",
                      "axis_twist_compensation_dockable.py")

# Bootstrap a fake klippy.extras package so the plugin's relative import
# (``from . import manual_probe, probe``) resolves without a real Klipper
# installation.
_klippy_extras = types.ModuleType("klippy.extras")
_klippy_extras.manual_probe = MagicMock()
_klippy_extras.probe = MagicMock()
_klippy_extras.__path__ = ["/mock/klippy/extras"]
sys.modules.setdefault("klippy", types.ModuleType("klippy"))
sys.modules["klippy"].extras = _klippy_extras
sys.modules.setdefault("klippy.extras", _klippy_extras)

_spec = importlib.util.spec_from_file_location(
    "klippy.extras.axis_twist_compensation_dockable", SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

AxisTwistCompensationDockable = _mod.AxisTwistCompensationDockable
CalibrationState = _mod.CalibrationState
manual_probe_mod = _klippy_extras.manual_probe
probe_mod = _klippy_extras.probe

# Marker raised by tests to force probe.run_single_probe to fail.
_PROBE_ERROR = RuntimeError("probe hardware fault")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_compensation(**overrides):
    c = MagicMock()
    c.calibrate_start_x = 25
    c.calibrate_end_x = 325
    c.calibrate_y = 150
    c.calibrate_start_y = 25
    c.calibrate_end_y = 325
    c.calibrate_x = 150
    c.speed = 50
    c.horizontal_move_z = 10
    c.z_compensations = []
    c.zy_compensations = []
    c.compensation_start_x = None
    c.compensation_end_x = None
    c.compensation_start_y = None
    c.compensation_end_y = None
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


def _make_gcmd(params=None):
    p = params or {}
    gcmd = MagicMock()
    gcmd.get_int = MagicMock(
        side_effect=lambda name, default=0: p.get(name, default))
    gcmd.get = MagicMock(
        side_effect=lambda name, default="": p.get(name, default))
    gcmd.respond_info = MagicMock()
    gcmd.error = MagicMock(side_effect=RuntimeError)
    return gcmd


class _ProbeResult:
    def __init__(self, bed_z):
        self.bed_z = bed_z


def _make_plugin(is_dockable=False, probe_offsets=None, user_vars=None,
                 compensation=None):
    """Create a fully wired plugin instance with mock Klipper objects."""
    if probe_offsets is None:
        probe_offsets = (0, 0, 0)

    # --- gcode ---------------------------------------------------------------
    gcode = MagicMock()
    _gcode_commands: dict[str, object] = {}

    def _register(name, handler, desc=None):
        _gcode_commands[name] = handler

    def _register_none(name, _handler=None, desc=None):
        _gcode_commands[name] = None

    gcode.register_command.side_effect = _register
    gcode.run_script_from_command = MagicMock()

    # --- probe ---------------------------------------------------------------
    prb = MagicMock()
    prb.get_offsets = MagicMock(return_value=probe_offsets)
    prb.get_probe_params = MagicMock(return_value={"lift_speed": 5})

    # --- probe.run_single_probe result factory ------------------------------
    def _run_single_probe(probe_obj, gcmd):
        auto_z = plugin.auto_z if hasattr(plugin, "auto_z") else []
        idx = len(auto_z)
        defaults = [1.0, 2.0, 3.0]
        return _ProbeResult(defaults[idx] if idx < len(defaults) else 1.5)

    probe_mod.run_single_probe = MagicMock(side_effect=_run_single_probe)

    # --- toolhead ------------------------------------------------------------
    toolhead = MagicMock()
    toolhead.get_position = MagicMock(return_value=[150, 150, 10])

    # --- configfile ----------------------------------------------------------
    configfile = MagicMock()

    # --- compensation --------------------------------------------------------
    if compensation is None:
        compensation = _make_compensation()

    # --- user vars (for dockable detection) ---------------------------------
    user_vars_mock = MagicMock()
    if user_vars is not None:
        user_vars_mock.variables = user_vars
    else:
        user_vars_mock.variables = {}

    # --- printer -------------------------------------------------------------
    printer = MagicMock()
    _objects = {
        "gcode": gcode,
        "probe": prb,
        "axis_twist_compensation": compensation,
        "toolhead": toolhead,
        "configfile": configfile,
        "gcode_macro _USER_VARIABLES": user_vars_mock,
    }
    printer.lookup_object = MagicMock(side_effect=lambda name, *a: _objects[name])
    printer.config_error = MagicMock(side_effect=RuntimeError)

    # --- ManualProbeHelper stub ---------------------------------------------
    _stored_callback = {}

    class _FakeManualProbeHelper:
        def __init__(self, printer, gcmd, callback):
            _stored_callback["cb"] = callback

    manual_probe_mod.ManualProbeHelper = _FakeManualProbeHelper
    manual_probe_mod.verify_no_manual_probe = MagicMock()

    # --- config stub ---------------------------------------------------------
    config = MagicMock()
    config.get_printer = MagicMock(return_value=printer)

    # --- build ---------------------------------------------------------------
    plugin = AxisTwistCompensationDockable(config)
    plugin._handle_connect()
    plugin._handle_connect()  # idempotent (compensation already resolved)
    # Only override is_dockable when caller did NOT provide explicit user_vars.
    # When user_vars is provided, _handle_connect already detected the right value.
    if user_vars is None:
        plugin.is_dockable = is_dockable

    # expose for tests
    plugin._gcode = gcode
    plugin._gcode_commands = _gcode_commands
    plugin._stored_callback = _stored_callback
    plugin._probe_mod = probe_mod
    plugin._manual_probe_mod = manual_probe_mod

    return plugin


def _accept_all_points(plugin):
    """Simulate the user accepting every manual probe point."""
    cb = plugin._stored_callback["cb"]
    for _ in range(len(plugin.bed_points)):
        cb(_ProbeResult(0.5))
        if plugin._stored_callback.get("cb") is None:
            break


def _dispatch(plugin, params=None):
    """Build a gcmd and dispatch it to the plugin."""
    gcmd = _make_gcmd(params)
    plugin.cmd_AXIS_TWIST_COMPENSATION_CALIBRATE(gcmd)
    return gcmd


def _dispatch_y(plugin, params=None):
    """Dispatch a Y-axis calibration (merges AXIS=Y into params)."""
    p = params.copy() if params else {}
    p["AXIS"] = "Y"
    return _dispatch(plugin, p)


def _dispatch_bad_axis(plugin, axis="Z"):
    """Dispatch with an invalid axis."""
    return _dispatch(plugin, {"AXIS": axis})


def _dispatch_low_sample(plugin):
    """Dispatch with SAMPLE_COUNT=1 (below minimum)."""
    return _dispatch(plugin, {"SAMPLE_COUNT": 1})


def _bad_x_compensation(**overrides):
    """Return compensation with one X param missing (None)."""
    return _make_compensation(calibrate_start_x=None, **overrides)


def _bad_y_compensation(**overrides):
    """Return compensation with one Y param missing (None)."""
    return _make_compensation(calibrate_start_y=None, **overrides)


def _make_single_point_compensation():
    """Compensation configured for exactly 2 points (minimum)."""
    return _make_compensation()


# ===========================================================================
# Tests
# ===========================================================================


# ---- Construction & registration -----------------------------------------


class AxisTwistCompensationConfigTest(unittest.TestCase):
    def test_load_config_returns_plugin_instance(self):
        plugin = _make_plugin()
        self.assertIsInstance(plugin, AxisTwistCompensationDockable)

    def test_constructor_registers_klippy_connect_handler(self):
        plugin = _make_plugin()
        plugin.printer.register_event_handler.assert_any_call(
            "klippy:connect", plugin._handle_connect)

    def test_constructor_registers_klippy_disconnect_handler(self):
        plugin = _make_plugin()
        plugin.printer.register_event_handler.assert_any_call(
            "klippy:disconnect", plugin._handle_disconnect)

    def test_constructor_registers_gcode_commands(self):
        plugin = _make_plugin()
        self.assertIn("AXIS_TWIST_COMPENSATION_CALIBRATE",
                      plugin._gcode_commands)
        self.assertIn("CLEAR_AXIS_TWIST_COMPENSATION",
                      plugin._gcode_commands)

    def test_constructor_unregisters_stock_command(self):
        plugin = _make_plugin()
        calls = plugin._gcode.register_command.call_args_list
        unregister_calls = [c for c in calls if c[0][1] is None]
        self.assertTrue(any(c[0][0] == "AXIS_TWIST_COMPENSATION_CALIBRATE"
                            for c in unregister_calls))

    def test_initial_state_is_idle(self):
        plugin = _make_plugin()
        self.assertEqual(plugin._state, CalibrationState.IDLE)


# ---- Connect handler -----------------------------------------------------


class AxisTwistConnectHandlerTest(unittest.TestCase):
    def test_connect_raises_error_when_probe_missing(self):
        printer = MagicMock()
        objects = {"gcode": MagicMock(), "axis_twist_compensation": MagicMock()}
        printer.lookup_object = MagicMock(
            side_effect=lambda name, *a: objects.get(name))
        printer.config_error = MagicMock(side_effect=RuntimeError)
        printer.register_event_handler = MagicMock()
        config = MagicMock()
        config.get_printer = MagicMock(return_value=printer)
        plugin = AxisTwistCompensationDockable(config)
        with self.assertRaises(RuntimeError):
            plugin._handle_connect()

    def test_connect_detects_dockable_probe(self):
        p = _make_plugin(is_dockable=False,
                         user_vars={"probe_type_enabled": "dockable"})
        self.assertTrue(p.is_dockable)

    def test_connect_detects_dockable_virtual_probe(self):
        p = _make_plugin(is_dockable=False,
                         user_vars={"probe_type_enabled": "dockable_virtual"})
        self.assertTrue(p.is_dockable)

    def test_connect_non_dockable_probe(self):
        p = _make_plugin(is_dockable=False,
                         user_vars={"probe_type_enabled": "inductive"})
        self.assertFalse(p.is_dockable)

    def test_connect_no_user_variables_is_non_dockable(self):
        p = _make_plugin(is_dockable=False, user_vars={})
        self.assertFalse(p.is_dockable)

    def test_connect_sets_lift_speed(self):
        p = _make_plugin()
        self.assertEqual(p.lift_speed, 5)


# ---- Validation ----------------------------------------------------------


class AxisTwistCalibrateValidationTest(unittest.TestCase):
    def test_invalid_axis_raises_error(self):
        p = _make_plugin(is_dockable=True)
        with self.assertRaises(RuntimeError):
            _dispatch_bad_axis(p)

    def test_sample_count_less_than_two_raises_error(self):
        p = _make_plugin(is_dockable=True)
        with self.assertRaises(RuntimeError):
            _dispatch_low_sample(p)

    def test_x_missing_calibrate_start_x_raises_error(self):
        p = _make_plugin(compensation=_bad_x_compensation())
        with self.assertRaises(RuntimeError):
            _dispatch(p)

    def test_x_missing_calibrate_end_x_raises_error(self):
        p = _make_plugin(compensation=_make_compensation(calibrate_end_x=None))
        with self.assertRaises(RuntimeError):
            _dispatch(p)

    def test_x_missing_calibrate_y_raises_error(self):
        p = _make_plugin(compensation=_make_compensation(calibrate_y=None))
        with self.assertRaises(RuntimeError):
            _dispatch(p)

    def test_y_missing_calibrate_start_y_raises_error(self):
        p = _make_plugin(compensation=_bad_y_compensation())
        with self.assertRaises(RuntimeError):
            _dispatch_y(p)

    def test_y_missing_calibrate_end_y_raises_error(self):
        p = _make_plugin(compensation=_make_compensation(calibrate_end_y=None))
        with self.assertRaises(RuntimeError):
            _dispatch_y(p)

    def test_y_missing_calibrate_x_raises_error(self):
        p = _make_plugin(compensation=_make_compensation(calibrate_x=None))
        with self.assertRaises(RuntimeError):
            _dispatch_y(p)


# ---- Full flow (dockable) -----------------------------------------------


class AxisTwistDockableFlowTest(unittest.TestCase):
    def test_calibrate_x_dockable_three_points(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        _accept_all_points(p)
        gcode = p._gcode
        gcode.run_script_from_command.assert_any_call("ACTIVATE_PROBE")
        gcode.run_script_from_command.assert_any_call("DEACTIVATE_PROBE")
        activate_calls = [c for c in
                          gcode.run_script_from_command.call_args_list
                          if c[0][0] == "ACTIVATE_PROBE"]
        self.assertGreaterEqual(len(activate_calls), 2)

    def test_calibrate_x_dockable_single_point(self):
        p = _make_plugin(is_dockable=True,
                         compensation=_make_single_point_compensation())
        _dispatch(p, {"SAMPLE_COUNT": 2})
        _accept_all_points(p)
        gcode = p._gcode
        gcode.run_script_from_command.assert_any_call("ACTIVATE_PROBE")
        gcode.run_script_from_command.assert_any_call("DEACTIVATE_PROBE")

    def test_calibrate_flow_moves_in_correct_order(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        _accept_all_points(p)
        toolhead = p.printer.lookup_object("toolhead")
        moves = toolhead.manual_move.call_args_list
        # First moves should be height-only, then XY
        self.assertTrue(len(moves) > 6)
        z_move = moves[0]
        self.assertIsNone(z_move[0][0][0])
        self.assertIsNone(z_move[0][0][1])
        self.assertIsNotNone(z_move[0][0][2])


# ---- Full flow (non-dockable) -------------------------------------------


class AxisTwistNonDockableFlowTest(unittest.TestCase):
    def test_calibrate_x_non_dockable_full_flow(self):
        p = _make_plugin(is_dockable=False)
        _dispatch(p)
        _accept_all_points(p)
        gcode = p._gcode
        gcode.run_script_from_command.assert_not_called()

    def test_calibrate_with_probe_offsets(self):
        p = _make_plugin(is_dockable=False, probe_offsets=(20, 10, 0))
        _dispatch(p)
        _accept_all_points(p)
        # bed_points are unchanged, test_points offset by probe offsets
        self.assertEqual(p.bed_points[0], (25, 150))
        self.assertEqual(p.test_points[0], (5, 140))


# ---- Y axis calibration --------------------------------------------------


class AxisTwistYAxisFlowTest(unittest.TestCase):
    def test_calibrate_y_dockable_full_flow(self):
        p = _make_plugin(is_dockable=True)
        _dispatch_y(p)
        _accept_all_points(p)
        gcode = p._gcode
        gcode.run_script_from_command.assert_any_call("ACTIVATE_PROBE")
        gcode.run_script_from_command.assert_any_call("DEACTIVATE_PROBE")
        self.assertEqual(p.current_axis, "Y")
        self.assertTrue(p.bed_points[0][0] == p.bed_points[1][0])

    def test_calibrate_y_non_dockable_full_flow(self):
        p = _make_plugin(is_dockable=False)
        _dispatch_y(p)
        _accept_all_points(p)
        self.assertEqual(p.current_axis, "Y")
        gcode = p._gcode
        gcode.run_script_from_command.assert_not_called()


# ---- Result calculation / normalization ----------------------------------


class AxisTwistResultCalculationTest(unittest.TestCase):
    def _finalize(self, plugin):
        plugin.gcmd = _make_gcmd()
        plugin._finalize_calibration()

    def test_result_calculation_known_values(self):
        p = _make_plugin(is_dockable=False,
                         compensation=_make_compensation())
        p.auto_z = [1.0, 2.0, 3.0]
        p.manual_z = [0.5, 1.0, 1.5]
        p.current_axis = "X"
        p.bed_points = [(25, 150), (175, 150), (325, 150)]
        self._finalize(p)
        expected_results = [0.5, 0.0, -0.5]
        self.assertAlmostEqual(p.compensation.z_compensations[0], 0.5, 6)
        self.assertAlmostEqual(p.compensation.z_compensations[1], 0.0, 6)
        self.assertAlmostEqual(p.compensation.z_compensations[2], -0.5, 6)

    def test_finalize_x_axis_saves_to_z_compensations(self):
        p = _make_plugin(is_dockable=False)
        p.auto_z = [1.0, 2.0]
        p.manual_z = [0.5, 1.5]
        p.current_axis = "X"
        p.bed_points = [(50, 150), (300, 150)]
        self._finalize(p)
        cf = p.printer.lookup_object("configfile")
        cf.set.assert_any_call("axis_twist_compensation",
                               "z_compensations", ANY)

    def test_finalize_y_axis_saves_to_zy_compensations(self):
        p = _make_plugin(is_dockable=False)
        p.auto_z = [1.0, 2.0]
        p.manual_z = [0.5, 1.5]
        p.current_axis = "Y"
        p.bed_points = [(150, 50), (150, 300)]
        self._finalize(p)
        cf = p.printer.lookup_object("configfile")
        cf.set.assert_any_call("axis_twist_compensation",
                               "zy_compensations", ANY)

    def test_result_normalization_constant_offset(self):
        p = _make_plugin(is_dockable=False)
        p.auto_z = [5.0, 6.0, 7.0]
        p.manual_z = [2.0, 3.0, 4.0]
        p.current_axis = "X"
        p.bed_points = [(25, 150), (175, 150), (325, 150)]
        self._finalize(p)
        for r in p.compensation.z_compensations:
            self.assertAlmostEqual(r, 0.0, 6)

    def test_finalize_dockable_reattaches_probe(self):
        p = _make_plugin(is_dockable=True)
        p.auto_z = [1.0, 2.0]
        p.manual_z = [0.5, 1.5]
        p.current_axis = "X"
        p.bed_points = [(50, 150), (300, 150)]
        self._finalize(p)
        gcode = p._gcode
        gcode.run_script_from_command.assert_any_call("ACTIVATE_PROBE")

    def test_finalize_non_dockable_no_reattach(self):
        p = _make_plugin(is_dockable=False)
        p.auto_z = [1.0, 2.0]
        p.manual_z = [0.5, 1.5]
        p.current_axis = "X"
        p.bed_points = [(50, 150), (300, 150)]
        self._finalize(p)
        gcode = p._gcode
        gcode.run_script_from_command.assert_not_called()

    def test_precision_formatting_in_config(self):
        p = _make_plugin(is_dockable=False)
        p.auto_z = [1.123456789, 2.987654321]
        p.manual_z = [0.5, 1.5]
        p.current_axis = "X"
        p.bed_points = [(50, 150), (300, 150)]
        self._finalize(p)
        cf = p.printer.lookup_object("configfile")
        set_calls = [c for c in cf.set.call_args_list
                     if c[0][1] == "z_compensations"]
        self.assertTrue(set_calls)
        values_str = set_calls[0][0][2]
        for part in values_str.split(","):
            decimals = part.strip().split(".")[1]
            self.assertLessEqual(len(decimals), 6)

    def test_calibration_complete_message(self):
        p = _make_plugin(is_dockable=False)
        p.auto_z = [1.0, 2.0]
        p.manual_z = [0.5, 1.5]
        p.current_axis = "X"
        p.bed_points = [(50, 150), (300, 150)]
        self._finalize(p)
        self.assertEqual(p._state, CalibrationState.COMPLETED)
        gcmd = MagicMock()
        gcmd.error = MagicMock(side_effect=RuntimeError)
        p.gcmd = gcmd
        p._finalize_calibration()
        # z_offsets = [0.5, 0.5], avg = 0.5, results = [0.0, 0.0]
        gcmd.respond_info.assert_any_call(
            "AXIS_TWIST_COMPENSATION_CALIBRATE: Calibration complete, "
            "offsets: [0.0, 0.0], mean z_offset: 0.500000")


# ---- Cancellation --------------------------------------------------------


class AxisTwistCancellationTest(unittest.TestCase):
    def test_cancellation_dockable_reattaches_probe(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        self.assertEqual(p._state, CalibrationState.MANUAL_PROBING)
        p._stored_callback["cb"](None)
        gcode = p._gcode
        gcode.run_script_from_command.assert_any_call("ACTIVATE_PROBE")
        self.assertEqual(p._state, CalibrationState.IDLE)

    def test_cancellation_non_dockable_does_not_call_activate(self):
        p = _make_plugin(is_dockable=False)
        _dispatch(p)
        self.assertEqual(p._state, CalibrationState.MANUAL_PROBING)
        p._stored_callback["cb"](None)
        gcode = p._gcode
        gcode.run_script_from_command.assert_not_called()
        self.assertEqual(p._state, CalibrationState.IDLE)

    def test_cancellation_after_first_point(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        cb = p._stored_callback["cb"]
        cb(_ProbeResult(1.0))
        self.assertEqual(len(p.manual_z), 1)
        cb(None)
        gcode = p._gcode
        gcode.run_script_from_command.assert_any_call("ACTIVATE_PROBE")
        self.assertEqual(p._state, CalibrationState.IDLE)

    def test_cancellation_no_probes_done(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        p._stored_callback["cb"](None)
        self.assertEqual(p.manual_z, [])
        self.assertEqual(p._state, CalibrationState.IDLE)


# ---- Probe failures / cleanup -------------------------------------------


class AxisTwistCleanupTest(unittest.TestCase):
    def test_cleanup_during_auto_probe_docks_probe(self):
        p = _make_plugin(is_dockable=True)
        probe_mod.run_single_probe = MagicMock(side_effect=_PROBE_ERROR)
        with self.assertRaises(RuntimeError):
            _dispatch(p)
        gcode = p._gcode
        gcode.run_script_from_command.assert_any_call("ACTIVATE_PROBE")
        gcode.run_script_from_command.assert_any_call("DEACTIVATE_PROBE")

    def test_cleanup_during_auto_probe_leaves_probe_docked_for_nondockable(self):
        p = _make_plugin(is_dockable=False)
        probe_mod.run_single_probe = MagicMock(side_effect=_PROBE_ERROR)
        with self.assertRaises(RuntimeError):
            _dispatch(p)
        gcode = p._gcode
        gcode.run_script_from_command.assert_not_called()

    def test_cleanup_on_cancel_reattaches_probe(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        p._stored_callback["cb"](None)
        gcode = p._gcode
        gcode.run_script_from_command.assert_any_call("ACTIVATE_PROBE")
        self.assertEqual(p._state, CalibrationState.IDLE)

    def test_cleanup_best_effort_swallows_gcode_error(self):
        p = _make_plugin(is_dockable=True)
        p._state = CalibrationState.ACTIVATING
        p._gcode.run_script_from_command = MagicMock(
            side_effect=RuntimeError("gcode failed"))
        p._cleanup()
        self.assertEqual(p._state, CalibrationState.IDLE)

    def test_cleanup_noop_when_never_activated(self):
        p = _make_plugin(is_dockable=True)
        self.assertEqual(p._state, CalibrationState.IDLE)
        p._cleanup()
        p._gcode.run_script_from_command.assert_not_called()

    def test_cleanup_manual_probing_no_reattach(self):
        p = _make_plugin(is_dockable=True)
        p._state = CalibrationState.MANUAL_PROBING
        p._cleanup()
        p._gcode.run_script_from_command.assert_not_called()

    def test_cleanup_manual_probing_with_reattach(self):
        p = _make_plugin(is_dockable=True)
        p._state = CalibrationState.MANUAL_PROBING
        p._cleanup(reattach_if_docked=True)
        p._gcode.run_script_from_command.assert_any_call("ACTIVATE_PROBE")


# ---- State machine -------------------------------------------------------


class AxisTwistStateTest(unittest.TestCase):
    def test_dockable_state_transitions_full_flow(self):
        p = _make_plugin(is_dockable=True)
        states = []

        def track_state(script):
            states.append(p._state.value)

        p._gcode.run_script_from_command.side_effect = track_state
        _dispatch(p)
        _accept_all_points(p)

        self.assertIn("activating", states)
        self.assertIn("docking", states)
        self.assertIn("reattaching", states)

    def test_state_resets_to_idle_after_success(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        _accept_all_points(p)
        self.assertEqual(p._state, CalibrationState.COMPLETED)

    def test_state_resets_to_idle_after_cancel(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        p._stored_callback["cb"](None)
        self.assertEqual(p._state, CalibrationState.IDLE)

    def test_state_resets_to_idle_after_probe_error(self):
        p = _make_plugin(is_dockable=True)
        probe_mod.run_single_probe = MagicMock(side_effect=_PROBE_ERROR)
        with self.assertRaises(RuntimeError):
            _dispatch(p)
        self.assertEqual(p._state, CalibrationState.IDLE)

    def test_disconnect_resets_state(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        self.assertNotEqual(p._state, CalibrationState.IDLE)
        p._handle_disconnect()
        self.assertEqual(p._state, CalibrationState.IDLE)
        self.assertIsNone(p.gcmd)


# ---- CLEAR command -------------------------------------------------------


class AxisTwistClearCommandTest(unittest.TestCase):
    def _clear(self, axis=None):
        p = _make_plugin(is_dockable=True)
        gcmd = MagicMock()
        gcmd.get = MagicMock(return_value=axis or "BOTH")
        gcmd.respond_info = MagicMock()
        gcmd.error = MagicMock(side_effect=RuntimeError)
        p.cmd_CLEAR_AXIS_TWIST_COMPENSATION(gcmd)
        return p, gcmd

    def test_clear_both(self):
        p, gcmd = self._clear("BOTH")
        p.compensation.clear_compensations.assert_called_once_with()
        cf = p.printer.lookup_object("configfile")
        cf.set.assert_any_call("axis_twist_compensation",
                               "z_compensations", "")
        cf.set.assert_any_call("axis_twist_compensation",
                               "zy_compensations", "")

    def test_clear_x(self):
        p, _ = self._clear("X")
        p.compensation.clear_compensations.assert_called_once_with("X")

    def test_clear_y(self):
        p, _ = self._clear("Y")
        p.compensation.clear_compensations.assert_called_once_with("Y")

    def test_clear_invalid_axis(self):
        with self.assertRaises(RuntimeError):
            self._clear("Z")


# ---- Move helper ---------------------------------------------------------


class AxisTwistMoveHelperTest(unittest.TestCase):
    def test_move_xy_only(self):
        p = _make_plugin(is_dockable=False)
        p._move_helper((100, 200))
        th = p.printer.lookup_object("toolhead")
        th.manual_move.assert_called_once()
        args = th.manual_move.call_args[0]
        self.assertEqual(args[0][:2], (100, 200))
        self.assertIsNone(args[0][2])

    def test_move_xyz(self):
        p = _make_plugin(is_dockable=False)
        p._move_helper((100, 200, 50))
        th = p.printer.lookup_object("toolhead")
        th.manual_move.assert_called_once()
        args = th.manual_move.call_args[0]
        self.assertEqual(args[0], (100, 200, 50))

    def test_move_override_speed(self):
        p = _make_plugin(is_dockable=False)
        p._move_helper((100, 200), override_speed=999)
        th = p.printer.lookup_object("toolhead")
        th.manual_move.assert_called_once()
        self.assertEqual(th.manual_move.call_args[0][1], 999)

    def test_move_uses_lift_speed_for_z(self):
        p = _make_plugin(is_dockable=False)
        p.lift_speed = 7
        p._move_helper((100, 200, 10))
        th = p.printer.lookup_object("toolhead")
        self.assertEqual(th.manual_move.call_args[0][1], 7)


# ---- Edge cases ----------------------------------------------------------


class AxisTwistEdgeCaseTest(unittest.TestCase):
    def test_calibrate_with_custom_sample_count(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p, {"SAMPLE_COUNT": 5})
        self.assertEqual(len(p.bed_points), 5)
        self.assertEqual(len(p.test_points), 5)
        _accept_all_points(p)

    def test_calibrate_x_dockable_probes_correct_points(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        self.assertEqual(p.bed_points[0], (25, 150))
        self.assertEqual(p.bed_points[1], (175, 150))
        self.assertEqual(p.bed_points[2], (325, 150))

    def test_calibrate_y_probes_correct_points(self):
        p = _make_plugin(is_dockable=True)
        _dispatch_y(p)
        self.assertEqual(p.bed_points[0], (150, 25))
        self.assertEqual(p.bed_points[1], (150, 175))
        self.assertEqual(p.bed_points[2], (150, 325))

    def test_calibrate_x_dockable_test_points_offset(self):
        p = _make_plugin(is_dockable=True, probe_offsets=(20, 10, 0))
        _dispatch(p)
        self.assertEqual(p.test_points[0], (5, 140))
        self.assertEqual(p.test_points[1], (155, 140))
        self.assertEqual(p.test_points[2], (305, 140))

    def test_default_sample_count_is_three(self):
        p = _make_plugin(is_dockable=True)
        _dispatch(p)
        self.assertEqual(len(p.bed_points), 3)

    def test_rejects_axis_z(self):
        p = _make_plugin(is_dockable=True)
        with self.assertRaises(RuntimeError):
            _dispatch_bad_axis(p, "Z")


if __name__ == "__main__":
    unittest.main()
