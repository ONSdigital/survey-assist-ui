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
    """Create the timeseries chart and return the Figure object."""
    x_labels = [f"{item['date']} {int(item['hour']):02d}:00" for item in timeseries]
    totals = [int(item["total"]) for item in timeseries]
    full_journey = [int(item["full_journey_count"]) for item in timeseries]
    survey_only = [int(item["survey_only_count"]) for item in timeseries]

    fig, ax = plt.subplots(figsize=(18, 7))

    ax.plot(x_labels, totals, marker="o", label="Total")
    ax.plot(x_labels, full_journey, marker="o", label="Full Journey")
    ax.plot(x_labels, survey_only, marker="o", label="Survey Only")

    ax.set_title(title)
    ax.set_xlabel("Date & Hour")
    ax.set_ylabel("Count")

    plt.xticks(rotation=60, ha="right")
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
