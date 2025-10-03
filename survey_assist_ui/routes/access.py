"""Access and login routes for the Survey Assist UI.

Verifies that the user has a valid code for access to the survey.
"""

from flask import Blueprint, redirect, render_template, request, session
from survey_assist_utils.logging import get_logger

from utils.access_utils import validate_access
from utils.session_utils import session_debug

access_blueprint = Blueprint("access", __name__)

logger = get_logger(__name__, "DEBUG")


@access_blueprint.route("/access", methods=["GET"])
@session_debug
def access():
    """Renders the access page.

    Returns:
        tuple: Rendered HTML for access page.
    """
    return render_template("access.html")


@access_blueprint.route("/check_access", methods=["POST"])
def check_access():
    # Get email and convert to lowercase
    access_id = request.form.get("email-username").lower()
    access_otp = request.form.get("password")

    if validate_access(access_id, access_otp):
        session["access_id"] = access_id
        session.modified = True
        logger.info(f"id: {access_id} successfully accessed survey")
        return redirect("/")
    else:
        return render_template(
            "access.html", error="Invalid credentials. Please try again."
        )
