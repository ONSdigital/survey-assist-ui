from http import HTTPStatus
from typing import Optional

import requests
from flask import jsonify, redirect, url_for

API_TIMER_SEC = 10


class APIClient:
    def __init__(
        self, base_url: str, token: str, logger, redirect_on_error: bool = False
    ):
        self.base_url = base_url
        self.token = token
        self.logger = logger
        self.redirect_on_error = redirect_on_error

    def _default_headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def get(
        self,
        endpoint: str,
        headers: Optional[dict] = None,
        logger=None,
        return_json: bool = True,
    ):
        return self._request(
            "GET", endpoint, headers=headers, logger=logger, return_json=return_json
        )

    def post(
        self,
        endpoint: str,
        body: Optional[dict] = None,
        headers: Optional[dict] = None,
        logger=None,
        return_json: bool = True,
    ):
        return self._request(
            "POST",
            endpoint,
            body=body,
            headers=headers,
            logger=logger,
            return_json=return_json,
        )

    def _request(  # noqa: PLR0913, C901
        self,
        method: str,
        endpoint: str,
        body: Optional[dict] = None,
        headers: Optional[dict] = None,
        logger=None,
        return_json: bool = True,
    ):
        url = f"{self.base_url}{endpoint}"
        combined_headers = {**self._default_headers(), **(headers or {})}

        if logger is None:
            logger = self.logger

        logger.info(f"Sending {method} request to {url} with body: {body}")
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
            logger.info(f"Received response from {url}: {data}")

        except requests.exceptions.Timeout:
            logger.error(f"Request to {url} timed out after {API_TIMER_SEC} seconds")
            error = "Request timed out"
            status_code = HTTPStatus.GATEWAY_TIMEOUT
        except requests.exceptions.ConnectionError:
            logger.error(f"Failed to connect to API at {url}")
            error = "Failed to connect to API"
            status_code = HTTPStatus.BAD_GATEWAY
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err}")
            error = f"HTTP error: {http_err.response.status_code}"
        except ValueError as val_err:
            logger.error(f"Value error: {val_err}")
            error = f"Value error: {val_err}"
        except KeyError as key_err:
            logger.error(f"Missing expected data in response: {key_err}")
            error = f"Missing expected data: {key_err}"
            status_code = HTTPStatus.BAD_GATEWAY
        except Exception as e:
            logger.exception(f"Unexpected error occurred: {e}")
            error = f"Unexpected error: {e!s}"

        if error:
            return self._handle_error(error, status_code)

        return data

    def _handle_error(self, message, status_code):
        self.logger.exception(message)
        if self.redirect_on_error:
            return redirect(url_for("error_page"))
        return jsonify({"error": message}), status_code
