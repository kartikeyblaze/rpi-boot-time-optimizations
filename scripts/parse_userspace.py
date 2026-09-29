#!/usr/bin/env python3
"""
Parses run_N_blame.txt (systemd-analyze blame) and run_N_chain.txt
(systemd-analyze critical-chain) across 10 boot iterations.

Outputs:
  critical_chain_detail.csv  - every run's critical-path services, in order,
                                with their offset and own duration
  blame_summary.csv          - every service seen in blame, mean/stdev/min/max
                                duration across runs, cross-referenced against
                                whether it appears on the critical chain

Usage:
    python3 parse_userspace.py [data_dir]
"""

import os
import re
import csv
import sys
import statistics

DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else (
    "./profile" if os.path.exists("./profile") else "/home/kartikey/profile"
)
CHAIN_DETAIL_CSV = os.path.join(DATA_DIR, "critical_chain_detail.csv")
BLAME_SUMMARY_CSV = os.path.join(DATA_DIR, "blame_summary.csv")

DURATION_RE = r"(?:\d+min\s*)?[\d.]+m?s"

# Tree-drawing characters systemd uses to render the critical-chain indentation
TREE_CHARS_RE = re.compile(r"[└─├│]+")


def parse_duration(text_fragment):
    """Parses '1min 9.822s', '9.822s', or '890ms' into float seconds."""
    if not text_fragment:
        return 0.0
    min_match = re.search(r"(\d+)\s*min", text_fragment)
    minutes = int(min_match.group(1)) if min_match else 0

    ms_match = re.search(r"([\d.]+)\s*ms\b", text_fragment)
    if ms_match:
        return minutes * 60 + float(ms_match.group(1)) / 1000.0

    sec_match = re.search(r"([\d.]+)\s*s\b", text_fragment)
    seconds = float(sec_match.group(1)) if sec_match else 0.0
    return minutes * 60 + seconds


def clean_service_name(name):
    """Normalizes systemd hex escape sequences (e.g. \\x2d -> '-') for readability."""
    return name.replace("\\x2d", "-").replace("\\x22d", "-")


def parse_chain_file(filepath):
    """Returns an ordered list of dicts: {service, offset_sec, own_duration_sec}."""
    entries = []
    if not os.path.exists(filepath):
        return entries

    with open(filepath, "r", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if "@" not in line:
                continue
            # Strip tree-drawing characters and leading/trailing whitespace
            stripped = TREE_CHARS_RE.sub("", line).strip()

            m = re.match(
                rf"^(\S+)\s+@({DURATION_RE})(?:\s+\+({DURATION_RE}))?$",
                stripped,
            )
            if not m:
                continue
            name, offset_str, dur_str = m.groups()
            entries.append({
                "service": clean_service_name(name),
                "offset_sec": parse_duration(offset_str),
                "own_duration_sec": parse_duration(dur_str) if dur_str else 0.0,
            })
    return entries


def parse_blame_file(filepath):
    """Returns dict: service_name -> duration_sec."""
    result = {}
    if not os.path.exists(filepath):
        return result

    with open(filepath, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            m = re.match(rf"^({DURATION_RE})\s+(.+)$", line)
            if not m:
                continue
            dur_str, name = m.groups()
            result[clean_service_name(name)] = parse_duration(dur_str)
    return result


def main():
    print(f"[-] Scanning profile workspace: {DATA_DIR}")

    chain_rows = []
    blame_by_service = {}   # service -> list of durations across runs
    critical_chain_services = {}  # service -> list of rank positions across runs (0 = target itself)

    for i in range(1, 11):
        chain_file = os.path.join(DATA_DIR, f"run_{i}_chain.txt")
        blame_file = os.path.join(DATA_DIR, f"run_{i}_blame.txt")

        chain_entries = parse_chain_file(chain_file)
        if not chain_entries:
            print(f"[!] WARNING: run_{i}_chain.txt missing or unparsed")
        for rank, entry in enumerate(chain_entries):
            chain_rows.append({
                "Iteration": i,
                "Order": rank,
                "Service": entry["service"],
                "Offset_Sec": entry["offset_sec"],
                "Own_Duration_Sec": entry["own_duration_sec"],
            })
            critical_chain_services.setdefault(entry["service"], []).append(rank)

        blame_data = parse_blame_file(blame_file)
        if not blame_data:
            print(f"[!] WARNING: run_{i}_blame.txt missing or unparsed")
        for service, duration in blame_data.items():
            blame_by_service.setdefault(service, []).append(duration)

    # ---- Write critical chain detail ----
    with open(CHAIN_DETAIL_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["Iteration", "Order", "Service", "Offset_Sec", "Own_Duration_Sec"])
        writer.writeheader()
        writer.writerows(chain_rows)
    print(f"[OK] Critical chain detail exported -> {CHAIN_DETAIL_CSV}")

    # ---- Write blame summary, cross-referenced with critical chain presence ----
    summary_rows = []
    for service, durations in blame_by_service.items():
        n = len(durations)
        mean = statistics.mean(durations)
        stdev = statistics.stdev(durations) if n > 1 else 0.0
        on_chain = service in critical_chain_services
        mean_rank = (
            round(statistics.mean(critical_chain_services[service]), 2) if on_chain else ""
        )
        summary_rows.append({
            "Service": service,
            "N_Runs": n,
            "Mean_Duration_Sec": round(mean, 4),
            "Stdev_Duration_Sec": round(stdev, 4),
            "Min_Duration_Sec": round(min(durations), 4),
            "Max_Duration_Sec": round(max(durations), 4),
            "On_Critical_Chain": on_chain,
            "Mean_Chain_Order": mean_rank,
        })

    # Sort: critical-chain services first (by mean order), then remaining by duration descending
    summary_rows.sort(key=lambda r: (
        0 if r["On_Critical_Chain"] else 1,
        r["Mean_Chain_Order"] if r["On_Critical_Chain"] else 0,
        -r["Mean_Duration_Sec"],
    ))

    with open(BLAME_SUMMARY_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Service", "N_Runs", "Mean_Duration_Sec", "Stdev_Duration_Sec",
            "Min_Duration_Sec", "Max_Duration_Sec", "On_Critical_Chain", "Mean_Chain_Order"
        ])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"[OK] Blame summary exported -> {BLAME_SUMMARY_CSV}")

    # ---- Console preview: critical-chain services first, in order ----
    print("\nServices on the critical chain (target-blocking path), ranked by position:")
    print(f"{'service':<50} {'mean_order':>10} {'mean_blame_sec':>15}")
    for row in summary_rows:
        if row["On_Critical_Chain"]:
            print(f"{row['Service']:<50} {row['Mean_Chain_Order']:>10} {row['Mean_Duration_Sec']:>15}")

    print("\nTop 10 services by blame duration NOT on the critical chain (footprint only, not boot-blocking):")
    off_chain = [r for r in summary_rows if not r["On_Critical_Chain"]]
    off_chain.sort(key=lambda r: -r["Mean_Duration_Sec"])
    for row in off_chain[:10]:
        print(f"{row['Service']:<50} {row['Mean_Duration_Sec']:>15}")


if __name__ == "__main__":
    main()
