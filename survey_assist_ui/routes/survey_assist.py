"""This module defines the Survey Assist route for the Survey Assist UI.

This is the Survey Assist Interaction interface for the Survey Assist UI
"""

from flask import (
    Blueprint,
    session,
)
from survey_assist_utils.logging import get_logger

from utils.access_utils import require_access
from utils.app_types import ResponseType
from utils.session_utils import log_route, session_debug
from utils.survey_assist_utils import classify_and_handle_followup

survey_assist_blueprint = Blueprint("survey_assist", __name__)
survey_assist_blueprint.before_request(require_access)

logger = get_logger(__name__, level="INFO")


@survey_assist_blueprint.route("/survey-assist", methods=["GET", "POST"])
@session_debug
@log_route()
def survey_assist() -> ResponseType | str:
    """Renders the Survey Assist Interaction.

    This route handles requests to the Survey Assist Interaction,
    performs the necessary API requests to the Survey Assist service,
    and serves the `survey_assist.html` template.

    Returns:
        str: Rendered HTML content of the Survey Assist Interaction.
    """
    job_description = session.get("response", {}).get("job_description")
    job_title = session.get("response", {}).get("job_title")
    org_description = session.get("response", {}).get("organisation_activity")

    return classify_and_handle_followup(job_title, job_description, org_description)
