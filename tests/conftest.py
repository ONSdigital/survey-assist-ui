"""Pytest configuration and fixtures for Survey Assist UI tests.

This module provides fixtures for creating and configuring a Flask application
instance for use in unit and integration tests.
"""

from datetime import datetime, timezone
from types import ModuleType
from typing import Any, Callable, TypedDict
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
from utils.feedback_utils import _make_feedback_session

# Disable line too many / too long warnings for this file
# pylint: disable=line-too-long, disable=too-many-lines

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
            "guidance_enabled": False,
            "guidance_text": "Guidance Text",
            "justification_enabled": False,
            "justification_title": "Why we ask this question",
            "justification_text": "Placeholder text",
            "placeholder_field": "",
            "button_text": "Save and continue",
            "used_for_classifications": [],
        },
        {
            "question_id": "q2",
            "question_name": "job_title_question",
            "title": "Job Title",
            "question_text": "What is the exact job title for your main job or business?",
            "question_description": "",
            "response_type": "text",
            "response_name": "job-title",
            "response_options": [],
            "guidance_enabled": True,
            "guidance_text": "Guidance Text",
            "justification_enabled": True,
            "justification_title": "Why we ask this question",
            "justification_text": "Placeholder text",
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
                "question_text": "What is the exact job title for your main job or business?",
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
def mock_feedback() -> dict:
    """Provides a mock feedback question set for testing the /survey route."""
    return {
        "enabled": True,
        "questions": [
            {
                "question_id": "fq1",
                "question_name": "survey_ease_question",
                "title": "Survey Ease",
                "question_text": "In general, how easy or difficult did you find this survey?",
                "question_description": "",
                "response_type": "radio",
                "response_name": "survey-ease",
                "response_options": [
                    {
                        "id": "survey-ease-very-easy",
                        "label": {"text": "Very easy"},
                        "value": "very easy",
                        "attributes": {"required": True},
                    },
                    {
                        "id": "survey-ease-easy",
                        "label": {"text": "Easy"},
                        "value": "easy",
                    },
                    {
                        "id": "survey-ease-neither",
                        "label": {"text": "Neither easy or difficult"},
                        "value": "neither easy or difficult",
                    },
                    {
                        "id": "survey-ease-difficult",
                        "label": {"text": "Difficult"},
                        "value": "difficult",
                    },
                    {
                        "id": "survey-ease-very-difficult",
                        "label": {"text": "Very difficult"},
                        "value": "very difficult",
                    },
                ],
                "guidance_enabled": False,
                "guidance_text": "",
                "justification_enabled": False,
                "justification_title": "Why we ask this question",
                "justification_text": "Placeholder text",
                "placeholder_field": "",
                "button_text": "Save and continue",
                "used_for_classifications": [],
            },
            {
                "question_id": "fq2",
                "question_name": "survey_relevance_question",
                "title": "Survey Relevance",
                "question_text": "How relevant or irrelevant did you find the questions to your situation?",
                "question_description": "",
                "response_type": "radio",
                "response_name": "survey-relevance",
                "response_options": [
                    {
                        "id": "survey-relevance-very-relevant",
                        "label": {"text": "Very relevant"},
                        "value": "very relevant",
                        "attributes": {"required": True},
                    },
                    {
                        "id": "survey-relevance-relevant",
                        "label": {"text": "Relevant"},
                        "value": "relevant",
                    },
                    {
                        "id": "survey-relevance-neither",
                        "label": {"text": "Neither relevant or irrelevant"},
                        "value": "neither relevant or irrelevant",
                    },
                    {
                        "id": "survey-relevance-irrelevant",
                        "label": {"text": "Irrelevant"},
                        "value": "irrelevant",
                    },
                    {
                        "id": "survey-relevance-very-irrelevant",
                        "label": {"text": "Very irrelevant"},
                        "value": "very irrelevant",
                    },
                ],
                "guidance_enabled": False,
                "guidance_text": "",
                "justification_enabled": False,
                "justification_title": "Why we ask this question",
                "justification_text": "Placeholder text",
                "placeholder_field": "",
                "button_text": "Save and continue",
                "used_for_classifications": [],
            },
            {
                "question_id": "fq3",
                "question_name": "survey_comfort_question",
                "title": "Survey Comfort",
                "question_text": "How comfortable or uncomfortable were you in providing this information?",
                "question_description": "",
                "response_type": "radio",
                "response_name": "survey-comfort",
                "response_options": [
                    {
                        "id": "survey-comfort-very-comfortable",
                        "label": {"text": "Very comfortable"},
                        "value": "very comfortable",
                        "attributes": {"required": True},
                    },
                    {
                        "id": "survey-comfort-comfortable",
                        "label": {"text": "Comfortable"},
                        "value": "comfortable",
                    },
                    {
                        "id": "survey-comfort-neither",
                        "label": {"text": "Neither comfortable or uncomfortable"},
                        "value": "neither comfortable or uncomfortable",
                    },
                    {
                        "id": "survey-comfort-uncomfortable",
                        "label": {"text": "Uncomfortable"},
                        "value": "uncomfortable",
                    },
                    {
                        "id": "survey-comfort-very-uncomfortable",
                        "label": {"text": "Very uncomfortable"},
                        "value": "very uncomfortable",
                    },
                ],
                "guidance_enabled": False,
                "guidance_text": "",
                "justification_enabled": False,
                "justification_title": "Why we ask this question",
                "justification_text": "Placeholder text",
                "placeholder_field": "",
                "button_text": "Save and continue",
                "used_for_classifications": [],
            },
        ],
        "include_survey_resp": False,
        "survey_responses": [""],
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
        "question_text": "What is the exact job title for your main job or business?",  # pylint: disable=line-too-long
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


@pytest.fixture()
def survey_result_session() -> dict[str, Any]:
    """Provide a realistic example session payload mirroring production shape.

    Returns:
        dict[str, Any]: A session dict containing a 'survey_result' key with nested responses.
    """
    return {
        "survey_result": {
            "case_id": "test-case-xyz",
            "responses": [
                {
                    "person_id": "user.respondent-a",
                    "survey_assist_interactions": [
                        {
                            "flavour": "sic",
                            "input": [
                                {
                                    "field": "org_description",
                                    "value": "Farm providing food for shops and wholesalers",
                                }
                            ],
                            "response": {
                                "found": False,
                                "potential_codes": [],
                                "potential_codes_count": 0,
                                "potential_divisions": [],
                            },
                            "time_end": "2025-09-05T08:12:21.861831Z",
                            "time_start": "2025-09-05T08:12:18.275881Z",
                            "type": "lookup",
                        },
                        {
                            "flavour": "sic",
                            "input": [
                                {"field": "job_title", "value": "Farm Hand"},
                                {
                                    "field": "job_description",
                                    "value": "I tend crops on a farm applying fertaliser and harvesting plants",
                                },
                                {
                                    "field": "org_description",
                                    "value": "Farm providing food for shops and wholesalers",
                                },
                            ],
                            "response": [
                                {
                                    "candidates": [
                                        {
                                            "code": "46210",
                                            "descriptive": "Wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                            "likelihood": 0.6,
                                        },
                                        {
                                            "code": "46390",
                                            "descriptive": "Non-specialised wholesale of food, beverages and tobacco",
                                            "likelihood": 0.4,
                                        },
                                    ],
                                    "classified": False,
                                    "code": "46210",
                                    "description": "Wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                    "follow_up": {
                                        "questions": [
                                            {
                                                "id": "f1.1",
                                                "response": "sells grain and animal feeds",
                                                "select_options": [],
                                                "text": "Does your farm primarily sell grain, seeds, animal feeds, or other types of food products?",
                                                "type": "text",
                                            },
                                            {
                                                "id": "f1.2",
                                                "response": "wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                                "select_options": [
                                                    "Wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                                    "Non-specialised wholesale of food, beverages and tobacco",
                                                    "None of the above",
                                                ],
                                                "text": "Which of these best describes your organisation's activities?",
                                                "type": "select",
                                            },
                                        ]
                                    },
                                    "reasoning": "Follow-up needed to determine most appropriate SIC code.",
                                    "type": "sic",
                                }
                            ],
                            "time_end": "2025-09-05T08:12:26.599931Z",
                            "time_start": "2025-09-05T08:12:26.599931Z",
                            "type": "classify",
                        },
                    ],
                    "time_end": "2025-09-05T08:12:26.599931Z",
                    "time_start": "2025-09-05T08:12:06.412975Z",
                }
            ],
            "survey_id": "shape_tomorrow_prototype",
            "time_end": "2025-09-05T08:12:26.599931Z",
            "time_start": "2025-09-05T08:12:06.412975Z",
            "user": "user.respondent-a",
        }
    }


