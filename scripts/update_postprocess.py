#!/usr/bin/env python3

##############################################
###### POST-UPDATE ORCHESTRATOR SCRIPT ######
##############################################
# Written for Klippain post-update system
# @version: 1.0

# Orchestrator for Klippain post-update operations.
# Called by install.sh after a version update. Runs:
# 1. Variable sync (appends new variables to user config)
# 2. New module detection (reports un-enabled new .cfg files)
# 3. Changelog digest (summary of changes between versions)
# Writes a combined report to ~/printer_data/config/klippain_update.log
# and creates a marker file for Klipper startup notification.

# CHANGELOG:
#   v1.0: first version - error-isolated orchestration with report generation

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

# Import sibling modules
sys.path.insert(0, str(Path(__file__).parent))

from update_sync_variables import sync_variables
from update_detect_modules import (
    get_new_cfg_files,
    get_enabled_includes,
    classify_modules,
    format_module_report,
)
from update_changelog_digest import generate_digest


LOG_FILENAME = "klippain_update.log"
MARKER_FILENAME = "klippain_pending_update"


def run_variable_sync(repo_path, user_config_path):
    """Run variable sync. Returns result summary string."""
    upstream_vars = repo_path / "user_templates" / "variables.cfg"
    user_vars = user_config_path / "variables.cfg"

    added = sync_variables(upstream_vars, user_vars, dry_run=False)

    if added:
        lines = [
            "New variables were added to your variables.cfg:",
            "",
        ]
        for name in added:
            lines.append(f"  variable_{name}")
        lines.append("")
        lines.append("Your existing values were preserved.")
        lines.append("Review variables.cfg to check defaults and adjust as needed.")
        return "\n".join(lines)
    else:
        return "No new variables to sync."


def run_module_detection(repo_path, user_config_path, old_commit, new_commit):
    """Run module detection. Returns result summary string."""
    new_files = get_new_cfg_files(repo_path, old_commit, new_commit)

    if not new_files:
        return "No new module files detected."

    printer_cfg = user_config_path / "printer.cfg"
    includes = get_enabled_includes(printer_cfg)
    enabled, disabled = classify_modules(new_files, includes, repo_path)

    report = format_module_report(enabled, disabled)
    return report if report else "All new modules are already enabled."


def run_changelog_digest(repo_path, old_commit, new_commit):
    """Run changelog digest. Returns result summary string."""
    digest = generate_digest(repo_path, old_commit, new_commit)
    return digest if digest else "No changelog entries found."


def write_report(report_path, sections):
    """Write combined report to log file."""
    report_path.write_text("\n\n".join(sections), encoding="utf-8")


def create_marker_file(marker_path):
    """Create marker file for Klipper startup notification."""
    marker_path.write_text("", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Klippain post-update orchestrator")
    parser.add_argument("--repo", type=Path, required=True, help="Path to klippain git repository")
    parser.add_argument("--user-config", type=Path, required=True, help="Path to user config directory")
    parser.add_argument("--old-commit", type=str, required=True, help="Previous commit hash")
    parser.add_argument("--new-commit", type=str, required=True, help="New commit hash")
    args = parser.parse_args()

    report_path = args.user_config / LOG_FILENAME
    marker_path = args.user_config / MARKER_FILENAME

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sections = [
        f"Klippain Update Report\nGenerated: {timestamp}\nUpdated: {args.old_commit[:8]} -> {args.new_commit[:8]}\n{'=' * 50}",
    ]

    # Run each component with error isolation
    for name, runner in [
        ("VARIABLE SYNC", lambda: run_variable_sync(args.repo, args.user_config)),
        ("NEW MODULES", lambda: run_module_detection(
            args.repo, args.user_config, args.old_commit, args.new_commit)),
        ("CHANGELOG", lambda: run_changelog_digest(
            args.repo, args.old_commit, args.new_commit)),
    ]:
        try:
            result = runner()
            sections.append(f"--- {name} ---\n\n{result}")
        except Exception as exc:
            sections.append(f"--- {name} (error) ---\n\n{exc}\n{traceback.format_exc()}")

    # Write report and marker
    write_report(report_path, sections)
    create_marker_file(marker_path)

    print(f"Post-update report written to: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
