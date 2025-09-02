"""Error routes for the Survey Assist UI.

Provides error handling and rendering for common error pages.
"""

from flask import Blueprint, render_template
from survey_assist_utils.logging import get_logger

from utils.session_utils import session_debug

error_blueprint = Blueprint("error", __name__)

logger = get_logger(__name__)


@error_blueprint.errorhandler(404)
@error_blueprint.route("/page-not-found")
@session_debug
def page_not_found(e=None):
    """Renders the 404 error page.

    Args:
        e (Exception, optional): The exception that triggered the error handler. Defaults to None.

    Returns:
        tuple: Rendered HTML for the 404 page and the HTTP status code.
    """
    return render_template("404.html"), 404 if e else 200