# Simulate a user answereing org description question with an answer that is in the lookup data
@pytest.fixture()
def survey_result_session_lookup_found() -> dict[str, Any]:
    """Mock survey result when SIC lookup finds a match."""
    return {
        "survey_result": {
            "case_id": "test-case-xyz",
            "responses": [
                {
                    "person_id": "user.respondent-a",
                    "survey_assist_interactions": [
                        {
                            "flavour": "sic",
                            "input": [{"field": "org_description", "value": "pubs"}],
                            "response": {
                                "found": True,
                                "potential_codes": [],
                                "potential_codes_count": 0,
                                "potential_divisions": [],
                            },
                            "time_end": "2025-09-05T09:00:46.000783Z",
                            "time_start": "2025-09-05T09:00:45.864491Z",
                            "type": "lookup",
                        }
                    ],
                    "time_end": "2025-09-05T09:00:46.000783Z",
                    "time_start": "2025-09-05T09:00:28.493081Z",
                }
            ],
            "survey_id": "shape_tomorrow_prototype",
            "time_end": "2025-09-05T09:00:46.000783Z",
            "time_start": "2025-09-05T09:00:28.493081Z",
            "user": "user.respondent-a",
        }
    }


@pytest.fixture(name="sample_questions")
def fixture_sample_questions() -> list[dict[str, Any]]:
    """Provide a minimal set of question dicts with stable IDs for tests.

    Returns:
        list[dict[str, Any]]: A list of question dictionaries,
        each with a ``question_id`` key.
    """
    return [
        {"question_id": "q1", "text": "First?"},
        {"question_id": "q2", "text": "Second?"},
        {"question_id": "q3", "text": "Third?"},
    ]


