"""Tests for translate_session_to_model without patching subfunctions.

This test validates the complete mapping pipeline:
- Top-level SurveyAssistResult fields are copied correctly.
- Responses are built with preserved ordering.
- Each SurveyAssistInteraction maps 'input' fields, timestamps, flavour, and type.
- 'classify' interactions map to a ClassificationResponse with:
  - candidates -> Candidate[], ensuring 'descriptive' is used for description fallback.
  - follow_up -> FollowUp with FollowUpQuestion[], ensuring empty select_options => None.
- 'lookup' interactions map to a LookupResponse with empty collections as appropriate.

Running:
    poetry run pytest -k translate_session_to_model_e2e -q
"""

# ruff: noqa: PLR2004
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

import pytest

from models.result_sic_only import (
    Candidate,
    ClassificationResponse,
    FollowUp,
    FollowUpQuestion,
    InputField,
    LookupResponse,
    Response,
    SurveyAssistInteraction,
    SurveyAssistResult,
)
from utils.map_results_utils import translate_session_to_model


def _parse_z(ts: str) -> datetime:
    """Parse an ISO8601 string with trailing 'Z' into a UTC-aware datetime.

    Args:
        ts (str): Timestamp in ISO8601 format, e.g. '2025-09-05T08:12:06.412975Z'.

    Returns:
        datetime: A timezone-aware datetime in UTC.
    """
    # datetime.fromisoformat does not accept 'Z', so normalise to '+00:00'
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


Scenario = Literal["lookup_and_classify", "lookup_only"]


@pytest.mark.utils
@pytest.mark.parametrize(
    ("fixture_name", "scenario"),
    [
        ("survey_result_session", "lookup_and_classify"),
        ("survey_result_session_lookup_found", "lookup_only"),
    ],
    ids=["lookup_then_classify", "lookup_only"],
)
# pylint: disable=too-many-statements
def test_translate_session_to_model_e2e(  # noqa: PLR0915
    request: pytest.FixtureRequest,
    fixture_name: str,
    scenario: Scenario,
) -> None:
    """Run the same end-to-end assertions over multiple input scenarios.

    Args:
        request (pytest.FixtureRequest): Pytest request object used to resolve the fixture by name.
        fixture_name (str): The fixture name holding the session payload.
        scenario (Scenario): Scenario discriminator for focused assertions.
    """
    session_payload: dict[str, Any] = request.getfixturevalue(fixture_name)
    result = translate_session_to_model(session_payload)

    # --- Top-level assertions (common) ---
    assert isinstance(result, SurveyAssistResult)
    assert result.survey_id == "shape_tomorrow_prototype"
    assert result.case_id == "test-case-xyz"
    assert result.user == "user.respondent-a"

    # Extract expected top-level timestamps from the input for robustness
    sr = session_payload["survey_result"]
    assert result.time_start == _parse_z(sr["time_start"])
    assert result.time_end == _parse_z(sr["time_end"])

    # --- Response assertions (common) ---
    assert isinstance(result.responses, list) and len(result.responses) == 1
    r0 = result.responses[0]
    assert isinstance(r0, Response)
    assert r0.person_id == sr["responses"][0]["person_id"]
    assert r0.time_start == _parse_z(sr["responses"][0]["time_start"])
    assert r0.time_end == _parse_z(sr["responses"][0]["time_end"])

    # --- Interactions (scenario-specific) ---
    interactions = r0.survey_assist_interactions
    assert isinstance(interactions, list) and len(interactions) >= 1
    assert all(isinstance(i, SurveyAssistInteraction) for i in interactions)

    # Always validate the first (lookup) interaction
    i_lookup = interactions[0]
    assert i_lookup.type == "lookup"
    assert i_lookup.flavour == "sic"
    assert [(inp.field, inp.value) for inp in i_lookup.input] == [
        (
            sr["responses"][0]["survey_assist_interactions"][0]["input"][0]["field"],
            sr["responses"][0]["survey_assist_interactions"][0]["input"][0]["value"],
        )
    ]
    assert i_lookup.time_start == _parse_z(
        sr["responses"][0]["survey_assist_interactions"][0]["time_start"]
    )
    assert i_lookup.time_end == _parse_z(
        sr["responses"][0]["survey_assist_interactions"][0]["time_end"]
    )
    assert isinstance(i_lookup.response, LookupResponse)
    assert isinstance(i_lookup.input[0], InputField)
    # Lookup response expected to mirror payload booleans and be empty collections by default
    assert i_lookup.response.potential_codes_count == int(
        sr["responses"][0]["survey_assist_interactions"][0]["response"][
            "potential_codes_count"
        ]
    )
    assert i_lookup.response.found is bool(
        sr["responses"][0]["survey_assist_interactions"][0]["response"]["found"]
    )
    assert i_lookup.response.potential_divisions == []
    assert i_lookup.response.potential_codes == []

    if scenario == "lookup_and_classify":
        # There must be a second interaction with full classification content
        assert len(interactions) == 2
        i_classify = interactions[1]
        assert i_classify.type == "classify"
        assert i_classify.flavour == "sic"
        assert i_classify.time_start == _parse_z(
            sr["responses"][0]["survey_assist_interactions"][1]["time_start"]
        )
        assert i_classify.time_end == _parse_z(
            sr["responses"][0]["survey_assist_interactions"][1]["time_end"]
        )
        assert isinstance(i_classify.response, ClassificationResponse)
        cr = i_classify.response

        # Candidate list presence and types
        assert isinstance(cr.candidates, list) and len(cr.candidates) == 2
        assert all(isinstance(c, Candidate) for c in cr.candidates)
        # Spot-check values and coercions
        assert cr.code == "46210"
        assert isinstance(cr.classified, bool)
        assert isinstance(cr.reasoning, str)

        # Follow-up questions
        assert isinstance(cr.follow_up, FollowUp)
        qs = cr.follow_up.questions
        assert isinstance(qs, list) and len(qs) == 2
        assert all(isinstance(q, FollowUpQuestion) for q in qs)
        # Empty select_options => None per mapper
        assert qs[0].select_options is None
        # Non-empty list preserved
        assert isinstance(qs[1].select_options, list) and len(qs[1].select_options) == 3
    else:
        # lookup_only: ensure only one interaction present and found=True
        assert len(interactions) == 1
        assert i_lookup.response.found is True
