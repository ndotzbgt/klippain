#!/usr/bin/env python3

"""Tests for the module detection component."""

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from update_detect_modules import (
    get_enabled_includes,
    extract_module_variables,
)


class TestGetEnabledIncludes(unittest.TestCase):
    """Test parsing of printer.cfg include lines."""

    def test_active_include(self):
        text = textwrap.dedent("""\
            [include config/hardware/fans/aux_fan.cfg]
            # [include config/hardware/lights/status_leds.cfg]
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = get_enabled_includes(Path(f.name))
        os.unlink(f.name)

        self.assertIn("config/hardware/fans/aux_fan.cfg", result)

    def test_commented_include_not_active(self):
        text = "# [include config/hardware/lights/status_leds.cfg]"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = get_enabled_includes(Path(f.name))
        os.unlink(f.name)

        self.assertEqual(len(result), 0)

    def test_mixed_active_and_commented(self):
        text = textwrap.dedent("""\
            # [include config/hardware/probes/voron_tap.cfg]
            [include config/hardware/fans/part_fan.cfg]
            # [include config/software/bed_mesh/bed_mesh_300mm.cfg]
            [include config/hardware/fans/hotend_fan.cfg]
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = get_enabled_includes(Path(f.name))
        os.unlink(f.name)

        self.assertEqual(len(result), 2)
        self.assertIn("config/hardware/fans/part_fan.cfg", result)
        self.assertIn("config/hardware/fans/hotend_fan.cfg", result)

    def test_empty_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write("")
            f.flush()
            result = get_enabled_includes(Path(f.name))
        os.unlink(f.name)

        self.assertEqual(len(result), 0)

    def test_nonexistent_file(self):
        result = get_enabled_includes(Path("/tmp/nonexistent.cfg"))
        self.assertEqual(len(result), 0)


class TestExtractModuleVariables(unittest.TestCase):
    """Test variable extraction from module .cfg files."""

    def test_simple_module(self):
        text = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_filter_enabled: True
            variable_filter_name: "filter"
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = extract_module_variables(Path(f.name))
        os.unlink(f.name)

        self.assertEqual(result["variable_filter_enabled"], "True")
        self.assertEqual(result["variable_filter_name"], '"filter"')

    def test_module_with_no_variables(self):
        text = "[stepper_x]\nstep_pin: PB0\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = extract_module_variables(Path(f.name))
        os.unlink(f.name)

        self.assertEqual(result, {})

    def test_module_with_equals_separator(self):
        text = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_status_leds_control_enabled = True
            variable_status_leds_enabled: True
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = extract_module_variables(Path(f.name))
        os.unlink(f.name)

        self.assertEqual(result["variable_status_leds_control_enabled"], "True")
        self.assertEqual(result["variable_status_leds_enabled"], "True")

    def test_nonexistent_file(self):
        result = extract_module_variables(Path("/tmp/nonexistent.cfg"))
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
