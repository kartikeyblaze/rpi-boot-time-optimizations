#!/usr/bin/env python3
"""
Plots userspace boot data from parse_userspace.py output:
  1. Critical chain timeline - horizontal bar per service showing when it
     started (offset) and how long it ran, in blocking order.
  2. Blame ranking - top services by duration, color-coded by whether they
     are on the critical chain (boot-blocking) or not (footprint only).

Usage:
    python3 plot_userspace.py [data_dir] --profile "Headless Server - Stage 3"
"""

import os
import argparse
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---- Shared visual style (matches plot_initcalls.py / analyze_global.py) ----
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

COLOR_ON_CHAIN = "#C44E52"     # red - boot-blocking, worth optimizing
COLOR_OFF_CHAIN = "#4C72B0"    # blue - footprint only, not boot-blocking


def plot_critical_chain_timeline(chain_csv, out_path, profile_label, run_iteration=None):
    """
    By default, aggregates all iterations (mean offset/duration per service,
    ordered by mean chain position), so the chart represents the full 10-run
    dataset rather than a single boot. Pass run_iteration to plot one specific
    run instead (useful for spot-checking a single boot's raw sequence).
    """
    df = pd.read_csv(chain_csv)

    if run_iteration is not None:
        plot_df = df[df["Iteration"] == run_iteration].sort_values("Order")
        if plot_df.empty:
            print(f"[!] No critical chain data found for iteration {run_iteration}, skipping timeline chart.")
            return
        services = plot_df["Service"].tolist()
        starts = plot_df["Offset_Sec"].tolist()
        durations = plot_df["Own_Duration_Sec"].tolist()
        dur_err = [0.0] * len(services)
        title_suffix = f"(run {run_iteration})"
    else:
        total_runs = df["Iteration"].nunique()

        grouped = df.groupby("Service").agg(
            Mean_Offset=("Offset_Sec", "mean"),
            Mean_Duration=("Own_Duration_Sec", "mean"),
            Stdev_Duration=("Own_Duration_Sec", "std"),
            Mean_Order=("Order", "mean"),
            Stdev_Order=("Order", "std"),
            N_Runs=("Order", "count"),
        ).reset_index()
        grouped["Stdev_Duration"] = grouped["Stdev_Duration"].fillna(0.0)
        grouped["Stdev_Order"] = grouped["Stdev_Order"].fillna(0.0)

        # Flag services missing from some runs - their mean would be misleading
        incomplete = grouped[grouped["N_Runs"] < total_runs]
        if not incomplete.empty:
            print(f"[!] WARNING: these services were not present in all {total_runs} runs "
                  f"(chain may vary between boots) - means may be unreliable:")
            for _, r in incomplete.iterrows():
                print(f"    {r['Service']}: present in {int(r['N_Runs'])}/{total_runs} runs")

        # Flag services whose position in the chain shifted noticeably between runs
        unstable = grouped[grouped["Stdev_Order"] > 0.5]
        if not unstable.empty:
            print(f"[!] WARNING: these services changed position in the critical chain across runs "
                  f"(boot ordering is not fully deterministic):")
            for _, r in unstable.iterrows():
                print(f"    {r['Service']}: order stdev = {r['Stdev_Order']:.2f}")

        grouped = grouped.sort_values("Mean_Order")
        services = grouped["Service"].tolist()
        starts = grouped["Mean_Offset"].tolist()
        durations = grouped["Mean_Duration"].tolist()
        dur_err = grouped["Stdev_Duration"].tolist()
        title_suffix = f"(mean of {total_runs} runs)"

    # Reverse so the target (first row / lowest order) appears at the top
    services = services[::-1]
    starts = starts[::-1]
    durations = durations[::-1]
    dur_err = dur_err[::-1]

    fig_height = max(4, 0.4 * len(services))
    fig, ax = plt.subplots(figsize=(10, fig_height))

    bars = ax.barh(services, durations, left=starts, xerr=dur_err, capsize=3,
                    color=COLOR_ON_CHAIN, edgecolor="black", linewidth=0.5, height=0.6)

    for bar, start, dur in zip(bars, starts, durations):
        if dur > 0:
            ax.text(bar.get_x() + bar.get_width() + 0.05, bar.get_y() + bar.get_height() / 2,
                    f"{dur:.2f}s", va="center", fontsize=8)

    ax.set_xlabel("Time since userspace start (seconds) - error bars = stdev of duration across runs")
    ax.set_title(f"Critical Path Timeline {title_suffix}\n{profile_label}")
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def plot_blame_ranking(blame_csv, out_path, profile_label, top_n=20):
    df = pd.read_csv(blame_csv)
    subset = df.head(top_n).copy()

    if subset.empty:
        print("[!] No blame data found, skipping ranking chart.")
        return

    subset = subset.iloc[::-1]  # reverse so #1 is at top of barh
    colors = [COLOR_ON_CHAIN if on else COLOR_OFF_CHAIN for on in subset["On_Critical_Chain"]]

    fig_height = max(4, 0.4 * len(subset))
    fig, ax = plt.subplots(figsize=(10, fig_height))

    bars = ax.barh(subset["Service"], subset["Mean_Duration_Sec"],
                    xerr=subset["Stdev_Duration_Sec"], capsize=3,
                    color=colors, edgecolor="black", linewidth=0.5)

    for bar, mean in zip(bars, subset["Mean_Duration_Sec"]):
        ax.text(bar.get_width() + max(subset["Mean_Duration_Sec"]) * 0.01,
                bar.get_y() + bar.get_height() / 2, f"{mean:.2f}s", va="center", fontsize=8)

    ax.set_xlabel("Mean service duration (seconds) - error bars = stdev across runs")
    ax.set_title(f"Top {top_n} Services by Duration\n{profile_label}")
    ax.grid(axis="x", linestyle="--", alpha=0.5)

    # Legend for the color coding
    on_patch = plt.Rectangle((0, 0), 1, 1, color=COLOR_ON_CHAIN, label="On critical chain (boot-blocking)")
    off_patch = plt.Rectangle((0, 0), 1, 1, color=COLOR_OFF_CHAIN, label="Not on critical chain (footprint only)")
    ax.legend(handles=[on_patch, off_patch], loc="lower right", frameon=True)

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"Saved: {out_path}")


def main():
    ap = argparse.ArgumentParser(description="Plot userspace boot profiling data")
    ap.add_argument("data_dir", nargs="?", default=(
        "./profile" if os.path.exists("./profile") else "/home/kartikey/profile"
    ))
    ap.add_argument("--profile", default="Boot Profile", help="Label describing this run/stage")
    ap.add_argument("--top", type=int, default=20, help="Number of services in the blame ranking chart")
    ap.add_argument("--chain-run", type=int, default=None,
                     help="Plot one specific iteration's critical chain instead of the mean across all runs")
    args = ap.parse_args()

    chain_csv = os.path.join(args.data_dir, "critical_chain_detail.csv")
    blame_csv = os.path.join(args.data_dir, "blame_summary.csv")

    if os.path.exists(chain_csv):
        plot_critical_chain_timeline(
            chain_csv,
            os.path.join(args.data_dir, "critical_chain_timeline.png"),
            args.profile,
            run_iteration=args.chain_run,
        )
    else:
        print(f"[!] {chain_csv} not found.")

    if os.path.exists(blame_csv):
        plot_blame_ranking(
            blame_csv,
            os.path.join(args.data_dir, "blame_ranking.png"),
            args.profile,
            top_n=args.top,
        )
    else:
        print(f"[!] {blame_csv} not found.")


if __name__ == "__main__":
    main()
