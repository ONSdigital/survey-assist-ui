#!/usr/bin/env python3.12
"""CLI tool to analyse survey logs for core, dynamic, and classification-related events.

It reads lines from a log file (or stdin), finds patterns such as:
- "saved response for <question_name>" (core questions)
- "question: organisation_activity_question" (core question)
- "survey_assist_followup_<n>" (dynamic follow-up questions)
- "match, skip classification" / "NOT matched, classify" (SIC lookup status)
- "classified unambiguously" / "not classified, followup" (classification status)
- "rerouted no employment" (not in employment routing)
- "survey result saved: <id>" / "feedback result saved: <id>" (persistence events)

It can:
- Stream individual events as JSONL (default)
- Emit a per-person summary as JSON with --summary
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Literal

# pylint: disable=too-many-locals
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
# pylint: disable=too-many-return-statements

# Core/dynamic question patterns.
PERSON_ID_RE = re.compile(r"person_id:([A-Za-z0-9_-]+)")
PARTICIPANT_ID_RE = re.compile(r"participant_id:([A-Za-z0-9_-]+)")
ACCESS_TIME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)")

# unsuccessful access
UNSUCCESSFUL_ACCESS_TOKEN = (
    "Validation unsuccessful for participant_id"  # noqa: S105 # nosec B105
)

CORE_Q_RE = re.compile(r"saved response for\s+([A-Za-z0-9_-]+)")
DYNAMIC_Q_RE = re.compile(r"(survey_assist_followup_[0-9]+)")
ORG_ACTIVITY_Q_TOKEN = (
    "question: organisation_activity_question"  # noqa: S105 # nosec B105
)

# Status tokens derived from your grep command.
SIC_MATCH_SKIP_TOKEN = "match, skip classification"  # noqa: S105 # nosec B105
SIC_NOT_MATCHED_CLASSIFY_TOKEN = "NOT matched, classify"  # noqa: S105 # nosec B105

CLASSIFIED_UNAMBIGUOUSLY_TOKEN = "classified unambiguously"  # noqa: S105 # nosec B105
NOT_CLASSIFIED_FOLLOWUP_TOKEN = "not classified, followup"  # noqa: S105 # nosec B105
REROUTED_NO_EMPLOYMENT_TOKEN = "rerouted no employment"  # noqa: S105 # nosec B105

SURVEY_RESULT_SAVED_TOKEN = "survey result saved"  # noqa: S105 # nosec B105
FEEDBACK_RESULT_SAVED_TOKEN = "feedback result saved"  # noqa: S105 # nosec B105
# Regexes to capture document IDs after "saved: <id>".
SURVEY_RESULT_SAVED_RE = re.compile(r"survey result saved:\s*([\w-]+)")
FEEDBACK_RESULT_SAVED_RE = re.compile(r"feedback result saved:\s*([\w-]+)")

# Regex to capture follow-up question from classification logs.
FOLLOWUP_QUESTION_RE = re.compile(r"not classified, followup question:\s*(.+)")

# Regex to capture SIC code from classification logs.
SIC_CODE_RE = re.compile(r"code[:\s]+([0-9]{4,5})")


EventKind = Literal[
    "access",
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
        document_id: Identifier of a saved survey/feedback document, when
            applicable. None for events that do not represent a persisted
            document.
        classification_code: SIC classification code where applicable. None if not present.
        access_time: Timestamp of access event.
        timestamp: Timestamp string when the event occurred.
        raw: Original log line.
    """

    person_id: str
    kind: EventKind
    question: str | None
    status: str | None
    document_id: str | None
    classification_code: str | None
    access_time: str | None
    timestamp: str | None
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
            "document_id": self.document_id,
            "classification_code": self.classification_code,
            "access_time": self.access_time,
            "timestamp": self.timestamp,
            "raw": self.raw,
        }


