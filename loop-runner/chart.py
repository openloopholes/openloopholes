#!/usr/bin/env python3
"""
OpenLoopholes.com — Staircase Chart Generator

Reads experiment results and generates:
1. A polished PNG for tweeting (1200x675)
2. An interactive HTML version using Chart.js

Usage:
    python chart.py
    python chart.py --results ../results/experiments.json
"""

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker


ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"


def load_experiments(path: Path) -> list[dict]:
    with open(path, "r") as f:
        return json.load(f)


def load_summary(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def build_staircase_data(experiments: list[dict], baseline: int) -> list[tuple[int, int]]:
    """Build [iteration, liability] pairs for the staircase chart."""
    points = [(0, baseline)]
    current_best = baseline
    for exp in experiments:
        if exp["result"] == "keep":
            current_best = exp["estimated_liability"]
            points.append((exp["iteration"], current_best))
    return points


def generate_png(
    staircase_data: list[tuple[int, int]],
    total_iterations: int,
    strategy_count: int,
    total_savings: int,
    output_path: Path,
):
    """Generate the polished staircase chart PNG."""
    bg_color = "#0a0a0a"
    line_color = "#22c55e"
    dot_color = "#22c55e"
    grid_color = "#1a1a1a"
    text_color = "#ffffff"
    secondary_text = "#a0a0a0"

    fig, ax = plt.subplots(figsize=(12, 6.75), dpi=100)
    fig.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)

    iterations = [p[0] for p in staircase_data]
    liabilities = [p[1] for p in staircase_data]

    # Extend the last point to the total iteration count for visual completeness
    if iterations[-1] < total_iterations:
        iterations.append(total_iterations)
        liabilities.append(liabilities[-1])

    # Stepped line
    ax.step(iterations, liabilities, where="post", color=line_color, linewidth=2.5, zorder=3)

    # Dots at keep points (skip the extended point)
    keep_iters = [p[0] for p in staircase_data[1:]]
    keep_liabs = [p[1] for p in staircase_data[1:]]
    ax.scatter(keep_iters, keep_liabs, color=dot_color, s=40, zorder=4, edgecolors="none")

    # Baseline dot
    ax.scatter([0], [staircase_data[0][1]], color="#ef4444", s=50, zorder=4, edgecolors="none")

    # Grid
    ax.grid(True, axis="y", color=grid_color, linewidth=0.5, alpha=0.5)
    ax.grid(True, axis="x", color=grid_color, linewidth=0.5, alpha=0.3)

    # Axes styling
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(grid_color)
    ax.spines["bottom"].set_color(grid_color)

    ax.tick_params(colors=secondary_text, labelsize=10)
    ax.set_xlabel("Experiment", color=secondary_text, fontsize=11, labelpad=10)
    ax.set_ylabel("Estimated Tax Liability", color=secondary_text, fontsize=11, labelpad=10)

    # Format Y axis as dollars
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, p: f"${x:,.0f}"))

    # Title
    savings_str = f"${total_savings:,}"
    title = f"{total_iterations} experiments  ·  {strategy_count} strategies  ·  {savings_str} saved"
    ax.set_title(title, color=text_color, fontsize=16, fontweight="bold", pad=20,
                 fontfamily="sans-serif")

    # Subtitle
    fig.text(0.5, 0.92, "openloopholes.com", ha="center", color=secondary_text,
             fontsize=10, fontstyle="italic")

    # Annotations: baseline and final
    baseline_val = staircase_data[0][1]
    final_val = staircase_data[-1][1]

    ax.annotate(
        f"Baseline: ${baseline_val:,}",
        xy=(0, baseline_val),
        xytext=(total_iterations * 0.15, baseline_val + (baseline_val * 0.02)),
        color="#ef4444",
        fontsize=9,
        arrowprops=dict(arrowstyle="-", color="#ef4444", lw=0.5),
    )

    ax.annotate(
        f"Optimized: ${final_val:,}",
        xy=(iterations[-1], final_val),
        xytext=(total_iterations * 0.7, final_val - (baseline_val * 0.03)),
        color=line_color,
        fontsize=9,
        arrowprops=dict(arrowstyle="-", color=line_color, lw=0.5),
    )

    # Y axis padding
    y_min = min(liabilities)
    y_max = max(liabilities)
    y_range = y_max - y_min
    ax.set_ylim(y_min - y_range * 0.1, y_max + y_range * 0.15)
    ax.set_xlim(-total_iterations * 0.02, total_iterations * 1.05)

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    fig.savefig(output_path, facecolor=bg_color, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    print(f"  PNG saved: {output_path}")


def generate_html(
    staircase_data: list[tuple[int, int]],
    total_iterations: int,
    strategy_count: int,
    total_savings: int,
    baseline: int,
    output_path: Path,
):
    """Generate an interactive Chart.js HTML page."""
    labels = json.dumps([p[0] for p in staircase_data])
    data = json.dumps([p[1] for p in staircase_data])
    savings_str = f"${total_savings:,}"
    title = f"{total_iterations} experiments · {strategy_count} strategies · {savings_str} saved"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>OpenLoopholes.com — Autoresearch Results</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    background: #0a0a0a;
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    padding: 2rem;
  }}
  h1 {{
    font-size: 1.5rem;
    font-weight: 700;
    margin-bottom: 0.5rem;
  }}
  .subtitle {{
    color: #a0a0a0;
    font-size: 0.875rem;
    margin-bottom: 2rem;
    font-style: italic;
  }}
  .chart-container {{
    width: 100%;
    max-width: 900px;
    background: #0a0a0a;
    border-radius: 1rem;
    padding: 1.5rem;
  }}
  .stats {{
    display: flex;
    gap: 2rem;
    margin-top: 1.5rem;
    justify-content: center;
  }}
  .stat {{
    text-align: center;
  }}
  .stat-value {{
    font-size: 1.5rem;
    font-weight: 700;
    color: #22c55e;
    font-variant-numeric: tabular-nums;
  }}
  .stat-label {{
    font-size: 0.75rem;
    color: #a0a0a0;
    margin-top: 0.25rem;
  }}
