"""This module defines the index route for the survey assist UI.

This is the home page for the Survey Assist UI
"""

from typing import cast

from flask import Blueprint, current_app, redirect, render_template, session
from flask.typing import ResponseReturnValue
from survey_assist_utils.logging import get_logger

from utils.access_utils import require_access
from utils.app_types import SurveyAssistFlask
from utils.session_utils import log_route, remove_model_from_session, session_debug

main_blueprint = Blueprint("main", __name__)
main_blueprint.before_request(require_access)

logger = get_logger(__name__)


# Method to render the index page
@main_blueprint.route("/")
@session_debug
@log_route()
def index() -> ResponseReturnValue:
    """Renders the index page.

    This route handles requests to the root URL ("/") and serves the `index.html` template.

    Returns:
        str: Rendered HTML content of the index page.
    """
    app = cast(SurveyAssistFlask, current_app)

    if "participant_id" not in session and "access_code" not in session:
        return redirect("/access")

    # Reset the current question index in the session
    if "current_question_index" in session:
        session["current_question_index"] = 0

    # Remove the survey_result if it exists
    remove_model_from_session("survey_result")

    # Reset the rerouted flag in the session
    if "rerouted" in session:
        session["rerouted"] = False

    return render_template(
        "index.html", survey_title=app.survey_title, show_intro=app.survey_intro
    )
