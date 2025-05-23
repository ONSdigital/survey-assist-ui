"""Session utility functions for Flask applications.

This module provides helper functions for debugging and inspecting the Flask session object.
"""
import sys
from datetime import datetime
from functools import wraps

from flask import current_app, session
from flask.sessions import SecureCookieSessionInterface
from survey_assist_utils.logging import get_logger

logger = get_logger(__name__, level="DEBUG")

def session_debug(f) -> callable:
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
    print the session's contents and its size in bytes to the console. Handles exceptions gracefully.

    Returns:
        None
    """
    if not current_app.config.get("SESSION_DEBUG", False):
        return

    try:
        session_data = dict(session)
        cleaned_session_data = _convert_datetimes(session_data)
        session_size = get_encoded_session_size(session_data)
        logger.debug("\n=== Session Debug Info ===")
        logger.debug(f"Session size: {session_size} bytes")
        logger.debug("Session content:")
        logger.debug(cleaned_session_data)
    except Exception as e:
        logger.error(f"Error printing session debug info: {e}")
