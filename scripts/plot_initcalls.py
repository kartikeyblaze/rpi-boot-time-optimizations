#!/usr/bin/env python3
"""
Plot initcall timing data from initcall_summary.csv (produced by parse_initcalls.py).

Generates:
  1. Horizontal bar chart of top N slowest initcalls (mean duration, with stdev error bars)
  2. Optional: stacked/cumulative view showing what % of total initcall time the top N account for

Usage:
    python3 plot_initcalls.py /home/pi/boot_logs/initcall_summary.csv --top 20
"""

import csv
import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # no display needed, just save to file
import matplotlib.pyplot as plt


def load_summary(csv_path):
    rows = []
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "name": r["name"],
                "n_runs": int(r["n_runs"]),
                "mean_us": float(r["mean_duration_us"]),
                "stdev_us": float(r["stdev_duration_us"]),
                "min_us": float(r["min_duration_us"]),
                "max_us": float(r["max_duration_us"]),
            })
    return rows


def plot_top_slowest(rows, top_n, out_path, unit="ms"):
    divisor = 1000.0 if unit == "ms" else 1.0
    subset = rows[:top_n]  # already sorted slowest-first by parse_initcalls.py
    names = [r["name"] for r in subset][::-1]  # reverse so slowest is at top of barh
    means = [r["mean_us"] / divisor for r in subset][::-1]
    stdevs = [r["stdev_us"] / divisor for r in subset][::-1]

    fig_height = max(4, 0.4 * len(subset))
    fig, ax = plt.subplots(figsize=(10, fig_height))

    bars = ax.barh(names, means, xerr=stdevs, capsize=3,
                    color="#4C72B0", edgecolor="black", linewidth=0.5)

    ax.set_xlabel(f"Mean initcall duration ({unit}) — error bars = stdev across runs")
    ax.set_title(f"Top {top_n} Slowest Initcalls (Raspberry Pi boot)")
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    # Annotate bar values
    for bar, mean in zip(bars, means):
        ax.text(bar.get_width() + max(means) * 0.01, bar.get_y() + bar.get_height() / 2,
                f"{mean:.1f}", va="center", fontsize=8)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved: {out_path}")
    plt.close(fig)


def plot_cumulative_contribution(rows, out_path):
    """Shows what fraction of total initcall time is consumed by the top N initcalls."""
    sorted_rows = sorted(rows, key=lambda r: r["mean_us"], reverse=True)
    total = sum(r["mean_us"] for r in sorted_rows)
    cumulative = []
    running = 0.0
    for r in sorted_rows:
        running += r["mean_us"]
        cumulative.append(running / total * 100.0)

    n = len(sorted_rows)
    x = list(range(1, n + 1))

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.plot(x, cumulative, marker="o", markersize=3, color="#C44E52")
    ax.set_xlabel("Number of initcalls (ranked slowest to fastest)")
    ax.set_ylabel("Cumulative % of total initcall time")
    ax.set_title("Cumulative Contribution of Slowest Initcalls to Total Boot Time")
    ax.grid(True, linestyle="--", alpha=0.5)
    ax.axhline(80, color="gray", linestyle=":", linewidth=1)
    ax.text(n * 0.7, 81, "80% line", fontsize=8, color="gray")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"Saved: {out_path}")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="Plot initcall summary data")
    ap.add_argument("summary_csv", help="Path to initcall_summary.csv")
    ap.add_argument("--top", type=int, default=20, help="Number of slowest initcalls to plot (default: 20)")
    ap.add_argument("--unit", choices=["us", "ms"], default="ms", help="Time unit for bar chart (default: ms)")
    ap.add_argument("--outdir", default=None, help="Output directory (default: same as input CSV)")
    args = ap.parse_args()

    csv_path = Path(args.summary_csv)
    if not csv_path.exists():
        print(f"File not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    outdir = Path(args.outdir) if args.outdir else csv_path.parent

    rows = load_summary(csv_path)
    if not rows:
        print("No rows found in summary CSV.", file=sys.stderr)
        sys.exit(1)

    # rows assumed already sorted slowest-first (parse_initcalls.py does this),
    # but sort defensively here too in case the CSV was edited/reordered
    rows.sort(key=lambda r: r["mean_us"], reverse=True)

    plot_top_slowest(rows, args.top, outdir / f"top_{args.top}_slowest_initcalls.png", unit=args.unit)
    plot_cumulative_contribution(rows, outdir / "cumulative_initcall_contribution.png")


if __name__ == "__main__":
    main()
