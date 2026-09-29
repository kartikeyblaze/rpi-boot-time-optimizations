#!/usr/bin/env python3
"""
Generates a stacked kernel/userspace boot-time bar chart from global_milestones.csv,
with a dashed line marking when the boot target (multi-user.target or graphical.target)
was reached. Styled to match plot_initcalls.py for visual consistency across the report.

Usage:
    python3 analyze_global.py [data_dir] --profile "Headless Server (Stage 2: VCHIQ disabled)"
"""

import os
import sys
import argparse
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---- Shared visual style (matches plot_initcalls.py) ----
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 10,
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 11,
    "axes.labelweight": "bold",
    "axes.grid": True,
    "grid.linestyle": "--",
    "grid.alpha": 0.5,
})

COLOR_KERNEL = "#4C72B0"      # blue - matches primary bar color in plot_initcalls.py
COLOR_USERSPACE = "#C44E52"   # red - matches cumulative-chart accent color
COLOR_TARGET_LINE = "#2c3e50"


def main():
    ap = argparse.ArgumentParser(description="Plot global (systemd-analyze time) boot metrics")
    ap.add_argument("data_dir", nargs="?", default=(
        "./profile" if os.path.exists("./profile") else "/home/kartikey/profile"
    ))
    ap.add_argument("--profile", default="Boot Profile",
                     help="Label describing this run, e.g. 'Headless Server - Stage 2'")
    ap.add_argument("--out", default=None, help="Output PNG path (default: <data_dir>/global_milestones.png)")
    args = ap.parse_args()

    input_csv = os.path.join(args.data_dir, "global_milestones.csv")
    summary_csv = os.path.join(args.data_dir, "global_summary.csv")
    chart_png = args.out or os.path.join(args.data_dir, "global_milestones.png")

    if not os.path.exists(input_csv):
        print(f"Error: {input_csv} not found.")
        return

    df = pd.read_csv(input_csv)

    # Drop any all-zero (missing/unparsed) rows before averaging, so a bad run
    # doesn't silently drag down the mean
    valid = df[df["Total_Sec"] > 0]
    if len(valid) < len(df):
        print(f"[!] Dropped {len(df) - len(valid)} invalid/zero run(s) out of {len(df)} before averaging.")
    if valid.empty:
        print("Error: no valid runs to plot.")
        return

    # ---- Summary stats ----
    metrics_cols = ["Kernel_Sec", "Userspace_Sec", "Total_Sec", "Target_Sec"]
    stats = {}
    for col in metrics_cols:
        stats[col] = {
            "Average_Sec": round(valid[col].mean(), 3),
            "Std_Dev_Sec": round(valid[col].std(ddof=1), 3) if len(valid) > 1 else 0.0,
            "Min_Sec": valid[col].min(),
            "Max_Sec": valid[col].max(),
        }
    pd.DataFrame(stats).T.to_csv(summary_csv, index_label="Metric")
    print(f"[OK] Summary stats exported -> {summary_csv}")

    kernel_avg = valid["Kernel_Sec"].mean()
    userspace_avg = valid["Userspace_Sec"].mean()
    total_avg = valid["Total_Sec"].mean()
    target_rel_avg = valid["Target_Sec"].mean()   # relative to userspace start
    target_abs_avg = kernel_avg + target_rel_avg  # absolute, from power-on

    # Use the most common target name across valid runs (should normally be uniform)
    target_name = valid["Target_Name"].mode().iloc[0] if not valid["Target_Name"].mode().empty else "target"

    # ---- Plot ----
    fig, ax = plt.subplots(figsize=(6, 7))
    bar_width = 0.5
    x_pos = [0]

    ax.bar(x_pos, [kernel_avg], width=bar_width, color=COLOR_KERNEL,
           edgecolor="black", linewidth=0.5, label="Kernel Time")
    ax.bar(x_pos, [userspace_avg], bottom=[kernel_avg], width=bar_width, color=COLOR_USERSPACE,
           edgecolor="black", linewidth=0.5, label="Userspace Time")

    # Target threshold line
    ax.hlines(y=target_abs_avg, xmin=-0.3, xmax=0.3, colors=COLOR_TARGET_LINE,
              linestyles="--", linewidth=2,
              label=f"{target_name} reached")
    ax.text(0.35, target_abs_avg, f"{target_name}:\n{target_abs_avg:.2f}s", va="center", ha="left",
            color=COLOR_TARGET_LINE, fontweight="bold", fontsize=9)

    # In-bar labels
    ax.text(0, kernel_avg / 2, f"Kernel\n{kernel_avg:.2f}s", va="center", ha="center",
            color="white", fontweight="bold", fontsize=10)
    ax.text(0, kernel_avg + userspace_avg / 2, f"Userspace\n{userspace_avg:.2f}s", va="center", ha="center",
            color="white", fontweight="bold", fontsize=10)
    ax.text(0, total_avg + total_avg * 0.02, f"Total: {total_avg:.2f}s", va="bottom", ha="center",
            color="#555555", fontweight="bold", fontsize=10)

    ax.set_xticks(x_pos)
    ax.set_xticklabels([args.profile])
    ax.set_ylabel("Boot Time (seconds)")
    ax.set_title(f"Average Boot Time Breakdown\n{args.profile}")
    ax.set_ylim(0, total_avg * 1.25)
    ax.legend(loc="upper right", frameon=True)

    fig.tight_layout()
    fig.savefig(chart_png, dpi=300)
    plt.close(fig)
    print(f"[OK] Chart exported -> {chart_png}")


if __name__ == "__main__":
    main()
