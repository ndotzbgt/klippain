#!/usr/bin/env python3

"""Tests for the changelog digest component."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
from update_changelog_digest import (
    parse_conventional_commit,
    generate_digest,
)


class TestParseConventionalCommit(unittest.TestCase):
    """Test parsing of conventional commit subjects."""

    def test_feat_with_scope(self):
        cat, desc = parse_conventional_commit("feat(aux-fan): add tach support")
        self.assertEqual(cat, "Features")
        self.assertEqual(desc, "add tach support")

    def test_fix_without_scope(self):
        cat, desc = parse_conventional_commit("fix: memory leak")
        self.assertEqual(cat, "Bug Fixes")
        self.assertEqual(desc, "memory leak")

    def test_feat_with_breaking(self):
        cat, desc = parse_conventional_commit("feat!: breaking change")
        self.assertEqual(cat, "Features")
        self.assertEqual(desc, "breaking change")

    def test_merge_commit(self):
        cat, desc = parse_conventional_commit("Merge branch 'main' into dev")
        self.assertIsNone(cat)

    def test_non_conventional(self):
        cat, desc = parse_conventional_commit("some random commit message")
        self.assertIsNone(cat)
        self.assertEqual(desc, "some random commit message")

    def test_case_insensitive(self):
        cat, desc = parse_conventional_commit("FEAT: new feature")
        self.assertEqual(cat, "Features")

    def test_klippain_add_prefix(self):
        cat, desc = parse_conventional_commit("add: new MCU template")
        self.assertEqual(cat, "Features")
        self.assertEqual(desc, "new MCU template")

    def test_klippain_fix_prefix(self):
        cat, desc = parse_conventional_commit("fixed: typo in docs")
        self.assertEqual(cat, "Bug Fixes")
        self.assertEqual(desc, "typo in docs")

    def test_description_preserved(self):
        cat, desc = parse_conventional_commit("feat: lowercase start")
        self.assertEqual(desc, "lowercase start")

    def test_empty_subject(self):
        cat, desc = parse_conventional_commit("")
        self.assertIsNone(cat)


class TestGenerateDigest(unittest.TestCase):
    """Test digest generation with real git repo."""

    def test_empty_repo(self):
        """Test with the actual Klippain repo (should have commits)."""
        repo = Path(__file__).parents[1]
        # Just verify it doesn't crash
        result = generate_digest(repo, "0000000000", "0000000001")
        # May be empty if hashes don't exist, but shouldn't crash
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
