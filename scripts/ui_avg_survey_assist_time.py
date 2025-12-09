#!/usr/bin/env python3.12
"""Compute timing metrics for users requiring follow-up classification.

This script processes a JSON array of survey user summaries and computes:

1. Time between:
   - organisation_activity_question → organisation_type
     → reported as `time_in_seconds`

2. Time between:
   - organisation_activity_question → earliest dynamic_question_texts timestamp
     → reported as `time_to_show_dynamic_question`

Only users containing the classification status "not_classified_followup"
are included in the outputs.

Output format:

{
  "users": [
    {
      "person_id": "...",
      "time_in_seconds": 123,
      "time_to_show_dynamic_question": 45   # optional
    }
  ],
  "summary": {
    "time_org_activity_to_org_type": {
      "count": ...,
      "average": ...,
      "longest": ...,
      "shortest": ...
    },
    "time_org_activity_to_dynamic_question": {
      "count": ...,
      "average": ...,
      "longest": ...,
      "shortest": ...
    }
  }
}
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


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
            "Compute timing deltas for users with not_classified_followup status."
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
    raw = json.load(open(path, encoding="utf-8")) if path != "-" else json.load(sys.stdin)

    people: list[PersonRecord] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue

        core_questions = [
            CoreQuestion(str(q.get("question", "")), str(q.get("timestamp", "")))
            for q in entry.get("core_questions", [])
            if isinstance(q, dict)
        ]

        classification_statuses = [
            StatusEntry(str(s.get("status", "")), str(s.get("timestamp", "")))
            for s in entry.get("classification_statuses", [])
            if isinstance(s, dict)
        ]

        dynamic_texts = [
            DynamicQuestionText(str(d.get("question", "")), str(d.get("timestamp", "")))
            for d in entry.get("dynamic_question_texts", [])
            if isinstance(d, dict)
        ]

        people.append(
            PersonRecord(
                person_id=str(entry.get("person_id", "")),
                core_questions=core_questions,
                classification_statuses=classification_statuses,
                dynamic_question_texts=dynamic_texts,
            )
        )
    return people


def has_followup(person: PersonRecord) -> bool:
    """Check if the user has a not_classified_followup status."""
    return any(s.status == "not_classified_followup" for s in person.classification_statuses)


def get_core_timestamp(person: PersonRecord, name: str) -> str | None:
    """Return timestamp for the given core question name."""
    for q in person.core_questions:
        if q.question == name:
            return q.timestamp
    return None


def earliest_dynamic_timestamp(person: PersonRecord) -> str | None:
    """Return earliest dynamic question timestamp."""
    valid = []
    for d in person.dynamic_question_texts:
        dt = parse_timestamp(d.timestamp)
        if dt:
            valid.append((dt, d.timestamp))

    if not valid:
        return None

    valid.sort(key=lambda t: t[0])
    return valid[0][1]


# -------------------------------------------------------------------
# Core computation
# -------------------------------------------------------------------

def compute_results(people: list[PersonRecord]) -> list[dict]:
    """Compute per-user timing results."""
    results: list[dict] = []

    for p in people:
        if not has_followup(p):
            continue

        act_ts = get_core_timestamp(p, "organisation_activity_question")
        type_ts = get_core_timestamp(p, "organisation_type")

        if not act_ts or not type_ts:
            continue

        start = parse_timestamp(act_ts)
        end = parse_timestamp(type_ts)
        if not start or not end:
            continue

        delta = int((end - start).total_seconds())
        if delta < 0:
            continue

        record: dict = {
            "person_id": p.person_id,
            "time_in_seconds": delta,
        }

        dyn_ts = earliest_dynamic_timestamp(p)
        if dyn_ts:
            dyn_dt = parse_timestamp(dyn_ts)
            if dyn_dt:
                dyn_delta = int((dyn_dt - start).total_seconds())
                if dyn_delta >= 0:
                    record["time_to_show_dynamic_question"] = dyn_delta

        results.append(record)

    return results


def summarise(values: list[int]) -> dict[str, int]:
    """Summarise a list of timing values."""
    if not values:
        return {
            "count": 0,
            "average": 0,
            "longest": 0,
            "shortest": 0,
        }

    return {
        "count": len(values),
        "average": sum(values) // len(values),
        "longest": max(values),
        "shortest": min(values),
    }


# -------------------------------------------------------------------
# Entry point
# -------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    people = load_people(args.input)

    user_results = compute_results(people)

    times_main = [r["time_in_seconds"] for r in user_results]
    times_dyn = [
        r["time_to_show_dynamic_question"]
        for r in user_results
        if "time_to_show_dynamic_question" in r
    ]

    summary = {
        "time_org_activity_to_org_type": summarise(times_main),
        "time_org_activity_to_dynamic_question": summarise(times_dyn),
    }

    output = {
        "users": user_results,
        "summary": summary,
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
