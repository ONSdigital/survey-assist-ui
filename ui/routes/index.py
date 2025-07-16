"""This module defines the index route for the survey assist UI.

This is the home page for the Survey Assist UI
"""

from typing import cast

from flask import Blueprint, current_app, render_template, session
from survey_assist_utils.logging import get_logger

from utils.app_types import SurveyAssistFlask
from utils.session_utils import session_debug

main_blueprint = Blueprint("main", __name__)

logger = get_logger(__name__)


# Method to render the index page
@main_blueprint.route("/")
@session_debug
def index() -> str:
    """Renders the index page.

    This route handles requests to the root URL ("/") and serves the `index.html` template.

    Returns:
        str: Rendered HTML content of the index page.
    """
    logger.info("Rendering index page")

    app = cast(SurveyAssistFlask, current_app)

    # Reset the current question index in the session
    if "current_question_index" in session:
        session["current_question_index"] = 0
        session.modified = True

    return render_template("index.html", survey_title=app.survey_title)
