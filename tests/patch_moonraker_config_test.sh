#!/usr/bin/env bash

set -euo pipefail

repo_root="$(CDPATH= cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"

assert_eq() {
    local expected="$1"
    local actual="$2"
    local message="$3"

    if [[ "${expected}" != "${actual}" ]]; then
        printf 'FAIL: %s\nexpected: %s\nactual:   %s\n' "${message}" "${expected}" "${actual}" >&2
        exit 1
    fi
}

tmpdir="$(mktemp -d)"
loader="$(mktemp)"
trap 'rm -rf "${tmpdir}"; rm -f "${loader}"' EXIT

# Load the function definitions of install.sh the same way the MCU
# template menu test does: everything above the first BACKUP_DIR= line.
awk '/^BACKUP_DIR=/{exit} {print}' "${repo_root}/install.sh" > "${loader}"
# shellcheck disable=SC1090
source "${loader}"

setup_moonraker_conf() {
    mkdir -p "${tmpdir}/moonraker"
    cp "${repo_root}/moonraker/base.conf" "${tmpdir}/moonraker/base.conf"
    cp "${repo_root}/moonraker/z_calibration.conf" "${tmpdir}/moonraker/z_calibration.conf"
}

config_origin() {
    sed -n 's|^origin: ||p' "$1"
}

config_primary_branch() {
    sed -n 's|^primary_branch: ||p' "$1"
}

FRIX_CONFIG_PATH="${tmpdir}"

# The BleedingPain selection must track the matching plugin fork
FORK_REPO_URL="https://github.com/ndotzbgt/klippain.git"
FORK_BRANCH="bleedingpain"
FORK_ZCALIB_REPO_URL="https://github.com/ndotzbgt/klipper_z_calibration.git"
setup_moonraker_conf
patch_moonraker_config > /dev/null

assert_eq "https://github.com/ndotzbgt/klippain.git" \
    "$(config_origin "${tmpdir}/moonraker/base.conf")" \
    "base.conf origin must match the Klippain fork"
assert_eq "bleedingpain" \
    "$(config_primary_branch "${tmpdir}/moonraker/base.conf")" \
    "base.conf primary_branch must match the fork branch"
assert_eq "https://github.com/ndotzbgt/klipper_z_calibration.git" \
    "$(config_origin "${tmpdir}/moonraker/z_calibration.conf")" \
    "z_calibration.conf origin must match the plugin fork"

# Re-running the patch must not change the result
patch_moonraker_config > /dev/null
assert_eq "https://github.com/ndotzbgt/klipper_z_calibration.git" \
    "$(config_origin "${tmpdir}/moonraker/z_calibration.conf")" \
    "patching twice must stay idempotent"

# The Frix-x selection must keep tracking the upstream plugin
FORK_REPO_URL="https://github.com/Frix-x/klippain.git"
FORK_BRANCH="main"
FORK_ZCALIB_REPO_URL="https://github.com/protoloft/klipper_z_calibration.git"
setup_moonraker_conf
patch_moonraker_config > /dev/null

assert_eq "https://github.com/Frix-x/klippain.git" \
    "$(config_origin "${tmpdir}/moonraker/base.conf")" \
    "base.conf origin must fall back to the upstream repository"
assert_eq "https://github.com/protoloft/klipper_z_calibration.git" \
    "$(config_origin "${tmpdir}/moonraker/z_calibration.conf")" \
    "z_calibration.conf origin must fall back to the upstream plugin"

# A repository without the plugin entry must still patch base.conf
rm -f "${tmpdir}/moonraker/z_calibration.conf"
FORK_REPO_URL="https://github.com/ndotzbgt/klippain.git"
FORK_BRANCH="bleedingpain"
FORK_ZCALIB_REPO_URL="https://github.com/ndotzbgt/klipper_z_calibration.git"
patch_moonraker_config > /dev/null
assert_eq "https://github.com/ndotzbgt/klippain.git" \
    "$(config_origin "${tmpdir}/moonraker/base.conf")" \
    "base.conf must be patched without z_calibration.conf"

# Without base.conf the patch skips entirely and must leave the plugin
# entry untouched
rm -f "${tmpdir}/moonraker/base.conf"
cp "${repo_root}/moonraker/z_calibration.conf" "${tmpdir}/moonraker/z_calibration.conf"
patch_moonraker_config > /dev/null
assert_eq "https://github.com/protoloft/klipper_z_calibration.git" \
    "$(config_origin "${tmpdir}/moonraker/z_calibration.conf")" \
    "a missing base.conf must skip the whole patch"

printf 'ok\n'
