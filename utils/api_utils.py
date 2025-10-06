"""API utility functions and client for Survey Assist UI.

This module provides an API client class for making HTTP requests to external APIs
and handling errors in a Flask application.

poetry run python scripts/run_api.py --action config
poetry run python scripts/run_api.py --type sic --action lookup
poetry run python scripts/run_api.py --type sic --action classify
poetry run python scripts/run_api.py --type sic --action both
"""

import subprocess  # nosec
from http import HTTPStatus
from shutil import which
from typing import Optional

import requests
from flask import jsonify, redirect, url_for
from survey_assist_utils.logging import get_logger

from models.result import (
    LookupResponse,
    PotentialCode,
    PotentialDivision,
)

API_TIMER_SEC = 10
logger = get_logger(__name__, level="DEBUG")


# Disabling pylint warning for too many arguments/locals in APIClient class
# This is to maintain clarity in the APIClient constructor and methods.
# pylint: disable=too-many-arguments,too-many-positional-arguments, too-many-locals
class APIClient:
    """API client for making HTTP requests to external APIs in Survey Assist UI.

    This class provides methods for sending GET and POST requests, handling errors,
    and managing authentication for API calls within a Flask application.
    """

    def __init__(
        self, base_url: str, token: str, logger_handle, redirect_on_error: bool = False
    ):
        """Initialises the API client with base URL, token, and logger.

        Args:
            base_url (str): The base URL for the API.
            token (str): The authentication token for API requests.
            logger_handle: Logger instance for logging messages.
            redirect_on_error (bool): Whether to redirect on error.
        """
        self.base_url = base_url
        self.token = token
        self.logger_handle = logger_handle
        self.redirect_on_error = redirect_on_error

    def _default_headers(self):
        """Returns the default headers for API requests.

        Returns:
            dict: Dictionary containing the authorisation header.
        """
        return {"Authorization": f"Bearer {self.token}"}

    def get(
        self,
        endpoint: str,
        headers: Optional[dict] = None,
        logger_handle=None,
        return_json: bool = True,
    ):
        """Sends a GET request to the specified API endpoint.

        Args:
            endpoint (str): The API endpoint to send the request to.
            headers (dict, optional): Additional headers for the request.
            logger_handle (optional): Logger instance for logging messages.
            return_json (bool): Whether to return JSON response.

        Returns:
            dict or str: The API response data.
        """
        return self._request(
            "GET",
            endpoint,
            headers=headers,
            logger_handle=logger_handle,
            return_json=return_json,
        )

    def post(
        self,
        endpoint: str,
        body: Optional[dict] = None,
        headers: Optional[dict] = None,
        logger_handle=None,
        return_json: bool = True,
    ):
        """Sends a POST request to the specified API endpoint.

        Args:
            endpoint (str): The API endpoint to send the request to.
            body (dict, optional): The request body as a dictionary.
            headers (dict, optional): Additional headers for the request.
            logger_handle (optional): Logger instance for logging messages.
            return_json (bool): Whether to return JSON response.

        Returns:
            dict or str: The API response data.
        """
        return self._request(
            "POST",
            endpoint,
            body=body,
            headers=headers,
            logger_handle=logger_handle,
            return_json=return_json,
        )

    def _request(  # noqa: PLR0913, C901
        self,
        method: str,
        endpoint: str,
        body: Optional[dict] = None,
        headers: Optional[dict] = None,
        logger_handle=None,
        return_json: bool = True,
    ):
        """Sends an HTTP request to the specified API endpoint.

        Args:
            method (str): The HTTP method ("GET" or "POST").
            endpoint (str): The API endpoint to send the request to.
            body (dict, optional): The request body for POST requests.
            headers (dict, optional): Additional headers for the request.
            logger_handle (optional): Logger instance for logging messages.
            return_json (bool): Whether to return JSON response.

        Returns:
            dict or str: The API response data, or error response if an error occurs.

        Raises:
            ValueError: If an unsupported HTTP method is provided.
        """
        url = f"{self.base_url}{endpoint}"
        combined_headers = {**self._default_headers(), **(headers or {})}

        if logger_handle is None:
            logger_handle = self.logger_handle

        logger_handle.info(f"Sending {method} request to {url}")

        # GET requests don't contain a body
        if body is not None:
            logger_handle.info(body)
        data = None
        error = None
        status_code = HTTPStatus.INTERNAL_SERVER_ERROR

        try:
            if method == "GET":
                response = requests.get(
                    url, headers=combined_headers, timeout=API_TIMER_SEC
                )
            elif method == "POST":
                response = requests.post(
                    url, json=body, headers=combined_headers, timeout=API_TIMER_SEC
                )
            else:
                raise ValueError(f"Unsupported method: {method}")

            response.raise_for_status()
            data = response.json() if return_json else response.text
            logger_handle.info(f"Received response from {url}")
            logger_handle.info(data)

        except requests.exceptions.Timeout:
            logger_handle.error(
                f"Request to {url} timed out after {API_TIMER_SEC} seconds"
            )
            error = "Request timed out"
            status_code = HTTPStatus.GATEWAY_TIMEOUT
        except requests.exceptions.ConnectionError:
            logger_handle.error(f"Failed to connect to API at {url}")
            error = "Failed to connect to API"
            status_code = HTTPStatus.BAD_GATEWAY
        except requests.exceptions.HTTPError as http_err:
            logger_handle.error(f"HTTP error occurred: {http_err}")
            error = f"HTTP error: {http_err.response.status_code}"
        except ValueError as val_err:
            logger_handle.error(f"Value error: {val_err}")
            error = f"Value error: {val_err}"
        except KeyError as key_err:
            logger_handle.error(f"Missing expected data in response: {key_err}")
            error = f"Missing expected data: {key_err}"
            status_code = HTTPStatus.BAD_GATEWAY
        except (TypeError, AttributeError) as exc:
            logger_handle.error(f"Unexpected type or attribute error: {exc}")
            error = f"Unexpected error: {exc!s}"

        if error:
            return self._handle_error(error, status_code)

        return data

    def _handle_error(self, message, status_code):
        """Handles API errors and returns a Flask response.

        Args:
            message (str): The error message to log and return.
            status_code (int): The HTTP status code for the error response.

        Returns:
            Response: A Flask redirect or JSON error response.
        """
        self.logger_handle.error(message)
        if self.redirect_on_error:
            return redirect(url_for("error_page"))
        return jsonify({"error": message}), status_code


