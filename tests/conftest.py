"""Pytest configuration and fixtures for Survey Assist UI tests.

This module provides fixtures for creating and configuring a Flask application
instance for use in unit and integration tests.
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest
from flask import Flask

from models.classify import (
    AppliedOptions,
    ClassificationType,
    GenericCandidate,
    GenericClassificationResponse,
    GenericClassificationResult,
    LLMModel,
    ResponseMeta,
)
from survey_assist_ui import create_app

# Disable line too long warnings for this file
# pylint: disable=line-too-long

# pylint cannot differentiate the use of fixtures in the test functions
# pylint: disable=unused-argument, disable=redefined-outer-name


# This fixture creates a Flask application instance for testing purposes.
@pytest.fixture
def app() -> Flask:
    """Creates and configures a Flask application instance for testing.

    Returns:
        Flask: A configured Flask application instance with testing enabled.
    """
    test_app = create_app()
    test_app.config.update(
        {
            "TESTING": True,
        }
    )
    return test_app


@pytest.fixture
def mock_questions() -> list[dict]:
    """Provides a mock survey question set for testing the /survey route."""
    return [
        {
            "question_id": "q1",
            "question_name": "paid_job_question",
            "title": "Paid Job",
            "question_text": "Did you have a paid job, either as an employee or self-employed, in the week 04 November to 11 November 2024?",
            "question_description": "",
            "response_type": "radio",
            "response_name": "paid-job",
            "response_options": [
                {"id": "paid-job-yes", "label": {"text": "Yes"}, "value": "yes"},
                {"id": "paid-job-no", "label": {"text": "No"}, "value": "no"},
            ],
            "justification_text": "Placeholder text",
            "placeholder_field": "",
            "button_text": "Save and continue",
            "used_for_classifications": [],
        },
        {
            "question_id": "q2",
            "question_name": "job_title_question",
            "title": "Job Title",
            "question_text": "What is your exact job title for your main job or business?",
            "question_description": "",
            "response_type": "text",
            "response_name": "job-title",
            "response_options": [],
            "justification_text": "<p>Placeholder text</p>",
            "placeholder_field": "",
            "button_text": "Save and continue",
            "used_for_classifications": ["sic", "soc"],
        },
        {
            "question_id": "q3",
            "question_name": "job_description_question",
            "title": "Job Description",
            "question_text": "Describe what you do in that job or business as a PLACEHOLDER_TEXT",
            "question_description": "<p>For example, I pack crates of goods in a warehouse for a supermarket chain</p>",
            "response_type": "text",
            "response_name": "job-description",
            "response_options": [],
            "justification_text": "<p>Placeholder text</p>",
            "button_text": "Save and continue",
            "placeholder_field": "job_title",
            "used_for_classifications": ["sic", "soc"],
        },
    ]


@pytest.fixture
def mock_survey_assist() -> dict:
    """Provides a mock survey assist data structure for testing."""
    return {
        "enabled": True,
        "question_assist_label": "<br><strong>(Asked by Survey Assist)</strong></br>",
        "consent": {
            "required": True,
            "question_id": "c1",
            "title": "Survey Assist Consent",
            "question_name": "survey_assist_consent",
            "question_text": "Can Survey Assist ask PLACEHOLDER_FOLLOWUP to better understand PLACEHOLDER_REASON?",
            "response_type": "radio",
            "response_name": "survey-assist-consent",
            "response_options": [
                {"id": "consent-yes", "label": {"text": "Yes"}, "value": "yes"},
                {"id": "consent-no", "label": {"text": "No"}, "value": "no"},
            ],
            "justification_text": "<p>Survey Assist generates intelligent follow up questions based on the answers you have given so far to help ONS to better understand your main job or the organisation you work for. ONS asks for your consent as Survey Assist uses artifical intelligence to pose questions that enable us to better understand your survey responses.</p>",
            "placeholder_reason": "your main job and workplace",
            "max_followup": 2,
        },
        "interactions": [
            {
                "after_question_id": "q4",
                "type": "lookup_classification",
                "param": "sic",
                "follow_up": {
                    "allowed": True,
                    "presentation": {"immediate": True, "after_question_id": ""},
                },
            }
        ],
    }


@pytest.fixture
def mock_survey_iteration() -> dict:
    """Provides a mock survey iteration data structure for testing."""
    return {
        "questions": [
            {
                "question_id": "q1",
                "question_text": "Did you have a paid job, either as an employee or self-employed, in the week 04 November to 11 November 2024?",
                "response": "yes",
                "response_name": "paid-job",
                "response_options": [
                    {"id": "paid-job-yes", "label": {"text": "Yes"}, "value": "yes"},
                    {"id": "paid-job-no", "label": {"text": "No"}, "value": "no"},
                ],
                "response_type": "radio",
                "used_for_classifications": [],
            },
            {
                "question_id": "q2",
                "question_text": "What is your exact job title for your main job or business?",
                "response": "teacher",
                "response_name": "job-title",
                "response_options": [],
                "response_type": "text",
                "used_for_classifications": ["sic", "soc"],
            },
            {
                "question_id": "q3",
                "question_text": "Describe what you do in that job or business as a teacher",
                "response": "teach maths",
                "response_name": "job-description",
                "response_options": [],
                "response_type": "text",
                "used_for_classifications": ["sic", "soc"],
            },
            {
                "question_id": "q4",
                "question_text": "At your main job, describe the main activity of the business or organisation",
                "response": "education",
                "response_name": "organisation-activity",
                "response_options": [],
                "response_type": "text",
                "used_for_classifications": ["sic", "soc"],
            },
            {
                "question_id": "q5",
                "question_text": "What kind of organisation was it?",
                "response": "Local government or council (including fire service and local authority controlled schools or colleges)",
                "response_name": "organisation-type",
                "response_options": [
                    {
                        "id": "limited-company",
                        "label": {"text": "A public limited company"},
                        "value": "A public limited company",
                    },
                    {
                        "id": "nationalised-industry",
                        "label": {
                            "text": "A nationalised industry or state corporation"
                        },
                        "value": "A nationalised industry or state corporation",
                    },
                    {
                        "id": "central-government",
                        "label": {"text": "Central government or civil service"},
                        "value": "Central government or civil service",
                    },
                    {
                        "id": "local-government",
                        "label": {
                            "text": "Local government or council (including fire service and local authority controlled schools or colleges)"
                        },
                        "value": "Local government or council (including fire service and local authority controlled schools or colleges)",
                    },
                    {
                        "id": "university-grant-funded",
                        "label": {
                            "text": "A university or other grant funded establishment (including opted-out schools)"
                        },
                        "value": "A university or other grant funded establishment (including opted-out schools)",
                    },
                    {
                        "id": "health-authority",
                        "label": {"text": "A health authority or NHS Trust"},
                        "value": "A health authority or NHS Trust",
                    },
                    {
                        "id": "charity-volunteer",
                        "label": {"text": "A charity, voluntary organisation or trust"},
                        "value": "A charity, voluntary organisation or trust",
                    },
                    {
                        "id": "armed-forces",
                        "label": {"text": "The armed forces"},
                        "value": "The armed forces",
                    },
                    {
                        "id": "other-organisation",
                        "label": {"text": "Some other kind of organisation"},
                        "value": "Some other kind of organisation",
                    },
                ],
                "response_type": "radio",
                "used_for_classifications": [],
            },
        ],
        "survey_assist_time_end": None,
        "survey_assist_time_start": None,
        "time_end": None,
        "time_start": datetime(2025, 7, 15, 12, 38, 22, tzinfo=timezone.utc),
        "user": "",
    }


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Provides a mock API client."""
    mock = MagicMock()
    return mock


