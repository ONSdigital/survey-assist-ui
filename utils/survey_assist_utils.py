"""Survey Assist utility functions for classification, follow-up, and SIC lookup.

This module provides helper functions for classifying survey responses, handling follow-up
questions, and performing SIC code lookups.
"""

from typing import Optional, cast

from flask import current_app, redirect, render_template, session, url_for
from survey_assist_utils.logging import get_logger

from models.api_map import map_api_response_to_internal
from models.question import Question
from utils.app_types import SurveyAssistFlask
from utils.session_utils import add_question_to_survey

# This is temporary, will be changed to configurable in the future
SHOW_CONSENT = True  # Whether to show the consent page
FOLLOW_UP_TYPE = "both"  # Options: open, closed, both

logger = get_logger(__name__)


def classify(
    classification_type: str, job_title: str, job_description: str, org_description: str
) -> Optional[dict]:
    """Classifies the given parameters using the API client.

    Args:
        classification_type (str): The type of classification to perform.
        job_title (str): The job title to classify.
        job_description (str): The job description to classify.
        org_description (str): The organisation description to classify.

    Returns:
        Optional[dict]: The classification response dictionary, or None if classification fails.
    """
    app = cast(SurveyAssistFlask, current_app)
    api_client = app.api_client
    response = api_client.post(
        "/survey-assist/classify",
        body={
            "llm": "gemini",
            "type": classification_type,
            "job_title": job_title,
            "job_description": job_description,
            "org_description": org_description,
        },
    )

    if isinstance(response, dict):
        logger.info(f"Successfully classified {classification_type}.")
        return response
    logger.error(f"Failed to classify {classification_type}.")
    return None


def get_next_followup(
    followup_questions: list[dict],
    question_type: str,
) -> tuple[str, dict] | None:
    """Add follow-up questions to the session and return the next one.

    This function stores incoming follow-up questions in the session's "follow_up"
    list, then retrieves the next question based on the specified order.

    Args:
        followup_questions (list[dict]): A list of follow-up question dictionaries to add.
        question_type (str): Determines how to retrieve the next question.
            - "open": retrieve from the beginning of the list.
            - "closed": retrieve from the end.
            - "both": behave the same as "open".

    Returns:
        tuple[str, dict] | None: A tuple containing the question text and full question dictionary,
        or None if no questions are available or the order is invalid.
    """
    logger.debug(f"Follow-up questions: {followup_questions}")

    if "follow_up" not in session:
        session["follow_up"] = []

    session["follow_up"].extend(followup_questions)
    session.modified = True

    followup_list = session.get("follow_up", [])
    if not followup_list:
        logger.warning("No follow-up questions available in session.")
        return None

    if question_type in ("open", "both"):
        question_data = followup_list.pop(0)
    elif question_type == "closed":
        question_data = followup_list.pop(-1)
    else:
        logger.warning(f"Invalid question_type: {question_type}")
        return None

    session["follow_up"] = followup_list
    logger.debug(f"Updated follow-up list: {session['follow_up']}")
    session.modified = True

    question_text = question_data.get("question_text", "")
    return question_text, question_data


def format_followup(question_data: dict, question_text: str) -> Question:
    """Formats a follow-up question and stores it in session.

    This function creates a Question object from raw follow-up question data
    and appends it to the session's "follow_up" list.

    Args:
        question_data (dict): Dictionary containing follow-up question fields,
            including 'follow_up_id', 'question_name', 'response_type',
            and optionally 'select_options'.
        question_text (str): The main text content of the question to be displayed.

    Returns:
        Question: An instance representing the formatted follow-up question.
    """
    response_type = question_data["response_type"]
    response_options = []

    # If the response type is "select", build the options
    if response_type == "select":
        response_options = [
            {
                "id": f"{option}-id",
                "label": {"text": option},
                "value": option,
            }
            for option in question_data.get("select_options", [])
        ]

    formatted_question = Question(
        question_id=question_data["follow_up_id"],
        question_name=question_data["question_name"],
        question_title=question_data["question_name"],
        question_text=question_text,
        question_description="This question is generated by Survey Assist",
        response_type=response_type,
        response_options=response_options,
    )

    logger.debug(f"Formatted question: {formatted_question.to_dict()}")

    return formatted_question


