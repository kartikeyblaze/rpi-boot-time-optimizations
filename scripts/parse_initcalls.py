#!/usr/bin/env python3
"""
Parse multiple run*_initcall.txt files (from initcall_debug boot logs)
into a per-run CSV and an aggregated summary CSV (mean/stddev per initcall).

Usage:
    python3 parse_initcalls.py /home/pi/boot_logs --pattern "run*_initcall.txt"

Expects lines like:
    [    0.051401] initcall proc_schedstat_init+0x0/0x58 returned 0 after 0 usecs
"""

import re
import csv
import sys
import glob
import argparse
import statistics
from pathlib import Path

# Matches: [    0.051401] initcall NAME+0xOFFSET/0xSIZE returned RET after N usecs
LINE_RE = re.compile(
    r"\[\s*(?P<ts>\d+\.\d+)\]\s+initcall\s+(?P<name>\S+?)\+0x[0-9a-fA-F]+/0x[0-9a-fA-F]+"
    r"\s+returned\s+(?P<ret>-?\d+)\s+after\s+(?P<dur>\d+)\s+usecs"
)


def parse_file(filepath):
    """Return list of dicts: name, timestamp_s, return_code, duration_us"""
    records = []
    with open(filepath, "r", errors="replace") as f:
        for line in f:
            m = LINE_RE.search(line)
            if m:
                records.append({
                    "name": m.group("name"),
                    "timestamp_s": float(m.group("ts")),
                    "return_code": int(m.group("ret")),
                    "duration_us": int(m.group("dur")),
                })
    return records


def main():
    ap = argparse.ArgumentParser(description="Parse initcall_debug boot logs across multiple runs")
    ap.add_argument("logdir", help="Directory containing run*_initcall.txt files")
    ap.add_argument("--pattern", default="run*_initcall.txt",
                     help="Glob pattern for log files (default: run*_initcall.txt)")
    ap.add_argument("--out-raw", default="initcall_raw.csv",
                     help="Output CSV for per-run raw data")
    ap.add_argument("--out-summary", default="initcall_summary.csv",
                     help="Output CSV for aggregated per-initcall stats")
    ap.add_argument("--top", type=int, default=20,
                     help="Print top N slowest initcalls by mean duration (default: 20)")
    args = ap.parse_args()

    logdir = Path(args.logdir)
    files = sorted(glob.glob(str(logdir / args.pattern)))

    if not files:
        print(f"No files matched pattern '{args.pattern}' in {logdir}", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(files)} log files:")
    for f in files:
        print(f"  {f}")

    # ---- Parse all runs ----
    all_records = []  # (run_id, name, timestamp_s, return_code, duration_us)
    for run_id, filepath in enumerate(files, start=1):
        records = parse_file(filepath)
        if not records:
            print(f"  WARNING: no initcall lines matched in {filepath}", file=sys.stderr)
        for r in records:
            all_records.append({
                "run_id": run_id,
                "source_file": Path(filepath).name,
                **r
            })

    if not all_records:
        print("No initcall records parsed from any file. Check the regex against your log format.",
              file=sys.stderr)
        sys.exit(1)

    # ---- Write raw CSV ----
    raw_path = logdir / args.out_raw
    with open(raw_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["run_id", "source_file", "name", "timestamp_s", "return_code", "duration_us"]
        )
        writer.writeheader()
        writer.writerows(all_records)
    print(f"\nWrote raw per-run data: {raw_path} ({len(all_records)} rows)")

    # ---- Aggregate per initcall name ----
    by_name = {}
    for r in all_records:
        by_name.setdefault(r["name"], []).append(r["duration_us"])

    summary_rows = []
    for name, durations in by_name.items():
        n = len(durations)
        mean = statistics.mean(durations)
        stdev = statistics.stdev(durations) if n > 1 else 0.0
        summary_rows.append({
            "name": name,
            "n_runs": n,
            "mean_duration_us": round(mean, 2),
            "stdev_duration_us": round(stdev, 2),
            "min_duration_us": min(durations),
            "max_duration_us": max(durations),
        })

    # Sort by mean duration descending (slowest first)
    summary_rows.sort(key=lambda r: r["mean_duration_us"], reverse=True)

    summary_path = logdir / args.out_summary
    with open(summary_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["name", "n_runs", "mean_duration_us", "stdev_duration_us",
                           "min_duration_us", "max_duration_us"]
        )
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Wrote aggregated summary: {summary_path} ({len(summary_rows)} unique initcalls)")

    # ---- Print top N slowest to console ----
    print(f"\nTop {args.top} slowest initcalls (by mean duration across runs):")
    print(f"{'name':<45} {'n':>3} {'mean_us':>10} {'stdev_us':>10} {'min_us':>8} {'max_us':>8}")
    for row in summary_rows[:args.top]:
        print(f"{row['name']:<45} {row['n_runs']:>3} {row['mean_duration_us']:>10} "
              f"{row['stdev_duration_us']:>10} {row['min_duration_us']:>8} {row['max_duration_us']:>8}")

    # ---- Sanity check: total time per run vs sum of durations ----
    print("\nPer-run total initcall time (sanity check):")
    per_run_totals = {}
    for r in all_records:
        per_run_totals.setdefault(r["run_id"], 0)
        per_run_totals[r["run_id"]] += r["duration_us"]
    for run_id in sorted(per_run_totals):
        total_ms = per_run_totals[run_id] / 1000.0
        print(f"  run{run_id}: {total_ms:.2f} ms total initcall time")


if __name__ == "__main__":
    main()
