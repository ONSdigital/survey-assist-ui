#!/usr/bin/env python3.12
"""Compute timing metrics for users by classification outcome.

This script processes a JSON array of survey user summaries and computes
time deltas for two groups:

1. Users with classification status "not_classified_followup":
   - organisation_activity_question → organisation_type
       -> `time_in_seconds`
   - organisation_activity_question → earliest dynamic_question_texts timestamp
       -> `time_to_show_dynamic_question`

2. Users with classification status "classified_unambiguously":
   - organisation_activity_question → organisation_type
       -> `time_in_seconds`

For each group, it outputs:
- Per-user results.
- Summary stats (count, average, average_excl_min_max, longest, shortest).

Expected input: JSON array, where each element looks like:

{
  "person_id": "STP23212-01",
  "core_questions": [...],
  "classification_statuses": [...],
  "dynamic_question_texts": [...]
  ...
}

See your existing summary output schema for full structure.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# -------------------------------------------------------------------
# Dataclasses
# -------------------------------------------------------------------


@dataclass(slots=True)
class CoreQuestion:
    """Represents a single core question entry."""

    question: str
    timestamp: str


@dataclass(slots=True)
class StatusEntry:
    """Represents a classification or SIC status entry."""

    status: str
    timestamp: str


@dataclass(slots=True)
class DynamicQuestionText:
    """Represents a dynamic follow-up question text."""

    question: str
    timestamp: str


@dataclass(slots=True)
class PersonRecord:
    """Subset of fields used for timing analysis."""

    person_id: str
    core_questions: list[CoreQuestion]
    classification_statuses: list[StatusEntry]
    dynamic_question_texts: list[DynamicQuestionText]


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Compute timing deltas between organisation_activity_question and "
            "other events, split by classification outcome."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to the JSON summary file (or '-' for stdin).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def parse_timestamp(value: str) -> datetime | None:
    """Convert an ISO-8601 timestamp with trailing Z to datetime.

    Args:
        value: Timestamp string.

    Returns:
        Parsed datetime or None if invalid.
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
            return datetime.fromisoformat(f"{core}+00:00")
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_people(path: str) -> list[PersonRecord]:
    """Load all person summaries into dataclasses."""
    if path == "-":
        raw: Any = json.load(sys.stdin)
    else:
        with open(path, encoding="utf-8") as file:
            raw = json.load(file)

    people: list[PersonRecord] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue

        core_questions = [
            CoreQuestion(
                str(q.get("question", "")),
                str(q.get("timestamp", "")),
            )
            for q in entry.get("core_questions", [])
            if isinstance(q, dict)
        ]

        classification_statuses = [
            StatusEntry(
                str(s.get("status", "")),
                str(s.get("timestamp", "")),
            )
            for s in entry.get("classification_statuses", [])
            if isinstance(s, dict)
        ]

        dynamic_texts = [
            DynamicQuestionText(
                str(d.get("question", "")),
                str(d.get("timestamp", "")),
            )
            for d in entry.get("dynamic_question_texts", [])
            if isinstance(d, dict)
        ]

        people.append(
            PersonRecord(
                person_id=str(entry.get("person_id", "")),
                core_questions=core_questions,
                classification_statuses=classification_statuses,
                dynamic_question_texts=dynamic_texts,
            ),
        )
    return people


def has_status(person: PersonRecord, status: str) -> bool:
    """Check if the user has the given classification status."""
    return any(s.status == status for s in person.classification_statuses)


def get_core_timestamp(person: PersonRecord, name: str) -> str | None:
    """Return timestamp for the given core question name."""
    for q in person.core_questions:
        if q.question == name:
            return q.timestamp
    return None


def earliest_dynamic_timestamp(person: PersonRecord) -> str | None:
    """Return earliest dynamic question timestamp."""
    valid: list[tuple[datetime, str]] = []
    for d in person.dynamic_question_texts:
        dt = parse_timestamp(d.timestamp)
        if dt is not None:
            valid.append((dt, d.timestamp))

    if not valid:
        return None

    valid.sort(key=lambda t: t[0])
    return valid[0][1]


