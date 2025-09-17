from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal, TypedDict, cast

from flask import session
from survey_assist_utils.logging import get_logger

logger = get_logger(__name__, level="DEBUG")


class FeedbackSession(TypedDict):
    case_id: str
    person_id: str
    survey_id: str
    questions: list[FeedbackQuestion]

class FeedbackQuestion(TypedDict, total=False):
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


def copy_feedback_from_survey_iteration(
    session: dict[str, Any],
    question_ids: str | Sequence[str] | None = None,
    *,
    src_key: str = "survey_iteration",
    dest_key: str = "feedback_response",
    overwrite: Literal["replace", "append"] = "replace",
) -> dict[str, Any]:
    """Copy selected answers from session[src_key]['questions'] to session[dest_key]['questions'].

    - Copies: response_name, response
    - If response_type == 'radio', also copies response_options as a list of label texts
      (e.g., ['Yes', 'No']). For non-radio, response_options is omitted.

    Args:
        session: Flask session-like mapping.
        question_ids: None for all, a single id (str), or a sequence of ids to include.
        src_key: Source session key (default 'survey_iteration').
        dest_key: Destination session key (default 'feedback_response').
        overwrite: 'replace' to replace dest questions, 'append' to append to any existing.

    Returns:
        The updated session[dest_key] dict.
    """
    src = session.get(src_key, {})
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
            # Extract label.text safely; keep only non-empty texts
            texts: list[str] = []
            for opt in opts:
                if not isinstance(opt, dict):
                    continue
                label = opt.get("label")
                if isinstance(label, dict):
                    text = label.get("text")
                    if isinstance(text, str) and text.strip():
                        texts.append(text)
            fq["response_options"] = texts

        copied.append(fq)

    dest = session.get(dest_key)
    if not isinstance(dest, dict) or not isinstance(dest.get("questions"), list):
        raise RuntimeError(
            f"{dest_key} not initialised; call init_feedback_session(...) first"
        )

    existing: list[FeedbackQuestion] = cast(list[FeedbackQuestion], dest.get("questions", []))
    new_questions = existing + copied if (overwrite == "append") else copied

    # Update questions only; preserve other keys like case_id/person_id ---
    dest["questions"] = new_questions
    session[dest_key] = dest
    if hasattr(session, "modified"):
        session.modified = True

    return cast("FeedbackSession", dest)


def _make_feedback_session(case_id: str, person_id: str, survey_id: str) -> FeedbackSession:
    return {"case_id": case_id, "person_id": person_id, "survey_id": survey_id, "questions": []}


def init_feedback_session(
    case_id: str,
    person_id: str,
    survey_id: str,
    *,
    key: str = "feedback_response",
) -> FeedbackSession:
    """Return session[key] as a FeedbackSession, creating a fresh one if absent/invalid."""
    raw: Any = session.get(key)

    logger.info(f"init {key} in session - case_id:{case_id} person_id:{person_id} survey_id:{survey_id}")
    if isinstance(raw, dict) and isinstance(raw.get("case_id"), str) and isinstance(raw.get("person_id"), str) and isinstance(raw.get("survey_id"), str):  # noqa: SIM102
        if isinstance(raw.get("questions"), list):
            return cast(FeedbackSession, raw)

    logger.debug("make session")
    fs = _make_feedback_session(case_id, person_id, survey_id)
    session[key] = fs
    session.modified = True
    return fs
