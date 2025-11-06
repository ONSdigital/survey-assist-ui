"""Access and login routes for the Survey Assist UI.

Verifies that the user has a valid code for access to the survey.
"""

from typing import cast

from flask import Blueprint, current_app, redirect, render_template, request, session
from survey_assist_utils.logging import get_logger

from utils.access_utils import format_access_code, validate_access
from utils.api_utils import mask_otp
from utils.app_types import SurveyAssistFlask
from utils.session_utils import log_route, session_debug

access_blueprint = Blueprint("access", __name__)

logger = get_logger(__name__, "DEBUG")


@access_blueprint.route("/access", methods=["GET"])
@session_debug
@log_route(participant_override="unavailable")
def access():
    """Renders the access page.

    Returns:
        tuple: Rendered HTML for access page.
    """
    app = cast(SurveyAssistFlask, current_app)
    return render_template("access.html", title=app.survey_title)


@access_blueprint.route("/check_access", methods=["POST"])
@log_route(participant_override="unavailable")
def check_access():
    """Checks participant access credentials and redirects accordingly.

    Retrieves the participant ID and access code from the form, formats the access code,
    and validates the credentials. If valid, stores the participant ID in the session and
    redirects to the home page. If invalid, re-renders the access page with an error.

    Returns:
        Response: A redirect to the home page if credentials are valid, otherwise the
        rendered access page with an error message.
    """
    app = cast(SurveyAssistFlask, current_app)
    participant_id = request.form.get("participant-id").upper()
    access_code = format_access_code(request.form.get("access-code"))

    logger.debug(f"participant_id:{participant_id} access code:{mask_otp(access_code)}")
    valid, error = validate_access(participant_id, access_code)
    if valid:
        session["participant_id"] = participant_id
        session["access_code"] = mask_otp(access_code)
        session.modified = True
        logger.info(f"participant_id:{participant_id} survey accessed")
        return redirect("/")
    else:
        return render_template(
            "access.html",
            title=app.survey_title,
            error=error,
        )