# -------------------------------------------------------------------
# Core computation
# -------------------------------------------------------------------


def compute_results_for_status(
    people: list[PersonRecord],
    status: str,
    include_dynamic: bool,
) -> list[dict[str, int | str]]:
    """Compute per-user timing results for a given classification status.

    For each matching person:
      - Always compute time_in_seconds =
            organisation_activity_question → organisation_type
      - If `include_dynamic` is True, also compute
            time_to_show_dynamic_question =
            organisation_activity_question → earliest dynamic_question_texts
    """
    results: list[dict[str, int | str]] = []

    for person in people:
        if not has_status(person, status):
            continue

        act_ts = get_core_timestamp(person, "organisation_activity_question")
        type_ts = get_core_timestamp(person, "organisation_type")

        if not act_ts or not type_ts:
            continue

        start = parse_timestamp(act_ts)
        end = parse_timestamp(type_ts)
        if start is None or end is None:
            continue

        delta = int((end - start).total_seconds())
        if delta < 0:
            continue

        record: dict[str, int | str] = {
            "person_id": person.person_id,
            "time_in_seconds": delta,
        }

        if include_dynamic:
            dyn_ts = earliest_dynamic_timestamp(person)
            if dyn_ts is not None:
                dyn_dt = parse_timestamp(dyn_ts)
                if dyn_dt is not None:
                    dyn_delta = int((dyn_dt - start).total_seconds())
                    if dyn_delta >= 0:
                        record["time_to_show_dynamic_question"] = dyn_delta

        results.append(record)

    return results


def summarise(values: list[int]) -> dict[str, int]:
    """Summarise a list of timing values.

    Includes:
    - count
    - average
    - average_excl_min_max (excluding shortest and longest if >= 3 values)
    - longest
    - shortest
    """
    if not values:
        return {
            "count": 0,
            "average": 0,
            "average_excl_min_max": 0,
            "longest": 0,
            "shortest": 0,
        }

    count = len(values)
    total = sum(values)
    average = total // count

    longest = max(values)
    shortest = min(values)

    if count > 2:  # noqa: PLR2004
        sorted_vals = sorted(values)
        trimmed = sorted_vals[1:-1]
        trimmed_avg = sum(trimmed) // len(trimmed)
    else:
        trimmed_avg = average

    return {
        "count": count,
        "average": average,
        "average_excl_min_max": trimmed_avg,
        "longest": longest,
        "shortest": shortest,
    }


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------


def main() -> None:
    """Main entry point."""
    args = parse_args()
    people = load_people(args.input)

    # Group 1: not_classified_followup
    ncf_results = compute_results_for_status(
        people,
        status="not_classified_followup",
        include_dynamic=True,
    )
    ncf_org_type_times = [int(r["time_in_seconds"]) for r in ncf_results]
    ncf_dyn_times = [
        int(r["time_to_show_dynamic_question"])
        for r in ncf_results
        if "time_to_show_dynamic_question" in r
    ]

    ncf_summary = {
        "time_org_activity_to_org_type": summarise(ncf_org_type_times),
        "time_org_activity_to_dynamic_question": summarise(ncf_dyn_times),
    }

    # Group 2: classified_unambiguously
    cu_results = compute_results_for_status(
        people,
        status="classified_unambiguously",
        include_dynamic=False,
    )
    cu_org_type_times = [int(r["time_in_seconds"]) for r in cu_results]

    cu_summary = {
        "time_org_activity_to_org_type": summarise(cu_org_type_times),
    }

    output = {
        "not_classified_followup": {
            "users": ncf_results,
            "summary": ncf_summary,
        },
        "classified_unambiguously": {
            "users": cu_results,
            "summary": cu_summary,
        },
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
