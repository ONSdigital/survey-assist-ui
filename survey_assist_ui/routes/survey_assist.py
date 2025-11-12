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
from utils.input_utils import replace_if_no_letters
from utils.session_utils import get_person_id, log_route, session_debug
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

    # Retrieve the survey data from the session
    survey_iteration = session.get("survey_iteration", {})
    questions = survey_iteration.get("questions", [])

    # Create a lookup for the response_name values to extract
    target_fields = {
        "job-description": None,
        "job-title": None,
        "organisation-activity": None,
    }

    # Iterate over all questions and capture matching responses
    for q in questions:
        response_name = q.get("response_name")
        if response_name in target_fields:
            target_fields[response_name] = q.get("response")

    # Use the information from the survey_iteration as
    # these values are sanitized, check for input that contains no letters
    person_id = get_person_id()
    job_description = replace_if_no_letters(person_id, target_fields["job-description"])
    job_title = replace_if_no_letters(person_id, target_fields["job-title"])
    org_description = replace_if_no_letters(
        person_id, target_fields["organisation-activity"]
    )

    # Keep the responses list to a minimum as the data is stored in
    # survey_iteration from here on in.
    # REFACTOR: The response dictionary should be retired entirely in favour of
    # survey_iteration but this is a larger change.
    for key in ("job_title", "job_description", "organisation_activity"):
        if key in session["response"] and isinstance(session["response"][key], str):
            session["response"][key] = session["response"][key][:10]

    return classify_and_handle_followup(
        job_title, job_description, org_description  # type: ignore[arg-type]
    )