@pytest.fixture(name="questions_with_missing_id")
def fixture_questions_with_missing_id() -> list[dict[str, Any]]:
    """Provide questions including one without a ``question_id`` key.

    This exercises the default value path (empty string) in the selector.

    Returns:
        list[dict[str, Any]]: Question dictionaries where one item
        lacks the ``question_id`` key.
    """
    return [
        {"question_id": "q1", "text": "First?"},
        {"text": "No id here"},  # will contribute '' to all_ids
    ]


@pytest.fixture(name="age_range_response_options")
def fixture_age_range_response_options() -> list[dict[str, Any]]:
    """Provide the sample `response_options` list from the age-range question.

    Returns:
        list[dict[str, Any]]: A list of option dictionaries containing
        label->text entries in the same order as provided by the UI.
    """
    return [
        {
            "attributes": {"required": True},
            "id": "age-range-18-24",
            "label": {"text": "18-24"},
            "value": "18-24",
        },
        {
            "id": "age-range-25-34",
            "label": {"text": "25-34"},
            "value": "25-34",
        },
        {
            "id": "age-range-35-49",
            "label": {"text": "35-49"},
            "value": "35-49",
        },
        {
            "id": "age-range-50-64",
            "label": {"text": "50-64"},
            "value": "50-64",
        },
        {
            "id": "age-range-65",
            "label": {"text": "65 plus"},
            "value": "65-plus",
        },
    ]


