"""Access utility functions.

This module provides an functionality used to verify access to the Survey Assist UI.

"""

import csv
import os
import re

from flask import redirect, session
from flask.typing import ResponseReturnValue
from survey_assist_utils.logging import get_logger

logger = get_logger(__name__, level="DEBUG")

FILENAME = "example_access.csv"


def validate_access(access_id: str, access_code: str) -> tuple[bool, str]:
    """STUBBED - Validate the user against the credentials in a local file.

    Args:
        access_id (str): The user's access identifier.
        access_code (str): The access code to validate.

    Returns:
        tuple[bool, str]: Tuple of (True, "") if valid, or (False, error message) if not.
    """
    logger.debug(f"Validate access for {access_id} : {access_code}")
    error_string = "Invalid credentials. Please try again."
    if not access_code:
        logger.warning(f"Empty access code entered for access_id: {access_id}")
        return False, "You must enter both ONS ID and PFR ID"
    try:
        if not os.path.exists(FILENAME):
            logger.error(f"Access file '{FILENAME}' not found.")
            return False, error_string

        with open(FILENAME, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if (
                    row.get("survey_access_id") == access_id
                    and row.get("one_time_passcode") == access_code
                ):
                    return True, ""
        logger.warning(f"Validation unsuccessful for id: {access_id}")
        return False, error_string
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.warning(f"Error validating user: {e}")
    return False, "Error in validation module"


def format_access_code(raw: str) -> str:
    """Convert whitespace in an access code to hyphens and ensure uppercase.

    Trims leading and trailing whitespace, and replaces any sequence of spaces or tabs
    within the string with a single hyphen.

    Args:
        raw (str): The raw access code string to format.

    Returns:
        str: The formatted access code as uppercase with hyphens.
    """
    # trims ends and turns any run of spaces/tabs into a single hyphen
    return re.sub(r"\s+", "-", raw.strip()).upper()


def require_access() -> ResponseReturnValue | None:
    """Checks if participant access credentials are present in the session.

    If either 'participant_id' or 'access_code' is missing from the session,
    redirects the user to the access page. Otherwise, allows the request to proceed.

    Returns:
        Response or None: Redirects to the access page if credentials are missing,
        otherwise None to allow further processing.
    """
    if "participant_id" not in session and "access_code" not in session:
        return redirect("/access")
    # else allow
    return None
