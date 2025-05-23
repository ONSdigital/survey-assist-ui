"""This module defines the generic survey route for the survey assist UI.

This is the generic question page for the Survey Assist UI
"""

from typing import Callable

from flask import Blueprint, Response, current_app, render_template, request, session
from survey_assist_utils.logging import get_logger

from utils.session_utils import session_debug
from utils.survey_utils import (
    consent_redirect,
    followup_redirect,
    get_question_routing,
    number_to_word,
    update_session_and_redirect,
)

survey_blueprint = Blueprint("survey", __name__)

logger = get_logger(__name__)

# Generic route to handle survey questions
@survey_blueprint.route("/survey", methods=["GET", "POST"])
@session_debug
def survey() -> str:
    # Initialise the current question index in the session if it doesn't exist
    if "current_question_index" not in session:
        session["current_question_index"] = 0

        session.modified = True

    # Get the current question based on the index
    current_index = session["current_question_index"]
    current_question = current_app.questions[current_index]

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
# TODO - The actions dictionary is currently hardcoded for survey questions, this
# needs to be updated to be more dynamic.  There is also cruft in the variables passed
# to the update_session_and_redirect function.
@survey_blueprint.route("/save_response", methods=["POST"])
@session_debug
def save_response() -> Response:

    # Define a dictionary to store responses
    if "response" not in session:
        session["response"] = {}

    if "survey_iteration" not in session:
        session["survey_iteration"] = current_app.survey_iteration

    actions: dict[str, Callable[[], Response]] = {
        "core_question": lambda: update_session_and_redirect(
            session,
            request,
            current_app.questions,
            current_app.survey_assist,
            *routing
        ),
        "survey_assist_consent": lambda: consent_redirect(),
        "follow_up_question": lambda: followup_redirect(),
    }

    # Store the user response to the question AI asked
    question = request.form.get("question_name")

    # If the question is not consent or AI
    if question not in ["survey_assist_consent", "follow_up_question"]:
        routing = get_question_routing(question, current_app.questions)
        question = "core_question"

    if question.startswith("survey_assist"):
        question = "follow_up_question"

        # get survey data
        survey_data = session.get("survey_iteration")
        # get questions
        survey_questions = survey_data["questions"]

        # get the last question
        last_question = survey_questions[-1]
        # update the response name, required by forward_redirect
        # TODO - can this be incorporated in the forward_redirect function?
        last_question["response"] = request.form.get(last_question["response_name"])

    if question in actions:
        return actions[question]()
    else:
        return "Invalid question ID", 400


@survey_blueprint.route("/survey_assist_consent")
@session_debug
def survey_assist_consent() -> str:

    if "PLACEHOLDER_FOLLOWUP" in current_app.survey_assist["consent"]["question_text"]:
        # Get the maximum followup
        max_followup = current_app.survey_assist["consent"]["max_followup"]

        if max_followup == 1:
            followup_text = "one additional question"
        else:
            # convert numeric to string
            number_word = number_to_word.get(max_followup, "unknown")

            followup_text = f"a maximum of {number_word} additional questions"

        # Replace PLACEHOLDER_FOLLOWUP wit the content of the placeholder field
        current_app.survey_assist["consent"]["question_text"] = current_app.survey_assist["consent"][
            "question_text"
        ].replace("PLACEHOLDER_FOLLOWUP", followup_text)

    if "PLACEHOLDER_REASON" in current_app.survey_assist["consent"]["question_text"]:
        # Replace PLACEHOLDER_REASON wit the content of the placeholder field
        current_app.survey_assist["consent"]["question_text"] = current_app.survey_assist["consent"][
            "question_text"
        ].replace("PLACEHOLDER_REASON", current_app.survey_assist["consent"]["placeholder_reason"])

    # print("AI Assist consent question text:", survey_assist["consent"]["question_text"])
    return render_template(
        "survey_assist_consent.html",
        title=current_app.survey_assist["consent"]["title"],
        question_name=current_app.survey_assist["consent"]["question_name"],
        question_text=current_app.survey_assist["consent"]["question_text"],
        justification_text=current_app.survey_assist["consent"]["justification_text"],
    )
