"""Tests for the format_access_code utility function."""

import re
from io import StringIO

import pytest

from utils.access_utils import format_access_code, validate_access


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


@pytest.mark.auth
class TestValidateAccess:
    """Tests for access validation logic that do not depend on file operations."""

    def test_returns_error_when_access_code_missing(self) -> None:
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

    def test_returns_error_when_access_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """It should return an error when no credentials match the provided id/code.

        Patches file existence and provides an empty CSV via StringIO to avoid disk I/O.
        """
        # Pretend the credentials file exists
        monkeypatch.setattr("utils.access_utils.os.path.exists", lambda _path: True)

        # Provide an empty CSV with headers only; no matching rows possible
        empty_csv = "survey_access_id,one_time_passcode\n"
        monkeypatch.setattr(
            "builtins.open", lambda *args, **kwargs: StringIO(empty_csv)
        )

        # Act
        result: tuple[bool, str] = validate_access(
            access_id="NONEXISTENT_ID",
            access_code="WRONG_CODE",
        )

        # Assert
        assert result == (
            False,
            "Invalid credentials. Please try again.",
        ), "Should return invalid credentials when no matching row is found"
