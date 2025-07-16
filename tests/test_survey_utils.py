"""Unit tests for survey utility functions in Survey Assist UI.

This module contains tests for survey session management, question routing, and session
update logic.
"""

from datetime import datetime
from http import HTTPStatus
from unittest.mock import patch

import pytest
from flask import Request, session, url_for

from utils.survey_utils import (
    consent_redirect,
    followup_redirect,
    get_question_routing,
    init_survey_iteration,
    update_session_and_redirect,
)


@pytest.mark.utils
def test_init_survey_iteration_structure():
    """Tests that `init_survey_iteration` returns the expected default structure."""
    result = init_survey_iteration()

    # Assert the result is a dictionary
    assert isinstance(result, dict)

    # Assert it contains all expected keys with correct initial values
    # pylint: disable=R0801
    expected_keys = {
        "user": "",
        "questions": [],
        "time_start": None,
        "time_end": None,
        "survey_assist_time_start": None,
        "survey_assist_time_end": None,
    }

    assert result == expected_keys


@pytest.mark.utils
def test_update_session_and_redirect_to_next_question(
    app, mock_questions, mock_survey_assist
):
    """Tests session updates and redirection for a standard survey flow."""
    # Simulate a POST request with form data

    with app.test_request_context(
        method="POST", data={"job-title": "Warehouse Manager"}
    ):
        session["current_question_index"] = 0
        session["response"] = {}
        session["interactions"] = []
        session.modified = True

        response = update_session_and_redirect(
            req=Request.from_values(data={"job-title": "Warehouse Manager"}),
            questions=mock_questions,
            survey_assist=mock_survey_assist,
            value="job-title",
            route="survey.survey",  # Ensure this endpoint exists in test app
        )

        # Verify redirect
        assert response.status_code == HTTPStatus.FOUND
        assert response.location.endswith("/survey")

        # Validate session changes
        assert session["response"]["job_title"] == "Warehouse Manager"
        assert session["current_question_index"] == 1
        assert len(session["survey_iteration"]["questions"]) == 1


@pytest.mark.utils
def test_update_session_and_redirect_to_survey_assist_consent(app):
    """Tests redirection to the survey_assist_consent page when interaction conditions match."""
    test_question = {
        "question_id": "job_role_q",
        "question_name": "job_role",
        "question_text": "What is your job role?",
        "response_type": "text",
        "response_options": [],
        "response_name": "job-role",
        "used_for_classifications": True,
        "placeholder_field": "job_title",
    }

    survey_assist = {"enabled": True}
    interactions = [{"after_question_id": "job_role_q"}]

    with app.test_request_context(method="POST", data={"job-role": "Engineer"}):
        # Prepare the session for the correct branching
        session["current_question_index"] = 0
        session["response"] = {"job_title": "Engineer"}
        session["interactions"] = interactions

        # Disable duplicate code check as the test needs to match the intent
        # pylint: disable=R0801
        session["survey_iteration"] = {
            "user": "",
            "questions": [],
            "time_start": None,
            "time_end": None,
            "survey_assist_time_start": None,
            "survey_assist_time_end": None,
        }
        session.modified = True

        response = update_session_and_redirect(
            req=Request.from_values(data={"job-role": "Engineer"}),
            questions=[test_question],
            survey_assist=survey_assist,
            value="job-role",
            route="survey.survey",
        )

        assert response.status_code == HTTPStatus.FOUND
        assert response.location.endswith(url_for("survey.survey_assist_consent"))


@pytest.mark.utils
@pytest.mark.parametrize(
    "question_name,expected_response_name,expected_route",
    [
        ("job_title", "job-title", "survey.survey"),  # Not final question
        ("org_description", "org-description", "survey.summary"),  # Final question
    ],
)
def test_get_question_routing_valid(
    question_name, expected_response_name, expected_route
):
    """Tests correct response name and routing based on position of the question."""
    questions = [
        {
            "question_id": "q1",
            "question_name": "job_title",
            "response_name": "job-title",
        },
        {
            "question_id": "q2",
            "question_name": "org_description",
            "response_name": "org-description",
        },
    ]

    response_name, route = get_question_routing(question_name, questions)
    assert response_name == expected_response_name
    assert route == expected_route


@pytest.mark.utils
def test_get_question_routing_invalid_question_name():
    """Tests ValueError is raised for unknown question name."""
    questions = [
        {
            "question_id": "q1",
            "question_name": "job_title",
            "response_name": "job-title",
        }
    ]

    with pytest.raises(
        ValueError, match="Question name 'invalid_q' not found in questions."
    ):
        get_question_routing("invalid_q", questions)


@pytest.mark.utils
@patch("utils.survey_utils.url_for", return_value="/survey-assist")
def test_consent_redirect_yes(_mock_url_for, app):
    """Test redirection to survey_assist when consent is given."""
    with app.test_request_context(method="POST", data={"survey-assist-consent": "yes"}):
        session["survey_iteration"] = {"questions": []}

        mock_app = app
        mock_app.survey_assist = {
            "consent": {
                "question_id": "consent-1",
                "question_text": "Do you want to use Survey Assist?",
            }
        }

        with patch("utils.survey_utils.current_app", mock_app):
            response = consent_redirect()

        assert response.status_code == HTTPStatus.FOUND
        assert response.location == "/survey-assist"
        assert len(session["survey_iteration"]["questions"]) == 1
        assert session["survey_iteration"]["questions"][0]["response"] == "yes"


