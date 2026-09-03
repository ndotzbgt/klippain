#!/usr/bin/env bash
# One-shot update notification script.
# Reads the marker file, prints the report, then deletes the marker.
# Called via RUN_SHELL_COMMAND at Klipper startup.

MARKER_FILE="${HOME}/printer_data/config/klippain_pending_update"
REPORT_FILE="${HOME}/printer_data/config/klippain_update.log"

if [ -f "${MARKER_FILE}" ]; then
    if [ -f "${REPORT_FILE}" ]; then
        echo "=== Klippain Update Report ==="
        cat "${REPORT_FILE}"
        echo ""
        echo "=== End of Report ==="
    else
        echo "Klippain was updated but the report file is missing."
    fi
    rm -f "${MARKER_FILE}"
fi
