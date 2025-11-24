#!/usr/bin/env python3.12
"""
Compute total survey time per person from survey log summary JSON.

This script expects as input a JSON array of per-person summary objects,
such as those produced by the UI log analysis script. For each person_id,
it computes:

    total_survey_time = end_timestamp - access_time

where the end timestamp is derived using the following precedence:

1. If feedback_results_saved > 0:
   - Use the timestamp of the last feedback_result_ids entry.

2. Else if survey_results_saved > 0:
   - Use the timestamp of the last survey_result_ids entry.

3. Else:
   - Use the timestamp of the final question the user answered:
     - Consider timestamps from:
       - core_questions
       - dynamic_questions
       - dynamic_question_texts
     - Take the maximum timestamp among these.

If access_time or an end timestamp cannot be determined, the total survey
time is returned as an empty string.

The output is a JSON array where each element contains:

    {
      "person_id": "...",
      "access_time": "...",
      "end_time": "...",
      "total_survey_time": "HH:MM:SS"
    }

Usage:

    python calc_survey_time.py summary.json > survey_times.json

    # Or from stdin:
    cat summary.json | python calc_survey_time.py - > survey_times.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, List, Optional


@dataclass(slots=True)
class PersonSummary:
    """Representation of a single person's survey summary.

    This mirrors the structure of the existing summary JSON produced by
    the log analysis script, but we only define the fields we need.

    Attributes:
        person_id: Identifier of the person.
        access_time: ISO 8601 timestamp string of when the survey was
            first accessed for this person (for example,
            "2025-11-24T11:39:05.021323130Z").
        core_questions: List of core question entries, each containing
            "question" and "timestamp".
        dynamic_questions: List of dynamic question entries, each containing
            "question" and "timestamp".
        sic_lookup_statuses: List of SIC lookup status entries, each
            containing "status" and "timestamp".
        classification_statuses: List of classification status entries, each
            containing "status" and "timestamp".
        rerouted_no_employment: Whether this person was rerouted due to
            no employment.
        survey_results_saved: Count of survey result save events.
        feedback_results_saved: Count of feedback result save events.
        survey_result_ids: List of survey result entries, each containing
            "id" and "timestamp".
        feedback_result_ids: List of feedback result entries, each containing
            "id" and "timestamp".
        dynamic_question_texts: List of dynamic follow-up question texts,
            each containing "question" and "timestamp".
    """

    person_id: str
    access_time: str
    core_questions: List[dict[str, Any]]
    dynamic_questions: List[dict[str, Any]]
    sic_lookup_statuses: List[dict[str, Any]]
    classification_statuses: List[dict[str, Any]]
    rerouted_no_employment: bool
    survey_results_saved: int
    feedback_results_saved: int
    survey_result_ids: List[dict[str, Any]]
    feedback_result_ids: List[dict[str, Any]]
    dynamic_question_texts: List[dict[str, Any]]


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional iterable of argument strings. If None, sys.argv is used.

    Returns:
        Parsed argparse.Namespace containing CLI options.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Compute total survey time per person from survey summary JSON."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to input JSON file, or '-' to read from stdin.",
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

    # Normalise: remove trailing 'Z', trim fractional seconds to at most 6
    # digits (Python's datetime supports microseconds), then re-add 'Z'.
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


def compute_end_time(summary: PersonSummary) -> Optional[str]:
    """Compute the end timestamp string for a person's survey.

    The precedence is:

    1. If feedback_results_saved > 0: use the last feedback_result_ids timestamp.
    2. Else if survey_results_saved > 0: use the last survey_result_ids timestamp.
    3. Else: use the latest timestamp among all answered questions:
       - core_questions
       - dynamic_questions
       - dynamic_question_texts

    Args:
        summary: PersonSummary instance.

    Returns:
        The end timestamp string if available, otherwise None.
    """
    # 1. Feedback result (if any).
    if summary.feedback_results_saved > 0 and summary.feedback_result_ids:
        last_feedback = max(
            summary.feedback_result_ids,
            key=lambda item: item.get("timestamp", ""),
        )
        ts = last_feedback.get("timestamp")
        if isinstance(ts, str) and ts:
            return ts

    # 2. Survey result (if any).
    if summary.survey_results_saved > 0 and summary.survey_result_ids:
        last_survey = max(
            summary.survey_result_ids,
            key=lambda item: item.get("timestamp", ""),
        )
        ts = last_survey.get("timestamp")
        if isinstance(ts, str) and ts:
            return ts

    # 3. Fallback to final question answered.
    candidate_ts: list[str] = []

    for entry in summary.core_questions:
        ts = entry.get("timestamp")
        if isinstance(ts, str) and ts:
            candidate_ts.append(ts)

    for entry in summary.dynamic_questions:
        ts = entry.get("timestamp")
        if isinstance(ts, str) and ts:
            candidate_ts.append(ts)

    for entry in summary.dynamic_question_texts:
        ts = entry.get("timestamp")
        if isinstance(ts, str) and ts:
            candidate_ts.append(ts)

    if not candidate_ts:
        return None

    # Timestamps are ISO-like strings; max() works lexicographically for
    # ISO 8601 in the same timezone, but to be safe we sort by parsed datetime.
    latest_ts = max(
        candidate_ts,
        key=lambda s: parse_timestamp(s) or datetime.min,
    )
    return latest_ts


def compute_total_survey_time(summary: PersonSummary) -> tuple[str, str]:
    """Compute total survey time in HH:MM:SS and return also the end timestamp.

    Args:
        summary: PersonSummary instance.

    Returns:
        A tuple of (end_time_str, total_survey_time_str). If the total
        survey time cannot be computed, both elements are empty strings.
    """
    access_dt = parse_timestamp(summary.access_time)
    if access_dt is None:
        return "", ""

    end_ts_str = compute_end_time(summary)
    if end_ts_str is None:
        return "", ""

    end_dt = parse_timestamp(end_ts_str)
    if end_dt is None:
        return "", ""

    delta = end_dt - access_dt
    if delta.total_seconds() < 0:
        return end_ts_str, ""

    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    hms = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    return end_ts_str, hms


def load_input(path: str) -> list[PersonSummary]:
    """Load the input JSON and convert to PersonSummary instances.

    Args:
        path: Path to the JSON file, or '-' for stdin.

    Returns:
        A list of PersonSummary objects.
    """
    if path == "-":
        data = json.load(sys.stdin)
    else:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)

    if not isinstance(data, list):
        raise ValueError("Input JSON must be an array of summary objects.")

    summaries: list[PersonSummary] = []
    for item in data:
        if not isinstance(item, dict):
            continue

        summaries.append(
            PersonSummary(
                person_id=str(item.get("person_id", "")),
                access_time=str(item.get("access_time", "")),
                core_questions=list(item.get("core_questions", [])),
                dynamic_questions=list(item.get("dynamic_questions", [])),
                sic_lookup_statuses=list(item.get("sic_lookup_statuses", [])),
                classification_statuses=list(
                    item.get("classification_statuses", []),
                ),
                rerouted_no_employment=bool(
                    item.get("rerouted_no_employment", False),
                ),
                survey_results_saved=int(item.get("survey_results_saved", 0)),
                feedback_results_saved=int(item.get("feedback_results_saved", 0)),
                survey_result_ids=list(item.get("survey_result_ids", [])),
                feedback_result_ids=list(item.get("feedback_result_ids", [])),
                dynamic_question_texts=list(
                    item.get("dynamic_question_texts", []),
                ),
            ),
        )

    return summaries


def main() -> None:
    """Entry point for the CLI tool.

    Reads a JSON array of per-person survey summaries and prints a JSON
    array of objects containing person_id, access_time, end_time, and
    total_survey_time in HH:MM:SS.
    """
    args = parse_args()
    summaries = load_input(args.input)

    results: list[dict[str, str]] = []
    for summary in summaries:
        end_time, total_time = compute_total_survey_time(summary)
        results.append(
            {
                "person_id": summary.person_id,
                "access_time": summary.access_time,
                "end_time": end_time,
                "total_survey_time": total_time,
            },
        )

    json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
