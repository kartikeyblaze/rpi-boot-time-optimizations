#!/bin/bash
TARGET_DIR="/home/kartikey/profile"
STATE_FILE="$TARGET_DIR/iteration.dat"

mkdir -p "$TARGET_DIR"

if [ ! -f "$STATE_FILE" ]; then
    echo 1 > "$STATE_FILE"
fi

CURRENT_ITERATION=$(cat "$STATE_FILE")

if [ "$CURRENT_ITERATION" -le 10 ]; then
    echo "=== Profiler Hook: Initializing Iteration $CURRENT_ITERATION/10 ==="

    # Loop until systemd finishes booting (handles both normal 'running' and 'degraded' states)
    while true; do
        SYS_STATE=$(systemctl is-system-running)
        if [ "$SYS_STATE" = "running" ] || [ "$SYS_STATE" = "degraded" ]; then
            break
        fi
        sleep 0.5
    done

    # 2-second stabilization delay
    sleep 2

    # Capture data
    systemd-analyze > "$TARGET_DIR/run_${CURRENT_ITERATION}_summary.txt" 2>&1
    systemd-analyze blame > "$TARGET_DIR/run_${CURRENT_ITERATION}_blame.txt" 2>&1
    systemd-analyze critical-chain > "$TARGET_DIR/run_${CURRENT_ITERATION}_chain.txt" 2>&1

    # Move to next run
    NEXT_ITERATION=$((CURRENT_ITERATION + 1))
    echo "$NEXT_ITERATION" > "$STATE_FILE"

    if [ "$NEXT_ITERATION" -le 10 ]; then
        echo "Iteration $CURRENT_ITERATION captured. Resetting hardware..."
        systemctl reboot
    else
        echo "=== Success: All 10 iterations successfully compiled ==="
        systemctl disable boot-profiler.service
    fi
else
    systemctl disable boot-profiler.service
fi
