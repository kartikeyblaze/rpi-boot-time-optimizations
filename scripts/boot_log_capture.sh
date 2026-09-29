#!/bin/bash
# /usr/local/bin/boot_log_capture.sh

LOGDIR="/home/pi/boot_logs"
STATEFILE="$LOGDIR/iteration.count"
MAX_ITER=10

mkdir -p "$LOGDIR"

# Initialize counter if first run
if [ ! -f "$STATEFILE" ]; then
    echo 0 > "$STATEFILE"
fi

ITER=$(cat "$STATEFILE")
ITER=$((ITER + 1))

# Save dmesg for this boot
dmesg > "$LOGDIR/run${ITER}_dmesg.txt"
dmesg | grep initcall > "$LOGDIR/run${ITER}_initcall.txt"

echo "$ITER" > "$STATEFILE"
echo "$(date): Captured run $ITER of $MAX_ITER" >> "$LOGDIR/capture.log"

if [ "$ITER" -lt "$MAX_ITER" ]; then
    # Give logs a moment to flush, then reboot
    sleep 5
    reboot
else
    echo "$(date): All $MAX_ITER runs captured. Disabling service." >> "$LOGDIR/capture.log"
    systemctl disable boot-log-capture.service
fi
