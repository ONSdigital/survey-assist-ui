"""Session utility functions for Flask applications.

This module provides helper functions for debugging and inspecting the Flask session object.
"""
import json
import sys
from functools import wraps

from flask import current_app, session
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
        session_size = sys.getsizeof(session_data)
        logger.debug("\n=== Session Debug Info ===")
        logger.debug(f"Session size: {session_size} bytes")
        logger.debug("Session content:")
        logger.debug(session_data)
    except Exception as e:
        logger.error(f"Error printing session debug info: {e}")