def map_to_lookup_response(
    data: dict,
    max_codes: Optional[int] = None,
    max_divisions: Optional[int] = None,
) -> LookupResponse:
    """Maps raw API data to a LookupResponse, with optional limits on results.

    Args:
        data: The raw dictionary from the API.
        max_codes: Optional maximum number of codes to include.
        max_divisions: Optional maximum number of divisions to include.

    Returns:
        A populated LookupResponse object.
    """
    found = data.get("code") is not None

    code = data.get("code")
    code_division = data.get("code_division")

    codes = data.get("potential_matches", {}).get("codes") or []
    codes_count = data.get("potential_matches", {}).get("codes_count") or 0
    divisions = data.get("potential_matches", {}).get("divisions") or []
    divisions_count = data.get("potential_matches", {}).get("divisions_count") or 0

    # Apply limits
    if max_codes is not None and codes_count > max_codes:
        logger.info(
            f"Limit potential sic-lookup codes to {max_codes}, received {codes_count}"
        )
        codes = codes[:max_codes]

    if max_divisions is not None and divisions_count > max_divisions:
        logger.info(
            f"Limit potential sic-lookup divisions to {max_divisions}, received {divisions_count}"
        )
        divisions = divisions[:max_divisions]

    potential_codes = [PotentialCode(code=code, description="") for code in codes]

    potential_divisions = [
        PotentialDivision(
            code=div.get("code", ""),
            title=div.get("meta", {}).get("title", ""),
            detail=div.get("meta", {}).get("detail", None),
        )
        for div in divisions
    ]

    return LookupResponse(
        found=found,
        code=code,
        code_division=code_division,
        potential_codes_count=len(potential_codes),
        potential_codes=potential_codes,
        potential_divisions=potential_divisions,
    )


def get_verification_api_id_token():
    """Generates a Google identity token for the Firestore OTP API.

    This function uses the Google Cloud CLI (`gcloud`) to generate an identity token
    for authenticating requests to the Firestore OTP API. The command is executed
    using a subprocess call with hardcoded arguments, ensuring no untrusted input
    is passed to the shell.

    Returns:
        str: The generated Google identity token.

    Raises:
        RuntimeError: If the `gcloud` CLI is not found in the system PATH.
        subprocess.CalledProcessError: If the subprocess call fails.
    """
    # Lint errors are ok to ignore since the code does not pass user input
    # to the subprocess, values are hardcoded and therefore valid
    gcloud = which("gcloud")
    if not gcloud:
        raise RuntimeError("gcloud not found in PATH")

    gcloud_print_id_token = subprocess.check_output(  # noqa: S603 # nosec: B603
        [gcloud, "auth", "print-identity-token"]
    )
    id_token = gcloud_print_id_token.decode().strip()
    return id_token
