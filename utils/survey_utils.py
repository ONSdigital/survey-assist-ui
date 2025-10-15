"""Utility functions for managing survey sessions, question routing, and redirects.

This module provides functions to update survey session data, determine question routing,
and handle redirects for consent and follow-up questions in a Flask-based survey application.

Globals:
    number_to_word (dict): Maps integers 1-6 to their corresponding English words.
"""

from datetime import datetime, timezone
from typing import Any, cast

from flask import (
    Request,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from survey_assist_utils.logging import get_logger

from models.result import FollowUpQuestion, GenericSurveyAssistResult
from utils.app_types import ResponseType, SurveyAssistFlask
from utils.session_utils import (
    add_follow_up_to_latest_classify,
    add_question_to_survey,
    add_sic_lookup_interaction,
    get_person_id,
    load_model_from_session,
    save_model_to_session,
    update_end_time_of_survey_response,
)
from utils.survey_assist_utils import (
    FOLLOW_UP_TYPE,
    add_question_justifcation_guidance,
    format_followup,
    perform_sic_lookup,
)

number_to_word: dict[int, str] = {
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
}

logger = get_logger(__name__, level="DEBUG")


def init_survey_iteration() -> dict:
    """Initialises the survey iteration data in the session.

    This function sets up the initial structure for the survey iteration,
    including user information, questions, and timestamps for start and end times.

    Returns:
        dict: The initial survey iteration data structure.
    """
    return {
        "user": "",
        "questions": [],
        "time_start": None,
        "time_end": None,
        "survey_assist_time_start": None,
        "survey_assist_time_end": None,
    }


def find_matching_interaction(
    current_question: dict[str, Any], interactions: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Finds the first interaction that matches the current question ID.

    Args:
        current_question (dict[str, Any]): The current question being processed.
        interactions (list[dict[str, Any]]): A list of interaction configuration objects.

    Returns:
        dict[str, Any] | None: The matching interaction, or None if no match is found.
    """
    current_id = current_question.get("question_id")
    for interaction in interactions:
        if interaction.get("after_question_id") == current_id:
            return interaction
    return None


# pylint: disable=too-many-locals, too-many-branches, too-many-statements
def update_session_and_redirect(  # noqa: C901, PLR0912, PLR0915
    req: Request,
    questions: list[dict[str, Any]],
    survey_assist: dict[str, Any],
    value: str,
    route: str,
) -> ResponseType:
    """Updates the survey session with the user's response, manages survey iteration data,
    and redirects to the appropriate route based on the current state and AI assist configuration.

    Args:
        req (flask.Request): The Flask request object containing form data.
        questions (list): List of question dictionaries for the survey.
        survey_assist (dict): Configuration for AI assist, including enabled state and interactions.
        value (str): The form field name corresponding to the current question's response.
        route (str): The name of the route to redirect to after processing.

    Returns:
        ResponseType: A redirect response to the next survey page or AI assist consent page.

    Side Effects:
        - Modifies the session to store user responses and survey iteration data.
        - May print debug information to the console.
        - Increments the current question index in the session.
        - Redirects the user to the next survey question or AI assist consent page.
    """
    # Set key as value but with hyphens replaced with underscores
    key = value.replace("-", "_")
    session["response"][key] = req.form.get(value)

    # Retrieve the survey data from the session
    survey_iteration = session.get("survey_iteration")

    if not survey_iteration:
        # Reinitialise survey in session if not present
        session["survey_iteration"] = init_survey_iteration()
        survey_iteration = session["survey_iteration"]
        # Set the time start based on the current timestamp
        survey_iteration["time_start"] = datetime.now(timezone.utc)
        logger.debug("Initialise survey data in update_session_and_redirect")
        logger.debug(f"Survey Iteration: {survey_iteration}")
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

    # Add the question and response to the list of questions
    add_question_to_survey(current_question, req.form.get(value))

    # Determine typical survey route should be bypassed based on config
    # Note: Only support a route to end at present.
    next_route = check_route_on_response(
        question=current_question,
        user_value=req.form.get(value, ""),
        current_route=route,
    )

    # If route is unchanged continue with core processing
    if next_route == route:
        # If survey assist is enabled and the current question has an interaction
        # then redirect to the consent page to ask the user if they want to
        # continue with the Survey Assist interaction
        if survey_assist.get("enabled", True):
            session.modified = True
            interactions: list[dict[str, Any]] = survey_assist.get("interactions", [])

            matching_interaction = find_matching_interaction(
                current_question, interactions
            )

            if matching_interaction:
                question_id = current_question.get("question_id")
                after_id = matching_interaction.get("after_question_id")
                logger.debug(
                    f"Survey Assist interaction found for question {question_id} and {after_id}",
                )

                perform_classification = True
                if matching_interaction.get("type") == "lookup_classification":
                    # Make the sic lookup request
                    org_description = session["response"].get(
                        "organisation_activity", ""
                    )
                    if org_description:
                        lookup_response, start_time, end_time = perform_sic_lookup(
                            org_description
                        )

                        # Add response to survey_result
                        add_sic_lookup_interaction(
                            lookup_response,
                            start_time,
                            end_time,
                            {"org_description": org_description},
                        )

                    else:
                        logger.warning(
                            "No organisation description - SIC lookup skipped"
                        )
                        lookup_response = None

                    if lookup_response and lookup_response.get("code"):
                        # If the SIC lookup returns a code skip
                        # classification
                        perform_classification = False

                if perform_classification:
                    app = cast(SurveyAssistFlask, current_app)
                    if app.show_consent:
                        return redirect(url_for("survey.survey_assist_consent"))
                    else:
                        # skip consent screen
                        logger.debug(
                            f"Skipping consent screen - app.show_consent {app.show_consent}"
                        )

                        survey_iteration["survey_assist_time_start"] = datetime.now(
                            timezone.utc
                        )
                        session.modified = True
                        return redirect(url_for("survey_assist.survey_assist"))
                else:
                    logger.debug("SIC lookup successful, skipping classification")
                    survey_iteration["survey_assist_time_end"] = datetime.now(
                        timezone.utc
                    )

        # Look at the next question for routing
        session["current_question_index"] += 1
        session.modified = True
    else:
        route = next_route
        logger.debug(f"Rerouting to {route} in update session and redirect")
        if route != "survey.survey":
            # Routing away from the survey
            # Update the end time for the survey result
            update_end_time_of_survey_response()

    return redirect(url_for(route))


# The question array defines the identifier for a question and the position
# indicates whether the next action is to ask another question or display the
# sumarry of the survey responses.
def get_question_routing(
    question_name: str,
    questions: list[dict[str, Any]],
) -> tuple[str, str]:
    """Determines the response name and next route for a given question.

    Args:
        question_name (str): The name of the current question.
        questions (list): List of question dictionaries for the survey.

    Returns:
        tuple[str, str]: The response name and the next route name.

    Raises:
        ValueError: If the question name is not found in the questions list.
    """
    for i, question in enumerate(questions):
        if question["question_name"] == question_name:
            response_name = question["response_name"]
            # If the question is the last in the list, redirect to summary
            # else redirect to the next question
            if i == len(questions) - 1:
                # Update the end time for the survey result
                update_end_time_of_survey_response()
                route = "survey.summary"
            else:
                route = "survey.survey"
            return response_name, route
    raise ValueError(f"Question name '{question_name}' not found in questions.")


def consent_redirect() -> ResponseType:
    """Handles redirect logic for the Survey Assist consent page.

    Adds the user's consent response to the survey iteration and redirects accordingly.

    Returns:
        ResponseType: Redirect response to the next page based on consent.

    Raises:
        ValueError: If the session state is invalid or malformed.
    """
    survey_iteration = session.get("survey_iteration")

    if not isinstance(survey_iteration, dict) or "questions" not in survey_iteration:
        raise ValueError(
            "Invalid session state: survey_iteration is missing or malformed."
        )

    # Get the form value for survey_assist_consent
    consent_response = request.form.get("survey-assist-consent")

    logger.info(f"Consent response: {consent_response}")

    questions: list[dict[str, Any]] = survey_iteration["questions"]

    app = cast(SurveyAssistFlask, current_app)
    survey_assist = app.survey_assist

    # Add the consent response to the survey
    questions.append(
        {
            "question_id": survey_assist["consent"]["question_id"],
            "question_text": survey_assist["consent"]["question_text"],
            "response_type": survey_assist["consent"]["response_type"],
            "response_name": survey_assist["consent"]["response_name"],
            "response_options": survey_assist["consent"]["response_options"],
            "response": consent_response,
        }
    )

    session["survey_iteration"] = survey_iteration
    session.modified = True

    # Did the user consent to Survey Assist?
    if consent_response == "yes":
        return redirect(url_for("survey_assist.survey_assist"))
    else:
        # Mark the end time for the survey assist
        survey_iteration["survey_assist_time_end"] = datetime.now(timezone.utc)

        # Skip to next standard question
        session["current_question_index"] += 1
        session.modified = True
        return redirect(url_for("survey.survey"))


def followup_redirect() -> ResponseType | str:
    """Redirects to the follow-up question page.

    This function is called when there are multiple follow-up questions to display.
    The current assumption is the initial follow-up is displayed in the survey_assist
    route and any extra follow-up is displayed here.

    Returns:
        ResponseType | str: Rendered follow-up question page or redirect response.
    """
    app = cast(SurveyAssistFlask, current_app)
    questions = app.questions
    survey_assist = app.survey_assist

    # Get the current core question and list of interactions
    current_question = questions[session["current_question_index"]]
    interactions = survey_assist.get("interactions", [])
    cqi = current_question.get("question_id")

    debug_text = f"cq: {current_question} interactions: {interactions} len: {len(interactions)} cqi: {cqi}"  # pylint: disable=line-too-long
    logger.debug(debug_text)

    # If the current question has an associated interaction and there
    # are interactions to process
    if len(interactions) > 0 and current_question.get("question_id") == interactions[
        0
    ].get("after_question_id"):
        logger.debug(f"follow up length: {len(session.get('follow_up', []))}")
        # Check if the session has follow-up questions
        if "follow_up" in session and FOLLOW_UP_TYPE == "both":
            follow_up = session["follow_up"]
            if len(follow_up) > 0:
                # Get the next follow-up question
                follow_up_question = follow_up.pop(0)

                follow_up_questions = [
                    FollowUpQuestion(
                        id=follow_up_question["follow_up_id"],
                        text=follow_up_question["question_text"],
                        type=follow_up_question["response_type"],
                        select_options=follow_up_question["select_options"],
                        response="",  # Added when user responds
                    )
                ]

                if interactions[0].get("param") == "sic":
                    person_id = get_person_id()
                    # SIC interaction
                    add_follow_up_to_latest_classify(
                        "sic",
                        questions=follow_up_questions,
                        person_id=person_id,
                    )

                    # Format for rendering and add to survey iteration in session
                    formatted_question = format_followup(
                        follow_up_question,
                        follow_up_question["question_text"],
                    )

                    question_dict = formatted_question.to_dict()

                    add_question_to_survey(
                        question_dict,
                        None,  # Response will be filled in later
                    )

                    # Add the display options for justification.
                    # Note: Justification values are not added to session as
                    # they are not required in results.
                    question_dict = add_question_justifcation_guidance(
                        question_dict=question_dict
                    )

                    return render_template("question_template.html", **question_dict)
                else:
                    logger.error(
                        f"Interaction {interactions[0].get("param")} is yet to be supported"
                    )

        # No more follow up questions, redirect to the next core question
        # increment the current question index to
        # get the next question
        session["current_question_index"] += 1
        session.modified = True

        return redirect(url_for("survey.survey"))

    return redirect(url_for("error.page_not_found"))


def check_route_on_response(
    question: dict[str, Any],
    user_value: str,
    current_route: str,
) -> str:
    """Resolve routing for a given question based on user response.

    Args:
        question: The full question dictionary (with response_options
        and optional route_on_response).
        user_value: The value selected by the user (e.g. "yes", "no").
        current_route: The route currently in play (e.g. "survey.summary").

    Returns:
        str: The resolved route, which may or may not be modified.
    """
    allowed_routes = {"survey.summary"}
    route_on_response = question.get("route_on_response")
    if not route_on_response:
        # No special routing defined
        return current_route

    # Build a set of valid values from the question response options
    valid_values = {opt.get("value") for opt in question.get("response_options", [])}

    # Iterate through route_on_response rules
    for rule in route_on_response:
        expected_value = rule.get("value")
        expected_route = rule.get("route")

        # Check for invalid configuration
        if expected_value not in valid_values:
            logger.error(
                f"Invalid route_on_response: value '{expected_value}' not in response_options for question '{question.get("question_id")}'. Route unchanged."  # pylint: disable=line-too-long
            )
            return current_route

        # Apply routing if the user value matches this rule
        if user_value == expected_value:
            if expected_route in allowed_routes:
                return "survey.summary"
            else:
                logger.error(
                    f"Invalid route_on_response: route '{expected_route}' is not allowed for value '{expected_value}' on question '{question.get("question_id")}'. Route unchanged."  # pylint: disable=line-too-long
                )
                return current_route

    # If no rules matched, return unchanged
    return current_route
