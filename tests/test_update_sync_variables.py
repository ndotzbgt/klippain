#!/usr/bin/env python3

"""Tests for the variable sync component."""

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# Add scripts/ to path for imports
sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from update_sync_variables import (
    parse_variables_from_file,
    strip_inline_comment,
    find_insert_point,
    sync_variables,
)


class TestStripInlineComment(unittest.TestCase):
    """Test inline comment extraction."""

    def test_no_comment(self):
        value, comment = strip_inline_comment("True")
        self.assertEqual(value, "True")
        self.assertEqual(comment, "")

    def test_comment_with_hash(self):
        value, comment = strip_inline_comment("True # enable feature")
        self.assertEqual(value, "True")
        self.assertEqual(comment, "# enable feature")

    def test_comment_in_single_quotes(self):
        value, comment = strip_inline_comment("'hello # world'")
        self.assertEqual(value, "'hello # world'")
        self.assertEqual(comment, "")

    def test_comment_in_double_quotes(self):
        value, comment = strip_inline_comment('"hello # world"')
        self.assertEqual(value, '"hello # world"')
        self.assertEqual(comment, "")

    def test_empty_value(self):
        value, comment = strip_inline_comment("")
        self.assertEqual(value, "")
        self.assertEqual(comment, "")

    def test_hash_only(self):
        value, comment = strip_inline_comment("# comment")
        self.assertEqual(value, "")
        self.assertEqual(comment, "# comment")


class TestParseVariables(unittest.TestCase):
    """Test parsing of variables.cfg files."""

    def test_simple_variables(self):
        text = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: True
            variable_homing_speed: 350
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = parse_variables_from_file(Path(f.name))
        os.unlink(f.name)

        self.assertIn("variable_verbose", result)
        self.assertIn("variable_homing_speed", result)
        self.assertEqual(result["variable_verbose"][0], "variable_verbose: True")
        self.assertEqual(result["variable_homing_speed"][0], "variable_homing_speed: 350")

    def test_equals_separator(self):
        text = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_light_enabled = True
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = parse_variables_from_file(Path(f.name))
        os.unlink(f.name)

        self.assertIn("variable_light_enabled", result)

    def test_multiline_dict_value(self):
        text = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_material_parameters: {
                    'PLA': {
                        'pressure_advance': 0.0525,
                    },
                    'ABS': {
                        'pressure_advance': 0.0480,
                    }
                }
            variable_simple: True
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = parse_variables_from_file(Path(f.name))
        os.unlink(f.name)

        self.assertIn("variable_material_parameters", result)
        self.assertIn("variable_simple", result)
        raw = result["variable_material_parameters"][0]
        self.assertIn("PLA", raw)
        self.assertIn("ABS", raw)

    def test_inline_comment(self):
        text = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: True # enable verbose output
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = parse_variables_from_file(Path(f.name))
        os.unlink(f.name)

        self.assertIn("variable_verbose", result)
        raw, comment = result["variable_verbose"]
        self.assertEqual(comment, "# enable verbose output")

    def test_comments_skipped(self):
        text = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            # This is a comment
            variable_verbose: True
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = parse_variables_from_file(Path(f.name))
        os.unlink(f.name)

        self.assertIn("variable_verbose", result)
        self.assertEqual(len(result), 1)

    def test_stops_at_gcode_directive(self):
        text = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_before: True
            gcode:
            variable_after: False
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = parse_variables_from_file(Path(f.name))
        os.unlink(f.name)

        self.assertIn("variable_before", result)
        self.assertNotIn("variable_after", result)

    def test_stops_at_next_section(self):
        text = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_before: True

            [save_variables]
            filename: ~/printer_data/config/save_variables.cfg
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
            f.write(text)
            f.flush()
            result = parse_variables_from_file(Path(f.name))
        os.unlink(f.name)

        self.assertIn("variable_before", result)

    def test_real_upstream_variables_cfg(self):
        """Test against the actual upstream variables.cfg file."""
        upstream = Path(__file__).parents[1] / "user_templates" / "variables.cfg"
        if upstream.exists():
            result = parse_variables_from_file(upstream)
            self.assertIn("variable_verbose", result)
            self.assertIn("variable_material_parameters", result)
            self.assertIn("variable_homing_travel_speed", result)
            self.assertIn("variable_prime_line_xy", result)

    def test_nonexistent_file(self):
        result = parse_variables_from_file(Path("/tmp/nonexistent_file.cfg"))
        self.assertEqual(result, {})


