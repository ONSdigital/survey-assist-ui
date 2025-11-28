#!/usr/bin/env python3.12
"""
Compute average, longest, and shortest total survey time per journey type
from journeys JSON, and produce a per-calendar-hour access time series.

Input JSON format (array):

[
  {
    "person_id": "...",
    "access_time": "2025-11-24T18:39:36.904907977Z",
    "end_time": "...",
    "total_survey_time": "HH:MM:SS",
    "journey_type": "full_journey|survey_only|abandoned",
    "overview": "...",
    "end_event": "..."
  },
  ...
]

Output example:

{
  "full_journey": {
    "average": { "seconds": 305, "hms": "00:05:05" },
    "longest": { "seconds": 5528, "hms": "01:32:08", "person_id": "STP04375-01" },
    "shortest": { "seconds": 91, "hms": "00:01:31", "person_id": "STP03268-01" }
  },
  "survey_only": {
    "average": { "seconds": 207, "hms": "00:03:27" },
    "longest": { "seconds": 1548, "hms": "00:25:48", "person_id": "STP03490-01" },
    "shortest": { "seconds": 17, "hms": "00:00:17", "person_id": "STP02252-01" }
  },
  "timeseries": [
    {
      "date": "2025-11-24",
      "hour": 15,
      "total": 12,
      "full_journey_count": 7,
      "survey_only_count": 5
    },
    ...
  ]
}
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Optional, Tuple


@dataclass(slots=True)
class JourneyRecord:
    """Represents a single journey summary row.

    Attributes:
        person_id: Identifier of the person.
        journey_type: Type of journey, such as "full_journey",
            "survey_only", or "abandoned".
        total_survey_time: Duration string in HH:MM:SS format, or empty
            string if not available.
        access_time: ISO 8601 timestamp string when the survey was first
            accessed (for example, "2025-11-24T18:39:36.904907977Z").
    """

    person_id: str
    journey_type: str
    total_survey_time: str
    access_time: str


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Compute journey time statistics and per-calendar-hour access "
            "time series from JSON."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to journeys JSON file, or '-' to read from stdin.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def hms_to_seconds(value: str) -> Optional[int]:
    """Convert HH:MM:SS string to total seconds."""
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


def parse_access_datetime(access_time: str) -> Optional[datetime]:
    """Parse access_time into a datetime.

    Expected format: ISO 8601 with trailing 'Z' and possibly >6 fractional
    second digits, for example "2025-11-24T18:39:36.904907977Z".
    """
    if not access_time:
        return None
    try:
        value = access_time
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
                person_id=str(item.get("person_id", "")),
                journey_type=str(item.get("journey_type", "")),
                total_survey_time=str(item.get("total_survey_time", "")),
                access_time=str(item.get("access_time", "")),
            ),
        )
    return journeys


def stats_for_type(
    journeys: list[JourneyRecord],
    journey_type: str,
) -> Tuple[
    Optional[int], Optional[int], Optional[str], Optional[int], Optional[str]
]:
    """Compute average, longest, and shortest durations for a journey type."""
    durations: list[tuple[int, str]] = []

    for record in journeys:
        if record.journey_type != journey_type:
            continue
        seconds = hms_to_seconds(record.total_survey_time)
        if seconds is not None:
            durations.append((seconds, record.person_id))

    if not durations:
        return None, None, None, None, None

    total_seconds = sum(d[0] for d in durations)
    avg_seconds = total_seconds // len(durations)

    longest_seconds, longest_person_id = max(durations, key=lambda t: t[0])
    shortest_seconds, shortest_person_id = min(durations, key=lambda t: t[0])

    return (
        avg_seconds,
        longest_seconds,
        longest_person_id,
        shortest_seconds,
        shortest_person_id,
    )


def assemble(journey_name: str, stats: Tuple[Any, ...]) -> dict[str, Any]:
    """Assemble journey stats into the desired nested JSON structure."""
    (
        avg,
        longest,
        longest_pid,
        shortest,
        shortest_pid,
    ) = stats

    return {
        journey_name: {
            "average": {
                "seconds": avg,
                "hms": seconds_to_hms(avg) if avg is not None else "",
            },
            "longest": {
                "seconds": longest,
                "hms": (
                    seconds_to_hms(longest)
                    if longest is not None
                    else ""
                ),
                "person_id": longest_pid,
            },
            "shortest": {
                "seconds": shortest,
                "hms": (
                    seconds_to_hms(shortest)
                    if shortest is not None
                    else ""
                ),
                "person_id": shortest_pid,
            },
        },
    }


def build_timeseries(journeys: list[JourneyRecord]) -> list[dict[str, int]]:
    """Build a per-calendar-hour access time series from journeys.

    Each entry in the returned list has the form:

        {
          "date": "YYYY-MM-DD",
          "hour": HH,
          "total": <count of all journeys accessed in this date+hour>,
          "full_journey_count": <count with journey_type == "full_journey">,
          "survey_only_count": <count with journey_type == "survey_only">
        }

    Where `hour` is 0-23 and `date` is the UTC calendar date (from access_time).
    """
    # Key: (date_str, hour) -> counts
    buckets: dict[tuple[str, int], dict[str, int]] = {}

    for record in journeys:
        dt = parse_access_datetime(record.access_time)
        if dt is None:
            continue

        date_str = dt.date().isoformat()
        hour = dt.hour
        key = (date_str, hour)

        bucket = buckets.get(key)
        if bucket is None:
            bucket = {
                "total": 0,
                "full_journey_count": 0,
                "survey_only_count": 0,
            }
            buckets[key] = bucket

        bucket["total"] += 1
        if record.journey_type == "full_journey":
            bucket["full_journey_count"] += 1
        elif record.journey_type == "survey_only":
            bucket["survey_only_count"] += 1

    timeseries: list[dict[str, int]] = []
    for (date_str, hour) in sorted(buckets.keys()):
        bucket = buckets[(date_str, hour)]
        timeseries.append(
            {
                "date": date_str,
                "hour": hour,
                "total": bucket["total"],
                "full_journey_count": bucket["full_journey_count"],
                "survey_only_count": bucket["survey_only_count"],
            },
        )

    return timeseries


def main() -> None:
    """Entry point."""
    args = parse_args()
    journeys = load_journeys(args.input)

    full_stats = stats_for_type(journeys, "full_journey")
    survey_stats = stats_for_type(journeys, "survey_only")
    timeseries = build_timeseries(journeys)

    result: dict[str, Any] = {
        **assemble("full_journey", full_stats),
        **assemble("survey_only", survey_stats),
        "timeseries": timeseries,
    }

    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
