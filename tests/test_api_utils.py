"""Unit tests for API utility functions in Survey Assist UI.

This module contains tests for the API client, error handling, and HTTP request logic.
"""

from http import HTTPStatus
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
import requests
from flask import Flask, current_app
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout

from utils.api_utils import APIClient
from utils.app_types import SurveyAssistFlask

BASE_URL = "https://api.example.com"
TOKEN = "test-token"  # noqa:S105


# Disable unused agument for this file
# pylint cannot differentiate the use of fixtures in the test functions
# pylint: disable=unused-argument, disable=redefined-outer-name
@pytest.fixture
def mock_api_logger():
    """Provides a mock logger for API client tests."""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()
    logger.exception = MagicMock()
    return logger


@pytest.fixture
def api_client(mock_api_logger):
    """Provides an APIClient instance with a mock logger for testing."""
    return APIClient(BASE_URL, TOKEN, mock_api_logger)


@pytest.mark.utils
def test_get_request_success(api_client):
    """Tests that APIClient.get returns JSON data on successful GET request."""
    with patch("utils.api_utils.requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": "success"}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = api_client.get("/test")
        assert result == {"message": "success"}
        mock_get.assert_called_once()


@pytest.mark.utils
def test_post_request_success(api_client):
    """Tests that APIClient.post returns JSON data on successful POST request."""
    with patch("utils.api_utils.requests.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "posted"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        result = api_client.post("/submit", body={"key": "value"})
        assert result == {"status": "posted"}
        mock_post.assert_called_once()


@pytest.mark.utils
def test_unsupported_method_error(client, api_client):
    """Tests that unsupported HTTP methods return an error and log appropriately."""
    app = cast(SurveyAssistFlask, current_app)

    with app.app_context(), patch.object(api_client.logger_handle, "error") as mock_error:
        response, status_code = api_client._request(  # pylint:disable=protected-access
            "DELETE", "/unsupported"
        )

        assert status_code == HTTPStatus.INTERNAL_SERVER_ERROR

        json_data = response.get_json()
        assert "Value error" in json_data["error"]

        mock_error.assert_called()


@pytest.mark.parametrize(
    "exception, expected_error, expected_status",
    [
        (Timeout(), "Request timed out", HTTPStatus.GATEWAY_TIMEOUT),
        (RequestsConnectionError(), "Failed to connect to API", HTTPStatus.BAD_GATEWAY),
        (
            HTTPError(response=MagicMock(status_code=500)),
            "HTTP error: 500",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        ),
        (
            KeyError("missing"),
            "Missing expected data: 'missing'",
            HTTPStatus.BAD_GATEWAY,
        ),
        (
            TypeError("wrong type"),
            "Unexpected error: wrong type",
            HTTPStatus.INTERNAL_SERVER_ERROR,
        ),
    ],
)
@pytest.mark.utils
def test_request_error_handling(
    client, api_client, exception, expected_error, expected_status
):
    """Tests error handling for various exceptions in APIClient.get requests.

    Args:
        client: The Flask test client fixture.
        api_client: The APIClient fixture.
        exception: The exception to simulate.
        expected_error: The expected error message substring.
        expected_status: The expected HTTP status code.
    """
    app = cast(SurveyAssistFlask, current_app)

    with app.app_context(), patch("utils.api_utils.requests.get") as mock_get:
        if isinstance(exception, requests.exceptions.HTTPError):
            response_mock = MagicMock()
            response_mock.raise_for_status.side_effect = exception
            mock_get.return_value = response_mock
        else:
            mock_get.side_effect = exception

        response, status_code = api_client.get("/error-case")
        assert expected_error in response.get_json()["error"]
        assert status_code == expected_status


@pytest.mark.utils
def test_handle_error_redirect():
    """Tests that _handle_error redirects to error page when redirect_on_error is True."""
    app = Flask(__name__)
    app.config["TESTING"] = True

    with app.test_request_context():
        test_api_client = APIClient(
            BASE_URL, TOKEN, MagicMock(), redirect_on_error=True
        )
        with patch("utils.api_utils.url_for", return_value="/error-page"):
            result = test_api_client._handle_error(  # pylint:disable=protected-access
                "Error occurred", HTTPStatus.BAD_REQUEST
            )
            assert result.status_code == HTTPStatus.FOUND
            assert result.location == "/error-page"


@pytest.mark.utils
def test_handle_error_json_response(client, api_client):
    """Tests that _handle_error returns a JSON error response with correct status code."""
    app = cast(SurveyAssistFlask, current_app)
    with app.app_context():
        result = api_client._handle_error(  # pylint:disable=protected-access
            "Something went wrong", HTTPStatus.NOT_FOUND
        )
        assert result[1] == HTTPStatus.NOT_FOUND
        assert result[0].json == {"error": "Something went wrong"}
