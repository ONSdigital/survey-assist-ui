"""Session utility functions for Flask applications.

This module provides helper functions for debugging and inspecting the Flask session object.
"""

from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any, Optional

from flask import current_app, session
from flask.sessions import SecureCookieSessionInterface
from pydantic import BaseModel
from survey_assist_utils.logging import get_logger

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


def load_model_from_session(key: str, model_class: type[BaseModel]) -> BaseModel:
    """Loads and reconstructs a Pydantic model from Flask session."""
    return model_class.model_validate(session[key])


def remove_model_from_session(key: str) -> None:
    """Remove a model from the Flask session."""
    session.pop(key, None)
    session.modified = True
