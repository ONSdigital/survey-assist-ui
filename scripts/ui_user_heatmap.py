#!/usr/bin/env python3
"""Generate a heatmap of user access by ID blocks and day.

This script reads a JSON file with user access records, groups users into
numeric ID blocks (e.g. STP00001 - STP02500), aggregates counts by date and
block, and outputs a heatmap as a PNG image.

Example:
-------
python user_block_heatmap.py input.json output.png

The JSON input is expected to have the structure:

{
  "count": 1176,
  "users": [
    {
      "person_id": "STP00038",
      "access_time": "2025-11-24T15:53:31.211494180Z"
    },
    ...
  ]
}

Missing or empty `access_time` values are ignored.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import BoundaryNorm

BLOCK_SIZE = 2500


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        argparse.Namespace: Parsed arguments containing input and output paths.
    """
    parser = argparse.ArgumentParser(
        description="Generate a heatmap of user access by ID block and day."
    )
    parser.add_argument(
        "input_json",
        type=Path,
        help="Path to input JSON file containing user access records.",
    )
    parser.add_argument(
        "output_png",
        type=Path,
        help="Path to output PNG file for the heatmap.",
    )
    parser.add_argument(
        "--block-size",
        type=int,
        default=BLOCK_SIZE,
        help="Number of IDs per block (default: 2500).",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict[str, Any]:
    """Load JSON data from a file.

    Args:
        path: Path to the JSON file.

    Returns:
        dict[str, Any]: Parsed JSON object.

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the file is not valid JSON.
    """
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def person_id_to_block_label(person_id: str, block_size: int) -> str | None:
    """Convert a person_id to a block label.

    The function extracts the alphabetic prefix and numeric suffix from the
    person_id. It then computes the block the numeric ID belongs to and
    returns a label such as "STP00001-STP02500".

    If no numeric part can be derived, the function returns None.

    Args:
        person_id: The person identifier, e.g. "STP00038".
        block_size: The number of IDs per block.

    Returns:
        A block label string or None if the ID cannot be parsed.
    """
    prefix_chars: list[str] = []
    digit_chars: list[str] = []

    for char in person_id:
        if char.isdigit():
            digit_chars.append(char)
        else:
            prefix_chars.append(char)

    if not digit_chars:
        return None

    prefix = "".join(prefix_chars)
    numeric_str = "".join(digit_chars)

    try:
        numeric_id = int(numeric_str)
    except ValueError:
        return None

    # Convert to 0-based index for grouping.
    block_index = (numeric_id - 1) // block_size
    start_id = block_index * block_size + 1
    end_id = (block_index + 1) * block_size

    # Zero-pad to match the length of the numeric part in the ID.
    width = len(numeric_str)
    start_str = f"{start_id:0{width}d}"
    end_str = f"{end_id:0{width}d}"
    return f"{prefix}{start_str}-{prefix}{end_str}"


def parse_access_time(access_time: str) -> date | None:
    """Parse an ISO 8601 access time string and return the date.

    The input is expected to be in UTC with a trailing 'Z', e.g.
    "2025-11-24T15:53:31.211494180Z". Empty strings or invalid values return
    None.

    Args:
        access_time: Access time string.

    Returns:
        The corresponding date or None if parsing fails.
    """
    if not access_time:
        return None

    # Replace trailing Z with +00:00 to make it ISO-compatible for fromisoformat.
    iso_string = access_time.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso_string)
    except ValueError:
        return None
    return dt.date()


def build_access_dataframe(data: dict[str, Any], block_size: int) -> pd.DataFrame:
    """Build a DataFrame of access records by date and block.

    Args:
        data: Parsed JSON data containing the 'users' list.
        block_size: Number of IDs per block.

    Returns:
        A DataFrame with columns ['access_date', 'block_label'].
    """
    records: list[dict[str, Any]] = []

    users = data.get("users", [])
    for user in users:
        person_id = user.get("person_id", "")
        access_time = user.get("access_time", "")

        access_date = parse_access_time(access_time)
        if access_date is None:
            continue

        block_label = person_id_to_block_label(person_id, block_size)
        if block_label is None:
            continue

        records.append(
            {
                "access_date": access_date,
                "block_label": block_label,
            }
        )

    if not records:
        return pd.DataFrame(columns=["access_date", "block_label"])

    return pd.DataFrame.from_records(records)


