"""Feedback utilities for Survey Assist UI.

This module defines utilities related to sending feedback.
"""

from __future__ import annotations

from collections.abc import MutableMapping, Sequence
from typing import Any, Literal, TypedDict, cast

from flask import session
from survey_assist_utils.logging import get_logger

logger = get_logger(__name__, level="DEBUG")


class FeedbackSession(TypedDict):
    """Feedback session structure.

    case_id - the unique id associated with (typically) the household.
    person_id - the unique id associated with a respondent in the household.
    survey_id - the unique id for the survey
    questions - list of questions used to gather respondent feedback.
    """

    case_id: str
    person_id: str
    survey_id: str
    questions: list[FeedbackQuestion]


class FeedbackQuestion(TypedDict, total=False):
    """Feedback question structure.

    response - the answer to the question.
    response_name - the id associated with the question.
    response_options - list of options provided for radio questions.
    """

    response: Any
    response_name: str
    response_options: list[str]  # only present for radio questions


def _selected_ids_selector(
    questions: list[dict[str, Any]],
    question_ids: str | Sequence[str] | None,
) -> set[str]:
    """Resolve which question_ids to include, validating explicit ids."""
    all_ids = {q.get("question_id", "") for q in questions}
    if not question_ids:
        return all_ids

    wanted = {question_ids} if isinstance(question_ids, str) else set(question_ids)

    missing = wanted - all_ids
    if missing:
        raise ValueError(f"question_id(s) not found: {sorted(missing)}")
    return wanted


def get_list_of_option_text(opts: list) -> list:
    """Extract non-empty label text values from a list of option dictionaries.

    Args:
        opts (list): List of option dictionaries, each possibly containing a 'label' dict
            with a 'text' field.

    Returns:
        list: List of non-empty label text strings found in the options.
    """
    texts: list[str] = []
    for opt in opts:
        if not isinstance(opt, dict):
            continue
        label = opt.get("label")
        if isinstance(label, dict):
            text = label.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
    return texts


def copy_feedback_from_survey_iteration(  # pylint: disable=too-many-locals
    session_data: MutableMapping[str, Any],
    question_ids: str | Sequence[str] | None = None,
    *,
    src_key: str = "survey_iteration",
    dest_key: str = "feedback_response",
    overwrite: Literal["replace", "append"] = "replace",
) -> FeedbackSession:
    """Copy selected answers from session[src_key]['questions'] to session[dest_key]['questions'].

    - Copies: response_name, response
    - If response_type == 'radio', also copies response_options as a list of label texts
      (e.g., ['Yes', 'No']). For non-radio, response_options is omitted.

    Args:
        session_data: Flask session-like mapping.
        question_ids: None for all, a single id (str), or a sequence of ids to include.
        src_key: Source session key (default 'survey_iteration').
        dest_key: Destination session key (default 'feedback_response').
        overwrite: 'replace' to replace dest questions, 'append' to append to any existing.

    Returns:
        The updated session[dest_key] dict.
    """
    src = session_data.get(src_key, {})
    questions: list[dict[str, Any]] = src.get("questions", [])
    if not isinstance(questions, list):
        raise TypeError(f"{src_key}['questions'] must be a list")

    wanted = _selected_ids_selector(questions, question_ids)

    copied: list[FeedbackQuestion] = []
    for q in questions:
        qid = q.get("question_id")
        if qid not in wanted:
            continue

        fq: FeedbackQuestion = {
            "response": q.get("response"),
            "response_name": q.get("response_name", ""),
        }

        if q.get("response_type") == "radio":
            opts = q.get("response_options") or []
            texts = get_list_of_option_text(opts)
            fq["response_options"] = texts

        copied.append(fq)

    dest = session_data.get(dest_key)
    if not isinstance(dest, dict) or not isinstance(dest.get("questions"), list):
        raise RuntimeError(
            f"{dest_key} not initialised; call init_feedback_session(...) first"
        )

    existing: list[FeedbackQuestion] = cast(
        list[FeedbackQuestion], dest.get("questions", [])
    )
    new_questions = existing + copied if (overwrite == "append") else copied

    # Update questions only; preserve other keys like case_id/person_id/survey_id
    dest["questions"] = new_questions
    session_data[dest_key] = dest
    if hasattr(session_data, "modified"):
        session_data.modified = True

    return cast(FeedbackSession, dest)


def _make_feedback_session(
    case_id: str, person_id: str, survey_id: str
) -> FeedbackSession:
    return {
        "case_id": case_id,
        "person_id": person_id,
        "survey_id": survey_id,
        "questions": [],
    }


def init_feedback_session(
    case_id: str,
    person_id: str,
    survey_id: str,
    *,
    key: str = "feedback_response",
) -> FeedbackSession:
    """Return session[key] as a FeedbackSession, creating a fresh one if absent/invalid."""
    raw: Any = session.get(key)

    logger.info(
        f"init {key} in session - case_id:{case_id} person_id:{person_id} survey_id:{survey_id}"
    )
    if (
        isinstance(raw, dict)
        and isinstance(raw.get("case_id"), str)
        and isinstance(raw.get("person_id"), str)
        and isinstance(raw.get("survey_id"), str)
    ) and isinstance(raw.get("questions"), list):
        return cast(FeedbackSession, raw)

    logger.debug("make session")
    fs = _make_feedback_session(case_id, person_id, survey_id)
    session[key] = fs
    session.modified = True
    return fs


def get_feedback_questions(feedback: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract and validate the questions list from a feedback dict.

    Args:
        feedback: A dictionary expected to contain a "questions" key.

    Returns:
        A list of question dictionaries.

    Raises:
        RuntimeError: If "questions" is missing or not a list.
    """
    questions = feedback.get("questions")
    if not isinstance(questions, list):
        raise RuntimeError("feedback['questions'] must be a list.")
    return questions


def get_current_feedback_index(
    session_data: MutableMapping[str, Any], questions: list[dict[str, Any]]
) -> int:
    """Extract and validate the current feedback index from the session.

    Args:
        session_data: The session mapping (e.g., Flask session).
        questions: The validated list of feedback questions.

    Returns:
        The current feedback index as an integer.

    Raises:
        RuntimeError: If "current_feedback_index" is not an int.
        IndexError: If the index is out of range of the questions list.
    """
    index_any = session_data.get("current_feedback_index")
    if not isinstance(index_any, int):
        raise RuntimeError("session['current_feedback_index'] must be an int.")
    if index_any < 0 or index_any >= len(questions):
        raise IndexError("current_feedback_index is out of range.")
    return index_any