@pytest.mark.utils
@patch("utils.survey_utils.url_for", return_value="/survey")
def test_consent_redirect_no(_mock_url_for, app):
    """Test redirection to /survey when consent is declined."""
    with app.test_request_context(method="POST", data={"survey-assist-consent": "no"}):
        session["survey_iteration"] = {"questions": []}
        session["current_question_index"] = 0

        mock_app = app
        mock_app.survey_assist = {
            "consent": {
                "question_id": "consent-2",
                "question_text": "Use AI to assist?",
            }
        }

        with patch("utils.survey_utils.current_app", mock_app):
            response = consent_redirect()

        assert response.status_code == HTTPStatus.FOUND
        assert response.location == "/survey"
        assert session["current_question_index"] == 1

        question = session["survey_iteration"]["questions"][0]
        assert question["response"] == "no"
        assert "survey_assist_time_end" in session["survey_iteration"]
        assert isinstance(
            session["survey_iteration"]["survey_assist_time_end"], datetime
        )


@pytest.mark.utils
def test_consent_redirect_invalid_session_raises_value_error(app):
    """Test ValueError is raised when survey_iteration is missing."""
    with app.test_request_context(method="POST", data={"survey-assist-consent": "yes"}):
        session["survey_iteration"] = None  # Simulate invalid session

        with pytest.raises(ValueError, match="Invalid session state"):
            consent_redirect()


@pytest.mark.utils
@patch("utils.survey_utils.FOLLOW_UP_TYPE", "both")
@patch("utils.survey_utils.url_for", return_value="/survey")
@patch("utils.survey_utils.render_template")
@patch("utils.survey_utils.format_followup")
def test_followup_redirect_renders_followup_question(
    mock_format, mock_render, _mock_url_for, app
):
    """Test followup_redirect renders a follow-up question correctly."""
    mock_question = {
        "question_id": "q1",
        "question_name": "job-title",
        "question_text": "What is your job title?",
        "response_type": "text",
    }

    mock_followup = [
        {
            "follow_up_id": "f1",
            "question_name": "extra-detail",
            "question_text": "Can you provide more detail?",
            "response_type": "text",
        }
    ]

    mock_question_obj = type(
        "MockQuestion", (), {"to_dict": lambda self: {"question_text": "rendered"}}
    )()
    mock_format.return_value = mock_question_obj

    mock_render.return_value = "rendered-html"

    with app.test_request_context():
        session["current_question_index"] = 0
        session["follow_up"] = mock_followup.copy()

        mock_app = app
        mock_app.questions = [mock_question]
        mock_app.survey_assist = {
            "interactions": [{"after_question_id": "q1"}],
        }

        with patch("utils.survey_utils.current_app", mock_app):
            response = followup_redirect()

            assert "follow_up" in session
            assert isinstance(session["follow_up"], list)
            assert len(session["follow_up"]) == 0
            assert session["follow_up"] == []

    mock_format.assert_called_once()
    mock_render.assert_called_once()
    assert response == "rendered-html"


@pytest.mark.utils
@patch("utils.survey_utils.url_for", return_value="/survey")
def test_followup_redirect_redirects_to_next_core_question(_mock_url_for, app):
    """Test followup_redirect redirects if no follow-up questions remain."""
    mock_question = {
        "question_id": "q1",
        "question_name": "job-title",
        "question_text": "What is your job title?",
        "response_type": "text",
    }

    with app.test_request_context():
        session["current_question_index"] = 0
        session["follow_up"] = []  # Empty list
        session.modified = False

        mock_app = app
        mock_app.questions = [mock_question]
        mock_app.survey_assist = {
            "interactions": [{"after_question_id": "q1"}],
        }

        with patch("utils.survey_utils.current_app", mock_app):
            response = followup_redirect()

        assert session["current_question_index"] == 1

    assert response.status_code == HTTPStatus.FOUND
    assert response.location == "/survey"


@pytest.mark.utils
@patch("utils.survey_utils.url_for", return_value="/page-not-found")
def test_followup_redirect_to_error_when_no_interaction_match(_mock_url_for, app):
    """Test redirect to error page if interaction doesn't match current question."""
    mock_question = {
        "question_id": "q9",  # No match with after_question_id
        "question_name": "location",
        "question_text": "Where do you work?",
        "response_type": "text",
    }

    with app.test_request_context():
        session["current_question_index"] = 0

        mock_app = app
        mock_app.questions = [mock_question]
        mock_app.survey_assist = {
            "interactions": [{"after_question_id": "q1"}],  # Different ID
        }

        with patch("utils.survey_utils.current_app", mock_app):
            response = followup_redirect()

    assert response.status_code == HTTPStatus.FOUND
    assert response.location == "/page-not-found"