class SessionDict(dict):
    """A minimal Flask-like session mapping with a `modified` flag.

    Notes:
        Flask's session sets ``modified = True`` after mutation.
        The function under test checks for the attribute via ``hasattr``.
    """

    modified: bool = False


class FeedbackQuestion(TypedDict, total=False):
    """TypedDict mirroring the FeedbackQuestion for clarity in tests."""

    response: Any
    response_name: str
    response_options: list[str]


class FeedbackSession(TypedDict):  # pylint: disable=duplicate-code
    """TypedDict mirroring the FeedbackSession for clarity in tests."""

    case_id: str
    person_id: str
    survey_id: str
    questions: list[FeedbackQuestion]


@pytest.fixture(name="survey_iteration_questions")
def fixture_survey_iteration_questions() -> list[dict[str, Any]]:
    """Example `survey_iteration["questions"]` data."""
    return [
        {
            "question_id": "q0",
            "question_text": "Select your age range from the options below",
            "response": "35-49",
            "response_name": "age-range",
            "response_options": [
                {
                    "attributes": {"required": True},
                    "id": "age-range-18-24",
                    "label": {"text": "18-24"},
                    "value": "18-24",
                },
                {"id": "age-range-25-34", "label": {"text": "25-34"}, "value": "25-34"},
                {"id": "age-range-35-49", "label": {"text": "35-49"}, "value": "35-49"},
                {"id": "age-range-50-64", "label": {"text": "50-64"}, "value": "50-64"},
                {
                    "id": "age-range-65",
                    "label": {"text": "65 plus"},
                    "value": "65-plus",
                },
            ],
            "response_type": "radio",
            "used_for_classifications": [],
        },
        {
            "question_id": "q1",
            "question_text": "Did you have a paid job...?",
            "response": "yes",
            "response_name": "paid-job",
            "response_options": [
                {
                    "attributes": {"required": True},
                    "id": "paid-job-yes",
                    "label": {"text": "Yes"},
                    "value": "yes",
                },
                {"id": "paid-job-no", "label": {"text": "No"}, "value": "no"},
            ],
            "response_type": "radio",
            "used_for_classifications": [],
        },
        {
            "question_id": "q2",
            "question_text": "What is the exact job title for your main job or business?",
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
            "question_id": "f1.2",
            "question_text": "Which of these best describes your organisation's activities?",
            "response": "none of the above",
            "response_name": "resp-survey-assist-followup",
            "response_options": [
                {
                    "attributes": {"required": True},
                    "id": "other-education-nec-id",
                    "label": {"text": "Other education nec"},
                    "value": "other education nec",
                },
                {
                    "id": "educational-support-activities-id",
                    "label": {"text": "Educational support activities"},
                    "value": "educational support activities",
                },
                {
                    "id": "primary-education-id",
                    "label": {"text": "Primary education"},
                    "value": "primary education",
                },
                {
                    "id": "cultural-education-id",
                    "label": {"text": "Cultural education"},
                    "value": "cultural education",
                },
                {
                    "id": "none-of-the-above-id",
                    "label": {"text": "None of the above"},
                    "value": "none of the above",
                },
            ],
            "response_type": "radio",
            "used_for_classifications": [],
        },
    ]


@pytest.fixture(name="empty_feedback_session")
def fixture_empty_feedback_session() -> FeedbackSession:
    """Provide an initialised, empty feedback session structure."""
    return {
        "case_id": "case-123",
        "person_id": "person-456",
        "survey_id": "survey-xyz",
        "questions": [],
    }


@pytest.fixture(name="session_ready")
def fixture_session_ready(
    survey_iteration_questions: list[dict[str, Any]],
    empty_feedback_session: FeedbackSession,
) -> SessionDict:
    """Provide a session mapping with src and dest keys initialised."""
    sess: SessionDict = SessionDict()
    sess["survey_iteration"] = {"questions": survey_iteration_questions}
    sess["feedback_response"] = empty_feedback_session.copy()
    return sess


