"""This module defines the generic survey route for the survey assist UI.

This is the generic question page for the Survey Assist UI
"""

import re
from datetime import datetime, timezone
from typing import Callable, cast

from flask import (
    Blueprint,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from survey_assist_utils.logging import get_logger

from models.result import (
    GenericResponse,
    GenericSurveyAssistResult,
)
from utils.access_utils import require_access
from utils.app_types import ResponseType, SurveyAssistFlask
from utils.map_results_utils import translate_session_to_model
from utils.session_utils import (
    FIRST_QUESTION,
    add_follow_up_response_to_classify,
    clean_text,
    get_person_id,
    log_route,
    remove_access_from_session,
    save_model_to_session,
    session_debug,
)
from utils.survey_assist_utils import result_sic_only
from utils.survey_utils import (
    consent_redirect,
    followup_redirect,
    get_question_routing,
    init_survey_iteration,
    number_to_word,
    update_session_and_redirect,
)

survey_blueprint = Blueprint("survey", __name__)
survey_blueprint.before_request(require_access)


logger = get_logger(__name__, level="INFO")


@survey_blueprint.route("/intro", methods=["GET"])
@log_route()
def intro():
    """Handles displaying an intro page prior to the survey."""
    app = cast(SurveyAssistFlask, current_app)
    return render_template("ons_shape_tomorrow.html", survey_title=app.survey_title)


# Generic route to handle survey questions
@survey_blueprint.route("/survey", methods=["GET", "POST"])
@session_debug
@log_route()
def survey() -> str:
    """Handles the generic survey question page for the Survey Assist UI.

    Returns:
        str: Rendered HTML for the current survey question.
    """
    app = cast(SurveyAssistFlask, current_app)
    survey_title = app.survey_title
    wave_id = app.wave_id
    questions = app.questions

    # Initialise the current question index in the session if it doesn't exist
    if "current_question_index" not in session:
        session["current_question_index"] = FIRST_QUESTION
        session.modified = True

    # If this is the first question, initialise the iteration data
    # and set the time_start
    if session["current_question_index"] == FIRST_QUESTION:
        # Initialise the survey iteration data in the session
        session["survey_iteration"] = init_survey_iteration()

        if "response" in session:
            # Initialise the response data in the session
            session["response"] = {}

        # Set the time start based on the current timestamp
        session["survey_iteration"]["time_start"] = datetime.now(timezone.utc)

        # Initialise the results model in the session
        # case_id is a unique identifier that identifies a household
        # that received the survey.
        # user is the main user that starts the survey.
        result_model = GenericSurveyAssistResult(
            survey_id=re.sub(r"\s+", "_", survey_title.strip().lower()),
            wave_id=wave_id,
            case_id=session["participant_id"],
            user=get_person_id(),
            time_start=session["survey_iteration"]["time_start"],
            time_end=session["survey_iteration"]["time_start"],  # will be updated later
            responses=[],
        )

        # person-id is an indiviual respondent in the household
        new_response = GenericResponse(
            person_id=get_person_id(),
            time_start=session["survey_iteration"]["time_start"],
            time_end=session["survey_iteration"]["time_start"],  # will be updated later
            survey_assist_interactions=[],
        )
        # Despite responses being a list pylint can't figure it out
        # so we have to disable the linter warning
        responses: list[GenericResponse] = result_model.responses
        responses.append(new_response)  # pylint: disable=no-member

        save_model_to_session("survey_result", result_model)
        session.modified = True

    # Get the current question based on the index
    current_index = session["current_question_index"]
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

    limit = (
        current_question.get("char_limit", 150)
        if current_question["response_type"] == "textarea"
        else None
    )

    return render_template(
        "question_template.html", limit=limit, rows=4, **current_question
    )


# Route called after each question (or interaction) to save response to session data.
# The response is saved to the session dictionary and the user is redirected to the
# next question or interaction.
@survey_blueprint.route("/save_response", methods=["POST"])
@session_debug
@log_route()
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
        "survey_assist_followup": followup_redirect,
    }

    question = request.form.get("question_name")

    question_name = question  # Store original question name for logs
    if question is None:
        raise ValueError("Missing form field: 'question_name'")

    # If the question is not consent or a follow up question from Survey Assist,
    # then get the routing for the normal survey question
    if question not in [
        "survey_assist_consent",
        "follow_up_question",
        "survey_assist_followup_1",
        "survey_assist_followup_2",
    ]:
        routing = get_question_routing(question, questions)
        logger.debug(
            f"person_id:{get_person_id()} question: {question} ans: {request.form.get(routing[0])}"
        )
        question = "core_question"

    # If the question is a follow up question from Survey Assist, then add
    # the user's response to the question to the session data
    if question.startswith("survey_assist_followup"):
        # get survey data
        survey_data = session.get("survey_iteration")
        if survey_data is None:
            raise ValueError("survey_data is None, cannot extract questions")

        # get questions
        survey_questions = survey_data["questions"]

        # get the last question and store the answer against it
        last_question = survey_questions[-1]
        last_question["response"] = request.form.get(last_question["response_name"])

        response_type = last_question.get("response_type", "none")

        user_id = get_person_id()
        if response_type in ("textarea", "text"):
            last_question["response"] = clean_text(
                last_question["response"], last_question["response_name"], user_id
            )

        add_follow_up_response_to_classify(
            last_question["question_id"], last_question["response"], user_id
        )
        # The followup questions perform the same action
        question = "survey_assist_followup"

    logger.info(
        f"person_id:{get_person_id()} question: {question_name} action: {question}"
    )

    logger.debug(
        f"person_id:{get_person_id()} response list: {session.get('response')}"
    )

    if question in actions:
        iteration_data = session.get("survey_iteration", {})
        logger.debug("Survey Iteration")
        logger.debug(iteration_data)
        logger.debug(f"Executing action for question: {question}")
        return actions[question]()

    return "Invalid question ID", 400


