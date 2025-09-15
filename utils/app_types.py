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
        sa_email (str): Survey Assist service account.
        survey_title (str): Title of the survey.
        survey_intro (bool): Is survey intro enabled or not.
        show_consent (bool): Should the consent be shown before Survey Assist questions.
        survey_assist (dict[str, Any]): Survey Assist configuration dictionary.
        token_start_time (int): Start time for the authentication token.
        questions (list[dict[str, Any]]): List of survey question dictionaries.
        show_feedback (bool): Display feedback questions.
        feedback: (list[dict[str, Any]]): Feedback config and list of feedback questions
    """

    api_client: Any
    api_base: str
    api_ver: str
    api_token: str
    sa_email: str
    survey_title: str
    survey_intro: bool
    show_consent: bool
    survey_assist: dict[str, Any]
    token_start_time: int
    questions: list[dict[str, Any]]
    show_feedback: bool
    feedback: dict[str, Any]