@pytest.fixture(name="example_feedback")
def _example_feedback() -> dict[str, Any]:
    """Build a representative feedback payload containing three radio questions.

    Returns:
        dict[str, Any]: A feedback dictionary with a 'questions' list.
    """
    return {
        "enabled": True,
        "questions": [
            {
                "question_id": "fq1",
                "response_type": "radio",
                "response_name": "survey-ease",
                "response_options": [
                    {
                        "id": "survey-ease-very-easy",
                        "label": {"text": "Very easy"},
                        "value": "very easy",
                    },
                    {
                        "id": "survey-ease-easy",
                        "label": {"text": "Easy"},
                        "value": "easy",
                    },
                ],
            },
            {
                "question_id": "fq2",
                "response_type": "radio",
                "response_name": "survey-relevance",
                "response_options": [
                    {
                        "id": "survey-relevance-very-relevant",
                        "label": {"text": "Very relevant"},
                        "value": "very relevant",
                    },
                ],
            },
            {
                "question_id": "fq3",
                "response_type": "radio",
                "response_name": "survey-comfort",
                "response_options": [
                    {
                        "id": "survey-comfort-very-comfortable",
                        "label": {"text": "Very comfortable"},
                        "value": "very comfortable",
                    },
                ],
            },
        ],
        "include_survey_resp": True,
        "survey_responses": ["q0"],
    }


@pytest.fixture()
def feedback_session_factory() -> Callable:
    """Return a factory for creating new FeedbackSession dicts."""

    def _factory(
        case_id: str = "case", person_id: str = "person", survey_id: str = "survey"
    ) -> FeedbackSession:
        return _make_feedback_session(case_id, person_id, survey_id)

    return _factory


class LogCapture:
    """Lightweight logger double for tests.

    Captures messages by level and supports %-style formatting to mirror the
    stdlib logging API. Accepts *args and **kwargs so calls with 'extra' work.
    """

    # pylint: disable=too-few-public-methods
    def __init__(self) -> None:
        self.infos: list[str] = []
        self.debugs: list[str] = []
        self.warnings: list[str] = []
        self.errors: list[str] = []

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture info logs."""
        self.infos.append(_fmt(msg, *args))

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture debug logs."""
        self.debugs.append(_fmt(msg, *args))

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture warning logs."""
        self.warnings.append(_fmt(msg, *args))

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture error logs."""
        self.errors.append(_fmt(msg, *args))

    def exception(self, msg: str, *args: Any, **kwargs: Any) -> None:
        """Capture exception logs (alias to error)."""
        self.error(msg, *args, **kwargs)


def _fmt(msg: str, *args: Any) -> str:
    """Format like logging.Logger using %-style, falling back safely.

    Args:
        msg: Message template.
        *args: Positional arguments for %-style formatting.

    Returns:
        The formatted message string.
    """
    if args:
        try:
            return msg % args
        except Exception:  # pylint: disable=broad-except
            return str(msg)
    return str(msg)


@pytest.fixture
def log_capture() -> LogCapture:
    """Provide a fresh LogCapture for each test."""
    return LogCapture()


@pytest.fixture
def patch_module_logger(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[ModuleType, LogCapture], LogCapture]:
    """Return a helper that patches `module.logger` with a LogCapture.

    This is convenient when your production logger uses custom handlers/formatters
    or has `propagate=False`. The monkeypatch is automatically reverted by pytest.

    Args:
        monkeypatch: Built-in pytest fixture for safe attribute patching.

    Returns:
        A callable that takes (module, log_capture) and applies the patch.
    """

    def _apply(module: ModuleType, stub: LogCapture) -> LogCapture:
        monkeypatch.setattr(module, "logger", stub, raising=True)
        return stub

    return _apply
