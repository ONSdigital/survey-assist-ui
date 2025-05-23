"""Utility functions for managing survey sessions, question routing, and redirects in a Flask-based survey application.

Functions:
    update_session_and_redirect(session, request, questions, survey_assist, value, route):
        Updates the session with the user's response to the current question, manages survey iteration data,
        handles AI assist interactions, and redirects to the appropriate route.

    get_question_routing(question_name, questions):
        Determines the response name and next route based on the current question's name and its position in the questions list.

    consent_redirect():
        Stub function for redirecting to a consent-related error page.

    followup_redirect():
        Stub function for redirecting to a follow-up-related error page.

Globals:
    number_to_word (dict): Maps integers 1-6 to their corresponding English words.
"""
from datetime import datetime, timezone
from typing import Any

from flask import Request, Response, redirect, url_for
from survey_assist_utils.logging import get_logger

number_to_word: dict[int, str] = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}

logger = get_logger(__name__, level="DEBUG")


def update_session_and_redirect(
    session: dict[str, Any],
    request: Request,
    questions: list[dict[str, Any]],
    survey_assist: dict[str, Any],
    value: str,
    route: str,
) -> Response:
    """Updates the survey session with the user's response, manages survey iteration data,
    and redirects to the appropriate route based on the current state and AI assist configuration.

    Args:
        session (dict): The session object for storing user and survey state.
        request (flask.Request): The Flask request object containing form data.
        questions (list): List of question dictionaries for the survey.
        survey_assist (dict): Configuration for AI assist, including enabled state and interactions.
        value (str): The form field name corresponding to the current question's response.
        route (str): The name of the route to redirect to after processing.

    Returns:
        flask.Response: A redirect response to the next survey page or AI assist consent page.

    Side Effects:
        - Modifies the session to store user responses and survey iteration data.
        - May print debug information to the console.
        - Increments the current question index in the session.
        - Redirects the user to the next survey question or AI assist consent page.
    """
    # Set key as value but with hyphens replaced with underscores
    key = value.replace("-", "_")
    session["response"][key] = request.form.get(value)

    # Retrieve the survey data from the session
    survey_iteration = session.get("survey_iteration")

    if not survey_iteration:
        # Reinitialise survey in session if not present
        session["survey_iteration"] = {
            "user": "",
            "questions": [],
            "time_start": None,
            "time_end": None,
            "survey_assist_time_start": None,
            "survey_assist_time_end": None,
        }
        survey_iteration = session["survey_iteration"]
        # Set the time start based on the current timestamp
        survey_iteration["time_start"] = datetime.now(timezone.utc)
        logger.debug("Initialise survey data in update_session_and_redirect")
        logger.debug("Survey Iteration: %s", session.get("survey_iteration"))
        session.modified = True

    # Get the current question and take a copy so
    # that the original question data is not modified
    current_question = questions[session["current_question_index"]]
    current_question = current_question.copy()

    placeholder_field = current_question["placeholder_field"]

    if "response" in session and placeholder_field in session["response"]:
        current_question["question_text"] = current_question["question_text"].replace(
            "PLACEHOLDER_TEXT", session["response"][placeholder_field]
        )

    # Append the question and response to the list of questions
    survey_iteration["questions"].append(
        {
            "question_id": current_question.get("question_id"),
            "question_text": current_question.get("question_text"),
            "response_type": current_question.get("response_type"),
            "response_options": current_question.get("response_options"),
            "response_name": current_question.get("response_name"),
            "response": request.form.get(value),
            "used_for_classifications": current_question.get(
                "used_for_classifications"
            ),
        }
    )
    logger.debug("===== Survey Iteration =====")
    logger.debug(session["survey_iteration"])

    # If ai assist is enabled and the current question has an interaction
    # then redirect to the consent page to ask the user if they want to
    # continue with the AI assist interaction
    if survey_assist.get("enabled", True):
        session.modified = True
        interactions = survey_assist.get("interactions")
        if len(interactions) > 0 and current_question.get(
            "question_id"
        ) == interactions[0].get("after_question_id"):
            # print("AI Assist interaction detected - REDIRECTING to consent")
            return redirect(url_for("survey.survey_assist_consent"))

    session["current_question_index"] += 1
    session.modified = True
    return redirect(url_for(route))


# The question array defines the identifier for a question and the position
# indicates whether the next action is to ask another question or display the
# sumarry of the survey responses.
def get_question_routing(
    question_name: str,
    questions: list[dict[str, Any]],
) -> tuple[str, str]:
    for i, question in enumerate(questions):
        if question["question_name"] == question_name:
            response_name = question["response_name"]
            route = "core.summary" if i == len(questions) - 1 else "survey.survey"
            return response_name, route
    raise ValueError(f"Question name '{question_name}' not found in questions.")


def consent_redirect() -> Response:
    logger.info("Consent redirect stub")
    return redirect(url_for("error.page_not_found"))


def followup_redirect() -> Response:
    logger.info("Followup redirect stub")
    return redirect(url_for("error.page_not_found"))
