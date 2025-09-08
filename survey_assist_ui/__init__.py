"""Flask application setup for the Survey Assist UI.

This module initializes the Flask application, configures extensions,
and defines the main route for rendering the index page.

Attributes:
    app (Flask): The Flask application instance.
"""

import os
from urllib.parse import urlparse

from flask import json, request
from flask_misaka import Misaka
from survey_assist_utils.api_token.jwt_utils import check_and_refresh_token
from survey_assist_utils.logging import get_logger

from survey_assist_ui.routes import register_blueprints
from utils.api_utils import APIClient
from utils.app_types import SurveyAssistFlask

from .versioning import get_app_version

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
    flask_app.sa_email = os.getenv("SA_EMAIL", "SA_EMAIL_NOT_SET")
    flask_app.api_base = os.getenv("BACKEND_API_URL", "http://127.0.0.1:5000")
    flask_app.api_ver = os.getenv("BACKEND_API_VERSION", "/v1")

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
    with open(
        "survey_assist_ui/survey/survey_definition.json", encoding="utf-8"
    ) as file:
        survey_definition = json.load(file)
        flask_app.survey_title = survey_definition.get(
            "survey_title", "Survey Assist Example"
        )

        survey_intro = survey_definition.get("survey_intro", {})
        if isinstance(survey_intro, dict):
            flask_app.survey_intro = survey_intro.get("enabled", False)
        else:
            flask_app.survey_intro = False

        flask_app.questions = survey_definition["questions"]
        flask_app.survey_assist = survey_definition["survey_assist"]

    register_blueprints(flask_app)

    parsed = urlparse(flask_app.api_base)
    gw_hostname = parsed.netloc.rstrip("/")
    flask_app.token_start_time, flask_app.api_token = check_and_refresh_token(
        flask_app.token_start_time,
        flask_app.api_token,
        gw_hostname,
        flask_app.sa_email,
    )

    # Initialise API client for Survey Assist
    flask_app.api_client = APIClient(
        base_url=f"{flask_app.api_base}{flask_app.api_ver}",
        token=flask_app.api_token,
        logger_handle=logger,
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

        parsed = urlparse(flask_app.api_base)
        gw_hostname = parsed.netloc.rstrip("/")

        app.token_start_time, app.api_token = check_and_refresh_token(
            app.token_start_time,
            app.api_token,
            gw_hostname,
            app.sa_email,
        )

        if orig_time != app.token_start_time:
            logger.info(
                f"JWT token refresh Rx Method: {request.method} - Route: {request.endpoint}"
            )

    @flask_app.after_request
    def add_version_header(resp):
        """Add a version header to requests to trace deployed software version."""
        resp.headers["X-App-Version"] = get_app_version()
        resp.headers["X-App-Revision"] = os.environ.get("APP_GIT_SHA", "unknown")
        return resp

    logger.info(f"Survey Assist UI initialised - version {get_app_version()}")

    return flask_app


# Create the Flask application instance
app = create_app()
