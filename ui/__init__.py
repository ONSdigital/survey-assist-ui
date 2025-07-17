"""Flask application setup for the Survey Assist UI.

This module initializes the Flask application, configures extensions,
and defines the main route for rendering the index page.

Attributes:
    app (Flask): The Flask application instance.
"""

import os

from flask import json, request
from flask_misaka import Misaka
from survey_assist_utils.api_token.jwt_utils import check_and_refresh_token
from survey_assist_utils.logging import get_logger

from ui.routes import register_blueprints
from utils.api_utils import APIClient
from utils.app_types import SurveyAssistFlask

logger = get_logger(__name__)


def create_app(test_config: dict | None = None) -> SurveyAssistFlask:
    """Initialises and configures the Survey Assist Flask application.

    This function sets up the Flask app, loads configuration and survey definition,
    registers blueprints, initialises the API client, and applies test overrides.

    Args:
        test_config (dict | None): Optional dictionary of test configuration overrides.

    Returns:
        SurveyAssistFlask: The initialised and configured Flask application instance.
    """
    flask_app = SurveyAssistFlask(__name__)
    flask_app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))
    flask_app.jwt_secret_path = os.getenv("JWT_SECRET", "SECRET_PATH_NOT_SET")
    flask_app.sa_email = os.getenv("SA_EMAIL", "SA_EMAIL_NOT_SET")
    flask_app.api_base = os.getenv("BACKEND_API_URL", "http://127.0.0.1:5000")

    # API token is generated at runtime, so we set it to an empty string initially
    flask_app.api_token = ""  # nosec
    flask_app.token_start_time = 0

    Misaka(flask_app)

    flask_app.jinja_env.add_extension("jinja2.ext.do")
    flask_app.jinja_env.trim_blocks = True
    flask_app.jinja_env.lstrip_blocks = True
    flask_app.config["FREEZER_IGNORE_404_NOT_FOUND"] = True
    flask_app.config["FREEZER_DEFAULT_MIMETYPE"] = "text/html"
    flask_app.config["FREEZER_DESTINATION"] = "../build"
    flask_app.config["SESSION_DEBUG"] = (
        os.getenv("SESSION_DEBUG", "false").lower() == "true"
    )
    flask_app.config["JSON_DEBUG"] = os.getenv("JSON_DEBUG", "false").lower() == "true"

    # Load the survey definition
    with open("ui/survey/survey_definition.json", encoding="utf-8") as file:
        survey_definition = json.load(file)
        flask_app.survey_title = survey_definition.get(
            "survey_title", "Survey Assist Example"
        )
        flask_app.questions = survey_definition["questions"]
        flask_app.survey_assist = survey_definition["survey_assist"]

    register_blueprints(flask_app)

    # Generate API JWT token
    flask_app.token_start_time, flask_app.api_token = check_and_refresh_token(
        flask_app.token_start_time,
        flask_app.api_token,
        flask_app.jwt_secret_path,
        flask_app.api_base,
        flask_app.sa_email,
    )

    # Initialise API client for Survey Assist
    flask_app.api_client = APIClient(
        base_url=flask_app.api_base,
        token=flask_app.api_token,
        logger=logger,
        redirect_on_error=False,
    )

    # Allow test overrides
    if test_config:
        flask_app.config.update(test_config)

    # Method provides a dictionary to the jinja templates, allowing variables
    # inside the dictionary to be directly accessed within the template files
    # This saves defining navigation variables in each route
    @flask_app.context_processor
    def set_variables():
        """Provides a dictionary to Jinja templates for global navigation variables.

        This function adds a `navigation` dictionary to the Jinja template context,
        allowing templates to directly access navigation variables without needing
        to define them in each route.

        Returns:
            dict: A dictionary containing the `navigation` object.
        """
        navigation = {"navigation": {}}
        return {"navigation": navigation}

    # Check the JWT token status before processing the request
    @flask_app.before_request
    def before_request():
        """Check token status before processing the request."""
        orig_time = app.token_start_time
        app.token_start_time, app.api_token = check_and_refresh_token(
            app.token_start_time,
            app.api_token,
            app.jwt_secret_path,
            app.api_base,
            app.sa_email,
        )

        if orig_time != app.token_start_time:
            logger.info(
                f"JWT token refresh Rx Method: {request.method} - Route: {request.endpoint}"
            )

    logger.info("Flask app initialised with Misaka and Jinja2 extensions.")

    return flask_app


# Create the Flask application instance
app = create_app()
