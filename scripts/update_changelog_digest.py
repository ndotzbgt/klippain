#!/usr/bin/env python3

##############################################
###### CHANGELOG DIGEST UPDATE SCRIPT #######
##############################################
# Written for Klippain post-update system
# @version: 1.0

# Generates a human-readable changelog digest from git log between two versions.
# Uses conventional commit prefixes to categorize commits.

# CHANGELOG:
#   v1.0: first version - conventional commit parsing, grouped output

import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


# Conventional commit type prefixes and their display categories
TYPE_MAP = {
    "feat": "Features",
    "fix": "Bug Fixes",
    "docs": "Documentation",
    "refactor": "Refactoring",
    "perf": "Performance",
    "test": "Tests",
    "chore": "Chores",
    "ci": "CI/CD",
    "style": "Style",
    "build": "Build",
    "revert": "Reverts",
}

# Additional Klippain-style prefixes (non-conventional but common)
KLIPPAIN_TYPE_MAP = {
    "add": "Features",
    "added": "Features",
    "fix": "Bug Fixes",
    "fixed": "Bug Fixes",
    "bugfix": "Bug Fixes",
    "bug": "Bug Fixes",
}

SKIP_PREFIXES = ("Merge ", "merge ", "backport ", "Backport ", "sync ", "main -> dev")


def get_commits_between(repo_path, old_commit, new_commit):
    """Get commit subjects between two commits.

    Returns list of (short_hash, subject) tuples.
    """
    try:
        result = subprocess.run(
            [
                "git", "-C", str(repo_path),
                "log", "--format=%h %s",
                f"{old_commit}..{new_commit}",
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []

        commits = []
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line or " " not in line:
                continue
            short_hash, subject = line.split(" ", 1)
            commits.append((short_hash, subject))
        return commits
    except (subprocess.TimeoutExpired, OSError):
        return []


def parse_conventional_commit(subject):
    """Parse a conventional commit subject line.

    Returns (category, description) or (None, original_subject) if not conventional.
    """
    stripped = subject.strip()

    # Skip merge commits and similar
    for skip in SKIP_PREFIXES:
        if stripped.startswith(skip):
            return None, stripped

    # Try conventional commit pattern: type(scope)!: description  OR  type: description
    m = re.match(r"^(\w+)(?:\([^)]*\))?!?:\s*(.+)$", stripped, re.IGNORECASE)
    if m:
        prefix = m.group(1).lower()
        description = m.group(2).strip()

        # Check standard conventional types
        if prefix in TYPE_MAP:
            return TYPE_MAP[prefix], description
        # Check Klippain-style prefixes
        if prefix in KLIPPAIN_TYPE_MAP:
            return KLIPPAIN_TYPE_MAP[prefix], description

    return None, stripped


def get_version_tag(commit_hash, repo_path):
    """Try to find the git tag closest to a commit hash."""
    try:
        result = subprocess.run(
            [
                "git", "-C", str(repo_path),
                "describe", "--tags", "--exact-match", commit_hash,
            ],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def generate_digest(repo_path, old_commit, new_commit):
    """Generate a changelog digest between two versions.

    Returns a formatted string, or empty string if no meaningful changes.
    """
    commits = get_commits_between(repo_path, old_commit, new_commit)

    if not commits:
        return ""

    # Parse and categorize commits
    groups = defaultdict(list)

    for short_hash, subject in commits:
        category, description = parse_conventional_commit(subject)

        if category is None:
            # Non-conventional commit, put in Other
            if description and not description.startswith("Merge"):
                groups["Other"].append(f"{short_hash} {description}")
        else:
            groups[category].append(f"{short_hash} {description}")

    if not groups:
        return ""

    # Build digest
    lines = []

    # Version tags
    old_tag = get_version_tag(old_commit, repo_path)
    new_tag = get_version_tag(new_commit, repo_path)
    version_info = ""
    if new_tag:
        version_info = f" ({new_tag})"
    elif old_tag:
        version_info = f" (since {old_tag})"

    lines.append(f"Klippain updated{version_info}")
    lines.append(f"Changes from {old_commit[:8]} to {new_commit[:8]}:")
    lines.append("")

    # Ordered output
    priority = ["Features", "Bug Fixes", "Performance", "Documentation",
                "Refactoring", "Tests", "CI/CD", "Chores", "Style", "Build",
                "Reverts", "Other"]

    for cat in priority:
        if cat in groups:
            lines.append(f"{cat.upper()}:")
            for entry in sorted(set(groups[cat])):
                lines.append(f"  - {entry}")
            lines.append("")

    lines.append("Review the full changelog at:")
    lines.append("  https://github.com/Frix-x/klippain/blob/main/CHANGELOG.md")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate changelog digest between versions")
    parser.add_argument("--repo-path", type=Path, required=True)
    parser.add_argument("--old-hash", required=True)
    parser.add_argument("--new-hash", required=True)
    args = parser.parse_args()

    digest = generate_digest(args.repo_path, args.old_hash, args.new_hash)

    if digest:
        print(digest)
    else:
        print("No changelog entries found between these versions.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
