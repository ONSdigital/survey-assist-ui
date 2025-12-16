#!/usr/bin/env python3.12
"""Plot survey access timeseries from a JSON file.

Supports JSON in either format:

{
  "timeseries": [ { "date": "...", "hour": ..., ... }, ... ]
}

or

[ { "date": "...", "hour": ..., ... }, ... ]
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from datetime import datetime
from collections import defaultdict


import matplotlib.pyplot as plt


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for plotting survey access timeseries.

    Args:
        argv (Iterable[str] | None): Optional iterable of argument strings. If None,
            `sys.argv` is used.

    Returns:
        argparse.Namespace: Parsed CLI options including input JSON file path, chart title,
        and optional output filename.
    """
    parser = argparse.ArgumentParser(
        description="Plot survey timeseries (total, full_journey, survey_only).",
    )
    parser.add_argument(
        "json_file",
        help="Path to JSON file containing 'timeseries' data.",
    )
    parser.add_argument(
        "--title",
        default="Survey Access Timeseries",
        help="Chart title (default: 'Survey Access Timeseries').",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Optional output image filename (e.g. graph.png). "
            "If omitted, the chart is displayed instead."
        ),
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def load_timeseries(path: str) -> list[dict[str, Any]]:
    """Load timeseries from JSON file."""
    with Path(path).open("r", encoding="utf-8") as f:
        data = json.load(f)

    ts = data["timeseries"] if isinstance(data, dict) and "timeseries" in data else data

    if not isinstance(ts, list):
        raise ValueError("Expected a list of timeseries entries.")

    return ts


def plot_timeseries(timeseries: list[dict[str, Any]], title: str) -> plt.Figure:
    """Create a daily-aggregated timeseries chart and return the Figure object."""

    # --- Aggregate by date ---
    daily = defaultdict(lambda: {"total": 0, "full": 0, "survey": 0})

    for item in timeseries:
        date = item["date"]
        daily[date]["total"] += int(item["total"])
        daily[date]["full"] += int(item["full_journey_count"])
        daily[date]["survey"] += int(item["survey_only_count"])

    # Sort by date to ensure correct order
    sorted_dates = sorted(daily.keys(), key=lambda d: datetime.strptime(d, "%Y-%m-%d"))

    x_labels = sorted_dates
    totals = [daily[d]["total"] for d in sorted_dates]
    full_journey = [daily[d]["full"] for d in sorted_dates]
    survey_only = [daily[d]["survey"] for d in sorted_dates]

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(18, 7))

    ax.plot(x_labels, totals, marker="o", label="Total per day")
    ax.plot(x_labels, full_journey, marker="o", label="Full Journey per day")
    ax.plot(x_labels, survey_only, marker="o", label="Survey Only per day")

    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("Count")

    plt.xticks(rotation=45, ha="right")
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.legend()
    plt.tight_layout()

    return fig

def main() -> None:
    """Main function to parse arguments, load data, plot chart, and save/show it."""
    args = parse_args()
    ts = load_timeseries(args.json_file)

    fig = plot_timeseries(ts, args.title)

    if args.output:
        fig.savefig(args.output, dpi=200)
        print(f"Graph saved to: {args.output}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