@pytest.fixture
def followup_questions() -> list[dict]:
    """Sample follow-up questions for tests."""
    return [
        {"question_text": "First question", "id": 1},
        {"question_text": "Second question", "id": 2},
        {"question_text": "Third question", "id": 3},
    ]


@pytest.fixture
def followup_question() -> dict:
    """Sample follow-up question for tests."""
    return {
        "question_id": "f1.1",
        "question_text": "Does your farm raise livestock or crops?",
        "response": "crop production",
        "response_name": "resp-survey-assist-followup",
        "response_options": [],
        "response_type": "text",
        "used_for_classifications": [],
    }


@pytest.fixture
def valid_question() -> dict[str, Any]:
    """Fixture to provide a valid question dictionary."""
    return {
        "question_id": "q1",
        "question_text": "What is your exact job title for your main job or business?",  # pylint: disable=line-too-long
        "response": "Farm Hand",
        "response_name": "job-title",
        "response_options": [],
        "response_type": "text",
        "used_for_classifications": ["sic", "soc"],
    }


@pytest.fixture
def generic_candidate() -> GenericCandidate:
    """Generic candidate entry."""
    return GenericCandidate(
        code="62012",
        descriptive="Business and domestic software development",
        likelihood=0.87,
    )


@pytest.fixture
def generic_classify_result(
    generic_candidate: GenericCandidate,
) -> GenericClassificationResult:
    """Generic classify result."""
    return GenericClassificationResult(
        type=ClassificationType.SIC.value,  # "sic"
        classified=True,
        followup=None,
        code="62012",
        description="Business and domestic software development",
        candidates=[generic_candidate],
        reasoning="Job title and description strongly align with code 62012.",
    )


