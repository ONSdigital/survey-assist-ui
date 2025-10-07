"""Access utility functions.

This module provides an functionality used to verify access to the Survey Assist UI.

"""

import re
from typing import cast

from flask import current_app, redirect, session
from flask.typing import ResponseReturnValue
from survey_assist_utils.logging import get_logger

from utils.api_utils import OTPVerificationService
from utils.app_types import SurveyAssistFlask

logger = get_logger(__name__, level="DEBUG")

FILENAME = "example_access.csv"


def validate_access(access_id: str, access_code: str) -> tuple[bool, str]:
    """Use the Verify API Service to determine if the entered id and access code is valid.

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
        app = cast(SurveyAssistFlask, current_app)
        verify_service = OTPVerificationService(app.verify_api_client)
        verify_resp = verify_service.verify(id_str=access_id, otp=access_code)

        if verify_resp.verified is True:
            return True, ""
        else:
            logger.warning(
                f"Validation unsuccessful for id: {access_id} - {verify_resp.message}"
            )
            return False, error_string
    except RuntimeError as e:
        logger.warning(f"Error validating user: {e}")
    return False, "Error in validation module"


def delete_access(access_id: str) -> tuple[bool, str]:
    """Use the Verify API Service to delete the access code associated with a access ID.

    Args:
        access_id (str): The access identifier to be deleted.

    Returns:
        tuple[bool, str]: Tuple of (True, "") if valid, or (False, error message) if not.
    """
    logger.debug(f"Delete access for {access_id}")
    error_string = f"Invalid id {access_id}. Not deleted."
    if not access_id:
        logger.warning("Access id not set. Not deleted.")
        return False, "ID not set in session"
    try:
        app = cast(SurveyAssistFlask, current_app)
        verify_service = OTPVerificationService(app.verify_api_client)
        delete_resp = verify_service.delete(id_str=access_id)

        if delete_resp.deleted is True:
            logger.info(f"Access code deleted for id:{access_id}")
            return True, ""
        else:
            logger.warning(
                f"Deletion unsuccessful for id: {access_id} - {delete_resp.message}"
            )
            return False, error_string
    except RuntimeError as e:
        logger.warning(f"Error deleting access: {e}")
    return False, "Error in validation module when deleting access code"


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
