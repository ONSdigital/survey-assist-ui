#!/usr/bin/env python3.12
"""
Identify abandoned survey journeys from journey summary JSON.

This script expects as input a JSON array of journey objects, such as those
produced by `calc_survey_time.py`. Each object is expected to contain:

    {
      "person_id": "...",
      "access_time": "...",
      "end_time": "...",
      "total_survey_time": "HH:MM:SS",
      "journey_type": "full_journey|survey_only|abandoned",
      "overview": "...",
      "end_event": "..."
    }

A journey is considered "abandoned" for the purposes of this script if:

  - journey_type == "abandoned", and
  - the journey's end_time is at least 30 minutes earlier than the
    latest end_time observed across all users.

The script outputs a JSON object of the form:

    {
      "latest_end_time": "...",
      "abandoned_count": <int>,
      "abandoned_users": [
        { ... full journey object ... },
        ...
      ]
    }

Usage:

    python identify_abandoned.py journeys.json > abandoned.json

    # Or from stdin:
    cat journeys.json | python identify_abandoned.py - > abandoned.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Any, Iterable, Optional


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional iterable of argument strings. If None, sys.argv is used.

    Returns:
        Parsed argparse.Namespace containing CLI options.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Identify abandoned survey journeys from journey summary JSON."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to journeys JSON file, or '-' to read from stdin.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def parse_timestamp(value: str) -> Optional[datetime]:
    """Parse a timestamp string into a datetime object.

    The expected format is an ISO 8601 string with a trailing 'Z' and
    potentially more than 6 fractional second digits, for example:
    "2025-11-24T11:39:05.021323130Z".

    Args:
        value: Timestamp string to parse.

    Returns:
        A timezone-aware datetime object in UTC if parsing succeeds,
        otherwise None.
    """
    if not value:
        return None

    try:
        if value.endswith("Z"):
            core = value[:-1]
            if "." in core:
                prefix, frac = core.split(".", maxsplit=1)
                frac = frac[:6]
                core = f"{prefix}.{frac}"
            iso_value = f"{core}+00:00"
        else:
            iso_value = value

        return datetime.fromisoformat(iso_value)
    except ValueError:
        return None


def load_journeys(path: str) -> list[dict[str, Any]]:
    """Load journey records from a JSON file or stdin.

    Args:
        path: Path to journeys JSON file, or '-' to read from stdin.

    Returns:
        A list of journey objects as dictionaries.
    """
    if path == "-":
        data = json.load(sys.stdin)
    else:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Input JSON must be an array of journey objects.")

    journeys: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            journeys.append(item)

    return journeys


def find_latest_end_time(journeys: list[dict[str, Any]]) -> Optional[datetime]:
    """Find the latest end_time across all journeys.

    Args:
        journeys: List of journey objects.

    Returns:
        The latest end_time as a datetime object, or None if none can be parsed.
    """
    latest: Optional[datetime] = None

    for journey in journeys:
        end_time_value = journey.get("end_time")
        if not isinstance(end_time_value, str):
            continue
        end_dt = parse_timestamp(end_time_value)
        if end_dt is None:
            continue
        if latest is None or end_dt > latest:
            latest = end_dt

    return latest


def identify_abandoned(
    journeys: list[dict[str, Any]],
    latest_end: datetime,
    threshold: timedelta,
) -> list[dict[str, Any]]:
    """Identify journeys that are considered abandoned.

    A journey is considered abandoned if:
      - journey_type == "abandoned", and
      - latest_end - end_time >= threshold.

    Args:
        journeys: List of journey objects.
        latest_end: Latest end_time across all journeys.
        threshold: Minimum time difference required to flag abandonment.

    Returns:
        A list of journey objects that meet the abandonment criteria.
    """
    abandoned: list[dict[str, Any]] = []

    for journey in journeys:
        journey_type = journey.get("journey_type")
        if journey_type != "abandoned":
            continue

        end_time_value = journey.get("end_time")
        if not isinstance(end_time_value, str):
            continue

        end_dt = parse_timestamp(end_time_value)
        if end_dt is None:
            continue

        if latest_end - end_dt >= threshold:
            abandoned.append(journey)

    return abandoned


def main() -> None:
    """Entry point for the CLI tool.

    Reads journey summary JSON, computes the latest end_time, identifies
    abandoned journeys (per the 30-minute rule), and prints a JSON object
    with the latest_end_time, abandoned_count, and abandoned_users.
    """
    args = parse_args()
    journeys = load_journeys(args.input)

    latest_end_dt = find_latest_end_time(journeys)
    if latest_end_dt is None:
        # No valid end_time values; output empty result.
        result: dict[str, Any] = {
            "latest_end_time": "",
            "abandoned_count": 0,
            "abandoned_users": [],
        }
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
        return

    threshold = timedelta(minutes=30)
    abandoned_users = identify_abandoned(journeys, latest_end_dt, threshold)

    result = {
        "latest_end_time": latest_end_dt.isoformat().replace("+00:00", "Z"),
        "abandoned_count": len(abandoned_users),
        "abandoned_users": abandoned_users,
    }

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