@survey_blueprint.route("/survey_assist_consent")
@session_debug
@log_route()
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
@log_route()
def summary():
    """Summarises the survey data entered by the user and displays it in a summary template.

    Returns:
        str: Rendered HTML for the summary page.
    """
    survey_data = session.get("survey_iteration")
    survey_questions = survey_data["questions"]

    if survey_data["time_start"] is None:
        logger.warning(f"person_id:{get_person_id()} - time_start is not set")

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

    # If survey summary is not enabled then skip showing the summary page
    if current_app.survey_summary is False:
        return redirect(url_for("survey.survey_result"))

    return render_template("summary_template.html", questions=survey_questions)


# The survey_result route handles sending the result to the
# survey assist API.
@survey_blueprint.route("/survey_result")
@session_debug
@log_route()
def survey_result():
    """Maps the session result to the API result body and makes API request.

    Returns:
    TBD
    """
    sr = session.get("survey_result")

    # Update the end time of the survey result
    sr["time_end"] = datetime.now(timezone.utc)

    result = translate_session_to_model(sr)

    response = result_sic_only(result)

    if response:
        return redirect(url_for("survey.thank_you"))
    else:
        logger.error(f"person_id:{get_person_id()} error saving survey result")
        # Will add error splash in later PR
        return redirect(url_for("survey.thank_you"))


@survey_blueprint.route("/thank_you")
@log_route()
def thank_you():
    """Render a thank you page to show results were submitted."""
    app = cast(SurveyAssistFlask, current_app)

    if session.get("rerouted") is True:
        # Reroute before feedback, say thank you
        # and show incentive message
        logger.info(
            f"person_id:{get_person_id()} - rerouted no employment, skip feedback"
        )
        remove_access_from_session()
        session["rerouted"] = False
        session.modified = True
        incentive_msg = True
    else:
        # No feedback, no reroute, no incentive message
        # This is the tahnk you at the end of the first
        # part of the survey
        incentive_msg = False

    return render_template(
        "thank_you.html",
        survey=app.survey_title,
        show_feedback=app.show_feedback,
        incentive_msg=incentive_msg,
    )
