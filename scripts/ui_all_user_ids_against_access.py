#!/usr/bin/env python3
"""Generate a stacked bar chart showing which issued IDs engaged, failed access,
or never attempted to access the survey system.

Usage
-----
python engagement_blocks.py input.json [output.png]

The script:
1. Generates the full issued ID list (STP00001-STP24800)
2. Joins with the JSON file that contains access attempts
3. Classifies each ID into:
   - engaged        → access_time is non-empty
   - failed_access  → access_time == ""
   - no_attempt     → ID never appears in the JSON
4. Groups into 2500-ID blocks and visualises with matplotlib.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

# -------- Configuration --------

BLOCK_SIZE = 2500
PREFIX = "STP"
START_ID = 1
END_ID = 24800
ID_WIDTH = 5  # STP00001 → 5 digits


# -------- Data Preparation --------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for input and output files."""
    parser = argparse.ArgumentParser(
        description="Generate engagement stacked bar chart by ID block."
    )
    parser.add_argument(
        "input_json",
        type=Path,
        help="Path to the JSON file containing user access attempts.",
    )
    parser.add_argument(
        "output_png",
        nargs="?",
        default="engagement_blocks.png",
        type=Path,
        help="Output filename for the bar chart (default: engagement_blocks.png).",
    )
    return parser.parse_args()


def generate_all_ids(prefix: str, start: int, end: int, width: int) -> list[str]:
    """Generate all issued person_ids from start to end."""
    return [f"{prefix}{i:0{width}d}" for i in range(start, end + 1)]


def load_attempts(path: Path) -> pd.DataFrame:
    """Load the JSON attempts file into a DataFrame."""
    with path.open("r", encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    df = pd.DataFrame(data.get("users", []))
    return df[["person_id", "access_time"]]


def classify_status(all_ids: list[str], attempts_df: pd.DataFrame) -> pd.DataFrame:
    """Classify each issued ID into one of: engaged, failed_access, no_attempt."""
    full_frame = pd.DataFrame({"person_id": all_ids})

    merged = full_frame.merge(attempts_df, on="person_id", how="left")

    def status(row: pd.Series) -> str:
        if pd.isna(row["access_time"]):
            return "no_attempt"
        if row["access_time"] == "":
            return "failed_access"
        return "engaged"

    merged["status"] = merged.apply(status, axis=1)
    return merged


def id_to_block_label(person_id: str) -> str:
    """Convert an ID like STP00038 → STP00001-STP02500."""
    numeric = int("".join(c for c in person_id if c.isdigit()))
    block_idx = (numeric - 1) // BLOCK_SIZE

    start_id = block_idx * BLOCK_SIZE + 1
    end_id = (block_idx + 1) * BLOCK_SIZE

    return f"{PREFIX}{start_id:0{ID_WIDTH}d}-{PREFIX}{end_id:0{ID_WIDTH}d}"


def summarise_blocks(df: pd.DataFrame) -> pd.DataFrame:
    """Group by ID block and engagement status."""
    df["block"] = df["person_id"].apply(id_to_block_label)

    summary = (
        df.groupby(["block", "status"])
        .agg(count=("status", "size"))
        .reset_index()
        .pivot(index="block", columns="status", values="count")
        .fillna(0)
    )

    # Ensure columns always exist
    for col in ["no_attempt", "failed_access", "engaged"]:
        if col not in summary:
            summary[col] = 0

    return summary.sort_index()


# -------- Plotting --------


def plot_stacked_bars(summary: pd.DataFrame, output_file: Path) -> None:
    """Plot a stacked bar chart of engagement per ID block."""
    blocks = summary.index.tolist()

    no_attempt = summary["no_attempt"].values
    failed = summary["failed_access"].values
    engaged = summary["engaged"].values

    x = range(len(blocks))

    plt.figure(figsize=(12, 6))

    # Engaged at bottom
    plt.bar(x, engaged, label="Engaged", color="#4caf50")

    # Failed access stacked on engaged
    plt.bar(x, failed, bottom=engaged, label="Failed Access", color="#ffbf00")

    # No attempt stacked on top
    plt.bar(x, no_attempt, bottom=engaged + failed, label="No Attempt", color="#c7c7c7")

    plt.xticks(x, blocks, rotation=45, ha="right")
    plt.ylabel("Number of Users")
    plt.xlabel("ID Block (2500 IDs each)")
    plt.title("Engagement Summary by ID Block")
    plt.legend(
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        borderaxespad=0,
        frameon=True,
    )
    plt.tight_layout()
    plt.savefig(output_file, dpi=150)
    plt.close()

    print(f"Saved chart → {output_file}")


# -------- Main --------


def main() -> None:
    """Main script entry point."""
    args = parse_args()

    all_ids = generate_all_ids(PREFIX, START_ID, END_ID, ID_WIDTH)
    attempts_df = load_attempts(args.input_json)
    classified = classify_status(all_ids, attempts_df)
    summary = summarise_blocks(classified)

    plot_stacked_bars(summary, args.output_png)


if __name__ == "__main__":
    main()
