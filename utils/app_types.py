"""Type definitions and custom Flask app class for Survey Assist UI.

This module provides type aliases and a custom Flask app class with additional attributes
for use in the Survey Assist UI application.
"""

from typing import Any, Union

from flask import Flask
from flask import Response as FlaskResponse
from werkzeug.wrappers import Response as WerkzeugResponse

# Type alias for the response type used in the application
ResponseType = Union[FlaskResponse, WerkzeugResponse]


class SurveyAssistFlask(Flask):
    """Custom Flask app class with additional attributes for Survey Assist.

    Attributes:
        api_client (Any): The API client instance for external requests.
        api_base (str): The base URL for the API.
        api_ver (str): The version of the API (defaults to v1).
        api_token (str): The API authentication token.
        jwt_secret_path (str): Path to the JWT secret file.
        sa_email (str): Survey Assist service account.
        survey_title (str): Title of the survey.
        survey_assist (dict[str, Any]): Survey Assist configuration dictionary.
        token_start_time (int): Start time for the authentication token.
        questions (list[dict[str, Any]]): List of survey question dictionaries.
    """

    api_client: Any
    api_base: str
    api_ver: str
    api_token: str
    jwt_secret_path: str
    sa_email: str
    survey_title: str
    survey_assist: dict[str, Any]
    token_start_time: int
    questions: list[dict[str, Any]]