@dataclass(slots=True)
class PersonSummary:
    """Aggregated information about a person's events.

    Attributes:
        person_id: Identifier of the person.
        core_questions: Mapping from core question identifier to its timestamp.
        dynamic_questions: Mapping from dynamic question identifier to timestamp.
        sic_lookup_statuses: Mapping from SIC lookup status label to timestamp.
        classification_statuses: Mapping from classification status label
            to timestamp.
        classification_code: The SIC classification code if available.
        rerouted_no_employment: Whether a "rerouted no employment" event
            was seen for this person.
        survey_results_saved: Count of "survey result saved" events.
        feedback_results_saved: Count of "feedback result saved" events.
        survey_result_ids: Mapping from survey result document ID to timestamp.
        feedback_result_ids: Mapping from feedback result document ID to timestamp.
        dynamic_question_texts: Mapping from follow-up question text to timestamp.
        access_time: Timestamp string of when the survey was first accessed
            for this person, or an empty string if not known.
        unsuccessful_access: Whether an unsuccessful access attempt was logged
            for this participant.
    """

    person_id: str
    core_questions: dict[str, str]
    dynamic_questions: dict[str, str]
    sic_lookup_statuses: dict[str, str]
    classification_statuses: dict[str, str]
    classification_code: str
    rerouted_no_employment: bool
    survey_results_saved: int
    feedback_results_saved: int
    survey_result_ids: dict[str, str]
    feedback_result_ids: dict[str, str]
    dynamic_question_texts: dict[str, str]
    access_time: str
    unsuccessful_access: bool


