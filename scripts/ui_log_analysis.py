#!/usr/bin/env python3.12
"""
CLI tool to analyse survey logs for core, dynamic, and classification-related events.

It reads lines from a log file (or stdin), finds patterns such as:
- "saved response for <question_name>" (core questions)
- "question: organisation_activity_question" (core question)
- "survey_assist_followup_<n>" (dynamic follow-up questions)
- "match, skip classification" / "NOT matched, classify" (SIC lookup status)
- "classified unambiguously" / "not classified, followup" (classification status)
- "rerouted no employment" (not in employment routing)
- "survey result saved" / "feedback result saved" (persistence events)

It can:
- Stream individual events as JSONL (default)
- Emit a per-person summary as JSON with --summary
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Iterable, Iterator, Literal

# Core/dynamic question patterns.
PERSON_ID_RE = re.compile(r"person_id:([A-Za-z0-9_-]+)")
CORE_Q_RE = re.compile(r"saved response for\s+([A-Za-z0-9_-]+)")
DYNAMIC_Q_RE = re.compile(r"(survey_assist_followup_[0-9]+)")
ORG_ACTIVITY_Q_TOKEN = "question: organisation_activity_question"

# Status tokens derived from your grep command.
SIC_MATCH_SKIP_TOKEN = "match, skip classification"
SIC_NOT_MATCHED_CLASSIFY_TOKEN = "NOT matched, classify"

CLASSIFIED_UNAMBIGUOUSLY_TOKEN = "classified unambiguously"
NOT_CLASSIFIED_FOLLOWUP_TOKEN = "not classified, followup"

REROUTED_NO_EMPLOYMENT_TOKEN = "rerouted no employment"

SURVEY_RESULT_SAVED_TOKEN = "survey result saved"
FEEDBACK_RESULT_SAVED_TOKEN = "feedback result saved"

EventKind = Literal[
    "core",
    "dynamic",
    "sic_lookup",
    "classification",
    "routing",
    "survey_saved",
    "feedback_saved",
]


@dataclass(slots=True)
class Event:
    """Represents a single parsed log event.

    Attributes:
        person_id: Identifier extracted from `person_id:<value>`.
        kind: Event kind, such as "core", "dynamic", "sic_lookup",
            "classification", "routing", "survey_saved", or "feedback_saved".
        question: Question identifier where applicable (for example, "age_range"
            or "survey_assist_followup_1"). None for events that are not
            question-specific.
        status: Status label for non-question events (for example,
            "match_skip_classification", "classified_unambiguously").
            May be None for question-based events.
        raw: Original log line.
    """

    person_id: str
    kind: EventKind
    question: str | None
    status: str | None
    raw: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable representation of the event.

        Returns:
            A dictionary containing event fields.
        """
        return {
            "person_id": self.person_id,
            "kind": self.kind,
            "question": self.question,
            "status": self.status,
            "raw": self.raw,
        }


@dataclass(slots=True)
class PersonSummary:
    """Aggregated information about a person's events.

    Attributes:
        person_id: Identifier of the person.
        core_questions: Set of core question identifiers.
        dynamic_questions: Set of dynamic question identifiers.
        sic_lookup_statuses: Set of SIC lookup status labels.
        classification_statuses: Set of classification status labels.
        rerouted_no_employment: Whether a "rerouted no employment" event
            was seen for this person.
        survey_results_saved: Count of "survey result saved" events.
        feedback_results_saved: Count of "feedback result saved" events.
    """

    person_id: str
    core_questions: set[str]
    dynamic_questions: set[str]
    sic_lookup_statuses: set[str]
    classification_statuses: set[str]
    rerouted_no_employment: bool
    survey_results_saved: int
    feedback_results_saved: int


def parse_line(line: str) -> Event | None:
    """Parse a single log line and extract an Event if relevant.

    The function looks for:
    - `person_id:<value>`
    - core question events:
        - `saved response for <question>`
        - `question: organisation_activity_question`
    - dynamic question events:
        - `survey_assist_followup_<n>`
    - SIC lookup status:
        - `match, skip classification`
        - `NOT matched, classify`
    - classification status:
        - `classified unambiguously`
        - `not classified, followup`
    - routing and persistence:
        - `rerouted no employment`
        - `survey result saved`
        - `feedback result saved`

    Args:
        line: A single log line.

    Returns:
        An Event instance if the line contains a recognised pattern,
        otherwise None.
    """
    person_match = PERSON_ID_RE.search(line)
    if person_match is None:
        return None

    person_id = person_match.group(1)
    stripped_raw = line.rstrip("\n")

    # Core question answered via "saved response for <question>".
    core_match = CORE_Q_RE.search(line)
    if core_match is not None:
        question = core_match.group(1)
        return Event(
            person_id=person_id,
            kind="core",
            question=question,
            status=None,
            raw=stripped_raw,
        )

    # Core question answered via "question: organisation_activity_question".
    if ORG_ACTIVITY_Q_TOKEN in line:
        return Event(
            person_id=person_id,
            kind="core",
            question="organisation_activity_question",
            status=None,
            raw=stripped_raw,
        )

    # Dynamic follow-up questions.
    dyn_match = DYNAMIC_Q_RE.search(line)
    if dyn_match is not None:
        question = dyn_match.group(1)
        return Event(
            person_id=person_id,
            kind="dynamic",
            question=question,
            status=None,
            raw=stripped_raw,
        )

    # SIC lookup statuses.
    if SIC_MATCH_SKIP_TOKEN in line:
        return Event(
            person_id=person_id,
            kind="sic_lookup",
            question=None,
            status="match_skip_classification",
            raw=stripped_raw,
        )
    if SIC_NOT_MATCHED_CLASSIFY_TOKEN in line:
        return Event(
            person_id=person_id,
            kind="sic_lookup",
            question=None,
            status="not_matched_classify",
            raw=stripped_raw,
        )

    # Classification statuses.
    if CLASSIFIED_UNAMBIGUOUSLY_TOKEN in line:
        return Event(
            person_id=person_id,
            kind="classification",
            question=None,
            status="classified_unambiguously",
            raw=stripped_raw,
        )
    if NOT_CLASSIFIED_FOLLOWUP_TOKEN in line:
        return Event(
            person_id=person_id,
            kind="classification",
            question=None,
            status="not_classified_followup",
            raw=stripped_raw,
        )

    # Routing.
    if REROUTED_NO_EMPLOYMENT_TOKEN in line:
        return Event(
            person_id=person_id,
            kind="routing",
            question=None,
            status="rerouted_no_employment",
            raw=stripped_raw,
        )

    # Persistence: survey/feedback saved.
    if SURVEY_RESULT_SAVED_TOKEN in line:
        return Event(
            person_id=person_id,
            kind="survey_saved",
            question=None,
            status="survey_result_saved",
            raw=stripped_raw,
        )
    if FEEDBACK_RESULT_SAVED_TOKEN in line:
        return Event(
            person_id=person_id,
            kind="feedback_saved",
            question=None,
            status="feedback_result_saved",
            raw=stripped_raw,
        )

    return None


