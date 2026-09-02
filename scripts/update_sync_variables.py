#!/usr/bin/env python3

##############################################
###### VARIABLE SYNC UPDATE SCRIPT ##########
##############################################
# Written for Klippain post-update system
# @version: 1.0

# Synchronizes new variable_* entries from upstream user_templates/variables.cfg
# into the user's ~/printer_data/config/variables.cfg.
# Append-only: never modifies existing user values.

# CHANGELOG:
#   v1.0: first version - parses Klipper config format, handles multi-line dicts,
#         inline comments, both '=' and ':' separators

import re
import sys
from pathlib import Path


def strip_inline_comment(value):
    """Remove trailing # comment from a value, respecting quotes."""
    in_single = False
    in_double = False
    for i, ch in enumerate(value):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return value[:i].rstrip(), value[i:]
    return value.rstrip(), ""


def parse_variables_from_file(path):
    """Parse variable_* entries from a Klippain variables.cfg file.

    Returns dict mapping variable_name -> (raw_value_text, inline_comment).
    Handles multi-line dict values, inline comments, '=' and ':' separators.
    Only reads within [gcode_macro _USER_VARIABLES] up to 'gcode:' directive.
    """
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    variables = {}
    in_target_section = False
    current_var = None
    current_lines = []
    brace_depth = 0

    for line in text.splitlines():
        stripped = line.strip()

        # Detect start of target section
        if re.match(r"\s*\[gcode_macro\s+_USER_VARIABLES\]", stripped):
            in_target_section = True
            continue

        if not in_target_section:
            continue

        # Section boundary: stop at gcode: directive
        if stripped.startswith("gcode:"):
            if current_var and brace_depth > 0:
                variables[current_var] = ("\n".join(current_lines), "")
            break

        # New section boundary
        if stripped.startswith("[") and stripped.endswith("]"):
            if current_var and brace_depth > 0:
                variables[current_var] = ("\n".join(current_lines), "")
            break

        # Skip blank lines and comment-only lines (but not inside multi-line values)
        if not stripped or stripped.startswith("#"):
            if current_var and brace_depth > 0:
                current_lines.append(line)
            continue

        # Variable line: variable_name <sep> value [# comment]
        var_match = re.match(r"^(variable_\w+)\s*[=:]\s*(.*)", stripped)
        if var_match:
            # Save previous variable if accumulating
            if current_var and brace_depth == 0:
                raw = "\n".join(current_lines)
                variables[current_var] = (raw, "")

            var_name = var_match.group(1)
            rest = var_match.group(2)

            # Extract inline comment
            raw_value, inline_comment = strip_inline_comment(rest)

            # Check for opening braces (multi-line dict)
            brace_depth += raw_value.count("{") - raw_value.count("}")

            current_var = var_name
            current_lines = [line.rstrip()]

            if brace_depth == 0:
                # Single-line variable, store immediately
                variables[var_name] = (current_lines[0].strip(), inline_comment)
                current_var = None
                current_lines = []
        elif current_var and brace_depth > 0:
            # Continuation of multi-line value
            brace_depth += stripped.count("{") - stripped.count("}")
            current_lines.append(line.rstrip())

            if brace_depth <= 0:
                # Multi-line value complete
                raw = "\n".join(current_lines)
                variables[current_var] = (raw, "")
                current_var = None
                current_lines = []
                brace_depth = 0

    return variables


def find_insert_point(user_text):
    """Find the byte offset just before the 'gcode:' directive in user variables.cfg.

    Returns the character position where new variables should be inserted.
    Returns -1 if not found.
    """
    lines = user_text.splitlines(True)
    in_target = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.match(r"\s*\[gcode_macro\s+_USER_VARIABLES\]", stripped):
            in_target = True
            continue
        if in_target and stripped.startswith("gcode:"):
            return sum(len(l) for l in lines[:i])
    return -1


