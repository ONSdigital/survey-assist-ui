"""Feedback routes for Survey Assist UI.

This module defines Flask routes and handlers for collecting user feedback after
survey completion. It manages feedback session state, question routing, and response
storage, and renders feedback-related templates for the Survey Assist UI.
"""

from typing import Any, Callable, cast

from flask import (
    Blueprint,
    Request,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from survey_assist_utils.logging import get_logger

from utils.access_utils import require_access
from utils.app_types import ResponseType, SurveyAssistFlask
from utils.feedback_utils import (
    FeedbackQuestion,
    copy_feedback_from_survey_iteration,
    get_current_feedback_index,
    get_feedback_questions,
    get_list_of_option_text,
    init_feedback_session,
    send_feedback,
)
from utils.session_utils import (
    FIRST_QUESTION,
    remove_access_from_session,
    remove_model_from_session,
    session_debug,
)
from utils.survey_utils import number_to_word

feedback_blueprint = Blueprint("feedback", __name__)
feedback_blueprint.before_request(require_access)

logger = get_logger(__name__, level="DEBUG")


@feedback_blueprint.route("/feedback_intro", methods=["GET"])
def intro():
    """Handles displaying an intro page prior to the feedback."""
    app = cast(SurveyAssistFlask, current_app)
    # Get the lenth of the feedback questions
    feedback_questions = get_feedback_questions(app.feedback)
    feedback_word = number_to_word.get(len(feedback_questions), "unknown")
    return render_template(
        "feedback_intro.html", survey=app.survey_title, feedback_count=feedback_word
    )


# Generic route to handle feedback questions
@feedback_blueprint.route("/feedback", methods=["GET", "POST"])
@session_debug
def feedback() -> str:
    """Handles the generic feedback question page for the Survey Assist UI.

    Returns:
        str: Rendered HTML for the current feedback question.
    """
    app = cast(SurveyAssistFlask, current_app)
    feedback_data = app.feedback

    if "current_feedback_index" not in session:
        session["current_feedback_index"] = FIRST_QUESTION

    # If this is the first question, determine if responses from the survey
    # are to be included in the feedback.
    if session["current_feedback_index"] == 0:
        survey_result = session.get("survey_result", {})
        if survey_result:
            responses = survey_result.get("responses", [])
            if responses:
                person_id = responses[0].get("person_id", "error_person_id")
            else:
                logger.error("Responses not found for feedback")
                person_id = "error_responses"

            init_feedback_session(
                case_id=survey_result.get("case_id", "error_case_id"),
                person_id=person_id,
                survey_id=survey_result.get("survey_id", "error_survey_id"),
                wave_id=app.wave_id,
            )
        else:
            logger.error("survey_result not found for feedback")

        # We need to clean the session
        # - copy any data from the survey section that is
        # required for feedback (e.g ids and survey responses that need to be saved)
        # - drop all of the non-feedback data to reduce session size.
        if feedback_data.get("include_survey_resp", False):
            copy_responses = feedback_data.get("survey_responses", [])
            if not copy_responses:
                # Include responses is true, but list is empty, copy all survey responses
                session["feedback_response"] = copy_feedback_from_survey_iteration(
                    session
                )
            else:
                # Copy the listed responses
                session["feedback_response"] = copy_feedback_from_survey_iteration(
                    session, copy_responses
                )

        # Reduce the data in session. Survey Assist classification
        # was sent and stored already. Survey Iteration data that
        # needed to be kept should have been copied above.
        remove_model_from_session("survey_result")
        remove_model_from_session("survey_iteration")
        remove_model_from_session("response")

        session.modified = True

    # Get the current question based on the index
    current_index = session["current_feedback_index"]
    current_feedback_question = feedback_data["questions"][current_index]

    return render_template("feedback_template.html", **current_feedback_question)


@feedback_blueprint.route("/feedback_response", methods=["POST"])
@session_debug
def feedback_response() -> ResponseType | str | tuple[str, int]:
    """Saves the response to the current feedback question and redirects appropriately.

    Returns:
        ResponseType | str | tuple[str, int]: Redirect or error response.
    """
    app = cast(SurveyAssistFlask, current_app)
    feedback_data = app.feedback

    actions: dict[str, Callable[[], ResponseType | str]] = {
        "feedback_question": lambda: update_feedback_and_redirect(
            request, value, route
        ),
    }

    question = request.form.get("question_name")
    if question is None:
        raise ValueError("Missing form field: 'question_name'")

    logger.debug(f"Feedback Question: {question}")
    value, route = get_feedback_routing(
        question_name=question, questions=feedback_data.get("questions", [])
    )
    question = "feedback_question"

    if question in actions:
        return actions[question]()

    return "Invalid question ID", 400


# The question array defines the identifier for a question and the position
# indicates whether the next action is to ask another question or thank the
# user for their responses.
def get_feedback_routing(
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
            route = (
                "feedback.feedback_thank_you"
                if i == len(questions) - 1
                else "feedback.feedback"
            )
            return response_name, route
    raise ValueError(
        f"Feedback question name '{question_name}' not found in questions."
    )


def update_feedback_and_redirect(
    req: Request,
    value: str,
    route: str,
) -> ResponseType:
    """Route feedback."""
    app = cast(SurveyAssistFlask, current_app)
    feedback_data = app.feedback

    # Index into the current feedback question
    questions = get_feedback_questions(feedback_data)
    question_index = get_current_feedback_index(session, questions)
    current_question = questions[question_index]
    response_name = current_question.get("response_name")
    if not isinstance(response_name, str) or not response_name:
        raise RuntimeError("Feedback question is missing a valid 'response_name'.")

    feedback_q: FeedbackQuestion = {
        "response_name": response_name,
        "response": req.form.get(value),
    }

    if current_question.get("response_type") == "radio":
        texts: list[str] = []
        opts = current_question.get("response_options") or []
        texts = get_list_of_option_text(opts)
        if texts:
            feedback_q["response_options"] = texts
    else:
        feedback_q["response_options"] = []

    feedback_resp = session.get("feedback_response")
    if not isinstance(feedback_resp, dict) or not isinstance(
        feedback_resp.get("questions"), list
    ):
        raise RuntimeError(
            "feedback_response not initialised; call init_feedback_session(...) first."
        )

    feedback_resp["questions"].append(feedback_q)
    session["feedback_response"] = feedback_resp

    # Look at the next question for routing
    session["current_feedback_index"] = question_index + 1
    session.modified = True

    return redirect(url_for(route))


@feedback_blueprint.route("/feedback_thank_you")
def feedback_thank_you():
    """Send the feedback and render a thank you page to show results were submitted."""
    app = cast(SurveyAssistFlask, current_app)
    if not send_feedback():
        # Error sending feedback
        logger.error("UI - error sending feedback")
        logger.warning("TBD - Error handling. Clean Feedback Session Data")

    remove_model_from_session("feedback_response")

    # Remove further access from the session
    remove_access_from_session()

    if "current_feedback_index" in session:
        session["current_feedback_index"] = 0

    return render_template("feedback_thank_you.html", survey=app.survey_title)
