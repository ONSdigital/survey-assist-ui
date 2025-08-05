"""Session utility functions for Flask applications.

This module provides helper functions for debugging and inspecting the Flask session object.
"""

from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any, Optional, TypeVar

from flask import current_app, session
from flask.sessions import SecureCookieSessionInterface
from pydantic import BaseModel
from survey_assist_utils.logging import get_logger

from models.result import (
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

    logger.debug("Survey Result")
    logger.debug(survey_result.model_dump_json(indent=2))
    save_model_to_session("survey_result", survey_result)