def parse_line(line: str) -> Event | None:  # noqa C901, PLR0911, PLR0912, PLR0915
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
        - `survey result saved: <id>`
        - `feedback result saved: <id>`

    Args:
        line: A single log line.

    Returns:
        An Event instance if the line contains a recognised pattern,
        otherwise None.
    """
    stripped_raw = line.rstrip("\n")
    text_for_matching = stripped_raw

    timestamp_match = ACCESS_TIME_RE.match(stripped_raw)
    event_timestamp = timestamp_match.group(1) if timestamp_match else None

    # Try to isolate JSON (after timestamp, if present) and use the "message" field.
    json_part = stripped_raw
    json_start = stripped_raw.find("{")
    if json_start != -1:
        json_part = stripped_raw[json_start:]

    try:
        payload = json.loads(json_part)
        text_for_matching = (
            str(payload["message"])
            if isinstance(payload, dict) and "message" in payload
            else json_part
        )
    except json.JSONDecodeError:
        # Not JSON, fall back to the raw line.
        text_for_matching = stripped_raw

    if "survey accessed" in text_for_matching:
        participant_match = PARTICIPANT_ID_RE.search(text_for_matching)
        if participant_match is not None:
            participant_id = participant_match.group(1)

            # Map participant_id -> person_id; assumption: STP01 -> STP01-01
            person_id_access = f"{participant_id}-01"

            timestamp_match = ACCESS_TIME_RE.match(stripped_raw)
            access_time = timestamp_match.group(1) if timestamp_match else None

            return Event(
                person_id=person_id_access,
                kind="access",
                question=None,
                status="survey_accessed",
                document_id=None,
                classification_code=None,
                access_time=access_time,
                timestamp=event_timestamp,
                raw=stripped_raw,
            )

    if UNSUCCESSFUL_ACCESS_TOKEN in text_for_matching:
        participant_match = PARTICIPANT_ID_RE.search(text_for_matching)
        if participant_match is not None:
            participant_id = participant_match.group(1)
            person_id_access = f"{participant_id}-01"

            return Event(
                person_id=person_id_access,
                kind="access",
                question=None,
                status="unsuccessful_access",
                document_id=None,
                classification_code=None,
                access_time=None,
                timestamp=event_timestamp,
                raw=stripped_raw,
            )

    person_match = PERSON_ID_RE.search(text_for_matching)
    if person_match is None:
        return None

    person_id = person_match.group(1)

    # Core question answered via "saved response for <question>".
    core_match = CORE_Q_RE.search(text_for_matching)
    if core_match is not None:
        question = core_match.group(1)
        return Event(
            person_id=person_id,
            kind="core",
            question=question,
            status=None,
            document_id=None,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )

    # Core question answered via "question: organisation_activity_question".
    if ORG_ACTIVITY_Q_TOKEN in text_for_matching:
        return Event(
            person_id=person_id,
            kind="core",
            question="organisation_activity_question",
            status=None,
            document_id=None,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )

    # Dynamic follow-up questions.
    dyn_match = DYNAMIC_Q_RE.search(text_for_matching)
    if dyn_match is not None:
        question = dyn_match.group(1)
        return Event(
            person_id=person_id,
            kind="dynamic",
            question=question,
            status=None,
            document_id=None,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )

    # SIC lookup statuses.
    if SIC_MATCH_SKIP_TOKEN in text_for_matching:
        sic_code = None
        code_match = SIC_CODE_RE.search(text_for_matching)
        if code_match:
            sic_code = code_match.group(1)

        return Event(
            person_id=person_id,
            kind="sic_lookup",
            question=None,
            status="match_skip_classification",
            document_id=None,
            classification_code=sic_code,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )
    if SIC_NOT_MATCHED_CLASSIFY_TOKEN in text_for_matching:
        return Event(
            person_id=person_id,
            kind="sic_lookup",
            question=None,
            status="not_matched_classify",
            document_id=None,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )

    # Classification statuses.
    if CLASSIFIED_UNAMBIGUOUSLY_TOKEN in text_for_matching:
        sic_code = None
        code_match = SIC_CODE_RE.search(text_for_matching)
        if code_match:
            sic_code = code_match.group(1)

        return Event(
            person_id=person_id,
            kind="classification",
            question=None,
            status="classified_unambiguously",
            document_id=None,
            classification_code=sic_code,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )

    followup_q_match = FOLLOWUP_QUESTION_RE.search(text_for_matching)
    if followup_q_match is not None:
        question_text = followup_q_match.group(1)
        return Event(
            person_id=person_id,
            kind="classification",
            question=question_text,
            status="not_classified_followup",
            document_id=None,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )

    if NOT_CLASSIFIED_FOLLOWUP_TOKEN in text_for_matching:
        return Event(
            person_id=person_id,
            kind="classification",
            question=None,
            status="not_classified_followup",
            document_id=None,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )

    # Routing.
    if REROUTED_NO_EMPLOYMENT_TOKEN in text_for_matching:
        return Event(
            person_id=person_id,
            kind="routing",
            question=None,
            status="rerouted_no_employment",
            document_id=None,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )

    # Persistence: survey result saved (with optional document ID).
    survey_match = SURVEY_RESULT_SAVED_RE.search(text_for_matching)
    if survey_match is not None:
        document_id = survey_match.group(1)
        return Event(
            person_id=person_id,
            kind="survey_saved",
            question=None,
            status="survey_result_saved",
            document_id=document_id,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )
    if SURVEY_RESULT_SAVED_TOKEN in text_for_matching:
        # Fallback in case older logs do not include an ID.
        return Event(
            person_id=person_id,
            kind="survey_saved",
            question=None,
            status="survey_result_saved",
            document_id=None,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )

    # Persistence: feedback result saved (with optional document ID).
    feedback_match = FEEDBACK_RESULT_SAVED_RE.search(text_for_matching)
    if feedback_match is not None:
        document_id = feedback_match.group(1)
        return Event(
            person_id=person_id,
            kind="feedback_saved",
            question=None,
            status="feedback_result_saved",
            document_id=document_id,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
            raw=stripped_raw,
        )
    if FEEDBACK_RESULT_SAVED_TOKEN in text_for_matching:
        # Fallback for logs without IDs.
        return Event(
            person_id=person_id,
            kind="feedback_saved",
            question=None,
            status="feedback_result_saved",
            document_id=None,
            classification_code=None,
            access_time=None,
            timestamp=event_timestamp,
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
        yield from sys.stdin
        return

    with open(source, encoding="utf-8") as file:
        yield from file


def build_summary(  # noqa: C901, PLR0912
    events: Iterable[Event],
) -> list[dict[str, object]]:
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
        - survey_result_ids: list of survey result document IDs
        - feedback_result_ids: list of feedback result document IDs
        - dynamic_question_texts: list of dynamic follow-up question texts
            shown to this person.
        - classification_code: SIC classification code if available
        - access_time: Timestamp string of when the survey was first accessed
            for this person, or an empty string if not known
        - unsuccessful_access: Whether an unsuccessful access attempt was logged
            for this participant.
    """
    summary: dict[str, PersonSummary] = {}

    for event in events:
        person_summary = summary.get(event.person_id)
        if person_summary is None:
            person_summary = PersonSummary(
                person_id=event.person_id,
                core_questions={},
                dynamic_questions={},
                sic_lookup_statuses={},
                classification_statuses={},
                rerouted_no_employment=False,
                survey_results_saved=0,
                feedback_results_saved=0,
                survey_result_ids={},
                feedback_result_ids={},
                dynamic_question_texts={},
                classification_code="",
                access_time="",
                unsuccessful_access=False,
            )
            summary[event.person_id] = person_summary

        if event.kind == "core" and event.question is not None:
            person_summary.core_questions[event.question] = event.timestamp or ""
        elif event.kind == "access":
            # Only set the access time once; keep the first seen.
            if event.status == "survey_accessed":
                # Only set the access time once; keep the first seen.
                if event.access_time is not None and person_summary.access_time == "":
                    person_summary.access_time = event.access_time
            elif event.status == "unsuccessful_access":
                person_summary.unsuccessful_access = True
        elif event.kind == "dynamic" and event.question is not None:
            person_summary.dynamic_questions[event.question] = event.timestamp or ""
        elif event.kind == "sic_lookup" and event.status is not None:
            person_summary.sic_lookup_statuses[event.status] = event.timestamp or ""
            if (
                event.status == "match_skip_classification"
                and event.classification_code is not None
            ):
                person_summary.classification_code = event.classification_code
        elif event.kind == "classification" and event.status is not None:
            person_summary.classification_statuses[event.status] = event.timestamp or ""
            if event.status == "not_classified_followup" and event.question is not None:
                person_summary.dynamic_question_texts[event.question] = (
                    event.timestamp or ""
                )
            if event.classification_code is not None:
                person_summary.classification_code = event.classification_code
        elif event.kind == "routing":
            person_summary.rerouted_no_employment = (
                person_summary.rerouted_no_employment
                or event.status == "rerouted_no_employment"
            )
        elif event.kind == "survey_saved":
            person_summary.survey_results_saved += 1
            if event.document_id is not None:
                person_summary.survey_result_ids[event.document_id] = (
                    event.timestamp or ""
                )
        elif event.kind == "feedback_saved":
            person_summary.feedback_results_saved += 1
            if event.document_id is not None:
                person_summary.feedback_result_ids[event.document_id] = (
                    event.timestamp or ""
                )
    serialisable: list[dict[str, object]] = []
    for person_summary in summary.values():
        serialisable.append(
            {
                "person_id": person_summary.person_id,
                "access_time": person_summary.access_time,
                "core_questions": [
                    {"question": q, "timestamp": t}
                    for q, t in sorted(person_summary.core_questions.items())
                ],
                "dynamic_questions": [
                    {"question": q, "timestamp": t}
                    for q, t in sorted(person_summary.dynamic_questions.items())
                ],
                "sic_lookup_statuses": [
                    {"status": s, "timestamp": t}
                    for s, t in sorted(person_summary.sic_lookup_statuses.items())
                ],
                "classification_statuses": [
                    {"status": s, "timestamp": t}
                    for s, t in sorted(person_summary.classification_statuses.items())
                ],
                "rerouted_no_employment": person_summary.rerouted_no_employment,
                "survey_results_saved": person_summary.survey_results_saved,
                "feedback_results_saved": person_summary.feedback_results_saved,
                "survey_result_ids": [
                    {"id": doc_id, "timestamp": t}
                    for doc_id, t in person_summary.survey_result_ids.items()
                ],
                "feedback_result_ids": [
                    {"id": doc_id, "timestamp": t}
                    for doc_id, t in person_summary.feedback_result_ids.items()
                ],
                "dynamic_question_texts": [
                    {"question": q, "timestamp": t}
                    for q, t in person_summary.dynamic_question_texts.items()
                ],
                "classification_code": person_summary.classification_code,
                "unsuccessful_access": person_summary.unsuccessful_access,
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
