#!/usr/bin/env python3.12
"""
Compute average total survey time per journey type from journeys JSON.

Input JSON format (array):

[
  {
    "person_id": "...",
    "access_time": "...",
    "end_time": "...",
    "total_survey_time": "HH:MM:SS",
    "journey_type": "full_journey|survey_only|abandoned",
    "overview": "..."
  },
  ...
]

Output is a small JSON object with average durations for full_journey and
survey_only journeys, in both seconds and HH:MM:SS.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(slots=True)
class JourneyRecord:
    """Represents a single journey summary row.

    Attributes:
        journey_type: Type of journey, such as "full_journey",
            "survey_only", or "abandoned".
        total_survey_time: Duration string in HH:MM:SS format, or empty
            string if not available.
    """

    journey_type: str
    total_survey_time: str


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Compute average total survey time per journey type from JSON."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to journeys JSON file, or '-' to read from stdin.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def hms_to_seconds(value: str) -> Optional[int]:
    """Convert HH:MM:SS string to total seconds.

    Args:
        value: String in the format "HH:MM:SS".

    Returns:
        Total seconds as an integer, or None if the value is not valid.
    """
    if not value:
        return None

    parts = value.split(":")
    if len(parts) != 3:
        return None
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = int(parts[2])
    except ValueError:
        return None

    if minutes < 0 or minutes >= 60 or seconds < 0 or seconds >= 60:
        return None

    return hours * 3600 + minutes * 60 + seconds


def seconds_to_hms(total_seconds: int) -> str:
    """Convert total seconds to HH:MM:SS string."""
    hours = total_seconds // 3600
    remaining = total_seconds % 3600
    minutes = remaining // 60
    seconds = remaining % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def load_journeys(path: str) -> list[JourneyRecord]:
    """Load journey records from a JSON file or stdin."""
    if path == "-":
        data = json.load(sys.stdin)
    else:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Input JSON must be an array of journey objects.")

    journeys: list[JourneyRecord] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        journeys.append(
            JourneyRecord(
                journey_type=str(item.get("journey_type", "")),
                total_survey_time=str(item.get("total_survey_time", "")),
            ),
        )
    return journeys


def average_seconds(journeys: list[JourneyRecord], journey_type: str) -> Optional[int]:
    """Compute average total survey time in seconds for a given journey type."""
    durations: list[int] = []
    for record in journeys:
        if record.journey_type != journey_type:
            continue
        seconds = hms_to_seconds(record.total_survey_time)
        if seconds is not None:
            durations.append(seconds)

    if not durations:
        return None

    return sum(durations) // len(durations)


def main() -> None:
    """Entry point."""
    args = parse_args()
    journeys = load_journeys(args.input)

    full_avg = average_seconds(journeys, "full_journey")
    survey_only_avg = average_seconds(journeys, "survey_only")

    result: dict[str, object] = {}

    if full_avg is not None:
        result["full_journey_avg_seconds"] = full_avg
        result["full_journey_avg_hms"] = seconds_to_hms(full_avg)
    else:
        result["full_journey_avg_seconds"] = None
        result["full_journey_avg_hms"] = ""

    if survey_only_avg is not None:
        result["survey_only_avg_seconds"] = survey_only_avg
        result["survey_only_avg_hms"] = seconds_to_hms(survey_only_avg)
    else:
        result["survey_only_avg_seconds"] = None
        result["survey_only_avg_hms"] = ""

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
