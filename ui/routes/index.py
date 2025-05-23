"""This module defines the index route for the survey assist UI.

This is the home page for the Survey Assist UI
"""

from flask import Blueprint, render_template, session
from survey_assist_utils.logging import get_logger

from utils.session_utils import session_debug
from utils.survey import add_numbers

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
    add_numbers(1, 2)
    return render_template("index.html")
