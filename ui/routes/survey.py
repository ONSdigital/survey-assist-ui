"""This module defines the generic survey route for the survey assist UI.

This is the generic question page for the Survey Assist UI
"""

from datetime import datetime, timezone
from typing import Callable, cast

from flask import Blueprint, current_app, render_template, request, session
from survey_assist_utils.logging import get_logger

from utils.app_types import ResponseType, SurveyAssistFlask
from utils.session_utils import session_debug
from utils.survey_utils import (
    consent_redirect,
    followup_redirect,
    get_question_routing,
    init_survey_iteration,
    number_to_word,
    update_session_and_redirect,
)

survey_blueprint = Blueprint("survey", __name__)

logger = get_logger(__name__, level="DEBUG")


# Generic route to handle survey questions
@survey_blueprint.route("/survey", methods=["GET", "POST"])
@session_debug
def survey() -> str:
    """Handles the generic survey question page for the Survey Assist UI.

    Returns:
        str: Rendered HTML for the current survey question.
    """
    # Initialise the current question index in the session if it doesn't exist
    if "current_question_index" not in session:
        session["current_question_index"] = 0
        session.modified = True

    # If this is the first question, initialise the iteration data
    # and set the time_start
    if session["current_question_index"] == 0:
        # Initialise the survey iteration data in the session
        session["survey_iteration"] = init_survey_iteration()

        if "response" in session:
            # Initialise the response data in the session
            session["response"] = {}

        # Set the time start based on the current timestamp
        session["survey_iteration"]["time_start"] = datetime.now(timezone.utc)
        session.modified = True

    # Get the current question based on the index
    current_index = session["current_question_index"]

    app = cast(SurveyAssistFlask, current_app)
    questions = app.questions
    current_question = questions[current_index]

    # if question_text contains PLACEHOLDER_TEXT, get the associated
    # placeholder_field associated with the question and replace the
    # PLACEHOLDER_TEXT string with the value of the specified field
    # held in session response
    if "PLACEHOLDER_TEXT" in current_question["question_text"]:
        # Copy the current question to a new dictionary
        current_question = current_question.copy()

        placeholder_field = current_question["placeholder_field"]

        if placeholder_field is not None:
            current_question["question_text"] = current_question[
                "question_text"
            ].replace("PLACEHOLDER_TEXT", session["response"][placeholder_field])

    return render_template("question_template.html", **current_question)


# Route called after each question (or interaction) to save response to session data.
# The response is saved to the session dictionary and the user is redirected to the
# next question or interaction.
@survey_blueprint.route("/save_response", methods=["POST"])
@session_debug
def save_response() -> ResponseType | str | tuple[str, int]:
    """Saves the response to the current survey question or interaction and redirects appropriately.

    Returns:
        ResponseType | str | tuple[str, int]: Redirect or error response.
    """
    app = cast(SurveyAssistFlask, current_app)
    questions = app.questions
    survey_assist = app.survey_assist

    # Define a dictionary to store responses
    if "response" not in session:
        session["response"] = {}

    actions: dict[str, Callable[[], ResponseType | str]] = {
        "core_question": lambda: update_session_and_redirect(
            request, questions, survey_assist, *routing
        ),
        "survey_assist_consent": consent_redirect,
        "follow_up_question": followup_redirect,
    }

    # Store the user response to the question AI asked
    question = request.form.get("question_name")
    if question is None:
        raise ValueError("Missing form field: 'question_name'")

    logger.debug(f"Received question: {question}")
    # If the question is not consent or a follow up question from Survey Assist,
    # then get the routing for the normal survey question
    if question not in [
        "survey_assist_consent",
        "follow_up_question",
        "survey_assist_followup",
    ]:
        routing = get_question_routing(question, questions)
        question = "core_question"

    # If the question is a follow up question from Survey Assist, then add
    # the response to the session data and update the question name
    if question.startswith("survey_assist") and question != "survey_assist_consent":
        question = "follow_up_question"

        # get survey data
        survey_data = session.get("survey_iteration")
        if survey_data is None:
            raise ValueError("survey_data is None, cannot extract questions")

        # get questions
        survey_questions = survey_data["questions"]

        # get the last question
        last_question = survey_questions[-1]
        # update the response name, required by forward_redirect
        # TODO - can this be incorporated in the forward_redirect function?  # pylint: disable=fixme
        last_question["response"] = request.form.get(last_question["response_name"])

    if question in actions:
        logger.debug(f"Executing action for question: {question}")
        return actions[question]()

    return "Invalid question ID", 400


@survey_blueprint.route("/survey_assist_consent")
@session_debug
def survey_assist_consent() -> str:
    """Renders the Survey Assist consent page, replacing placeholders as needed.

    Returns:
        str: Rendered HTML for the consent page.
    """
    app = cast(SurveyAssistFlask, current_app)
    survey_assist = app.survey_assist

    if "PLACEHOLDER_FOLLOWUP" in survey_assist["consent"]["question_text"]:
        # Get the maximum followup
        max_followup = survey_assist["consent"]["max_followup"]

        if max_followup == 1:
            followup_text = "one additional question"
        else:
            # convert numeric to string
            number_word = number_to_word.get(max_followup, "unknown")

            followup_text = f"a maximum of {number_word} additional questions"

        # Replace PLACEHOLDER_FOLLOWUP with the content of the placeholder field
        survey_assist["consent"]["question_text"] = survey_assist["consent"][
            "question_text"
        ].replace("PLACEHOLDER_FOLLOWUP", followup_text)

    if "PLACEHOLDER_REASON" in survey_assist["consent"]["question_text"]:
        # Replace PLACEHOLDER_REASON with the content of the placeholder field
        survey_assist["consent"]["question_text"] = survey_assist["consent"][
            "question_text"
        ].replace(
            "PLACEHOLDER_REASON",
            survey_assist["consent"]["placeholder_reason"],
        )

    return render_template(
        "survey_assist_consent.html",
        title=survey_assist["consent"]["title"],
        question_name=survey_assist["consent"]["question_name"],
        question_text=survey_assist["consent"]["question_text"],
        justification_text=survey_assist["consent"]["justification_text"],
    )


# The survey route summarises the data that has been
# entered by user, using the session data held in the survey
# dictionary. The data is then displayed in a summary template
@survey_blueprint.route("/summary")
@session_debug
def summary():
    """Summarises the survey data entered by the user and displays it in a summary template.

    Returns:
        str: Rendered HTML for the summary page.
    """
    survey_data = session.get("survey_iteration")
    logger.warning(f"Survey iteration: {survey_data}")
    survey_questions = survey_data["questions"]

    logger.debug(f"Survey Questions: {survey_questions}")
    if survey_data["time_start"] is None:
        logger.warning("time_start is not set")

    # Calculate the time_end based on the current timestamp
    survey_data["time_end"] = datetime.now(timezone.utc)
    session.modified = True

    # Log the time taken in seconds to answer the survey
    time_taken = (survey_data["time_end"] - survey_data["time_start"]).total_seconds()

    logger.debug(
        f"Start: {survey_data['time_start']}, End: {survey_data['time_end']}, "
        f"Duration: {time_taken} seconds"
    )

    # Loop through the questions, when a question_name starts with survey_assist
    # uppdate the question_text to have a label added to say it was generated by
    # Survey Assist
    for question in survey_questions:
        if question["response_name"].startswith("resp-survey-assist"):
            question["question_text"] = (
                question["question_text"]
                + current_app.survey_assist["question_assist_label"]
            )

    return render_template("summary_template.html", questions=survey_questions)
