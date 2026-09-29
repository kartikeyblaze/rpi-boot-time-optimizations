#!/usr/bin/env python3
import os
import pandas as pd
import matplotlib.pyplot as plt

# Workspace Configurations
DATA_DIR = "./profile" if os.path.exists("./profile") else "/home/kartikey/profile"
INPUT_CSV = os.path.join(DATA_DIR, "component_bottlenecks.csv")
SUMMARY_CSV = os.path.join(DATA_DIR, "component_summary.csv")
CHART_PNG = os.path.join(DATA_DIR, "component_bottlenecks.png")
CHART_PIE_PNG = os.path.join(DATA_DIR, "component_pie.png")

def clean_service_name(name):
    """Sanitizes systemd hex escapes and shortens over-extended block device hashes."""
    # Convert systemd hex escape sequence '\x2d' to standard dash
    clean_name = name.replace('\\x2d', '-').replace('\\x22d', '-')
    
    # Condense long hardware UUID nodes to keep the chart axis clean
    if "systemd-fsck@" in clean_name:
        return "systemd-fsck (Storage Check)"
    if "dev-disk-by" in clean_name:
        return "Storage Device Initialization"
    return clean_name

def main():
    if not os.path.exists(INPUT_CSV):
        print(f"Error: Target file not found at {INPUT_CSV}")
        return

    # Load Dataset
    df = pd.read_csv(INPUT_CSV)
    raw_services = [col for col in df.columns if col != 'Iteration']

    # 1. Statistical Calculations Matrix
    stats = {}
    for service in raw_services:
        mean_val = df[service].mean()
        std_val = df[service].std(ddof=1)  # Sample Std Dev (n-1)
        cv_val = (std_val / mean_val) if mean_val > 0 else 0
        min_val = df[service].min()
        max_val = df[service].max()

        # Save under cleaned human-readable names
        clean_label = clean_service_name(service)
        stats[clean_label] = {
            "Average_ms": round(mean_val, 2),
            "Std_Dev_ms": round(std_val, 2),
            "Coef_of_Variation": round(cv_val, 4),
            "Min_ms": min_val,
            "Max_ms": max_val
        }

    # Save Metrics File
    summary_df = pd.DataFrame(stats).T
    summary_df.index.name = "Service"
    summary_df.to_csv(SUMMARY_CSV)
    print(f"[✓] Cleaned statistical matrix exported to: {SUMMARY_CSV}")

    # 2. Chart Generation: Conditional Horizontal Bar Chart
    chart_data = summary_df.sort_values(by="Average_ms", ascending=True)

    plt.figure(figsize=(14, 8))
    
    # Optimization: Apply conditional color assignment based on runtime threshold
    # Heavy optimization targets (>1000ms) get a warning color (coral); others remain blue.
    bar_colors = ['#e74c3c' if x >= 1000 else '#3498db' for x in chart_data["Average_ms"]]
    
    bars = plt.barh(chart_data.index, chart_data["Average_ms"], color=bar_colors, edgecolor="#2c3e50", alpha=0.85)
    
    plt.xlabel("Execution Duration (Milliseconds)", fontsize=11, fontweight='bold')
    plt.ylabel("Systemd Service / Unit Node", fontsize=11, fontweight='bold')
    plt.title("Average Component Overhead on Boot Critical Path", fontsize=14, fontweight='bold', pad=15)
    plt.grid(axis='x', linestyle='--', alpha=0.5)

    # Annotate values to the right of each bar
    for bar in bars:
        width = bar.get_width()
        if width > 0:
            plt.text(width + (max(chart_data["Average_ms"]) * 0.01), 
                     bar.get_y() + bar.get_height()/2, 
                     f'{width:,.1f} ms', 
                     va='center', ha='left', fontsize=9, fontweight='semibold')

    plt.tight_layout()
    plt.savefig(CHART_PNG, dpi=300)
    plt.close()
    print(f"[✓] Bottleneck analysis chart exported to: {CHART_PNG}")

    # =========================================================================
    # 3. New Chart Generation: Proportional Breakdown Donut Chart
    # =========================================================================
    # Sort descending to lay out slices systematically from largest to smallest
    pie_data = summary_df.sort_values(by="Average_ms", ascending=False)
    pie_data = pie_data[pie_data["Average_ms"] > 0]

    # Increase width slightly to accommodate the side legend perfectly
    plt.figure(figsize=(13, 10))
    total_ms = pie_data["Average_ms"].sum()
    theme_colors = plt.cm.tab20c(range(len(pie_data)))
    
    # Clean Legend Labels: "Service: Time (Percentage)"
    legend_labels = [
        f"{idx}: {row['Average_ms']:.1f}ms ({(row['Average_ms']/total_ms)*100:.1f}%)"
        for idx, row in pie_data.iterrows()
    ]

    # Conditional display function: hides text labels if the slice is too narrow (< 3%)
    def conditional_pct(pct):
        return f"{pct * total_ms / 100:.1f}ms\n({pct:.1f}%)" if pct >= 3.0 else ''

    # Generate pie layout configuration (without direct labels to prevent overlap)
    wedges, texts, autotexts = plt.pie(
        pie_data["Average_ms"], 
        labels=None,  # Labels moved entirely to the legend
        autopct=conditional_pct, 
        startangle=140, 
        colors=theme_colors, 
        wedgeprops={'edgecolor': '#2c3e50', 'linewidth': 0.8, 'alpha': 0.9},
        textprops={'fontsize': 9, 'fontweight': 'bold'},
        pctdistance=0.75
    )

    # Style the inside text to be highly visible against colored slices
    for autotext in autotexts:
        autotext.set_color('white')

    # Optimization: Transform the Pie into a clean Donut Chart
    centre_circle = plt.Circle((0, 0), 0.55, fc='white', edgecolor='#2c3e50', linewidth=0.5)
    fig = plt.gcf()
    fig.gca().add_artist(centre_circle)
    
    # Detach legend and place it cleanly on the right side of the canvas
    plt.legend(
        wedges, 
        legend_labels, 
        title="Service Execution Breakdown", 
        title_fontproperties={'weight': 'bold', 'size': 11},
        loc="center left", 
        bbox_to_anchor=(0.95, 0.5),
        frameon=True,
        facecolor='#f8f9fa'
    )
    
    plt.title("Proportional Distribution of Service Overhead on Boot Critical Path", 
              fontsize=14, fontweight='bold', pad=25)
    
    # Adjust bounding boxes so the legend doesn't get cut off on export
    plt.tight_layout()
    plt.savefig(CHART_PIE_PNG, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"[✓] High-readability proportional chart exported to: {CHART_PIE_PNG}")

if __name__ == "__main__":
    main()