def extract_upstream_block(upstream_text, var_name):
    """Extract the variable line plus any preceding comment/blank lines from upstream.

    This preserves the author's documentation context for the variable.
    """
    lines = upstream_text.splitlines()
    target_idx = None

    # Find the variable line
    for i, line in enumerate(lines):
        if re.match(rf"\s*{re.escape(var_name)}\s*[=:]", line):
            target_idx = i
            break

    if target_idx is None:
        return ""

    # Walk backwards to find preceding comment block
    start_idx = target_idx
    i = target_idx - 1
    while i >= 0:
        stripped = lines[i].strip()
        if stripped.startswith("#") or stripped == "":
            start_idx = i
            i -= 1
        else:
            break

    # Extract lines, skip leading blank lines
    block = lines[start_idx : target_idx + 1]
    while block and block[0].strip() == "":
        block.pop(0)

    return "\n".join(block)


def sync_variables(upstream_path, user_path, dry_run=False):
    """Sync new variables from upstream template to user config.

    Returns list of variable names that were added.
    If dry_run=True, returns the list without modifying the user file.

    Safety: only ADDS variable_* entries, never modifies or removes existing ones.
    """
    if not user_path.exists():
        return []

    user_text = user_path.read_text(encoding="utf-8")
    upstream_text = upstream_path.read_text(encoding="utf-8")

    # Parse both files
    user_vars = parse_variables_from_file(user_path)
    upstream_vars = parse_variables_from_file(upstream_path)

    # Find missing variables
    missing = [name for name in upstream_vars if name not in user_vars]

    if not missing:
        return []

    # Find insert point in user file
    insert_pos = find_insert_point(user_text)
    if insert_pos < 0:
        return []

    # Build insertion text (in upstream file order)
    insert_blocks = []
    added_names = []
    for line in upstream_text.splitlines():
        m = re.match(r"\s*(variable_\w+)\s*[=:]", line)
        if m and m.group(1) in missing:
            block = extract_upstream_block(upstream_text, m.group(1))
            if block:
                insert_blocks.append(block)
                added_names.append(m.group(1))

    if not insert_blocks:
        return []

    # Insert before gcode: line
    insert_text = "\n\n## ---- New variables added by Klippain updater ----\n\n"
    insert_text += "\n\n".join(insert_blocks) + "\n\n"
    new_text = user_text[:insert_pos] + insert_text + user_text[insert_pos:]

    if not dry_run:
        # Idempotency guard: re-check current state
        current_vars = parse_variables_from_file(user_path)
        truly_new = [v for v in added_names if v not in current_vars]
        if not truly_new:
            return []
        # Re-build with only truly new vars
        insert_blocks_2 = []
        final_names = []
        for line in upstream_text.splitlines():
            m = re.match(r"\s*(variable_\w+)\s*[=:]", line)
            if m and m.group(1) in truly_new:
                block = extract_upstream_block(upstream_text, m.group(1))
                if block:
                    insert_blocks_2.append(block)
                    final_names.append(m.group(1))
        if not final_names:
            return []
        insert_text_2 = "\n\n## ---- New variables added by Klippain updater ----\n\n"
        insert_text_2 += "\n\n".join(insert_blocks_2) + "\n\n"
        final_pos = find_insert_point(user_text)
        final_text = user_text[:final_pos] + insert_text_2 + user_text[final_pos:]
        user_path.write_text(final_text, encoding="utf-8")
        return final_names

    return added_names


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Sync new variables from upstream to user config")
    parser.add_argument("--upstream", type=Path, required=True, help="Path to user_templates/variables.cfg")
    parser.add_argument("--user-config", type=Path, required=True, help="Path to user's variables.cfg")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be added without writing")
    args = parser.parse_args()

    if not args.upstream.exists():
        print(f"ERROR: upstream template not found: {args.upstream}", file=sys.stderr)
        return 1

    if not args.user_config.exists():
        print(f"INFO: user variables.cfg not found at {args.user_config}")
        print("INFO: Skipping variable sync (first install copies template).")
        return 0

    added = sync_variables(args.upstream, args.user_config, dry_run=args.dry_run)

    if not added:
        print("No new variables to add.")
        return 0

    print(f"Found {len(added)} new variable(s):")
    for name in added:
        print(f"  + {name}")

    if args.dry_run:
        print("\n[dry-run] No changes made.")
    else:
        print(f"Updated {args.user_config}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
