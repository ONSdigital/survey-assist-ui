"""This module defines the Survey Assist route for the Survey Assist UI.

This is the Survey Assist Interaction interface for the Survey Assist UI
"""

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    session,
    url_for,
)
from survey_assist_utils.logging import get_logger

from models.api_map import map_api_response_to_internal
from utils.session_utils import session_debug
from utils.survey_assist_utils import classify, format_followup, get_next_followup

survey_assist_blueprint = Blueprint("survey_assist", __name__)

logger = get_logger(__name__, level="DEBUG")

# This is temporary, will be changed to configurable in the future
FOLLOW_UP_TYPE = "both"  # Options: open, closed, both


@survey_assist_blueprint.route("/survey-assist", methods=["GET", "POST"])
@session_debug
def survey_assist() -> str:
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

    # If survey assist is not enabled, redirect to the survey page
    if not current_app.survey_assist.get("enabled", True):
        logger.warning("Survey Assist is not enabled, redirecting to survey page")
        return redirect(url_for("survey.survey"))
    else:
        # If survey assist is enabled, determine the type of interaction
        survey_assist = current_app.survey_assist
        interactions = survey_assist.get("interactions", [])
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
                    logger.info("SIC lookup interaction found")
                    org_description = user_response.get("organisation_activity")
                    job_title = user_response.get("job_title")
                    job_description = user_response.get("job_description")

                    # Perform SIC lookup
                    api_client = current_app.api_client
                    api_url = f"/survey-assist/sic-lookup?description={org_description}&similarity=true"

                    if org_description:
                        response = api_client.get(endpoint=api_url)
                        logger.debug(f"SIC lookup response: {response}")
                        session.modified = True

                        if response:
                            lookup_code = response.get("code", None)
                            # Perform the classification
                            if lookup_code:
                                logger.info(
                                    "Skip classify. SIC lookup successful org: {org_description} code: {lookup_code}"
                                )
                            else:
                                logger.info(
                                    "SIC lookup failed, redirecting to classify"
                                )

                                classification = classify(
                                    type="sic",
                                    job_title=job_title,
                                    job_description=job_description,
                                    org_description=org_description,
                                )
                                logger.debug(
                                    f"Classification response: {classification}"
                                )

                                mapped_api_response = map_api_response_to_internal(
                                    classification
                                )
                                logger.debug(f"Mapped response: {mapped_api_response}")

                                followup_questions = mapped_api_response.get(
                                    "follow_up", {}
                                ).get("questions", [])

                                # If at least one question is available, loop through the questions
                                # and print the question text
                                if followup_questions:

                                    question = get_next_followup(
                                        followup_questions, FOLLOW_UP_TYPE
                                    )
                                    if question:
                                        question_text, question_data = question
                                        logger.debug(
                                            f"Next follow-up question: {question_text}"
                                        )
                                        logger.debug(f"Question data: {question_data}")

                                        formatted_question = format_followup(
                                            question_data=question_data,
                                            question_text=question_text,
                                        )

                                        return render_template(
                                            "question_template.html",
                                            **formatted_question.to_dict(),
                                        )

                        else:
                            logger.error("SIC lookup API request failure")
                    else:
                        logger.info(
                            "No organisation activity provided for SIC lookup. Try classify"
                        )
                        classification = classify(
                            type="sic",
                            job_title=job_title,
                            job_description=job_description,
                            org_description=org_description,
                        )

                        logger.debug(f"Classification response: {classification}")

                return redirect(url_for("survey.question_template"))
            else:
                logger.error(
                    f"Interaction type {interaction_type} found, redirecting to survey page"
                )
                return redirect(url_for("survey.survey"))

    return render_template("survey_assist.html")
