"""Regression test for the START_PRINT action ordering.

The prime line must be executed after the final Z offsets (slicer Z_ADJUST and
the material additional_z_offset) are applied. Otherwise machines using a
multi Z endstop setup (dockable probe + physical Z endstop / auto z calibration)
print the prime line with a different Z reference than the object first layer,
which drives the nozzle into the bed when a significant material z offset is
configured.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
START_PRINT_CFG = REPO_ROOT / "macros" / "base" / "start_print.cfg"

PRIMELINE_CALL = "_MODULE_PRIMELINE"
PRIMELINE_LOOP_BRANCH = '{% elif action == "primeline" %}'
Z_ADJUST_LINE = "SET_GCODE_OFFSET Z_ADJUST={Z_ADJUST} MOVE=1"
MATERIAL_Z_OFFSET_LINE = "SET_GCODE_OFFSET Z_ADJUST={material.additional_z_offset} MOVE=1"
PRIMELINE_GUARD = '{% if "primeline" in sp_actions %}'


def start_print_lines() -> list[str]:
    text = START_PRINT_CFG.read_text(encoding="utf-8")
    # Keep only the START_PRINT macro body (the file defines other macros after it)
    body = text.split("[gcode_macro START_PRINT]", 1)[1]
    body = body.split("\n[gcode_macro ", 1)[0]
    return body.splitlines()


class StartPrintPrimeLineOrderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lines = start_print_lines()
        cls.stripped = [line.strip() for line in cls.lines]

    def _single_index(self, value: str) -> int:
        matches = [i for i, line in enumerate(self.stripped) if line == value]
        self.assertEqual(
            len(matches),
            1,
            f"expected exactly one {value!r} in START_PRINT, found {len(matches)}",
        )
        return matches[0]

    def test_primeline_not_executed_inside_action_loop(self) -> None:
        self.assertNotIn(
            PRIMELINE_LOOP_BRANCH,
            self.stripped,
            "primeline must not be dispatched from the startprint_actions loop",
        )
        loop_lines = [line for line in self.stripped if line.startswith("{% for action in sp_actions")]
        self.assertEqual(len(loop_lines), 1, "expected a single startprint_actions loop")
        self.assertIn('action != "primeline"', loop_lines[0])

    def test_final_z_offsets_are_applied_before_primeline(self) -> None:
        slicer_offset = self._single_index(Z_ADJUST_LINE)
        material_offset = self._single_index(MATERIAL_Z_OFFSET_LINE)
        primeline = self._single_index(PRIMELINE_CALL)

        self.assertLess(slicer_offset, material_offset)
        self.assertLess(
            material_offset,
            primeline,
            "the prime line must run after the final Z offsets are applied",
        )

    def test_primeline_call_is_guarded_by_the_action_list(self) -> None:
        primeline = self._single_index(PRIMELINE_CALL)
        self.assertGreater(primeline, 0)
        self.assertEqual(
            self.stripped[primeline - 1],
            PRIMELINE_GUARD,
            "the prime line call must be conditional on the primeline action being listed",
        )
        self.assertEqual(
            self.stripped[primeline + 1],
            "{% endif %}",
        )


if __name__ == "__main__":
    unittest.main()
