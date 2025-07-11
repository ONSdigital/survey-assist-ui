"""This module defines the Survey Assist route for the Survey Assist UI.

This is the Survey Assist Interaction interface for the Survey Assist UI
"""

from typing import cast

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    session,
    url_for,
)
from survey_assist_utils.logging import get_logger

from utils.app_types import ResponseType, SurveyAssistFlask
from utils.session_utils import session_debug
from utils.survey_assist_utils import handle_sic_interaction

survey_assist_blueprint = Blueprint("survey_assist", __name__)

logger = get_logger(__name__, level="DEBUG")


@survey_assist_blueprint.route("/survey-assist", methods=["GET", "POST"])
@session_debug
def survey_assist() -> ResponseType | str:
    """Renders the Survey Assist Interaction.

    This route handles requests to the Survey Assist Interaction,
    performs the necessary API requests to the Survey Assist service,
    and serves the `survey_assist.html` template.

    Returns:
        str: Rendered HTML content of the Survey Assist Interaction.
    """
    logger.info("Rendering survey assist page")

    # Find the question about job_title --- TODO NEED To CHeck if EMPTY
    user_response = session.get("response")

    logger.debug(f"User response: {user_response}")

    app = cast(SurveyAssistFlask, current_app)
    survey_assist_data = app.survey_assist

    # If survey assist is not enabled, redirect to the survey page
    if not survey_assist_data.get("enabled", True):
        logger.warning("Survey Assist is not enabled, redirecting to survey page")
        return redirect(url_for("survey.survey"))
    else:
        # If survey assist is enabled, determine the type of interaction
        interactions = survey_assist_data.get("interactions", [])
        if not interactions:
            logger.warning("No interactions defined for Survey Assist")
            return redirect(url_for("survey.survey"))

        if len(interactions) > 0:
            interaction = interactions[0]

            logger.debug(f"Processing interaction: {interaction}")

            interaction_type = interaction.get("type", None)
            logger.debug(f"Survey Assist interaction type: {interaction_type}")

            # Check if the interaction requires consent
            if interaction_type == "lookup_classification":
                logger.info("Interaction type is lookup_classification")
                interaction_param = interaction.get("param", None)
                if interaction_param == "sic":
                    return handle_sic_interaction(user_response)
                else:
                    logger.warning(
                        f"Unsupported interaction param: {interaction_param}"
                    )
                    return redirect(url_for("survey.question_template"))
            else:
                logger.error(
                    f"Interaction type {interaction_type} found, redirecting to survey page"
                )
                return redirect(url_for("survey.survey"))

    return render_template("survey_assist.html")
