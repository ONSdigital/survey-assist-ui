"""Session utility functions for Flask applications.

This module provides helper functions for debugging and inspecting the Flask session object.
"""

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Optional, TypeVar, Union

from flask import current_app, session
from flask.sessions import SecureCookieSessionInterface
from pydantic import BaseModel
from survey_assist_utils.logging import get_logger

from models.result import (
    FollowUp,
    FollowUpQuestion,
    GenericClassificationResult,
    GenericResponse,
    GenericSurveyAssistInteraction,
    GenericSurveyAssistResult,
    InputField,
)
from utils.api_utils import map_to_lookup_response

T = TypeVar("T", bound=BaseModel)

logger = get_logger(__name__, level="DEBUG")


def session_debug(f: Callable) -> Callable:
    """Decorator to print session information after a view function is executed.
    This decorator checks if the application's config has SESSION_DEBUG set to True,
    and if so, it prints the session's contents and its size in bytes to the console.

    Args:
        f (function): The view function to be decorated.

    Returns:
        function: The decorated view function.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        response = f(*args, **kwargs)
        print_session_info()
        return response

    return decorated_function


def _convert_datetimes(obj):
    """Recursively converts datetime objects in a dictionary or list to ISO format strings.
    This function is used to ensure that datetime objects in the session are
    serializable to JSON format.

    Args:
        obj (dict or list): The object to be converted. Can be a dictionary, list, or datetime.

    Returns:
        dict or list: The input object with datetime objects converted to ISO format strings.
    """
    if isinstance(obj, dict):
        return {k: _convert_datetimes(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_datetimes(i) for i in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def get_encoded_session_size(session_obj):
    """Calculates the size of the encoded session object in bytes.
    This function uses the SecureCookieSessionInterface to serialize the session object
    and then calculates the size of the serialized string.

    Args:
        session_obj (dict): The session object to be encoded.

    Returns:
        int: The size of the encoded session object in bytes.
    """
    serializer = SecureCookieSessionInterface().get_signing_serializer(current_app)
    if serializer is None:
        return 0
    encoded = serializer.dumps(session_obj)
    return len(encoded.encode("utf-8"))


def print_session_info() -> None:
    """Prints debug information about the current Flask session.

    If the application's config has SESSION_DEBUG set to True, this function will
    print the session's contents and its size in bytes to the console.

    Returns:
        None

    Raises:
        KeyError: If expected keys are missing in the session or config.
        TypeError: If session data is not serialisable.
        ValueError: If session encoding fails.
    """
    if not current_app.config.get("SESSION_DEBUG", False):
        return

    try:
        session_data = dict(session)
        cleaned_session_data = _convert_datetimes(session_data)
        session_size = get_encoded_session_size(session_data)
        logger.debug("\n=== Session Debug Info ===")
        logger.debug(f"Session size: {session_size} bytes")
        if not current_app.config.get("JSON_DEBUG", False):
            return
        logger.debug("Session content:")
        logger.debug(cleaned_session_data)
    except (KeyError, TypeError, ValueError) as err:
        logger.error(f"Error printing session debug info: {err}")


def add_question_to_survey(
    question: dict[str, Any], user_response: Optional[str]
) -> None:
    """Append a new question and user response to the session survey iteration.

    Args:
        question (dict[str, Any]): A dictionary representing the question metadata,
            containing keys like "question_id", "question_text", etc.
        user_response (Optional[str]): The response value submitted by the user.

    Raises:
        KeyError: If "survey_iteration" or "questions" is not in the session.
        ValueError: If required keys are missing in the question dictionary.
    """
    required_keys = [
        "question_id",
        "question_text",
        "response_type",
        "response_options",
        "response_name",
    ]

    # Validate input
    missing_keys = [key for key in required_keys if key not in question]
    if missing_keys:
        raise ValueError(f"Question dictionary is missing keys: {missing_keys}")

    # Ensure session structure
    if (
        "survey_iteration" not in session
        or "questions" not in session["survey_iteration"]
    ):
        raise KeyError("Session does not contain a valid 'survey_iteration' structure.")

    # Append the new question response block
    session["survey_iteration"]["questions"].append(
        {
            "question_id": question["question_id"],
            "question_text": question["question_text"],
            "response_type": question["response_type"],
            "response_options": question.get("response_options", []),
            "response_name": question["response_name"],
            "response": user_response,
            "used_for_classifications": question.get("used_for_classifications", []),
        }
    )

    session.modified = True


def save_model_to_session(key: str, model: BaseModel) -> None:
    """Convert a Pydantic model to dict and saves in session."""
    session[key] = model.model_dump(mode="json")


def load_model_from_session(key: str, model_class: type[T]) -> T:
    """Loads and reconstructs a Pydantic model from Flask session."""
    return model_class.model_validate(session[key])


def remove_model_from_session(key: str) -> None:
    """Remove a model from the Flask session."""
    session.pop(key, None)
    session.modified = True


def add_interaction_to_response(
    result_model: GenericSurveyAssistResult,
    person_id: str,
    interaction: GenericSurveyAssistInteraction,
    input_fields: Optional[dict[str, str]] = None,
) -> GenericSurveyAssistResult:
    """Adds an interaction to a person's response and optionally appends inputs.

    Args:
        result_model: The full survey result.
        person_id: The person to attach the interaction to.
        interaction: The interaction to append.
        input_fields: Optional dictionary of input fields to add to the interaction.

    Returns:
        The updated result model.

    Raises:
        ValueError: If no response matches the person_id.
    """
    if input_fields:
        input_objs = [InputField(field=k, value=v) for k, v in input_fields.items()]
        interaction.input.extend(input_objs)

    for response in result_model.responses:
        if response.person_id == person_id:
            response.survey_assist_interactions.append(interaction)
            response.time_end = interaction.time_end
            result_model.time_end = max(result_model.time_end, interaction.time_end)
            return result_model

    raise ValueError(f"No response found for person_id '{person_id}'")


def add_sic_lookup_interaction(
    lookup_resp: Any,
    start_time: datetime,
    end_time: datetime,
    inputs_dict: dict[str, str],
):
    """Adds a SIC lookup interaction to the survey result in the session.

    This function loads the current survey result from the session, creates a new
    GenericSurveyAssistInteraction for a SIC lookup, and appends it to the respondent's
    interactions. The updated survey result is then saved back to the session.

    Args:
        lookup_resp (Any): The raw lookup response from the SIC API.
        start_time (datetime): The start time of the lookup interaction.
        end_time (datetime): The end time of the lookup interaction.
        inputs_dict (dict[str, str]): Dictionary of input fields for the interaction.

    Returns:
        None
    """
    survey_result = load_model_from_session("survey_result", GenericSurveyAssistResult)

    lookup_result = map_to_lookup_response(lookup_resp, max_codes=3, max_divisions=3)

    # Create the interaction
    interaction = GenericSurveyAssistInteraction(
        type="lookup",
        flavour="sic",
        time_start=start_time,
        time_end=end_time,
        input=[],
        response=lookup_result,
    )

    survey_result = add_interaction_to_response(
        survey_result,
        person_id="user.respondent-a",
        interaction=interaction,
        input_fields=inputs_dict,
    )

    save_model_to_session("survey_result", survey_result)


def add_classify_interaction(
    flavour: str,
    classify_resp: Any,
    start_time: datetime,
    end_time: datetime,
    inputs_dict: dict[str, str],
):
    """Adds a SIC lookup interaction to the survey result in the session.

    This function loads the current survey result from the session, creates a new
    GenericSurveyAssistInteraction for a SIC lookup, and appends it to the respondent's
    interactions. The updated survey result is then saved back to the session.

    Args:
        flavour (str): one of "sic" or "soc".
        classify_resp (Any): The classify response from the SIC API.
        start_time (datetime): The start time of the lookup interaction.
        end_time (datetime): The end time of the lookup interaction.
        inputs_dict (dict[str, str]): Dictionary of input fields for the interaction.

    Returns:
        None
    """
    survey_result = load_model_from_session("survey_result", GenericSurveyAssistResult)

    classification_result = classify_resp.results[0]
    response_dict = classification_result.model_dump()
    interaction = GenericSurveyAssistInteraction(
        type="classify",
        flavour=flavour,
        time_start=start_time,
        time_end=end_time,
        input=[],
        response=[response_dict],
    )

    survey_result = add_interaction_to_response(
        survey_result,
        person_id="user.respondent-a",
        interaction=interaction,
        input_fields=inputs_dict,
    )

    save_model_to_session("survey_result", survey_result)


def add_follow_up_to_latest_classify(
    flavour: str,
    questions: list[FollowUpQuestion],
    person_id: str = "user.respondent-a",
):
    """Add follow-up questions to the latest classify interaction for a person.

    This function finds the latest response for the given person, locates the most
    recent classify interaction with the specified flavour, and attaches or extends
    the follow-up questions for the first classification result. Handles both dict
    and Pydantic model representations.

    Args:
        flavour (str): The classification flavour (e.g., "sic" or "soc").
        questions (list[FollowUpQuestion]): List of follow-up questions to add.
        person_id (str, optional): The person ID to update. Defaults to
            "user.respondent-a".

    Returns:
        GenericSurveyAssistResult: The updated survey result model.

    Raises:
        ValueError: If no responses or classify interaction is found for the person/flavour.
        TypeError: If the classify interaction response is not a list.
    """
    survey_result = load_model_from_session("survey_result", GenericSurveyAssistResult)

    # Find the latest response for this person
    latest_resp = next(
        (
            resp
            for resp in reversed(survey_result.responses)
            if resp.person_id == person_id
        ),
        None,
    )
    if latest_resp is None:
        raise ValueError(f"No responses for person_id={person_id}")

    # Find the latest classify interaction with the given flavour
    latest_interaction = next(
        (
            itx
            for itx in reversed(latest_resp.survey_assist_interactions)
            if itx.type == "classify" and itx.flavour == flavour
        ),
        None,
    )
    if latest_interaction is None:
        raise ValueError(f"No classify interaction found for flavour={flavour}")

    # Expecting a list of classification results, not LookupResponse
    if not isinstance(latest_interaction.response, list):
        raise TypeError("Expected classification response list, got LookupResponse")

    # Attach or extend follow_up.questions for the first classification result
    primary = latest_interaction.response[0]

    if isinstance(primary, dict):
        # Handle raw dict case
        existing_follow_up = primary.get("follow_up")
        if existing_follow_up and "questions" in existing_follow_up:
            existing_follow_up["questions"].extend([q.model_dump() for q in questions])
        else:
            primary["follow_up"] = FollowUp(questions=questions).model_dump()
    # Handle Pydantic model case
    elif primary.follow_up:
        primary.follow_up.questions.extend(questions)
    else:
        primary.follow_up = FollowUp(questions=questions)

    save_model_to_session("survey_result", survey_result)
    return survey_result


# Local type for readability
ClassificationResultLike = Union[dict, GenericClassificationResult]
QuestionsListLike = Optional[list]


def add_follow_up_response_to_classify(
    question_id: str,
    response_value: str,
    person_id: str = "user.respondent-a",
) -> GenericSurveyAssistResult:
    """Set the response for a follow-up question identified by a unique question_id.

    This function searches across all classify interactions (any flavour) for the given
    person and sets the response for the follow-up question with the specified ID.

    Args:
        question_id (str): The unique identifier of the follow-up question.
        response_value (str): The value to set as the response.
        person_id (str, optional): The person ID to search for. Defaults to
            "user.respondent-a".

    Returns:
        GenericSurveyAssistResult: The updated survey result model.

    Raises:
        ValueError: If no responses exist for the person or the question is not found.
    """
    survey_result = load_model_from_session("survey_result", GenericSurveyAssistResult)

    latest_resp = _get_latest_response_for_person(survey_result, person_id)
    if latest_resp is None:
        raise ValueError(f"No responses for person_id={person_id}")

    updated = _update_followup_response_in_response(
        latest_resp, question_id, response_value
    )
    if not updated:
        raise ValueError(f"No follow-up question found with id={question_id}")

    save_model_to_session("survey_result", survey_result)
    return survey_result


def _get_latest_response_for_person(
    survey_result: "GenericSurveyAssistResult", person_id: str
) -> Optional["GenericResponse"]:
    """Return the latest response for a given person ID from the survey result.

    Args:
        survey_result (GenericSurveyAssistResult): The survey result model.
        person_id (str): The person ID to search for.

    Returns:
        Optional[GenericResponse]: The latest response for the person, or None if not found.
    """
    return next(
        (
            resp
            for resp in reversed(survey_result.responses)
            if resp.person_id == person_id
        ),
        None,
    )


def _update_followup_response_in_response(
    person_response: "GenericResponse",
    question_id: str,
    response_value: str,
) -> bool:
    """Set the follow-up response in all classify interactions for a person.

    Iterates all classify interactions in a person's response and sets the response for
    the follow-up question with the given ID.

    Args:
        person_response (GenericResponse): The person's response object.
        question_id (str): The follow-up question ID to update.
        response_value (str): The value to set as the response.

    Returns:
        bool: True if an update occurred, False otherwise.
    """
    for result in _iter_classify_results(person_response):
        questions = _get_questions_from_result(result)
        if not questions:
            continue
        if _set_response_on_question_list(questions, question_id, response_value):
            return True
    return False


def _iter_classify_results(
    person_response: "GenericResponse",
) -> Iterable[ClassificationResultLike]:
    """Yield each classification result (dict or model) from all 'classify' interactions.

    Skips non-classify interactions and non-list responses (e.g., lookups).

    Updates end_time associated with classify interaction.

    Args:
        person_response (GenericResponse): The person's response object.

    Yields:
        ClassificationResultLike: Each classification result (dict or model).
    """
    for interaction in person_response.survey_assist_interactions:
        if interaction.type != "classify":
            continue
        if not isinstance(interaction.response, list):
            continue

        # Update the end_time associated with the classification
        # now that the user has answered questions.  The last time
        # this is accessed will be the time that the final
        # classification related question is answered.
        interaction.time_end = datetime.now(timezone.utc)
        yield from interaction.response


def _get_questions_from_result(result: ClassificationResultLike) -> QuestionsListLike:
    """Return the list of follow-up questions from a classification result.

    Handles both dict and Pydantic model representations. Returns None if absent.

    Args:
        result (ClassificationResultLike): The classification result (dict or model).

    Returns:
        Optional[list]: The list of follow-up questions, or None if not present.
    """
    if isinstance(result, dict):
        fu = result.get("follow_up")
        if not fu:
            return None
        return fu.get("questions")
    # Pydantic object path
    fu = getattr(result, "follow_up", None)
    return None if fu is None else getattr(fu, "questions", None)


def _set_response_on_question_list(
    questions: list, question_id: str, response_value: str
) -> bool:
    """Set the response value for a question with a matching ID in a list.

    Mutates the question with matching ID in-place, whether each question is a dict
    or a FollowUpQuestion model.

    Args:
        questions (list): List of question dicts or FollowUpQuestion models.
        question_id (str): The ID of the question to update.
        response_value (str): The value to set as the response.

    Returns:
        bool: True if a question was updated, False otherwise.
    """
    for q in questions:
        # dict-backed or model-backed access, done branchlessly with getattr fallback
        q_id = q.get("id") if isinstance(q, dict) else getattr(q, "id", None)
        if q_id != question_id:
            continue

        if isinstance(q, dict):
            q["response"] = response_value
        else:
            q.response = response_value
        return True
    return False
