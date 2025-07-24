"""Tests routes of the Survey Assist UI application.

This module contains tests to verify that routes return the correct response.
"""

from http import HTTPStatus
from typing import cast
from unittest.mock import patch

import pytest
from flask import current_app

from utils.app_types import SurveyAssistFlask


@pytest.mark.route
def test_index_route(client) -> None:
    """Tests that the index route contains survey title and returns a 200 OK response.

    Args:
        client: Flask test client fixture.
    """
    app = cast(SurveyAssistFlask, current_app)
    response = client.get("/")
    expected_text = app.survey_title

    assert (
        expected_text.encode() in response.data
    ), f"Index page should contain '{expected_text}'"
    assert response.status_code == HTTPStatus.OK, "Index route should return 200 OK"


@pytest.mark.route
def test_error_route(client) -> None:
    """Tests that the error route contains correct text and returns a 200 OK response.

    Args:
        client: Flask test client fixture.
    """
    route_text = "page-not-found"
    response = client.get("/" + route_text)
    expected_text = "Page not found"

    assert (
        expected_text.encode() in response.data
    ), f"{route_text} page should contain '{expected_text}'"
    assert (
        response.status_code == HTTPStatus.OK
    ), "{route_text} route should return 200 OK"


@pytest.mark.route
def test_first_survey_question(client, mock_questions) -> None:
    """Tests that the survey route contains correct text
    for the first question and returns a 200 OK response.

    Args:
        client: Flask test client fixture.
        mock_questions: Mocked questions to simulate survey data.
    """
    app = cast(SurveyAssistFlask, current_app)

    with patch.object(app, "questions", mock_questions):
        with client.session_transaction() as sess:
            # Ensure a clean state to trigger init logic
            sess.pop("current_question_index", None)
            sess.pop("survey_iteration", None)

        response = client.get("/survey")

        expected_text = mock_questions[0]["question_text"]
        assert (
            expected_text.encode() in response.data
        ), "Survey page should contain the first question text"
        assert response.status_code == HTTPStatus.OK, "/survey should return 200 OK"
        assert (
            b"Save and continue" in response.data
        ), "Expected 'Save and continue' in response"

        # Validate session was initialised correctly
        with client.session_transaction() as sess:
            assert "current_question_index" in sess
            assert sess["current_question_index"] == 0
            assert "survey_iteration" in sess
            assert "time_start" in sess["survey_iteration"]


QUESTION_THREE_INDEX = 2


@pytest.mark.route
def test_placeholder_survey_question(client, mock_questions) -> None:
    """Tests that the survey route contains correct text
    for the first question and returns a 200 OK response.

    Args:
        client: Flask test client fixture.
        mock_questions: Mocked questions to simulate survey data.
    """
    app = cast(SurveyAssistFlask, current_app)

    with patch.object(app, "questions", mock_questions):
        with client.session_transaction() as sess:
            sess["current_question_index"] = QUESTION_THREE_INDEX

            sess["response"] = {"job_title": "Warehouse Manager"}
            sess.modified = True

        response = client.get("/survey")
        expected_text = mock_questions[QUESTION_THREE_INDEX]["question_text"].replace(
            "PLACEHOLDER_TEXT", "Warehouse Manager"
        )
        assert (
            expected_text.encode() in response.data
        ), "Survey page should contain the third question text"
        assert response.status_code == HTTPStatus.OK, "/survey should return 200 OK"
        assert (
            b"Save and continue" in response.data
        ), "Expected 'Save and continue' in response"


@pytest.mark.route
def test_survey_assist_consent(client, mock_survey_assist) -> None:
    """Tests that the consent route returns a 200 OK response.

    Args:
        client: Flask test client fixture.
        mock_survey_assist: Mocked survey assist data.
    """
    app = cast(SurveyAssistFlask, current_app)

    route_text = "survey_assist_consent"

    with patch.object(app, "survey_assist", mock_survey_assist):
        response = client.get("/" + route_text)
        assert (
            response.status_code == HTTPStatus.OK
        ), "{route_text} should return 200 OK"
        assert (
            b"Can Survey Assist ask" in response.data
        ), "Consent page should contain consent text"


@pytest.mark.route
def test_survey_summary(client, mock_survey_iteration) -> None:
    """Tests that the survey summary route returns a 200 OK response.

    Args:
        client: Flask test client fixture.
        mock_survey_iteration: Mocked survey iteration data.
    """
    route_text = "summary"

    with client.session_transaction() as sess:
        sess["survey_iteration"] = mock_survey_iteration
        sess.modified = True

    response = client.get("/" + route_text)
    assert response.status_code == HTTPStatus.OK, "{route_text} should return 200 OK"
    assert (
        b"Summary" in response.data
    ), "{route_text} page should contain 'Summary' text"
