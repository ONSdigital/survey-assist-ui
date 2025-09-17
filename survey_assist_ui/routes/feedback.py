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

from utils.app_types import ResponseType, SurveyAssistFlask
from utils.feedback_utils import FeedbackQuestion, copy_feedback_from_survey_iteration, init_feedback_session
from utils.session_utils import (
    remove_model_from_session,
    session_debug,
)

feedback_blueprint = Blueprint("feedback", __name__)

logger = get_logger(__name__, level="DEBUG")

@feedback_blueprint.route("/feedback_intro", methods=["GET"])
def intro():
    """Handles displaying an intro page prior to the feedback."""
    app = cast(SurveyAssistFlask, current_app)
    return render_template("feedback_intro.html", survey=app.survey_title)


# Generic route to handle feedback questions
@feedback_blueprint.route("/feedback", methods=["GET", "POST"])
@session_debug
def feedback() -> str:
    """Handles the generic feedback question page for the Survey Assist UI.

    Returns:
        str: Rendered HTML for the current feedback question.
    """
    app = cast(SurveyAssistFlask, current_app)
    feedback = app.feedback

    if "current_feedback_index" not in session:
        session["current_feedback_index"] = 0

    # If this is the first question, determine if responses from the survey
    # are to be included in the feedback.
    if session["current_feedback_index"] == 0:
        survey_result = session.get("survey_result",{})
        if survey_result:
            responses = survey_result.get("responses",[])
            if responses:
                person_id = responses[0].get("person_id", "error_person_id")
            else:
                logger.error("Responses not found for feedback")
                person_id = "error_responses"

            init_feedback_session(case_id=survey_result.get("case_id","error_case_id"),
                                  person_id=person_id,
                                  survey_id=survey_result.get("survey_id","error_survey_id"))
        else:
            logger.error("survey_result not found for feedback")

        # We need to clean the session
        # - copy any data from the survey section that is
        # required for feedback (e.g ids and survey responses that need to be saved)
        # - drop all of the non-feedback data to reduce session size.
        if feedback.get("include_survey_resp",False):
            copy_responses = feedback.get("survey_responses",[])
            if not copy_responses:
                # Include responses is true, but list is empty, copy all survey responses
                session["feedback_response"] = copy_feedback_from_survey_iteration(session)
            else:
                # Copy the listed responses
                session["feedback_response"] = copy_feedback_from_survey_iteration(session, copy_responses)

        # Reduce the data in session. Survey Assist classification
        # was sent and stored already. Survey Iteration data that
        # needed to be kept should have been copied above.
        remove_model_from_session("survey_result")
        remove_model_from_session("survey_iteration")
        remove_model_from_session("response")

        session.modified = True

    # Get the current question based on the index
    current_index = session["current_feedback_index"]
    current_feedback_question = feedback["questions"][current_index]

    return render_template("feedback_template.html", **current_feedback_question)


@feedback_blueprint.route("/feedback_response", methods=["POST"])
@session_debug
def feedback_response() -> ResponseType | str | tuple[str, int]:
    """Saves the response to the current feedback question and redirects appropriately.

    Returns:
        ResponseType | str | tuple[str, int]: Redirect or error response.
    """
    app = cast(SurveyAssistFlask, current_app)
    feedback = app.feedback

    actions: dict[str, Callable[[], ResponseType | str]] = {
        "feedback_question": lambda: update_feedback_and_redirect(
            request, value, route
        ),
    }

    question = request.form.get("question_name")
    if question is None:
        raise ValueError("Missing form field: 'question_name'")

    logger.debug(f"Feedback Question: {question}")
    value, route = get_feedback_routing(question_name=question,
                                   questions=feedback.get("questions", []))
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
            route = "feedback.feedback_thank_you" if i == len(questions) - 1 else "feedback.feedback"
            return response_name, route
    raise ValueError(f"Feedback question name '{question_name}' not found in questions.")


def update_feedback_and_redirect(
    req: Request,
    value: str,
    route: str,
) -> ResponseType:
    """Route feedback."""
    app = cast(SurveyAssistFlask, current_app)
    feedback = app.feedback

    # key = value.replace("-", "_")
    # session["feedback_response"][key] = req.form.get(value)

    # Index into the current feedback question
    questions = feedback.get("questions")
    current_question = questions[session["current_feedback_index"]]
    response_name = current_question.get("response_name")
    if not isinstance(response_name, str) or not response_name:
        raise RuntimeError("Feedback question is missing a valid 'response_name'.")

    feedback_q: FeedbackQuestion = {
        "response_name": response_name,
        "response": req.form.get(value)
    }

    if current_question.get("response_type") == "radio":
        texts: list[str] = []
        for opt in current_question.get("response_options") or []:
            if isinstance(opt, dict):
                label = opt.get("label")
                if isinstance(label, dict):
                    text = label.get("text")
                    if isinstance(text, str) and text.strip():
                        texts.append(text)
        if texts:
            feedback_q["response_options"] = texts

    feedback_resp = session.get("feedback_response")
    if not isinstance(feedback_resp, dict) or not isinstance(feedback_resp.get("questions"), list):
        raise RuntimeError("feedback_response not initialised; call init_feedback_session(...) first.")

    feedback_resp["questions"].append(feedback_q)
    session["feedback_response"] = feedback_resp

    # Look at the next question for routing
    session["current_feedback_index"] += 1
    session.modified = True

    return redirect(url_for(route))


@feedback_blueprint.route("/feedback_thank_you")
def feedback_thank_you():
    logger.debug("Clean Feedback Session Data")
    remove_model_from_session("feedback_response")

    if "current_feedback_index" in session:
        session["current_feedback_index"] = 0

    """Render a thank you page to show results were submitted."""
    return render_template("feedback_thank_you.html",
                           survey="Feedback Feedback",
                           show_feedback=False)
