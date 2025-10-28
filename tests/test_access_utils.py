"""Tests for the format_access_code utility function."""

import re
from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

from utils.access_utils import delete_access, format_access_code, validate_access
from utils.app_types import SurveyAssistFlask


@pytest.mark.utils
class TestFormatAccessCode:
    """Unit tests for format_access_code."""

    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("abc123", "ABC123"),
            (" abc123 ", "ABC123"),  # trims whitespace
            ("\tabc123\t", "ABC123"),  # trims tabs
            ("abc 123", "ABC-123"),  # converts single space
            ("abc\t123", "ABC-123"),  # converts tab
            ("abc   123", "ABC-123"),  # converts multiple spaces
            (" abc \t 123 ", "ABC-123"),  # mixed whitespace
            ("a b\tc  d", "A-B-C-D"),  # mixed spacing between letters
            ("Ex12 8rtY AeFF 33CV", "EX12-8RTY-AEFF-33CV"),  # 16 char example
            ("", ""),  # empty string
            ("   ", ""),  # only whitespace
        ],
    )
    def test_valid_access_code_formats(self, raw: str, expected: str) -> None:
        """It should correctly format and normalise valid access codes.

        Args:
            raw (str): The unformatted access code.
            expected (str): The expected formatted code.
        """
        result = format_access_code(raw)
        assert result == expected, f"Expected '{expected}' but got '{result}'"

    def test_returns_uppercase(self) -> None:
        """It should always return uppercase output."""
        result = format_access_code("aBcDe fGh")
        assert result.isupper(), "Access code should be converted to uppercase"

    def test_handles_multiple_internal_whitespace(self) -> None:
        """It should replace multiple consecutive whitespace sequences with a single hyphen."""
        result = format_access_code("abc   \t   def")
        assert result == "ABC-DEF"

    def test_does_not_mutate_input(self) -> None:
        """It should not modify the input string in place."""
        raw = "abc 123"
        original = raw[:]
        _ = format_access_code(raw)
        assert raw == original, "Input string should remain unchanged"

    def test_regex_used_for_whitespace_replacement(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """It should call re.sub with the correct whitespace pattern."""
        spy_called = {}

        def fake_sub(pattern: str, repl: str, text: str) -> str:
            spy_called.update({"pattern": pattern, "repl": repl, "text": text})
            return "MOCKED"

        monkeypatch.setattr(re, "sub", fake_sub)
        result = format_access_code("abc def")

        assert result == "MOCKED"
        assert spy_called["pattern"] == r"\s+", "Should use regex pattern '\\s+'"
        assert spy_called["repl"] == "-", "Should replace with a single hyphen"
        assert spy_called["text"] == "abc def", "Should pass stripped text to re.sub"


@pytest.mark.utils
def test_returns_error_when_access_code_missing() -> None:
    """It should return an error when the access code is missing.

    Verifies the early-return branch for a falsy access_code.
    """
    # Act
    result: tuple[bool, str] = validate_access(access_id="ONS123", access_code="")

    # Assert
    assert result == (
        False,
        "You must enter both ONS ID and PFR ID",
    ), "Should require both ONS ID and PFR ID"


@pytest.mark.utils
def test_returns_true_when_service_verifies_success(client) -> None:
    """It should return (True, '') when the service reports verified=True."""
    app = cast(SurveyAssistFlask, client.application)
    with app.app_context(), patch(
        "utils.access_utils.OTPVerificationService"
    ) as service, patch("utils.access_utils.logger") as mock_logger:

        # Provide the dependency used by validate_access
        app.verify_api_client = MagicMock()

        svc_inst = service.return_value
        svc_inst.verify.return_value = SimpleNamespace(verified=True, message="OK")

        result = validate_access(access_id="ONS123", access_code="PFR456")

    assert result == (True, "")
    mock_logger.warning.assert_not_called()  # type: ignore[attr-defined]
    service.assert_called_once_with(app.verify_api_client)  # type: ignore[attr-defined]
    svc_inst.verify.assert_called_once_with(id_str="ONS123", otp="PFR456")


@pytest.mark.utils
def test_returns_invalid_credentials_when_verification_fails(client) -> None:
    """It should return a generic invalid-credentials message when verified=False."""
    app = cast(SurveyAssistFlask, client.application)
    with app.app_context(), patch(
        "utils.access_utils.OTPVerificationService"
    ) as service, patch("utils.access_utils.logger") as mock_logger:

        app.verify_api_client = MagicMock()

        svc_inst = service.return_value
        svc_inst.verify.return_value = SimpleNamespace(
            verified=False, message="invalid or expired code"
        )

        result = validate_access(access_id="ONS123", access_code="BADCODE")

    assert result == (False, "Invalid credentials. Please try again.")
    mock_logger.warning.assert_called()  # type: ignore[attr-defined]
    args, _ = mock_logger.warning.call_args  # type: ignore[attr-defined]
    assert (
        "Validation unsuccessful for participant_id:ONS123 - invalid or expired code"
        in args[0]
    )
    service.assert_called_once_with(app.verify_api_client)  # type: ignore[attr-defined]
    svc_inst.verify.assert_called_once_with(id_str="ONS123", otp="BADCODE")


@pytest.mark.utils
def test_returns_module_error_when_service_raises_runtime_error(client) -> None:
    """It should catch RuntimeError from the service and return the module error message."""
    app = cast(SurveyAssistFlask, client.application)
    with app.app_context(), patch(
        "utils.access_utils.OTPVerificationService"
    ) as service, patch("utils.access_utils.logger") as mock_logger:

        app.verify_api_client = MagicMock()

        svc_inst = service.return_value
        svc_inst.verify.side_effect = RuntimeError("boom")

        result = validate_access(access_id="ONS123", access_code="ANYCODE")

    assert result == (False, "Error in validation module")
    mock_logger.warning.assert_called()  # type: ignore[attr-defined]
    args, _ = mock_logger.warning.call_args  # type: ignore[attr-defined]
    assert "participant_id:ONS123 error validating user: boom" in args[0]
    service.assert_called_once_with(app.verify_api_client)  # type: ignore[attr-defined]
    svc_inst.verify.assert_called_once_with(id_str="ONS123", otp="ANYCODE")


@pytest.mark.utils
def test_delete_access_returns_true_when_service_deletes_successfully(client) -> None:
    """It should return (True, '') when the service reports deleted=True.

    Behaviour:
        - Builds OTPVerificationService with current_app.verify_api_client.
        - Calls delete(id_str=...).
        - Logs info on success.
    """
    app = cast(SurveyAssistFlask, client.application)
    with app.app_context(), patch(
        "utils.access_utils.OTPVerificationService"
    ) as service, patch("utils.access_utils.logger") as mock_logger:

        app.verify_api_client = MagicMock()

        svc_inst = service.return_value
        svc_inst.delete.return_value = SimpleNamespace(deleted=True, message="OK")

        out = delete_access(access_id="ONS123")

    assert out == (True, "")
    service.assert_called_once_with(app.verify_api_client)  # type: ignore[attr-defined]
    svc_inst.delete.assert_called_once_with(id_str="ONS123")
    mock_logger.info.assert_called()  # type: ignore[attr-defined]
    mock_logger.warning.assert_not_called()  # type: ignore[attr-defined]


@pytest.mark.utils
def test_delete_access_returns_invalid_id_when_service_reports_failure(client) -> None:
    """It should return the formatted invalid-id message when deleted=False.

    Behaviour:
        - Service returns deleted=False with a failure message.
        - Function returns (False, f"Invalid id {access_id}. Not deleted.").
        - Logs a warning that includes the service message.
    """
    app = cast(SurveyAssistFlask, client.application)
    with app.app_context(), patch(
        "utils.access_utils.OTPVerificationService"
    ) as service, patch("utils.access_utils.logger") as mock_logger:

        app.verify_api_client = MagicMock()

        svc_inst = service.return_value
        svc_inst.delete.return_value = SimpleNamespace(
            deleted=False, message="not found or expired"
        )

        out = delete_access(access_id="ONS999")

    assert out == (False, "Invalid id ONS999. Not deleted.")
    service.assert_called_once_with(app.verify_api_client)  # type: ignore[attr-defined]
    svc_inst.delete.assert_called_once_with(id_str="ONS999")
    mock_logger.warning.assert_called()  # type: ignore[attr-defined]
    args, _ = mock_logger.warning.call_args  # type: ignore[attr-defined]
    assert (
        "Deletion unsuccessful for participant_id:ONS999 - not found or expired"
        in args[0]
    )


@pytest.mark.utils
def test_delete_access_returns_module_error_when_service_raises_runtime_error(
    client,
) -> None:
    """It should catch RuntimeError from the service and return the module error message.

    Behaviour:
        - Service.delete raises RuntimeError('boom').
        - Function logs a warning and returns the generic module error tuple.
    """
    app = cast(SurveyAssistFlask, client.application)
    with app.app_context(), patch(
        "utils.access_utils.OTPVerificationService"
    ) as service, patch("utils.access_utils.logger") as mock_logger:

        app.verify_api_client = MagicMock()

        svc_inst = service.return_value
        svc_inst.delete.side_effect = RuntimeError("boom")

        out = delete_access(access_id="ONS123")

    assert out == (False, "Error in validation module when deleting access code")
    service.assert_called_once_with(app.verify_api_client)  # type: ignore[attr-defined]
    svc_inst.delete.assert_called_once_with(id_str="ONS123")
    mock_logger.error.assert_called()  # type: ignore[attr-defined]
    args, _ = mock_logger.error.call_args  # type: ignore[attr-defined]
    assert "participant_id:ONS123 error deleting access: boom" in args[0]


@pytest.mark.utils
def test_delete_access_returns_error_when_id_missing(client) -> None:
    """It should return an error when the access id is missing.

    Behaviour:
        - Early return branch for falsy access_id.
        - Logs a warning and returns (False, 'ID not set in session').
    """
    app = cast(SurveyAssistFlask, client.application)
    with app.app_context(), patch("utils.access_utils.logger") as mock_logger:
        out = delete_access(access_id="")

    assert out == (False, "ID not set in session")
    mock_logger.error.assert_called()  # type: ignore[attr-defined]
