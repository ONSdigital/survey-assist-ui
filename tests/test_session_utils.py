"""Unit tests for session utility functions in Survey Assist UI.

This module contains tests for session encoding, datetime conversion, and session debug
decorators.
"""

from datetime import datetime
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from flask import current_app, session

from utils.app_types import SurveyAssistFlask
from utils.session_utils import (
    _convert_datetimes,
    get_encoded_session_size,
    print_session_info,
    session_debug,
)


@pytest.mark.utils
def test_session_debug_decorator_calls_view_and_prints(
    client, monkeypatch  # pylint:disable=unused-argument
):
    """Tests that session_debug calls the view function and prints session info."""
    app = cast(SurveyAssistFlask, current_app)
    mock_response = MagicMock(name="Response")

    # Fake function to decorate
    def test_view():
        return mock_response

    # Patch the session printer
    with patch("utils.session_utils.print_session_info") as mock_print:
        decorated = session_debug(test_view)

        with app.app_context():
            app.config["SESSION_DEBUG"] = True
            result = decorated()

        # Assertions
        assert result == mock_response
        mock_print.assert_called_once()


@pytest.mark.utils
def test_convert_datetimes_dict():
    """Tests that datetime values in a dictionary are converted to ISO format."""
    dt = datetime(2024, 1, 1, 12, 0, 0)
    input_data = {"key": dt}
    result = _convert_datetimes(input_data)
    assert result == {"key": dt.isoformat()}


@pytest.mark.utils
def test_convert_datetimes_list():
    """Tests that datetime values in a list are converted to ISO format."""
    dt = datetime(2023, 6, 15, 8, 30)
    input_data = [dt]
    result = _convert_datetimes(input_data)
    assert result == [dt.isoformat()]


@pytest.mark.utils
def test_convert_datetimes_nested_structures():
    """Tests that datetime values in nested dicts and lists are converted."""
    dt = datetime(2022, 12, 25, 0, 0)
    input_data = {
        "outer": {
            "inner": [dt, {"deep": dt}],
        }
    }
    result = _convert_datetimes(input_data)
    assert result == {
        "outer": {
            "inner": [dt.isoformat(), {"deep": dt.isoformat()}],
        }
    }


@pytest.mark.utils
def test_convert_datetimes_primitive_passthrough():
    """Tests that non-datetime primitive values are returned unchanged."""
    assert _convert_datetimes("string") == "string"
    assert _convert_datetimes(42) == 42  # noqa: PLR2004
    assert _convert_datetimes(None) is None
    assert _convert_datetimes(3.14) == 3.14  # noqa: PLR2004
    assert _convert_datetimes(True) is True


@pytest.mark.utils
def test_get_encoded_session_size_returns_byte_length(
    client,
):  # pylint:disable=unused-argument
    """Tests that get_encoded_session_size returns correct byte size of session object."""
    app = cast(SurveyAssistFlask, current_app)

    session_data = {"user": "test", "logged_in": True}
    with app.app_context():
        size = get_encoded_session_size(session_data)
        assert isinstance(size, int)
        assert size > 0


@pytest.mark.utils
def test_get_encoded_session_size_returns_zero_if_no_serializer(
    client,
):  # pylint:disable=unused-argument
    """Tests that get_encoded_session_size returns 0 if serializer is None."""
    app = cast(SurveyAssistFlask, current_app)
    with (
        patch(
            "utils.session_utils.SecureCookieSessionInterface.get_signing_serializer",
            return_value=None,
        ),
        app.app_context(),
    ):
        result = get_encoded_session_size({"any": "data"})
        assert result == 0


@pytest.mark.utils
def test_print_session_info_debug_disabled(app):
    """Should return early if SESSION_DEBUG is False."""
    with app.test_request_context():
        app.config["SESSION_DEBUG"] = False
        with patch("utils.session_utils.logger.debug") as mock_debug:
            print_session_info()
            mock_debug.assert_not_called()


@pytest.mark.utils
def test_print_session_info_json_debug_false(app):
    """Should log size but not session content if JSON_DEBUG is False."""
    with app.test_request_context():
        app.config["SESSION_DEBUG"] = True
        app.config["JSON_DEBUG"] = False
        session["foo"] = "bar"
        with patch("utils.session_utils.logger.debug") as mock_debug, patch(
            "utils.session_utils.get_encoded_session_size", return_value=123
        ):
            print_session_info()
            debug_calls = [call.args[0] for call in mock_debug.call_args_list]
            assert any("Session size: 123 bytes" in msg for msg in debug_calls)
            assert not any("Session content:" in msg for msg in debug_calls)


@pytest.mark.utils
def test_print_session_info_full_output(app):
    """Should log both size and session content when all debug flags enabled."""
    with app.test_request_context():
        app.config["SESSION_DEBUG"] = True
        app.config["JSON_DEBUG"] = True
        session["key"] = "value"
        with patch("utils.session_utils.logger.debug") as mock_debug, patch(
            "utils.session_utils.get_encoded_session_size", return_value=456
        ):
            print_session_info()
            debug_calls = [call.args[0] for call in mock_debug.call_args_list]
            assert any("Session size: 456 bytes" in msg for msg in debug_calls)
            assert any("Session content:" in msg for msg in debug_calls)


@pytest.mark.utils
def test_print_session_info_raises_and_logs_error(app):
    """Should catch and log exceptions that occur during session processing."""
    with app.test_request_context():
        app.config["SESSION_DEBUG"] = True
        session["bad"] = object()  # Unserialisable

        with patch(
            "utils.session_utils.get_encoded_session_size", side_effect=TypeError("bad")
        ), patch("utils.session_utils.logger.error") as mock_error:
            print_session_info()
            mock_error.assert_called_once()
            assert "Error printing session debug info" in mock_error.call_args[0][0]
