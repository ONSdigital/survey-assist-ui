"""Unit tests for feedback_util functionality."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable, cast

import pytest

# Module import for monkeypatching globals
import utils.feedback_utils as feedback_mod
from tests.conftest import SessionDict
from utils.feedback_utils import (  # pylint: disable=wrong-import-position
    FeedbackSession,
    _make_feedback_session,
    _selected_ids_selector,
    copy_feedback_from_survey_iteration,
    get_current_feedback_index,
    get_feedback_questions,
    get_list_of_option_text,
)
from utils.session_utils import FIRST_QUESTION


@pytest.mark.utils
def test_returns_all_ids_when_question_ids_is_none(
    sample_questions: list[dict[str, Any]],
) -> None:
    """It should return all IDs when ``question_ids`` is ``None``."""
    result = _selected_ids_selector(sample_questions, None)
    assert result == {"q1", "q2", "q3"}


@pytest.mark.parametrize("empty_value", [[], (), set()])  # type: ignore[list-item, arg-type]
@pytest.mark.utils
def test_returns_all_ids_when_question_ids_is_empty_sequence(
    sample_questions: list[dict[str, Any]],
    empty_value: Sequence[str],
) -> None:
    """It should return all IDs when ``question_ids`` is an empty sequence."""
    result = _selected_ids_selector(sample_questions, empty_value)
    assert result == {"q1", "q2", "q3"}


@pytest.mark.utils
def test_accepts_single_string_returns_singleton_set(
    sample_questions: list[dict[str, Any]],
) -> None:
    """It should accept a single string and return a singleton set."""
    result = _selected_ids_selector(sample_questions, "q2")
    assert result == {"q2"}


@pytest.mark.utils
def test_accepts_sequence_of_strings_and_deduplicates(
    sample_questions: list[dict[str, Any]],
) -> None:
    """It should accept a sequence and naturally deduplicate into a set."""
    result = _selected_ids_selector(sample_questions, ["q1", "q1", "q3"])
    assert result == {"q1", "q3"}


@pytest.mark.utils
def test_raises_value_error_for_missing_single_id(
    sample_questions: list[dict[str, Any]],
) -> None:
    """It should raise ``ValueError`` when any requested ID is absent."""
    with pytest.raises(ValueError) as err:
        _selected_ids_selector(sample_questions, "q9")

    # Exact message shape matters to callers that log/propagate errors.
    assert "question_id(s) not found: ['q9']" in str(err.value)


@pytest.mark.utils
def test_raises_value_error_lists_missing_ids_sorted(
    sample_questions: list[dict[str, Any]],
) -> None:
    """It should report missing IDs as a sorted list in the error message."""
    with pytest.raises(ValueError) as err:
        _selected_ids_selector(sample_questions, ["q9", "q0", "q8"])

    # Expect alphabetical sort in the rendered list
    assert "question_id(s) not found: ['q0', 'q8', 'q9']" in str(err.value)


@pytest.mark.utils
def test_includes_empty_string_when_question_lacks_id(
    questions_with_missing_id: list[dict[str, Any]],
) -> None:
    """It should include the empty string ID when a question lacks ``question_id``."""
    result = _selected_ids_selector(questions_with_missing_id, None)
    assert result == {"q1", ""}


@pytest.mark.utils
def test_extracts_texts_in_order(
    age_range_response_options: list[dict[str, Any]],
) -> None:
    """It should extract the label texts in the original order."""
    result = get_list_of_option_text(age_range_response_options)
    assert result == ["18-24", "25-34", "35-49", "50-64", "65 plus"]


@pytest.mark.utils
def test_empty_input_returns_empty_list() -> None:
    """It should return an empty list when options are empty."""
    assert not get_list_of_option_text([])


@pytest.mark.utils
def test_skips_non_dict_entries() -> None:
    """It should skip entries that are not dictionaries."""
    opts: list[Any] = [
        {"label": {"text": "Alpha"}},
        None,
        "string",
        123,
        4.5,
        {"label": {"text": "Beta"}},
    ]
    result = get_list_of_option_text(opts)
    assert result == ["Alpha", "Beta"]


@pytest.mark.utils
def test_skips_when_label_missing_or_not_a_dict() -> None:
    """It should skip options with no `label` or with a non-dict `label`."""
    opts: list[Any] = [
        {"id": "no-label"},
        {"label": "not-a-dict"},
        {"label": {"not_text": "ignored"}},
        {"label": {"text": "Included"}},
    ]
    result = get_list_of_option_text(opts)
    assert result == ["Included"]


@pytest.mark.utils
def test_skips_empty_or_whitespace_only_texts() -> None:
    """It should ignore empty or whitespace-only `label.text` values."""
    opts: list[Any] = [
        {"label": {"text": ""}},
        {"label": {"text": "   "}},
        {"label": {"text": "\n\t "}},
        {"label": {"text": "Valid"}},
    ]
    result = get_list_of_option_text(opts)
    assert result == ["Valid"]


@pytest.mark.utils
def test_preserves_original_spacing_of_non_empty_texts() -> None:
    """It should preserve surrounding whitespace of non-empty texts when appended.

    Notes:
        The implementation checks `text.strip()` for truthiness but appends `text`
        as-is. This test locks in that behaviour (useful for regression detection).
    """
    opts: list[Any] = [
        {"label": {"text": "  Yes  "}},
        {"label": {"text": "No"}},
    ]
    result = get_list_of_option_text(opts)
    assert result == ["  Yes  ", "No"]


@pytest.mark.utils
def test_allows_duplicate_texts_and_preserves_both() -> None:
    """It should allow duplicates and preserve each occurrence in order."""
    opts: list[Any] = [
        {"label": {"text": "Yes"}},
        {"label": {"text": "Yes"}},
        {"label": {"text": "No"}},
        {"label": {"text": "Yes"}},
    ]
    result = get_list_of_option_text(opts)
    assert result == ["Yes", "Yes", "No", "Yes"]


@pytest.mark.utils
def test_ignores_non_string_text_types() -> None:
    """It should ignore `label.text` values that are not strings."""
    opts: list[Any] = [
        {"label": {"text": 1}},
        {"label": {"text": {"nested": "value"}}},
        {"label": {"text": ["a", "b"]}},
        {"label": {"text": "Valid"}},
    ]
    result = get_list_of_option_text(opts)
    assert result == ["Valid"]


@pytest.mark.utils
def test_copies_all_questions_replace_mode(session_ready: dict[str, Any]) -> None:
    """It should copy all questions (default overwrite=replace)
    and include radio options as texts.
    """
    dest = copy_feedback_from_survey_iteration(session_ready)
    questions = dest["questions"]

    # Basic shape and count
    assert isinstance(questions, list)
    assert len(questions) == len(session_ready["survey_iteration"]["questions"])

    # Radio question: q0 should include response_options as text list
    q0 = questions[0]
    assert q0["response_name"] == "age-range"
    assert q0["response"] == "35-49"
    assert q0["response_options"] == ["18-24", "25-34", "35-49", "50-64", "65 plus"]

    # Non-radio question: q2 should NOT include response_options
    q2 = questions[2]
    assert q2["response_name"] == "job-title"
    assert q2["response"] == "teacher"
    assert "response_options" not in q2


@pytest.mark.utils
def test_select_subset_of_question_ids(session_ready: dict[str, Any]) -> None:
    """It should copy only the requested question ids when provided."""
    dest = copy_feedback_from_survey_iteration(session_ready, question_ids=["q1", "q3"])
    texts = [q["response_name"] for q in dest["questions"]]
    assert texts == [
        "paid-job",
        "job-description",
    ]  # preserve order of source traversal


@pytest.mark.utils
def test_single_string_question_id(session_ready: dict[str, Any]) -> None:
    """It should accept a single string id and copy only that question."""
    dest = copy_feedback_from_survey_iteration(session_ready, question_ids="q2")
    assert len(dest["questions"]) == 1
    assert dest["questions"][0]["response_name"] == "job-title"


@pytest.mark.utils
def test_append_mode_preserves_existing_and_appends_new(
    session_ready: dict[str, Any],
) -> None:
    """It should append to existing feedback questions when overwrite='append'."""
    # Seed some existing feedback content
    session_ready["feedback_response"]["questions"] = [
        {"response_name": "seed", "response": "value"}
    ]

    dest = copy_feedback_from_survey_iteration(
        session_ready, question_ids=["q1"], overwrite="append"
    )
    names = [q["response_name"] for q in dest["questions"]]
    assert names == ["seed", "paid-job"]


@pytest.mark.utils
def test_replace_mode_replaces_existing_questions(
    session_ready: dict[str, Any],
) -> None:
    """It should replace existing questions when overwrite!='append' (default)."""
    session_ready["feedback_response"]["questions"] = [
        {"response_name": "stale", "response": "x"}
    ]
    dest = copy_feedback_from_survey_iteration(
        session_ready, question_ids=["q1"], overwrite="replace"
    )
    names = [q["response_name"] for q in dest["questions"]]
    assert names == ["paid-job"]


@pytest.mark.utils
def test_preserves_feedback_session_metadata(session_ready: dict[str, Any]) -> None:
    """It should update only the `questions` key and preserve other feedback session fields."""
    before = session_ready["feedback_response"].copy()
    dest = copy_feedback_from_survey_iteration(session_ready, question_ids="q2")

    assert dest["case_id"] == before["case_id"]
    assert dest["person_id"] == before["person_id"]
    assert dest["survey_id"] == before["survey_id"]
    assert isinstance(dest["questions"], list) and len(dest["questions"]) == 1


@pytest.mark.utils
def test_sets_session_modified_flag_when_present(session_ready: Any) -> None:
    """It should set `session.modified = True` if the mapping exposes the attribute."""
    assert hasattr(session_ready, "modified")
    assert not session_ready.modified
    _ = copy_feedback_from_survey_iteration(session_ready, question_ids="q2")
    assert session_ready.modified is True


@pytest.mark.utils
def test_raises_type_error_when_src_questions_not_list(
    session_ready: dict[str, Any],
) -> None:
    """It should raise `TypeError` if `survey_iteration['questions']` is not a list."""
    session_ready["survey_iteration"]["questions"] = "not-a-list"  # type: ignore[assignment]
    with pytest.raises(TypeError) as err:
        _ = copy_feedback_from_survey_iteration(session_ready)
    assert "survey_iteration['questions'] must be a list" in str(err.value)


@pytest.mark.utils
def test_raises_runtime_error_when_dest_not_initialised() -> None:
    """It should raise `RuntimeError` if `feedback_response` is missing or malformed."""
    session_data: dict[str, Any] = {
        "survey_iteration": {"questions": []},
        # "feedback_response" intentionally absent
    }
    with pytest.raises(RuntimeError) as err:
        _ = copy_feedback_from_survey_iteration(session_data)
    assert "feedback_response not initialised; call init_feedback_session" in str(
        err.value
    )


@pytest.mark.utils
def test_raises_value_error_for_unknown_question_id(
    session_ready: dict[str, Any],
) -> None:
    """It should bubble up `ValueError` for missing question ids via the selector."""
    with pytest.raises(ValueError) as err:
        _ = copy_feedback_from_survey_iteration(session_ready, question_ids=["q999"])
    assert "question_id(s) not found" in str(err.value)


@pytest.mark.utils
def test_radio_options_are_extracted_as_texts(session_ready: dict[str, Any]) -> None:
    """It should extract option label texts for radio questions consistently."""
    dest = copy_feedback_from_survey_iteration(session_ready, question_ids="f1.2")
    q = dest["questions"][0]
    assert q["response_name"] == "resp-survey-assist-followup"
    assert q["response_options"] == [
        "Other education nec",
        "Educational support activities",
        "Primary education",
        "Cultural education",
        "None of the above",
    ]


@pytest.mark.utils
def test_empty_or_missing_response_options_on_radio_results_in_empty_list(
    session_ready: dict[str, Any],
) -> None:
    """It should handle radio questions with empty/missing options by returning an empty list."""
    # Mutate a radio question to remove options
    for q in session_ready["survey_iteration"]["questions"]:
        if q.get("question_id") == "q1":
            q["response_options"] = []
            break

    dest = copy_feedback_from_survey_iteration(session_ready, question_ids="q1")
    q = dest["questions"][0]
    assert q["response_name"] == "paid-job"
    # `get_list_of_option_text([])` returns []
    assert "response_options" in q and q["response_options"] == []


@pytest.mark.utils
def test_returns_expected_structure() -> None:
    """It should return a FeedbackSession with the expected keys and values."""
    case_id = "case-123"
    person_id = "person-456"
    survey_id = "survey-xyz"

    session = _make_feedback_session(case_id, person_id, survey_id)

    # Basic shape
    assert isinstance(session, dict)
    assert set(session.keys()) == {"case_id", "person_id", "survey_id", "questions"}

    # Values
    assert session["case_id"] == case_id
    assert session["person_id"] == person_id
    assert session["survey_id"] == survey_id

    # Questions initialisation
    assert isinstance(session["questions"], list)
    assert not session["questions"]


@pytest.mark.utils
def test_returns_fresh_list_each_call_no_shared_state() -> None:
    """It should create a new questions list each call (no shared mutable state)."""
    s1 = _make_feedback_session("a", "b", "c")
    s2 = _make_feedback_session("a", "b", "c")

    # Change s1 and ensure s2 is unaffected
    s1["questions"].append({"response_name": "x", "response": "y"})  # type: ignore[index]
    assert s1["questions"] != s2["questions"]
    assert not s2["questions"]


@pytest.mark.parametrize(
    ("case_id", "person_id", "survey_id"),
    [
        ("", "", ""),  # empty strings are accepted and stored verbatim
        ("CASE", "PERSON", "SURVEY"),
        ("123", "456", "789"),
    ],
)
@pytest.mark.utils
def test_stores_values_verbatim(
    case_id: str,
    person_id: str,
    survey_id: str,
) -> None:
    """It should store provided identifiers verbatim, including empty strings."""
    session = _make_feedback_session(case_id, person_id, survey_id)
    assert session["case_id"] == case_id
    assert session["person_id"] == person_id
    assert session["survey_id"] == survey_id


@pytest.mark.utils
def test_type_narrowing_matches_feedbacksession() -> None:
    """It should be assignable to FeedbackSession for static type checks."""
    session: FeedbackSession = _make_feedback_session("c", "p", "s")
    # Minimal runtime assertion to keep pylint/mypy happy and document intent.
    assert isinstance(session["questions"], list)


# Mark all tests in this module with @pytest.mark.utils
pytestmark = pytest.mark.utils


class SpyFactory:  # pylint: disable=too-few-public-methods
    """Callable spy to emulate `_make_feedback_session` and capture inputs."""

    def __init__(self, to_return: FeedbackSession) -> None:
        """Initialise the spy with a fixed return value."""
        self.to_return = to_return
        self.calls: list[tuple[str, str, str]] = []

    def __call__(self, case_id: str, person_id: str, survey_id: str) -> FeedbackSession:
        """Record call args and return the predefined session."""
        self.calls.append((case_id, person_id, survey_id))
        return self.to_return


class LogCapture:
    """Simple logger stub that records `.info` and `.debug` messages."""

    def __init__(self) -> None:
        self.infos: list[str] = []
        self.debugs: list[str] = []

    def info(self, msg: str) -> None:
        """Capture info logs."""
        self.infos.append(msg)

    def debug(self, msg: str) -> None:
        """Capture debug logs."""
        self.debugs.append(msg)


def test_returns_existing_valid_session_without_modifying_or_factory_call(
    monkeypatch: pytest.MonkeyPatch,
    empty_feedback_session: FeedbackSession,
    feedback_session_factory,
) -> None:
    """It should return existing `session[key]` when valid,
    without calling the factory or modifying the session.
    """
    fake_sess = SessionDict()
    existing = empty_feedback_session.copy()
    fake_sess["feedback_response"] = existing

    spy = SpyFactory(feedback_session_factory("X", "Y", "Z"))

    monkeypatch.setattr(feedback_mod, "session", fake_sess, raising=True)
    monkeypatch.setattr(
        feedback_mod,
        "_make_feedback_session",
        cast(Callable[..., FeedbackSession], spy),
        raising=True,
    )
    monkeypatch.setattr(feedback_mod, "logger", LogCapture(), raising=True)

    result = feedback_mod.init_feedback_session(
        case_id="case-123", person_id="person-456", survey_id="survey-xyz"
    )

    assert result is existing  # identity preserved
    assert fake_sess.modified is False
    assert not spy.calls  # factory not called


def test_creates_when_missing_key_sets_modified_and_stores_in_session(
    monkeypatch: pytest.MonkeyPatch, feedback_session_factory
) -> None:
    """It should create a fresh feedback session when key
    is missing, store it, and set `session.modified = True`.
    """
    fake_sess = SessionDict()
    created = feedback_session_factory("C-1", "P-1", "S-1")
    spy = SpyFactory(created)
    logs = LogCapture()

    monkeypatch.setattr(feedback_mod, "session", fake_sess, raising=True)
    monkeypatch.setattr(
        feedback_mod,
        "_make_feedback_session",
        cast(Callable[..., FeedbackSession], spy),
        raising=True,
    )
    monkeypatch.setattr(feedback_mod, "logger", logs, raising=True)

    result = feedback_mod.init_feedback_session(
        case_id="C-1", person_id="P-1", survey_id="S-1"
    )

    assert result == created
    assert fake_sess["feedback_response"] == created
    assert fake_sess.modified is True
    assert spy.calls == [("C-1", "P-1", "S-1")]
    # Logging expectations
    assert any("init feedback_response in session" in msg for msg in logs.infos)
    assert any("make session" in msg for msg in logs.debugs)


def test_creates_when_existing_is_invalid_shape(
    monkeypatch: pytest.MonkeyPatch, feedback_session_factory
) -> None:
    """It should create a new session when existing value is malformed."""
    fake_sess = SessionDict()
    # Malformed: questions is not a list (violates the acceptance predicate)
    fake_sess["feedback_response"] = {
        "case_id": "c",
        "person_id": "p",
        "survey_id": "s",
        "questions": "not-a-list",  # type: ignore[dict-item]
    }
    created = feedback_session_factory("c", "p", "s")
    spy = SpyFactory(created)
    logs = LogCapture()

    monkeypatch.setattr(feedback_mod, "session", fake_sess, raising=True)
    monkeypatch.setattr(
        feedback_mod,
        "_make_feedback_session",
        cast(Callable[..., FeedbackSession], spy),
        raising=True,
    )
    monkeypatch.setattr(feedback_mod, "logger", logs, raising=True)

    result = feedback_mod.init_feedback_session(
        case_id="c", person_id="p", survey_id="s"
    )

    assert result == created
    assert fake_sess["feedback_response"] == created
    assert fake_sess.modified is True
    assert spy.calls == [("c", "p", "s")]
    assert any("make session" in msg for msg in logs.debugs)


def test_custom_key_supported(
    monkeypatch: pytest.MonkeyPatch, feedback_session_factory
) -> None:
    """It should allow a custom `key` parameter for the destination session entry."""
    fake_sess = SessionDict()
    created = feedback_session_factory("C", "P", "S")
    spy = SpyFactory(created)

    monkeypatch.setattr(feedback_mod, "session", fake_sess, raising=True)
    monkeypatch.setattr(
        feedback_mod,
        "_make_feedback_session",
        cast(Callable[..., FeedbackSession], spy),
        raising=True,
    )
    monkeypatch.setattr(feedback_mod, "logger", LogCapture(), raising=True)

    result = feedback_mod.init_feedback_session(
        case_id="C", person_id="P", survey_id="S", key="alt_feedback"
    )

    assert result == created
    assert fake_sess["alt_feedback"] == created
    assert fake_sess.modified is True
    assert spy.calls == [("C", "P", "S")]


def test_existing_valid_session_with_extra_keys_is_accepted_as_is(
    monkeypatch: pytest.MonkeyPatch,
    empty_feedback_session: FeedbackSession,
    feedback_session_factory,
) -> None:
    """It should accept an existing valid mapping with extra keys, and avoid factory call."""
    fake_sess = SessionDict()
    existing: FeedbackSession = empty_feedback_session.copy()
    # Add an extra field; the predicate only checks known keys.
    cast(dict[str, Any], existing)["extra"] = {"ignored": True}
    fake_sess["feedback_response"] = existing

    spy = SpyFactory(feedback_session_factory("X", "Y", "Z"))

    monkeypatch.setattr(feedback_mod, "session", fake_sess, raising=True)
    monkeypatch.setattr(
        feedback_mod,
        "_make_feedback_session",
        cast(Callable[..., FeedbackSession], spy),
        raising=True,
    )
    monkeypatch.setattr(feedback_mod, "logger", LogCapture(), raising=True)

    result = feedback_mod.init_feedback_session(
        case_id="case-123", person_id="person-456", survey_id="survey-xyz"
    )

    assert result is existing
    assert fake_sess.modified is False
    assert not spy.calls


def test_returns_questions_list_from_valid_feedback(
    example_feedback: dict[str, Any],
) -> None:
    """It should return the 'questions' list when present and of type list."""
    result = get_feedback_questions(example_feedback)
    assert isinstance(result, list)
    assert len(result) == 3  # noqa: PLR2004
    # Spot-check a couple of fields to ensure we got the same objects back
    assert result[0]["question_id"] == "fq1"
    assert result[1]["response_name"] == "survey-relevance"


def test_returns_same_list_object_not_a_copy(example_feedback: dict[str, Any]) -> None:
    """It should return the same list object (no defensive copy)."""
    questions = example_feedback["questions"]
    result = get_feedback_questions(example_feedback)
    # Identity check ensures callers can intentionally mutate the same list if desired
    assert result is questions


def test_handles_empty_questions_list() -> None:
    """It should return an empty list when 'questions' is an empty list."""
    feedback: dict[str, Any] = {"enabled": True, "questions": []}
    result = get_feedback_questions(feedback)
    assert result == []


def test_does_not_validate_question_element_types() -> None:
    """It should pass through the list even when it contains non-dict items.

    Notes:
        The function validates only that 'questions' is a list; it does not inspect
        or validate the elements. This test locks in that behaviour.
    """
    mixed_list: list[Any] = [
        {"question_id": "fq1"},
        "not-a-dict",
        123,
        None,
        {"question_id": "fq2"},
    ]
    feedback: dict[str, Any] = {"questions": mixed_list}
    result = get_feedback_questions(feedback)
    assert result is mixed_list
    assert result[0] == {"question_id": "fq1"}
    assert result[1] == "not-a-dict"


@pytest.mark.parametrize(
    "bad_questions",
    [
        None,
        "not-a-list",
        42,
        3.14,
        {"nested": "dict"},
        set(),  # type: ignore[arg-type]
    ],
)
def test_raises_runtime_error_when_questions_missing_or_not_list(
    bad_questions: Any,
) -> None:
    """It should raise RuntimeError if 'questions' is missing or not a list.

    Args:
        bad_questions: A value to use for feedback['questions'] that is not a list.
    """
    # Case 1: key present but wrong type
    feedback_with_wrong_type: dict[str, Any] = {"questions": bad_questions}
    if not isinstance(bad_questions, list):
        with pytest.raises(
            RuntimeError, match=r"feedback\['questions'\] must be a list\."
        ):
            _ = get_feedback_questions(feedback_with_wrong_type)

    # Case 2: key completely missing
    feedback_missing: dict[str, Any] = {}
    with pytest.raises(RuntimeError, match=r"feedback\['questions'\] must be a list\."):
        _ = get_feedback_questions(feedback_missing)


def _questions(n: int) -> list[dict[str, Any]]:
    """Helper to generate a list of dummy questions with IDs q0..qn-1."""
    return [{"question_id": f"q{i}"} for i in range(n)]


def test_returns_valid_index_when_present_and_in_range() -> None:
    """It should return the integer index when present and within range."""
    session = {"current_feedback_index": 1}
    questions = _questions(3)
    result = get_current_feedback_index(session, questions)
    assert result == 1


def test_returns_zero_for_first_question() -> None:
    """It should return 0 when the index is the first element."""
    session = {"current_feedback_index": 0}
    questions = _questions(2)
    result = get_current_feedback_index(session, questions)
    assert result == FIRST_QUESTION


@pytest.mark.parametrize("bad_value", [None, "1", 1.5, [], {}, True])
def test_raises_runtime_error_when_index_not_int(bad_value: Any) -> None:
    """It should raise RuntimeError when `current_feedback_index` is missing or not an int."""
    session = {"current_feedback_index": bad_value}
    with pytest.raises(
        RuntimeError, match=r"session\['current_feedback_index'\] must be an int\."
    ):
        _ = get_current_feedback_index(session, _questions(2))


@pytest.mark.parametrize("bad_index", [-1, 2, 99])
def test_raises_index_error_when_index_out_of_range(bad_index: int) -> None:
    """It should raise IndexError when the int index is negative or >= len(questions)."""
    session = {"current_feedback_index": bad_index}
    with pytest.raises(IndexError, match="current_feedback_index is out of range."):
        _ = get_current_feedback_index(session, _questions(2))


def test_raises_index_error_when_questions_empty() -> None:
    """It should raise IndexError when questions list is empty, regardless of index value."""
    session = {"current_feedback_index": 0}
    with pytest.raises(IndexError):
        _ = get_current_feedback_index(session, [])
