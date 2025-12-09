#!/usr/bin/env python3.12
"""Compute time between key questions for dynamically classified users.

Given a JSON file containing a list of per-person survey summaries, this script:

1. Selects only users where `classification_statuses` contains
   a status "not_classified_followup".
2. For each such user, finds:
   - the timestamp of core question "organisation_activity_question"
   - the timestamp of core question "organisation_type"
   - the earliest timestamp in `dynamic_question_texts` (if present)
3. Computes:
   - `time_in_seconds`:
       organisation_activity_question -> organisation_type
   - `time_to_show_dynamic_question`:
       organisation_activity_question -> earliest dynamic_question_texts timestamp
4. Outputs:
   - "users": list of:
       {
         "person_id": "...",
         "time_in_seconds": N,
         "time_to_show_dynamic_question": M  # only if available
       }
   - "summary":
       {
         "time_org_activity_to_org_type": {
           "count": ...,
           "average_time_in_seconds": ...,
           "longest_time_in_seconds": ...,
           "shortest_time_in_seconds": ...
         },
         "time_org_activity_to_dynamic_question": {
           "count": ...,
           "average_time_in_seconds": ...,
           "longest_time_in_seconds": ...,
           "shortest_time_in_seconds": ...
         }
       }

Usage:
    python calc_org_gap.py summary.json > org_gap_results.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Dict, Optional


@dataclass(slots=True)
class CoreQuestion:
    """Represents a single core question entry."""

    question: str
    timestamp: str


@dataclass(slots=True)
class StatusEntry:
    """Represents a status entry (e.g., classification_statuses)."""

    status: str
    timestamp: str


@dataclass(slots=True)
class DynamicQuestionText:
    """Represents a dynamic follow-up question text entry."""

    question: str
    timestamp: str


@dataclass(slots=True)
class PersonRecord:
    """Represents the subset of fields we need from the summary JSON.

    Attributes:
        person_id: Identifier of the person (e.g., "STP23212-01").
        core_questions: List of core question entries.
        classification_statuses: List of classification status entries.
        dynamic_question_texts: List of dynamic question text entries.
    """

    person_id: str
    core_questions: List[CoreQuestion]
    classification_statuses: List[StatusEntry]
    dynamic_question_texts: List[DynamicQuestionText]


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Compute time (in seconds) between organisation_activity_question "
            "and organisation_type / dynamic question for users with "
            "not_classified_followup."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to input JSON file (array of person objects), or '-' for stdin.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def parse_timestamp_to_datetime(value: str) -> Optional[datetime]:
    """Parse an ISO 8601 timestamp with trailing 'Z' and high precision.

    Example input: "2025-12-08T10:40:13.057712807Z"
    """
    if not value:
        return None
    try:
        if value.endswith("Z"):
            core = value[:-1]
            if "." in core:
                prefix, frac = core.split(".", maxsplit=1)
                # Truncate fractional seconds to microseconds (6 digits).
                frac = frac[:6]
                core = f"{prefix}.{frac}"
            iso_value = f"{core}+00:00"
        else:
            iso_value = value
        return datetime.fromisoformat(iso_value)
    except ValueError:
        return None


def load_people(path: str) -> List[PersonRecord]:
    """Load people from a JSON file or stdin into PersonRecord objects."""
    if path == "-":
        data = json.load(sys.stdin)
    else:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Input JSON must be an array of person objects.")

    people: List[PersonRecord] = []

    for item in data:
        if not isinstance(item, dict):
            continue

        person_id = str(item.get("person_id", ""))

        # core_questions
        core_raw = item.get("core_questions", [])
        core_questions: List[CoreQuestion] = []
        if isinstance(core_raw, list):
            for q in core_raw:
                if not isinstance(q, dict):
                    continue
                question = str(q.get("question", ""))
                ts = str(q.get("timestamp", ""))
                core_questions.append(CoreQuestion(question=question, timestamp=ts))

        # classification_statuses
        cls_raw = item.get("classification_statuses", [])
        classification_statuses: List[StatusEntry] = []
        if isinstance(cls_raw, list):
            for s in cls_raw:
                if not isinstance(s, dict):
                    continue
                status = str(s.get("status", ""))
                ts = str(s.get("timestamp", ""))
                classification_statuses.append(
                    StatusEntry(status=status, timestamp=ts),
                )

        # dynamic_question_texts
        dyn_raw = item.get("dynamic_question_texts", [])
        dynamic_question_texts: List[DynamicQuestionText] = []
        if isinstance(dyn_raw, list):
            for d in dyn_raw:
                if not isinstance(d, dict):
                    continue
                question = str(d.get("question", ""))
                ts = str(d.get("timestamp", ""))
                dynamic_question_texts.append(
                    DynamicQuestionText(question=question, timestamp=ts),
                )

        people.append(
            PersonRecord(
                person_id=person_id,
                core_questions=core_questions,
                classification_statuses=classification_statuses,
                dynamic_question_texts=dynamic_question_texts,
            ),
        )

    return people


def has_not_classified_followup(person: PersonRecord) -> bool:
    """Return True if person has classification status 'not_classified_followup'."""
    return any(
        entry.status == "not_classified_followup"
        for entry in person.classification_statuses
    )


def find_core_timestamp(person: PersonRecord, question_name: str) -> Optional[str]:
    """Find the timestamp for a given core question name."""
    for entry in person.core_questions:
        if entry.question == question_name:
            return entry.timestamp
    return None


def earliest_dynamic_timestamp(person: PersonRecord) -> Optional[str]:
    """Return the earliest timestamp from dynamic_question_texts, if any."""
    if not person.dynamic_question_texts:
        return None

    # Filter out empty timestamps and parse them.
    parsed: List[tuple[datetime, str]] = []
    for entry in person.dynamic_question_texts:
        dt = parse_timestamp_to_datetime(entry.timestamp)
        if dt is not None:
            parsed.append((dt, entry.timestamp))

    if not parsed:
        return None

    parsed.sort(key=lambda t: t[0])
    return parsed[0][1]


def compute_differences(
    people: List[PersonRecord],
) -> List[Dict[str, Any]]:
    """Compute per-person time differences for matching people.

    For each person with classification_status 'not_classified_followup',
    compute:

    - time_in_seconds:
        organisation_activity_question -> organisation_type
    - time_to_show_dynamic_question (if possible):
        organisation_activity_question -> earliest dynamic_question_texts timestamp
    """
    results: List[Dict[str, Any]] = []

    for person in people:
        if not has_not_classified_followup(person):
            continue

        act_ts = find_core_timestamp(person, "organisation_activity_question")
        org_type_ts = find_core_timestamp(person, "organisation_type")

        if not act_ts or not org_type_ts:
            # Cannot compute main metric; skip this user entirely.
            continue

        start_dt = parse_timestamp_to_datetime(act_ts)
        end_dt = parse_timestamp_to_datetime(org_type_ts)

        if start_dt is None or end_dt is None:
            continue

        delta = end_dt - start_dt
        seconds = int(delta.total_seconds())
        if seconds < 0:
            # Skip pathological cases where timestamps are out of order.
            continue

        record: Dict[str, Any] = {
            "person_id": person.person_id,
            "time_in_seconds": seconds,
        }

        # Optional: time_to_show_dynamic_question
        dyn_ts = earliest_dynamic_timestamp(person)
        if dyn_ts is not None:
            dyn_dt = parse_timestamp_to_datetime(dyn_ts)
            if dyn_dt is not None:
                dyn_delta = dyn_dt - start_dt
                dyn_seconds = int(dyn_delta.total_seconds())
                if dyn_seconds >= 0:
                    record["time_to_show_dynamic_question"] = dyn_seconds

        results.append(record)

    return results


def summarize_times(times: List[int]) -> Dict[str, int]:
    """Summarise a list of times (seconds) into count/avg/longest/shortest."""
    if not times:
        return {
            "count": 0,
            "average_time_in_seconds": 0,
            "longest_time_in_seconds": 0,
            "shortest_time_in_seconds": 0,
        }

    count = len(times)
    total = sum(times)
    average = total // count
    longest = max(times)
    shortest = min(times)

    return {
        "count": count,
        "average_time_in_seconds": average,
        "longest_time_in_seconds": longest,
        "shortest_time_in_seconds": shortest,
    }


def main() -> None:
    """Entry point for the CLI tool."""
    args = parse_args()
    people = load_people(args.input)
    results = compute_differences(people)

    # Collect times for summaries.
    times_org_type: List[int] = []
    times_dyn: List[int] = []

    for r in results:
        # main metric
        times_org_type.append(int(r["time_in_seconds"]))
        # dynamic metric (optional per user)
        dyn_val = r.get("time_to_show_dynamic_question")
        if isinstance(dyn_val, int):
            times_dyn.append(dyn_val)

    summary: Dict[str, Any] = {
        "time_org_activity_to_org_type": summarize_times(times_org_type),
        "time_org_activity_to_dynamic_question": summarize_times(times_dyn),
    }

    output: Dict[str, Any] = {
        "users": results,
        "summary": summary,
    }

    json.dump(output, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
