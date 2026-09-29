#!/usr/bin/env python3
"""
Parses run_N_summary.txt files (plain `systemd-analyze` / `systemd-analyze time`
output) into a single CSV of boot-time milestones per run.

Handles systemd duration formats: "821ms", "8.793s", and "1min 9.822s".

Usage:
    python3 parse_metrics.py [data_dir]
"""

import os
import re
import csv
import sys

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else (
    "./profile" if os.path.exists("./profile") else "/home/kartikey/profile"
)
GLOBAL_CSV = os.path.join(DATA_DIR, "global_milestones.csv")

# Matches one systemd duration token: "1min 9.822s", "9.822s", or "821ms"
DURATION_RE = r"(?:\d+min\s*)?[\d.]+m?s"


def parse_duration(text_fragment):
    """Parses a systemd duration string - '1min 9.822s', '9.822s', or '821ms' - into float seconds."""
    min_match = re.search(r"(\d+)\s*min", text_fragment)
    minutes = int(min_match.group(1)) if min_match else 0

    # Check milliseconds FIRST - "821ms" would otherwise also match a bare-"s" pattern
    # incorrectly if checked after stripping, so anchor on the "ms" suffix specifically.
    ms_match = re.search(r"([\d.]+)\s*ms\b", text_fragment)
    if ms_match:
        return minutes * 60 + float(ms_match.group(1)) / 1000.0

    sec_match = re.search(r"([\d.]+)\s*s\b", text_fragment)
    seconds = float(sec_match.group(1)) if sec_match else 0.0
    return minutes * 60 + seconds


def extract_global_metrics(file_path):
    """Parses a systemd-analyze time summary for kernel/userspace/total and
    whichever boot target (multi-user.target or graphical.target) is reported."""
    metrics = {
        "kernel_sec": 0.0,
        "userspace_sec": 0.0,
        "total_sec": 0.0,
        "target_name": "",
        "target_sec": 0.0,
    }
    if not os.path.exists(file_path):
        return metrics

    with open(file_path, "r") as f:
        content = f.read()

    startup_match = re.search(
        rf"Startup finished in ({DURATION_RE})\s*\(kernel\)\s*\+\s*"
        rf"({DURATION_RE})\s*\(userspace\)\s*=\s*"
        rf"({DURATION_RE})",
        content,
    )
    if startup_match:
        metrics["kernel_sec"] = parse_duration(startup_match.group(1))
        metrics["userspace_sec"] = parse_duration(startup_match.group(2))
        metrics["total_sec"] = parse_duration(startup_match.group(3))

    target_match = re.search(
        rf"([\w\-]+\.target) reached after ({DURATION_RE}) in userspace",
        content,
    )
    if target_match:
        metrics["target_name"] = target_match.group(1)
        metrics["target_sec"] = parse_duration(target_match.group(2))

    return metrics


def main():
    print(f"[-] Scanning profile workspace: {DATA_DIR}")

    global_rows = []
    warned_zero = False

    for i in range(1, 11):
        summary_file = os.path.join(DATA_DIR, f"run_{i}_summary.txt")
        g = extract_global_metrics(summary_file)

        if g["total_sec"] == 0.0:
            print(f"[!] WARNING: run_{i}_summary.txt missing or unparsed (all-zero result)")
            warned_zero = True

        global_rows.append({
            "Iteration": i,
            "Kernel_Sec": g["kernel_sec"],
            "Userspace_Sec": g["userspace_sec"],
            "Total_Sec": g["total_sec"],
            "Target_Name": g["target_name"],
            "Target_Sec": g["target_sec"],
        })

    with open(GLOBAL_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Iteration", "Kernel_Sec", "Userspace_Sec", "Total_Sec", "Target_Name", "Target_Sec"]
        )
        writer.writeheader()
        writer.writerows(global_rows)

    print(f"[OK] Global milestones exported -> {GLOBAL_CSV}")
    if warned_zero:
        print("[!] One or more runs returned all-zero values - check the source summary files.")


if __name__ == "__main__":
    main()
