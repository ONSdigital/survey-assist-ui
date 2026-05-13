"""Smoke Tests for the Survey UI."""

import os, json

import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry


class TestSurveyAssistUI:
    """Smoke Tests for the Survey Assist UI."""

    target_environment = os.environ.get("TARGET_ENVIRONMENT")
    if target_environment is None:
        print("TARGET_ENVIRONMENT environment variable is not set. Optionally, set this to select the environment to proxy to i.e. sandbox(default), dev or preprod.")
        target_environment = "sandbox"

    url_base = os.environ.get("SURVEY_ASSIST_UI_URL")
    if url_base is None:
        raise ValueError("SURVEY_ASSIST_UI_URL environment variable is not set.")

    id_token = os.environ.get("UI_SA_ID_TOKEN")
    if id_token is None:
        raise ValueError("UI_SA_ID_TOKEN environment variable is not set.")

    git_short_sha = os.environ.get("GIT_SHORT_SHA")
    if git_short_sha is None:
        print("GIT_SHORT_SHA environment variable is not set. Optionally, set this to assert the meta data value matches.")

    def test_survey_assist_api_status(self) -> None:
        """Test Survey Assist UI returns successful /meta response (via proxy API)."""


        endpoint = f"{self.url_base}/survey-ui/meta/{self.target_environment}"

        print(f"Calling {endpoint}...")
        response = requests.get(
            endpoint,
            headers={"Authorization": f"Bearer {self.id_token}"},
            timeout=30,
        )

        print("Checking status code is 200..")
        assert (  # noqa: S101
            response.status_code == 200  # noqa: PLR2004
        ), f"Expected status code 200, but got {response.status_code}."

        if self.git_short_sha:
            print(f"Checking git short sha matches the expected value {self.git_short_sha}..")
            response_json = response.json()
            assert self.git_short_sha == response_json["git_sha"]