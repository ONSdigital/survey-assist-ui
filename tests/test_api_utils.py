"""Unit tests for API utility functions in Survey Assist UI.

This module contains tests for the API client, error handling, and HTTP request logic.
"""

from http import HTTPStatus
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
import requests
from flask import Flask, current_app, session
from pydantic import ValidationError
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout

from models.result import LookupResponse
from utils.api_utils import APIClient, OTPVerificationService, map_to_lookup_response
from utils.app_types import SurveyAssistFlask
from utils.feedback_utils import (
    feedback_session_to_model,
    map_feedback_result_from_session,
    send_feedback,
    send_feedback_result,
)

BASE_URL = "https://api.example.com"
TOKEN = "test-token"  # noqa:S105


# Disable unused agument for this file
# pylint cannot differentiate the use of fixtures in the test functions
# pylint: disable=unused-argument, disable=redefined-outer-name
# pylint: disable=line-too-long
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

    with app.app_context(), patch.object(
        api_client.logger_handle, "error"
    ) as mock_error:
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


POTENTIAL_CODES = 2
POTENTIAL_DIVISIONS = 2
POTENTIAL_CODE_STR = "123"
POTENTIAL_DIVISION_TITLE = "Div A"


@pytest.mark.utils
def test_map_to_lookup_response_with_limits() -> None:
    """Test limits in map_to_lookup_response."""
    raw = {
        "code": "12345",
        "potential_matches": {
            "codes": ["123", "456", "789", "999"],
            "codes_count": 4,
            "divisions": [
                {"code": "A", "meta": {"title": "Div A", "detail": "Detail A"}},
                {"code": "B", "meta": {"title": "Div B", "detail": "Detail B"}},
                {"code": "C", "meta": {"title": "Div C", "detail": "Detail C"}},
            ],
            "divisions_count": 3,
        },
    }

    result = map_to_lookup_response(raw, max_codes=2, max_divisions=2)

    assert result.found is True
    assert isinstance(result, LookupResponse)
    assert len(result.potential_codes) == POTENTIAL_CODES
    assert len(result.potential_divisions) == POTENTIAL_DIVISIONS
    assert result.potential_codes[0].code == POTENTIAL_CODE_STR
    assert result.potential_divisions[0].title == POTENTIAL_DIVISION_TITLE


@pytest.mark.utils
def test_map_to_lookup_response_empty_data() -> None:
    """Test empty data in map_to_lookup_response."""
    raw = {
        "potential_matches": {
            "codes": [],
            "codes_count": 0,
            "divisions": [],
            "divisions_count": 0,
        }
    }

    result = map_to_lookup_response(raw)

    assert result.found is False
    assert result.potential_codes == []
    assert result.potential_divisions == []
    assert result.potential_codes_count == 0


def _make_validation_error(title: str = "FeedbackResult") -> ValidationError:
    """Build a Pydantic v2 ValidationError for use as a side_effect.

    Args:
        title: A short title for the error, typically the model name.

    Returns:
        A ValidationError instance that can be used as a side_effect to raise.
    """
    line_errors = [
        {
            "type": "string_type",
            "loc": ("field",),
            "msg": "Input should be a valid string",
            "input": None,
        }
    ]
    return ValidationError.from_exception_data(title, line_errors=line_errors)  # type: ignore[arg-type]


@pytest.fixture()
def fake_feedback_model() -> MagicMock:
    """Provides a MagicMock that behaves like a Pydantic model with model_dump(mode='json')."""
    m = MagicMock()
    m.model_dump.return_value = {"score": 5, "comment": "great"}
    return m


# pylint: disable=invalid-name
@pytest.mark.utils
def test_feedback_session_to_model_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """It delegates to FeedbackResult.model_validate and returns the validated model."""
    sess_payload = {"message": "hello"}
    expected_model = MagicMock()

    with patch("utils.feedback_utils.FeedbackResult") as FeedbackResult:
        FeedbackResult.model_validate.return_value = expected_model  # type: ignore[attr-defined]
        out = feedback_session_to_model(sess_payload)  # type: ignore[arg-type]

    FeedbackResult.model_validate.assert_called_once_with(sess_payload)  # type: ignore[attr-defined]
    assert out is expected_model