</style>
</head>
<body>
  <h1>{title}</h1>
  <p class="subtitle">openloopholes.com</p>
  <div class="chart-container">
    <canvas id="staircase"></canvas>
  </div>
  <div class="stats">
    <div class="stat">
      <div class="stat-value">${baseline:,}</div>
      <div class="stat-label">Baseline Liability</div>
    </div>
    <div class="stat">
      <div class="stat-value">${staircase_data[-1][1]:,}</div>
      <div class="stat-label">Optimized Liability</div>
    </div>
    <div class="stat">
      <div class="stat-value">{savings_str}</div>
      <div class="stat-label">Estimated Savings</div>
    </div>
  </div>
  <script>
    const ctx = document.getElementById('staircase').getContext('2d');
    new Chart(ctx, {{
      type: 'line',
      data: {{
        labels: {labels},
        datasets: [{{
          label: 'Estimated Tax Liability',
          data: {data},
          stepped: 'before',
          borderColor: '#22c55e',
          backgroundColor: 'rgba(34, 197, 94, 0.1)',
          borderWidth: 2.5,
          pointBackgroundColor: '#22c55e',
          pointBorderColor: '#22c55e',
          pointRadius: 4,
          pointHoverRadius: 6,
          fill: true,
        }}]
      }},
      options: {{
        responsive: true,
        plugins: {{
          legend: {{ display: false }},
          tooltip: {{
            callbacks: {{
              label: (ctx) => '$' + ctx.parsed.y.toLocaleString()
            }}
          }}
        }},
        scales: {{
          x: {{
            title: {{ display: true, text: 'Experiment', color: '#a0a0a0' }},
            grid: {{ color: 'rgba(255,255,255,0.05)' }},
            ticks: {{ color: '#a0a0a0' }}
          }},
          y: {{
            title: {{ display: true, text: 'Estimated Tax Liability', color: '#a0a0a0' }},
            grid: {{ color: 'rgba(255,255,255,0.05)' }},
            ticks: {{
              color: '#a0a0a0',
              callback: (val) => '$' + val.toLocaleString()
            }}
          }}
        }}
      }}
    }});
  </script>
</body>
</html>"""

    with open(output_path, "w") as f:
        f.write(html)
    print(f"  HTML saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate staircase chart from experiment results")
    parser.add_argument("--results", type=str, default=str(RESULTS_DIR / "experiments.json"))
    parser.add_argument("--summary", type=str, default=str(RESULTS_DIR / "summary.json"))
    args = parser.parse_args()

    experiments = load_experiments(Path(args.results))
    summary = load_summary(Path(args.summary))

    baseline = summary["baseline_liability"]
    total_iterations = summary["iterations_completed"]
    strategy_count = summary["strategy_count"]
    total_savings = summary["total_savings"]

    staircase_data = build_staircase_data(experiments, baseline)

    print("Generating staircase chart...")
    print(f"  Data points: {len(staircase_data)} (baseline + {len(staircase_data) - 1} improvements)")

    generate_png(
        staircase_data, total_iterations, strategy_count, total_savings,
        RESULTS_DIR / "staircase.png",
    )

    generate_html(
        staircase_data, total_iterations, strategy_count, total_savings, baseline,
        RESULTS_DIR / "staircase.html",
    )

    print("\nDone.")


if __name__ == "__main__":
    main()
