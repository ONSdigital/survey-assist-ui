"""Unit tests for Survey Assist utility functions.

This module contains tests for the survey assist related utility functions
used in the Survey Assist UI application.
"""

from datetime import datetime
from http import HTTPStatus
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from flask import current_app, session

from models.classify import GenericClassificationResponse
from models.question import Question
from utils.app_types import SurveyAssistFlask
from utils.survey_assist_utils import (
    classify,
    classify_and_handle_followup,
    classify_and_redirect,
    format_followup,
    get_next_followup,
    perform_sic_lookup,
)

# pylint: disable=line-too-long


@pytest.mark.parametrize(
    "api_response, expect_none",
    [
        pytest.param("valid_will_use_fixture", False, id="valid_response"),
        pytest.param("some string error", True, id="string_error"),
        pytest.param(None, True, id="none_response"),
    ],
)
@pytest.mark.utils
def test_classify_response_handling(
    app,
    api_response,
    expect_none,
    mock_api_client: MagicMock,
    generic_classification_response_no_meta,
) -> None:
    """Tests classify() returns expected result based on API client response."""
    if api_response == "valid_will_use_fixture":
        api_response = generic_classification_response_no_meta.model_copy(deep=True)

    mock_api_client.post.return_value = api_response

    with patch.object(app, "api_client", mock_api_client):
        result, _start_time = classify(
            classification_type="sic",
            job_title="Data Scientist",
            job_description="Build predictive models",
            org_description="Government department",
        )

    if expect_none:
        assert result is None
    else:
        assert isinstance(result, GenericClassificationResponse)
        # Compare dicts for stability
        assert (
            result.model_dump() == generic_classification_response_no_meta.model_dump()
        )

    mock_api_client.post.assert_called_once_with(
        "/survey-assist/classify",
        body={
            "llm": "gemini",
            "type": "sic",
            "job_title": "Data Scientist",
            "job_description": "Build predictive models",
            "org_description": "Government department",
        },
    )


@pytest.mark.parametrize(
    "question_type, expected_text",
    [
        ("open", "First question"),
        ("both", "First question"),
        ("closed", "Third question"),
    ],
)
@pytest.mark.utils
def test_get_next_followup_valid_types(
    app, client, followup_questions, question_type, expected_text
):
    """Test that follow-up question is correctly returned based on question_type."""
    with client.session_transaction() as sess:
        sess["follow_up"] = []  # start clean

    with app.test_request_context():
        result = get_next_followup(followup_questions.copy(), question_type)

        assert isinstance(result, tuple)
        question_text, question_data = result
        assert question_text == expected_text
        assert "question_text" in question_data

        # Check that session is updated
        remaining = session.get("follow_up")
        assert len(remaining) == 2  # noqa: PLR2004
        assert all(isinstance(q, dict) for q in remaining)


@pytest.mark.utils
def test_get_next_followup_invalid_type(app, client, followup_questions):
    """Test that an invalid question_type returns None and logs warning."""
    with client.session_transaction() as sess:
        sess["follow_up"] = []

    with app.test_request_context():
        result = get_next_followup(followup_questions.copy(), "invalid_type")
        assert result is None
        assert session["follow_up"] == followup_questions


@pytest.mark.utils
def test_get_next_followup_empty_input(app, client):
    """Test that None is returned when there are no follow-ups."""
    with client.session_transaction() as sess:
        sess["follow_up"] = []

    with app.test_request_context():
        result = get_next_followup([], "open")
        assert result is None
        assert session["follow_up"] == []


@pytest.mark.parametrize(
    "response_type, select_options, expected_option_count",
    [
        ("select", ["A", "B"], 2),
        ("text", [], 0),
    ],
)
@pytest.mark.utils
def test_format_followup_creates_question(
    response_type, select_options, expected_option_count
):
    """Tests that format_followup constructs a valid Question instance."""
    question_data = {
        "follow_up_id": "fu-123",
        "question_name": "follow_up_test",
        "response_type": response_type,
    }

    if response_type == "select":
        response_type = "radio"
        question_data["select_options"] = select_options

    question_text = "What industry best matches your job?"

    result = format_followup(question_data, question_text)

    # Check type
    assert isinstance(result, Question)

    # Check core attributes
    assert result.question_id == "fu-123"
    assert result.question_name == "follow_up_test"
    assert result.title == "follow_up_test"
    assert result.question_text == question_text
    assert (
        result.question_description
        == "<p>This question is generated by Survey Assist</p>"
    )
    assert result.response_type == response_type

    # Check response options
    assert len(result.response_options) == expected_option_count
    for option in result.response_options:
        assert "id" in option
        assert "label" in option and "text" in option["label"]
        assert "value" in option


@pytest.mark.utils
def test_perform_sic_lookup(app, client, mock_api_client):
    """Tests that perform_sic_lookup calls the API client and returns the response."""
    app = current_app  # type: ignore
    app = cast(SurveyAssistFlask, app)

    # Prepare expected behaviour
    test_description = "education services"
    expected_response = {"sic_code": "12345", "description": "Education"}
    mock_api_client.get.return_value = expected_response

    with client.session_transaction():
        pass  # Ensure session is initialised

    with patch.object(app, "api_client", mock_api_client), app.test_request_context():
        result, _start_time, _end_time = perform_sic_lookup(test_description)

        # Assert correct URL was called
        expected_url = (
            f"/survey-assist/sic-lookup?description={test_description}&similarity=true"
        )
        mock_api_client.get.assert_called_once_with(endpoint=expected_url)

        # Assert correct return value
        assert result == expected_response

        # Assert session is marked modified
        assert session.modified is True


