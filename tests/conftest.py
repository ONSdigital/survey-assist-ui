"""Pytest configuration and fixtures for Survey Assist UI tests.

This module provides fixtures for creating and configuring a Flask application
instance for use in unit and integration tests.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from flask import Flask

from ui import create_app

# Disable line too long warnings for this file
# pylint: disable=line-too-long


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