# @pytest.mark.utils
def test_feedback_session_to_model_raises_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It lets ValidationError propagate when session payload is invalid."""
    with patch("utils.feedback_utils.FeedbackResult") as FeedbackResult:
        FeedbackResult.model_validate.side_effect = _make_validation_error()  # type: ignore[attr-defined]
        with pytest.raises(ValidationError):
            _ = feedback_session_to_model({"bad": "payload"})  # type: ignore[typeddict-item]


@pytest.mark.utils
def test_map_feedback_result_from_session_missing_returns_none(client) -> None:
    """It returns None when 'feedback_response' is not in session."""
    assert map_feedback_result_from_session() is None


@pytest.mark.utils
def test_map_feedback_result_from_session_success(client) -> None:
    """It returns the validated model when session payload is valid."""
    app = cast(SurveyAssistFlask, current_app)
    payload = {"ok": True}
    with app.test_request_context():
        session["feedback_response"] = payload
        expected = MagicMock()
        with patch("utils.feedback_utils.FeedbackResult") as FeedbackResult:
            FeedbackResult.model_validate.return_value = expected  # type: ignore[attr-defined]
            out = map_feedback_result_from_session()

        FeedbackResult.model_validate.assert_called_once_with(payload)  # type: ignore[attr-defined]
        assert out is expected


@pytest.mark.utils
def test_map_feedback_result_from_session_validation_error_returns_none(client) -> None:
    """It catches ValidationError and returns None if validation fails."""
    app = cast(SurveyAssistFlask, current_app)

    with app.test_request_context():
        session["feedback_response"] = {"broken": True}

        with patch("utils.feedback_utils.FeedbackResult") as FeedbackResult:
            FeedbackResult.model_validate.side_effect = _make_validation_error()  # type: ignore[attr-defined]
            out = map_feedback_result_from_session()

        assert out is None


@pytest.mark.utils
def test_send_feedback_calls_send_feedback_result_when_body_present(client) -> None:
    """It calls send_feedback_result when the mapped model exists."""
    fake_model = MagicMock()
    with patch(
        "utils.feedback_utils.map_feedback_result_from_session", return_value=fake_model
    ) as p_map, patch(
        "utils.feedback_utils.send_feedback_result", return_value={"status": "ok"}
    ) as p_send:
        out = send_feedback()

    p_map.assert_called_once_with()
    p_send.assert_called_once_with(fake_model)
    assert out == {"status": "ok"}


@pytest.mark.utils
def test_send_feedback_returns_none_when_no_body(client) -> None:
    """It returns None when mapping yields None and does not call downstream."""
    with patch(
        "utils.feedback_utils.map_feedback_result_from_session", return_value=None
    ) as p_map, patch("utils.feedback_utils.send_feedback_result") as p_send:
        out = send_feedback()

    p_map.assert_called_once_with()
    p_send.assert_not_called()
    assert out is None


@pytest.mark.utils
def test_send_feedback_result_posts_model_dump_and_validates_response(
    client, fake_feedback_model: MagicMock
) -> None:
    """It posts model_dump(mode='json') to the API and returns the validated response."""
    app = cast(SurveyAssistFlask, current_app)
    with app.app_context(), patch.object(
        current_app, "api_client", MagicMock()
    ) as api_client, patch("utils.feedback_utils.FeedbackResultResponse") as FRR:
        # API returns raw dict; model_validate then transforms/returns object
        api_client.post.return_value = {"status": "ok", "id": "fbk_123"}  # type: ignore[attr-defined]
        FRR.model_validate.return_value = {"status": "ok", "id": "fbk_123"}  # type: ignore[attr-defined]

        out = send_feedback_result(fake_feedback_model)

    # Ensure correct endpoint and payload sourced from model_dump(mode='json')
    api_client.post.assert_called_once_with(  # type: ignore[attr-defined]
        "/survey-assist/feedback", body={"score": 5, "comment": "great"}
    )
    FRR.model_validate.assert_called_once_with({"status": "ok", "id": "fbk_123"})  # type: ignore[attr-defined]
    assert out == {"status": "ok", "id": "fbk_123"}


@pytest.mark.utils
def test_send_feedback_result_returns_none_on_response_validation_error(
    client, fake_feedback_model: MagicMock
) -> None:
    """It logs (via module logger) and returns None when response validation fails."""
    app = cast(SurveyAssistFlask, current_app)
    with app.app_context(), patch.object(
        current_app, "api_client", MagicMock()
    ) as api_client, patch("utils.feedback_utils.FeedbackResultResponse") as FRR, patch(
        "utils.feedback_utils.logger"
    ) as mock_logger:
        api_client.post.return_value = {"unexpected": "shape"}  # type: ignore[attr-defined]
        FRR.model_validate.side_effect = _make_validation_error("FeedbackResultResponse")  # type: ignore[attr-defined]

        out = send_feedback_result(fake_feedback_model)

    assert out is None
    # Basic sanity that we logged an error
    mock_logger.error.assert_called()  # type: ignore[attr-defined]


@pytest.fixture
def mock_api() -> MagicMock:
    """Provide a minimal API client double with logger_handle and post()."""
    m = MagicMock()
    m.logger_handle = MagicMock()
    m.logger_handle.info = MagicMock()
    m.post = MagicMock()
    return m


@pytest.mark.utils
def test_verify_success_posts_and_validates_response(
    monkeypatch: pytest.MonkeyPatch, mock_api: MagicMock
) -> None:
    """It should POST the typed payload to /verify, log with masked OTP, and return the validated response."""
    service = OTPVerificationService(mock_api, base_path="/otp")

    # Patch request/response builders and masking
    with patch("utils.api_utils.OtpVerifyRequest") as Req, patch(
        "utils.api_utils.OtpVerifyResponse"
    ) as Resp, patch("utils.api_utils.mask_otp", return_value="***456") as p_mask:
        fake_req = MagicMock()
        fake_req.model_dump.return_value = {"id": "abc", "otp": "123456"}
        Req.return_value = fake_req

        expected = {"ok": True, "verified": True}
        Resp.model_validate.return_value = expected  # type: ignore[attr-defined]

        mock_api.post.return_value = {"ok": True, "verified": True}

        out = service.verify("abc", "123456")

    # Correct endpoint, payload, and masked logging
    mock_api.post.assert_called_once_with(
        endpoint="/otp/verify", body={"id": "abc", "otp": "123456"}, return_json=True
    )
    p_mask.assert_called_once_with("123456")
    mock_api.logger_handle.info.assert_called()  # content checked implicitly by mask call
    assert out == expected


@pytest.mark.utils
def test_verify_api_error_tuple_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch, mock_api: MagicMock
) -> None:
    """It should raise RuntimeError when API returns an error tuple (dict, status_code)."""
    service = OTPVerificationService(mock_api, base_path="/otp")

    # Ensure ERROR_LEN matches in the module under test (defensive in case constant differs)
    monkeypatch.setattr("utils.api_utils.ERROR_LEN", 2, raising=False)

    mock_api.post.return_value = ({"error": "invalid otp"}, 400)

    with patch("utils.api_utils.OtpVerifyRequest") as Req, patch(
        "utils.api_utils.mask_otp", return_value="***"
    ):
        fake_req = MagicMock()
        fake_req.model_dump.return_value = {"id": "abc", "otp": "000000"}
        Req.return_value = fake_req

        with pytest.raises(RuntimeError) as err:
            _ = service.verify("abc", "000000")

    assert "OTP verify failed: invalid otp" in str(err.value)


@pytest.mark.utils
def test_verify_response_validation_error_wrapped_in_runtime_error(
    monkeypatch: pytest.MonkeyPatch, mock_api: MagicMock
) -> None:
    """It should wrap a Pydantic ValidationError from model_validate in a RuntimeError."""
    service = OTPVerificationService(mock_api, base_path="/otp")
    mock_api.post.return_value = {"unexpected": "shape"}

    with patch("utils.api_utils.OtpVerifyRequest") as Req, patch(
        "utils.api_utils.OtpVerifyResponse"
    ) as Resp, patch("utils.api_utils.mask_otp", return_value="***"):
        fake_req = MagicMock()
        fake_req.model_dump.return_value = {"id": "abc", "otp": "999999"}
        Req.return_value = fake_req

        Resp.model_validate.side_effect = _make_validation_error("OtpVerifyResponse")  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError) as err:
            _ = service.verify("abc", "999999")

    assert "Unexpected OTP verify response:" in str(err.value)


@pytest.mark.utils
def test_delete_success_posts_and_validates_response(
    monkeypatch: pytest.MonkeyPatch, mock_api: MagicMock
) -> None:
    """It should POST the typed payload to /delete and return the validated response."""
    service = OTPVerificationService(mock_api, base_path="/otp")

    with patch("utils.api_utils.OtpDeleteRequest") as Req, patch(
        "utils.api_utils.OtpDeleteResponse"
    ) as Resp:
        fake_req = MagicMock()
        fake_req.model_dump.return_value = {"id": "abc"}
        Req.return_value = fake_req

        mock_api.post.return_value = {"status": "deleted"}
        Resp.model_validate.return_value = {"status": "deleted"}  # type: ignore[attr-defined]

        out = service.delete("abc")

    mock_api.post.assert_called_once_with(
        endpoint="/otp/delete", body={"id": "abc"}, return_json=True
    )
    mock_api.logger_handle.info.assert_called()  # ensures we logged the delete call
    assert out == {"status": "deleted"}


@pytest.mark.utils
def test_delete_api_error_tuple_raises_runtime_error(
    monkeypatch: pytest.MonkeyPatch, mock_api: MagicMock
) -> None:
    """It should raise RuntimeError when delete receives an API error tuple."""
    service = OTPVerificationService(mock_api, base_path="/otp")
    monkeypatch.setattr("utils.api_utils.ERROR_LEN", 2, raising=False)

    mock_api.post.return_value = ({"error": "not found"}, 404)

    with patch("utils.api_utils.OtpDeleteRequest") as Req:
        fake_req = MagicMock()
        fake_req.model_dump.return_value = {"id": "abc"}
        Req.return_value = fake_req

        with pytest.raises(RuntimeError) as err:
            _ = service.delete("abc")

    assert "OTP delete failed: not found" in str(err.value)


@pytest.mark.utils
def test_delete_response_validation_error_wrapped_in_runtime_error(
    monkeypatch: pytest.MonkeyPatch, mock_api: MagicMock
) -> None:
    """It should wrap a Pydantic ValidationError from delete model_validate in a RuntimeError."""
    service = OTPVerificationService(mock_api, base_path="/otp")
    mock_api.post.return_value = {"unexpected": "shape"}

    with patch("utils.api_utils.OtpDeleteRequest") as Req, patch(
        "utils.api_utils.OtpDeleteResponse"
    ) as Resp:
        fake_req = MagicMock()
        fake_req.model_dump.return_value = {"id": "abc"}
        Req.return_value = fake_req

        Resp.model_validate.side_effect = _make_validation_error("OtpDeleteResponse")  # type: ignore[attr-defined]

        with pytest.raises(RuntimeError) as err:
            _ = service.delete("abc")

    assert "Unexpected OTP delete response:" in str(err.value)


@pytest.mark.parametrize(
    ("base", "expected_verify_endpoint", "expected_delete_endpoint"),
    [
        ("", "/verify", "/delete"),
        ("/otp", "/otp/verify", "/otp/delete"),
        ("/otp/", "/otp/verify", "/otp/delete"),
    ],
)
@pytest.mark.utils
def test_base_path_endpoint_construction(
    base: str,
    expected_verify_endpoint: str,
    expected_delete_endpoint: str,
    mock_api: MagicMock,
) -> None:
    """It should rstrip the base path and construct endpoints without double slashes."""
    service = OTPVerificationService(mock_api, base_path=base)

    with patch("utils.api_utils.OtpVerifyRequest") as VReq, patch(
        "utils.api_utils.OtpVerifyResponse"
    ) as VResp, patch("utils.api_utils.mask_otp", return_value="***"):
        vreq = MagicMock()
        vreq.model_dump.return_value = {"id": "X", "otp": "111111"}
        VReq.return_value = vreq
        VResp.model_validate.return_value = {"ok": True}  # type: ignore[attr-defined]
        mock_api.post.return_value = {"ok": True}
        _ = service.verify("X", "111111")
        mock_api.post.assert_called_with(
            endpoint=expected_verify_endpoint,
            body={"id": "X", "otp": "111111"},
            return_json=True,
        )

    mock_api.post.reset_mock()

    with patch("utils.api_utils.OtpDeleteRequest") as DReq, patch(
        "utils.api_utils.OtpDeleteResponse"
    ) as DResp:
        dreq = MagicMock()
        dreq.model_dump.return_value = {"id": "Y"}
        DReq.return_value = dreq
        DResp.model_validate.return_value = {"status": "deleted"}  # type: ignore[attr-defined]
        mock_api.post.return_value = {"status": "deleted"}
        _ = service.delete("Y")
        mock_api.post.assert_called_with(
            endpoint=expected_delete_endpoint, body={"id": "Y"}, return_json=True
        )
