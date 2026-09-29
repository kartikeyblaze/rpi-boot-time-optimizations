#!/bin/bash
# toggle_kernel_logging.sh — add/remove kernel boot-time debug logging params
# Usage: sudo ./toggle_kernel_logging.sh on
#        sudo ./toggle_kernel_logging.sh off

set -euo pipefail

CMDLINE_FILE="/boot/firmware/cmdline.txt"
BACKUP_FILE="/boot/firmware/cmdline.txt.orig"

# The exact debug parameters this script manages - edit this list in one place only
DEBUG_PARAMS="initcall_debug printk.time=1 loglevel=8"

usage() {
    echo "Usage: $0 on|off"
    exit 1
}

if [ $# -ne 1 ]; then
    usage
fi

MODE="$1"

if [ ! -f "$CMDLINE_FILE" ]; then
    echo "Error: $CMDLINE_FILE not found."
    exit 1
fi

# Keep a pristine backup on first run, so 'off' always has a clean baseline to fall back to
if [ ! -f "$BACKUP_FILE" ]; then
    cp "$CMDLINE_FILE" "$BACKUP_FILE"
    echo "Saved original cmdline.txt to $BACKUP_FILE"
fi

CURRENT=$(cat "$CMDLINE_FILE")

# Strip any debug params that may already be present, regardless of mode,
# so toggling is idempotent and never duplicates params on repeated 'on' calls.
STRIPPED=$(echo "$CURRENT" | sed -E \
    -e 's/\s*initcall_debug//g' \
    -e 's/\s*printk\.time=[0-9]+//g' \
    -e 's/\s*loglevel=[0-9]+//g' \
    -e 's/[[:space:]]+/ /g' \
    -e 's/^ //; s/ $//')

case "$MODE" in
    on)
        NEW_LINE="${STRIPPED} ${DEBUG_PARAMS}"
        echo "$NEW_LINE" > "$CMDLINE_FILE"
        echo "Kernel debug logging ENABLED. New cmdline.txt:"
        ;;
    off)
        echo "$STRIPPED" > "$CMDLINE_FILE"
        echo "Kernel debug logging DISABLED. New cmdline.txt:"
        ;;
    *)
        usage
        ;;
esac

cat "$CMDLINE_FILE"
echo ""
echo "Reboot for the change to take effect: sudo reboot"