def handle_sic_interaction(user_response):
    """Handles SIC code lookup interaction for a user's survey response.

    Args:
        user_response (dict): Dictionary containing user response fields.

    Returns:
        Response: Redirect or rendered template based on SIC lookup and classification results.
    """
    logger.info("SIC lookup interaction found")

    org_description = user_response.get("organisation_activity")
    job_title = user_response.get("job_title")
    job_description = user_response.get("job_description")

    if not org_description:
        logger.info("No organisation activity provided for SIC lookup. Try classify")
        return classify_and_redirect(job_title, job_description, org_description)

    response = perform_sic_lookup(org_description)

    if not response:
        logger.error("SIC lookup API request failure")
        return redirect(url_for("survey.question_template"))

    lookup_code = response.get("code")
    if lookup_code:
        logger.info(
            f"Skip classify. SIC lookup successful org: {org_description} code: {lookup_code}"
        )
        return redirect(url_for("survey.question_template"))

    logger.info("SIC lookup failed, redirecting to classify")
    return classify_and_handle_followup(job_title, job_description, org_description)


def perform_sic_lookup(org_description: str) -> dict | None:
    """Performs a SIC code lookup using the API client.

    Args:
        org_description (str): The organisation description to look up.

    Returns:
        dict | None: The API response dictionary, or None if lookup fails.
    """
    app = cast(SurveyAssistFlask, current_app)
    api_client = app.api_client
    api_url = f"/survey-assist/sic-lookup?description={org_description}&similarity=true"
    response = api_client.get(endpoint=api_url)
    logger.debug(f"SIC lookup response: {response}")
    session.modified = True
    return response


def classify_and_redirect(job_title: str, job_description: str, org_description: str):
    """Classifies the user's job and organisation details and redirects to the question template.

    Args:
        job_title (str): The job title to classify.
        job_description (str): The job description to classify.
        org_description (str): The organisation description to classify.

    Returns:
        Response: Redirect to the question template page.
    """
    classification = classify(
        classification_type="sic",
        job_title=job_title,
        job_description=job_description,
        org_description=org_description,
    )
    logger.debug("Classification response")
    logger.debug(f"{classification}")

    return redirect(url_for("survey.question_template"))


def classify_and_handle_followup(
    job_title: str, job_description: str, org_description: str
):
    """Classifies the user's job and organisation details, handles follow-up
    and renders the next question.

    Args:
        job_title (str): The job title to classify.
        job_description (str): The job description to classify.
        org_description (str): The organisation description to classify.

    Returns:
        Response: Redirect or rendered template for the next follow-up question.
    """
    classification = classify(
        classification_type="sic",
        job_title=job_title,
        job_description=job_description,
        org_description=org_description,
    )

    if classification is None:
        # TODO: Handle the error case appropriately, for now skip to next question #pylint: disable=fixme
        logger.error("Classification response was None.")
        return redirect(url_for("survey.question_template"))

    mapped_api_response = map_api_response_to_internal(classification)

    followup_questions = mapped_api_response.get("follow_up", {}).get("questions", [])

    if not followup_questions:
        logger.info(
            "No follow-up questions available, redirecting to question template."
        )
        return redirect(url_for("survey.question_template"))

    question = get_next_followup(followup_questions, FOLLOW_UP_TYPE)
    if not question:
        logger.info("No follow-up question found, redirecting to question template.")
        return redirect(url_for("survey.question_template"))

    question_text, question_data = question
    logger.debug(f"Next follow-up question: {question_text}")
    logger.debug(f"Question data: {question_data}")

    formatted_question = format_followup(
        question_data=question_data,
        question_text=question_text,
    )

    # Add to survey iteration
    # survey_iteration = session.get("survey_iteration", {})
    question_dict = formatted_question.to_dict()
    add_question_to_survey(
        question=question_dict,
        user_response=None,  # User response is saved later
    )

    return render_template(
        "question_template.html",
        **formatted_question.to_dict(),
    )
