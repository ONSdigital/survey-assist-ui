"""Survey Assist utility functions for classification, follow-up, and SIC lookup.

This module provides helper functions for classifying survey responses, handling follow-up
questions, and performing SIC code lookups.
"""

from datetime import datetime, timezone
from typing import cast

from flask import current_app, redirect, render_template, session, url_for
from pydantic import ValidationError
from survey_assist_utils.logging import get_logger

from models.api_map import (
    map_api_response_to_internal,
)
from models.classify import GenericClassificationResponse
from models.question import Question
from models.result import FollowUpQuestion
from models.result_sic_only import ResultResponse, SurveyAssistResult
from utils.app_types import SurveyAssistFlask
from utils.session_utils import (
    add_classify_interaction,
    add_follow_up_to_latest_classify,
    add_question_to_survey,
)

# This is temporary, will be changed to configurable in the future
SHOW_CONSENT = True  # Whether to show the consent page
FOLLOW_UP_TYPE = "both"  # Options: open, closed, both

logger = get_logger(__name__)


def classify(
    classification_type: str, job_title: str, job_description: str, org_description: str
) -> tuple[GenericClassificationResponse | None, datetime]:
    """Classifies the given parameters using the API client.

    Args:
        classification_type (str): The type of classification to perform.
        job_title (str): The job title to classify.
        job_description (str): The job description to classify.
        org_description (str): The organisation description to classify.

    Returns:
        tuple[GenericClassificationResponse, datetime] | None: A tuple containing the classification
        response.
        and the classification start time, or None and start_time if classification fails.
    """
    app = cast(SurveyAssistFlask, current_app)
    api_client = app.api_client
    start_time = datetime.now(timezone.utc)
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

    try:
        validated_response = GenericClassificationResponse.model_validate(response)
        logger.info(f"Classification type {classification_type}.")
        logger.info(f"Followup question: {validated_response.results[0].followup}")
        return validated_response, start_time
    except ValidationError as e:
        logger.error(f"Validation error in classification response: {e}")
        return None, start_time


# This option is added to interwork with the initial API that only supports SIC
def result_sic_only(result: SurveyAssistResult) -> ResultResponse | None:
    """Classifies the given parameters using the API client.

    Args:
        result (GenericSurveyAssistResult): The result body to send to Survey Assist.

    Returns:
        ResultResponse | None: result response or None if result fails.
    """
    app = cast(SurveyAssistFlask, current_app)
    api_client = app.api_client
    response = api_client.post(
        "/survey-assist/result",
        body=result.model_dump(mode="json"),
    )

    try:
        validated_response = ResultResponse.model_validate(response)
        return validated_response
    except ValidationError as e:
        logger.error(f"Validation error in result response: {e}")
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


def perform_sic_lookup(org_description: str) -> tuple[dict, datetime, datetime]:
    """Performs a SIC code lookup using the API client.

    Args:
        org_description (str): The organisation description to look up.

    Returns:
        tuple: A tuple containing the API response dictionary, lookup start time,
            and lookup end time.
    """
    app = cast(SurveyAssistFlask, current_app)
    api_client = app.api_client
    start_time = datetime.now(timezone.utc)
    api_url = f"/survey-assist/sic-lookup?description={org_description}&similarity=true"
    response = api_client.get(endpoint=api_url)
    end_time = datetime.now(timezone.utc)
    logger.debug(f"SIC lookup response: {response}")
    session.modified = True
    return response, start_time, end_time


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
    classification, start_time = classify(
        classification_type="sic",
        job_title=job_title,
        job_description=job_description,
        org_description=org_description,
    )

    if classification is None:
        # TODO: Handle the error case appropriately, for now skip to next question #pylint: disable=fixme
        logger.error("Classification response was None.")
        return redirect(url_for("survey.question_template"))

    mapped_api_response = map_api_response_to_internal(classification.model_dump())

    followup_questions = mapped_api_response.get("follow_up", {}).get("questions", [])

    inputs_dict = {
        "job_title": job_title,
        "job_description": job_description,
        "org_description": org_description,
    }
    # Add interaction to survey_results
    add_classify_interaction(
        flavour="sic",
        classify_resp=classification,
        start_time=start_time,
        end_time=start_time,  # intentional - end time added when user responds
        inputs_dict=inputs_dict,
    )

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

    questions = [
        FollowUpQuestion(
            id=question_data["follow_up_id"],
            text=question_data["question_text"],
            type=question_data["response_type"],
            select_options=question_data["select_options"],
            response="",  # Added when user responds
        )
    ]

    add_follow_up_to_latest_classify(
        "sic", questions=questions, person_id="user.respondent-a"
    )

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

    # Add the display options for justification.
    # Note: Justification values are not added to session as
    # they are not required in results.
    app = cast(SurveyAssistFlask, current_app)
    survey_assist = app.survey_assist

    consent = survey_assist.get("consent", {})

    j_enabled = consent.get("justification_enabled", False)
    j_title = consent.get("justification_title", "Why we ask this question")
    j_text = consent.get("justification_text", "<p>Placeholder text</p>")

    question_dict.update(
        justification_enabled=j_enabled,
        justification_title=j_title,
        justification_text=j_text
    )

    return render_template(
        "question_template.html",
        **question_dict,
    )