class TestFindInsertPoint(unittest.TestCase):
    """Test finding the insert point before gcode: directive."""

    def test_finds_gcode_line(self):
        text = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: True
            gcode:
        """)
        pos = find_insert_point(text)
        self.assertGreater(pos, 0)
        self.assertEqual(text[pos], "g")

    def test_no_gcode_returns_negative(self):
        text = "[gcode_macro _USER_VARIABLES]\nvariable_verbose: True\n"
        pos = find_insert_point(text)
        self.assertEqual(pos, -1)

    def test_insert_before_gcode_preserves_position(self):
        text = "header\n[gcode_macro _USER_VARIABLES]\nvariable_a: True\n\ngcode:\n"
        pos = find_insert_point(text)
        before = text[:pos]
        after = text[pos:]
        self.assertTrue(before.endswith("\n"))
        self.assertTrue(after.startswith("gcode:"))


class TestSyncVariables(unittest.TestCase):
    """Test the full sync operation."""

    def test_adds_missing_variable(self):
        upstream = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: True
            variable_new_feature: False
            gcode:
        """)
        user = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: False
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False, dir="/tmp") as uf:
            uf.write(upstream)
            uf.flush()
            upstream_path = Path(uf.name)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False, dir="/tmp") as uf:
            uf.write(user)
            uf.flush()
            user_path = Path(uf.name)

        added = sync_variables(upstream_path, user_path, dry_run=True)
        self.assertIn("variable_new_feature", added)
        self.assertNotIn("variable_verbose", added)

        os.unlink(upstream_path)
        os.unlink(user_path)

    def test_no_missing_variables(self):
        upstream = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: True
            gcode:
        """)
        user = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: True
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False, dir="/tmp") as uf:
            uf.write(upstream)
            uf.flush()
            upstream_path = Path(uf.name)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False, dir="/tmp") as uf:
            uf.write(user)
            uf.flush()
            user_path = Path(uf.name)

        added = sync_variables(upstream_path, user_path, dry_run=True)
        self.assertEqual(added, [])

        os.unlink(upstream_path)
        os.unlink(user_path)

    def test_preserves_user_values(self):
        upstream = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: True
            variable_speed: 350
            gcode:
        """)
        user = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: False
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False, dir="/tmp") as uf:
            uf.write(upstream)
            uf.flush()
            upstream_path = Path(uf.name)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False, dir="/tmp") as uf:
            uf.write(user)
            uf.flush()
            user_path = Path(uf.name)

        added = sync_variables(upstream_path, user_path, dry_run=False)

        result = user_path.read_text()
        self.assertIn("variable_verbose: False", result)
        self.assertIn("variable_speed: 350", result)

        os.unlink(upstream_path)
        os.unlink(user_path)

    def test_idempotent(self):
        upstream = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: True
            variable_new: False
            gcode:
        """)
        user = textwrap.dedent("""\
            [gcode_macro _USER_VARIABLES]
            variable_verbose: True
            gcode:
        """)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False, dir="/tmp") as uf:
            uf.write(upstream)
            uf.flush()
            upstream_path = Path(uf.name)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False, dir="/tmp") as uf:
            uf.write(user)
            uf.flush()
            user_path = Path(uf.name)

        added1 = sync_variables(upstream_path, user_path, dry_run=False)
        self.assertEqual(len(added1), 1)

        added2 = sync_variables(upstream_path, user_path, dry_run=False)
        self.assertEqual(len(added2), 0)

        os.unlink(upstream_path)
        os.unlink(user_path)

    def test_no_user_file(self):
        upstream = Path("/tmp/nonexistent_upstream.cfg")
        user = Path("/tmp/nonexistent_user.cfg")
        added = sync_variables(upstream, user, dry_run=True)
        self.assertEqual(added, [])


if __name__ == "__main__":
    unittest.main()