@pytest.mark.utils
def test_classify_and_redirect_redirects_to_question_template(app):
    """Tests that classify_and_redirect performs classification and redirects."""
    with patch("utils.survey_assist_utils.classify") as mock_classify, patch(
        "utils.survey_assist_utils.url_for"
    ) as mock_url_for:

        mock_classify.return_value = {"result": "classified"}
        mock_url_for.return_value = "/survey/question-template"

        with app.test_request_context():
            response = classify_and_redirect(
                job_title="Software Engineer",
                job_description="Develop and maintain software",
                org_description="Tech startup",
            )

        mock_classify.assert_called_once()
        mock_url_for.assert_called_once_with("survey.question_template")
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == "/survey/question-template"


# Needs rework
#
# @pytest.mark.utils
# def test_classify_and_handle_followup_renders_followup(app, valid_question):
#     """Tests successful classification and follow-up rendering."""
#     classification_response = {"some": "classification"}
#     mapped_response = {
#         "follow_up": {
#             "questions": [
#                 {
#                     "question_text": "Example?",
#                     "response_type": "text",
#                     "question_name": "followup_1",
#                     "follow_up_id": "fu1",
#                 }
#             ]
#         }
#     }
#     followup_question = (
#         "Example?",
#         {
#             "question_text": "Example?",
#             "response_type": "text",
#             "question_name": "followup_1",
#             "follow_up_id": "fu1",
#         },
#     )

#     # Mock the question to_dict conversion
#     mock_question = MagicMock()
#     mock_question.to_dict.return_value = valid_question

#     with patch(
#         "utils.survey_assist_utils.classify", return_value=classification_response
#     ), patch(
#         "utils.survey_assist_utils.map_api_response_to_internal",
#         return_value=mapped_response,
#     ), patch(
#         "utils.survey_assist_utils.get_next_followup", return_value=followup_question
#     ), patch(
#         "utils.survey_assist_utils.format_followup", return_value=mock_question
#     ), patch(
#         "utils.survey_assist_utils.render_template",
#         return_value="rendered-question-template",
#     ):

#         with app.test_request_context():
#             # Initialise the expected session structure
#             session["survey_iteration"] = {"questions": []}
#             response = classify_and_handle_followup(
#                 job_title="Developer",
#                 job_description="Builds systems",
#                 org_description="Tech company",
#             )

#         assert response == "rendered-question-template"


@pytest.mark.utils
def test_classify_and_handle_followup_redirects_on_none_classification(app):
    """Tests redirect occurs when classification returns None in follow-up handler.

    Args:
        app: The Flask application fixture.
    """
    with patch(
        "utils.survey_assist_utils.classify", return_value=(None, datetime(2024, 1, 1))
    ), patch("utils.survey_assist_utils.url_for") as mock_url_for:
        mock_url_for.return_value = "/survey/question-template"

        with app.test_request_context():
            response = classify_and_handle_followup("Dev", "Builds tools", "Gov")

        mock_url_for.assert_called_once_with("survey.question_template")
        assert response.status_code == HTTPStatus.FOUND
        assert response.location == "/survey/question-template"


# Need to rework tests following classify updates and survey_results
# @pytest.mark.utils
# def test_classify_and_handle_followup_redirects_on_no_followup(app):
#     """Tests redirect occurs when no follow-up questions are returned after classification.

#     Args:
#         app: The Flask application fixture.
#     """
#     with patch(
#         "utils.survey_assist_utils.classify", return_value=({"classified": "yes"},datetime(2024, 1, 1))
#     ), patch(
#         "utils.survey_assist_utils.map_api_response_to_internal",
#         return_value={"follow_up": {"questions": []}},
#     ), patch(
#         "utils.survey_assist_utils.url_for"
#     ) as mock_url_for:
#         mock_url_for.return_value = "/survey/question-template"
#         with app.test_request_context():
#             response = classify_and_handle_followup("Dev", "Builds tools", "Gov")

#         assert response.status_code == HTTPStatus.FOUND
#         assert response.location == "/survey/question-template"


# @pytest.mark.utils
# def test_classify_and_handle_followup_redirects_on_no_next_question(app, generic_classification_response_no_meta):
#     """Tests redirect occurs when no next follow-up question is found after classification.

#     Args:
#         app: The Flask application fixture.
#     """
#     with patch(
#         "utils.survey_assist_utils.classify", return_value=(generic_classification_response_no_meta,datetime.now(timezone.utc))
#     ), patch(
#         "utils.survey_assist_utils.map_api_response_to_internal",
#         return_value={"follow_up": {"questions": [{}]}},
#     ), patch(
#         "utils.survey_assist_utils.get_next_followup", return_value=None
#     ), patch(
#         "utils.survey_assist_utils.url_for"
#     ) as mock_url_for:
#         mock_url_for.return_value = "/survey/question-template"
#         with app.test_request_context():
#             response = classify_and_handle_followup("Dev", "Builds tools", "Gov")

#         assert response.status_code == HTTPStatus.FOUND
#         assert response.location == "/survey/question-template"
