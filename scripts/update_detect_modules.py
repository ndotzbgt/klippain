#!/usr/bin/env python3

##############################################
###### MODULE DETECTION UPDATE SCRIPT #######
##############################################
# Written for Klippain post-update system
# @version: 1.0

# Detects new hardware/software .cfg modules added between git versions.
# Reports which modules are available but not enabled in the user's printer.cfg.
# For each new module, also lists the variable_* entries it introduces.

# CHANGELOG:
#   v1.0: first version - git diff for new files, include parsing, variable extraction

import re
import subprocess
import sys
from pathlib import Path


# Directories to scan for new modules
MODULE_DIRS = ("config/hardware", "config/software")


def get_new_cfg_files(repo_path, old_commit, new_commit):
    """Use git diff to find .cfg files added between two commits.

    Returns list of relative paths (e.g. 'config/hardware/fans/aux_fan.cfg').
    """
    try:
        result = subprocess.run(
            [
                "git", "-C", str(repo_path),
                "diff", "--name-only", "--diff-filter=A",
                f"{old_commit}..{new_commit}",
                "--",
            ] + list(MODULE_DIRS),
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []
        files = [
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip().endswith(".cfg")
        ]
        return sorted(files)
    except (subprocess.TimeoutExpired, OSError):
        return []


def get_enabled_includes(printer_cfg_path):
    """Parse printer.cfg for active [include] references.

    Returns set of paths that are included (active, not commented).
    """
    includes = set()

    if not printer_cfg_path.exists():
        return includes

    for line in printer_cfg_path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()

        # Match active include (not commented)
        m = re.match(r"\[include\s+(.+?)\s*\]", stripped)
        if m:
            path = m.group(1).strip()
            # Remove inline comments
            if "#" in path:
                path = path[:path.index("#")].strip()
            includes.add(path)

    return includes


def extract_module_variables(module_path):
    """Extract variable_* names and raw values from a module's _USER_VARIABLES section.

    Returns {variable_name: raw_value_string}.
    """
    if not module_path.exists():
        return {}

    from update_sync_variables import parse_variables_from_file
    vars_dict = parse_variables_from_file(module_path)
    result = {}
    for name, (raw_value, _) in vars_dict.items():
        # Strip the variable name and separator from the raw value
        # raw_value is like "variable_filter_enabled: True" -> extract "True"
        import re
        m = re.match(r"variable_\w+\s*[=:]\s*(.*)", raw_value)
        if m:
            result[name] = m.group(1).strip()
        else:
            result[name] = raw_value
    return result


def classify_modules(new_files, printer_includes, repo_path):
    """Classify new modules as enabled or disabled based on printer.cfg includes.

    Returns (enabled_list, disabled_list).
    Each entry is a dict with path, filename, variables.
    """
    enabled = []
    disabled = []

    for filepath in new_files:
        filename = Path(filepath).name
        full_path = repo_path / filepath
        variables = extract_module_variables(full_path)

        entry = {
            "path": filepath,
            "filename": filename,
            "variables": variables,
        }

        # Check if any include references this file
        is_enabled = False
        for inc in printer_includes:
            inc_normalized = inc.lstrip("./")
            if inc_normalized == filepath:
                is_enabled = True
                break
            # Handle glob includes (e.g., mmu/base/mmu_*.cfg)
            if "*" in inc:
                import fnmatch
                if fnmatch.fnmatch(filepath, inc_normalized):
                    is_enabled = True
                    break

        if is_enabled:
            enabled.append(entry)
        else:
            disabled.append(entry)

    return enabled, disabled


def format_module_report(enabled, disabled):
    """Format a human-readable report of new modules."""
    lines = []

    if disabled:
        lines.append("New modules available (not enabled in printer.cfg):")
        lines.append("")

        # Group by category
        by_category = {}
        for mod in disabled:
            parts = Path(mod["path"]).parts
            if "hardware" in parts:
                hw_idx = parts.index("hardware")
                category = "/".join(parts[hw_idx + 1 : -1]) or "root"
            elif "software" in parts:
                sw_idx = parts.index("software")
                category = "/".join(parts[sw_idx + 1 : -1]) or "root"
            else:
                category = "other"
            by_category.setdefault(category, []).append(mod)

        for cat in sorted(by_category):
            lines.append(f"  [{cat}]")
            for mod in sorted(by_category[cat], key=lambda m: m["filename"]):
                lines.append(f"    + {mod['filename']}")
                if mod["variables"]:
                    lines.append("      Tunable variables:")
                    for var_name, default_val in sorted(mod["variables"].items()):
                        lines.append(f"        - {var_name} (default: {default_val})")
                lines.append(
                    f"      To enable: uncomment [include {mod['path']}] in printer.cfg"
                )
            lines.append("")

    if enabled:
        lines.append(f"New modules already enabled: {len(enabled)}")
        for mod in enabled:
            lines.append(f"  [x] {mod['filename']}")
        lines.append("")

    if not enabled and not disabled:
        return ""

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Detect new hardware/software modules between versions")
    parser.add_argument("--repo-path", type=Path, required=True)
    parser.add_argument("--user-config-path", type=Path, required=True)
    parser.add_argument("--old-hash", required=True)
    parser.add_argument("--new-hash", required=True)
    args = parser.parse_args()

    new_files = get_new_cfg_files(args.repo_path, args.old_hash, args.new_hash)

    if not new_files:
        print("No new module files detected.")
        return 0

    print(f"Detected {len(new_files)} new .cfg file(s) in hardware/software directories.")

    printer_cfg = args.user_config_path / "printer.cfg"
    includes = get_enabled_includes(printer_cfg)
    enabled, disabled = classify_modules(new_files, includes, args.repo_path)

    report = format_module_report(enabled, disabled)
    if report:
        print(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