@pytest.fixture
def response_meta() -> ResponseMeta:
    """Valid response meta."""
    return ResponseMeta(
        llm=LLMModel.GEMINI.value,  # "gemini"
        applied_options=AppliedOptions(
            sic={"rephrased": True},
            soc={"rephrased": True},
        ),
    )


@pytest.fixture
def generic_classification_response(
    generic_classify_result: GenericClassificationResult,
    response_meta: ResponseMeta,
) -> GenericClassificationResponse:
    """Valid response INCLUDING meta."""
    return GenericClassificationResponse(
        requested_type=ClassificationType.SIC.value,  # "sic"
        results=[generic_classify_result],
        meta=response_meta,
    )


@pytest.fixture
def generic_classification_response_no_meta(
    generic_classify_result: GenericClassificationResult,
) -> GenericClassificationResponse:
    """Valid response WITHOUT meta (meta is optional)."""
    return GenericClassificationResponse(
        requested_type=ClassificationType.SIC.value,
        results=[generic_classify_result],
        # meta omitted on purpose
    )


@pytest.fixture
def make_generic_classification_response():
    """Factory to build a GenericClassificationResponse with easy overrides.

    Example:
        resp = make_generic_classification_response(
            requested_type="soc",
            result_overrides={"classified": False, "followup": "What does your role involve daily?"},
            meta=False,  # to omit meta
        )
    """

    def _make(
        *,
        requested_type: str = ClassificationType.SIC.value,
        candidate_overrides: dict | None = None,
        result_overrides: dict | None = None,
        meta: bool | ResponseMeta = True,
    ) -> GenericClassificationResponse:
        candidate = GenericCandidate(
            code="62012",
            descriptive="Business and domestic software development",
            likelihood=0.87,
        )
        if candidate_overrides:
            candidate = GenericCandidate(
                **{**candidate.model_dump(), **candidate_overrides}
            )

        result = GenericClassificationResult(
            type=requested_type,
            classified=True,
            followup=None,
            code=candidate.code,
            description=candidate.descriptive,
            candidates=[candidate],
            reasoning="Strong semantic similarity between inputs and target code.",
        )
        if result_overrides:
            result = GenericClassificationResult(
                **{**result.model_dump(), **result_overrides}
            )

        meta_value: ResponseMeta | None
        if meta is True:
            meta_value = ResponseMeta(
                llm=LLMModel.GEMINI.value,
                applied_options=AppliedOptions(
                    sic={"rephrased": True}, soc={"rephrased": True}
                ),
            )
        elif meta is False:
            meta_value = None
        else:
            meta_value = meta  # already a ResponseMeta

        return GenericClassificationResponse(
            requested_type=requested_type,
            results=[result],
            meta=meta_value,
        )

    return _make