def pivot_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot the access records into a block-by-date count matrix.

    Axis layout is:
        rows (index)   -> block_label (ID blocks)
        columns        -> access_date (days)

    This supports plotting with days on the x-axis and blocks on the y-axis.

    Args:
        df: DataFrame with columns ['access_date', 'block_label'].

    Returns:
        A pivoted DataFrame with index as block_label, columns as access_date,
        and values as counts. Missing combinations are filled with zero.
    """
    if df.empty:
        return df

    counts = (
        df.groupby(["access_date", "block_label"])
        .agg(count=("block_label", "size"))
        .reset_index()
    )

    pivot = counts.pivot(
        index="block_label",
        columns="access_date",
        values="count",
    ).fillna(0)

    # Ensure blocks and dates are in a stable, sorted order.
    pivot = pivot.sort_index(axis=0)  # blocks on y-axis
    pivot = pivot.sort_index(axis=1)  # dates on x-axis

    return pivot


def plot_heatmap(
    pivot_df: pd.DataFrame,
    output_path: Path,
    step: int = 5,
) -> None:
    """Plot and save a heatmap from the pivoted counts DataFrame.

    The heatmap uses:
    * Days on the x-axis.
    * User ID blocks on the y-axis.
    * Colour levels in steps of `step` (e.g. 0, 5, 10, ...).

    Args:
        pivot_df: Pivoted DataFrame with blocks as index and dates as columns.
        output_path: Path to the output PNG file.
        step: Step size for colour levels in the heatmap (default: 5).
    """
    if pivot_df.empty:
        msg = "No data available to plot. Check input JSON or filters."
        raise ValueError(msg)

    heatmap_data = pivot_df.values
    max_value = int(heatmap_data.max())

    if max_value == 0:
        msg = "All counts are zero. Nothing to visualise in the heatmap."
        raise ValueError(msg)

    # Define boundaries in steps of `step` to make low-level differences clearer.
    # Example: 0, 5, 10, 15, ...
    bounds = np.arange(0, max_value + step, step)
    if bounds[-1] < max_value:
        bounds = np.append(bounds, max_value)

    norm = BoundaryNorm(boundaries=bounds, ncolors=256)

    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot with days on x-axis (columns) and blocks on y-axis (rows).
    image = ax.imshow(
        heatmap_data,
        aspect="auto",
        norm=norm,
        cmap="YlOrRd",
        origin="upper",
    )

    # Y-axis: blocks.
    ax.set_yticks(range(pivot_df.shape[0]))
    ax.set_yticklabels(pivot_df.index, fontsize=8)

    # X-axis: dates.
    ax.set_xticks(range(pivot_df.shape[1]))
    ax.set_xticklabels(
        [d.strftime("%Y-%m-%d") for d in pivot_df.columns],
        rotation=45,
        ha="right",
        fontsize=8,
    )

    ax.set_xlabel("Access Date")
    ax.set_ylabel("User ID Block")
    ax.set_title("User Access Heatmap by ID Block and Day")

    # Colourbar with ticks in the same step size.
    cbar = fig.colorbar(image, ax=ax, boundaries=bounds, ticks=bounds)
    cbar.set_label("Number of Accesses")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> None:
    """Main entry point for the script."""
    args = parse_args()

    data = load_json(args.input_json)
    df = build_access_dataframe(data, args.block_size)
    pivot_df = pivot_counts(df)
    plot_heatmap(pivot_df, args.output_png)


if __name__ == "__main__":
    main()