def iter_lines(source: str) -> Iterator[str]:
    """Yield lines from a file path or stdin.

    Args:
        source: Path to the log file, or "-" to read from stdin.

    Yields:
        Lines from the given source, one by one.
    """
    if source == "-":
        for line in sys.stdin:
            yield line
        return

    with open(source, "r", encoding="utf-8") as file:
        for line in file:
            yield line


def build_summary(events: Iterable[Event]) -> list[dict[str, object]]:
    """Build a per-person summary from a sequence of events.

    Args:
        events: Iterable of Event objects.

    Returns:
        A list of JSON-serialisable dictionaries, each containing:
        - person_id
        - core_questions: sorted list of core questions
        - dynamic_questions: sorted list of dynamic questions
        - sic_lookup_statuses: sorted list of SIC lookup statuses
        - classification_statuses: sorted list of classification statuses
        - rerouted_no_employment: boolean flag
        - survey_results_saved: count of survey save events
        - feedback_results_saved: count of feedback save events
    """
    summary: dict[str, PersonSummary] = {}

    for event in events:
        person_summary = summary.get(event.person_id)
        if person_summary is None:
            person_summary = PersonSummary(
                person_id=event.person_id,
                core_questions=set(),
                dynamic_questions=set(),
                sic_lookup_statuses=set(),
                classification_statuses=set(),
                rerouted_no_employment=False,
                survey_results_saved=0,
                feedback_results_saved=0,
            )
            summary[event.person_id] = person_summary

        if event.kind == "core" and event.question is not None:
            person_summary.core_questions.add(event.question)
        elif event.kind == "dynamic" and event.question is not None:
            person_summary.dynamic_questions.add(event.question)
        elif event.kind == "sic_lookup" and event.status is not None:
            person_summary.sic_lookup_statuses.add(event.status)
        elif event.kind == "classification" and event.status is not None:
            person_summary.classification_statuses.add(event.status)
        elif event.kind == "routing":
            person_summary.rerouted_no_employment = (
                person_summary.rerouted_no_employment
                or event.status == "rerouted_no_employment"
            )
        elif event.kind == "survey_saved":
            person_summary.survey_results_saved += 1
        elif event.kind == "feedback_saved":
            person_summary.feedback_results_saved += 1

    serialisable: list[dict[str, object]] = []
    for person_summary in summary.values():
        serialisable.append(
            {
                "person_id": person_summary.person_id,
                "core_questions": sorted(person_summary.core_questions),
                "dynamic_questions": sorted(person_summary.dynamic_questions),
                "sic_lookup_statuses": sorted(person_summary.sic_lookup_statuses),
                "classification_statuses": sorted(
                    person_summary.classification_statuses,
                ),
                "rerouted_no_employment": person_summary.rerouted_no_employment,
                "survey_results_saved": person_summary.survey_results_saved,
                "feedback_results_saved": person_summary.feedback_results_saved,
            },
        )

    return serialisable


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional iterable of argument strings. If None, sys.argv is used.

    Returns:
        Parsed argparse.Namespace containing CLI options.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Analyse survey logs for core, dynamic, and classification-related "
            "events. Reads from a file or stdin and outputs JSON."
        ),
    )
    parser.add_argument(
        "logfile",
        help='Path to log file, or "-" to read from stdin.',
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Output a per-person summary instead of JSONL events.",
    )

    return parser.parse_args(list(argv) if argv is not None else None)


def main() -> None:
    """Entry point for the CLI tool.

    This function orchestrates reading the log source, parsing events,
    and printing either JSONL events or a JSON summary to stdout.
    """
    args = parse_args()

    events: list[Event] = []

    for line in iter_lines(args.logfile):
        event = parse_line(line)
        if event is not None:
            events.append(event)
            if not args.summary:
                # Stream JSONL events for easy downstream processing.
                print(json.dumps(event.to_dict(), ensure_ascii=False))

    if args.summary:
        summary = build_summary(events)
        print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

