"""Access utility functions.

This module provides an functionality used to verify access to the Survey Assist UI.

"""
import csv
import os

from survey_assist_utils.logging import get_logger

logger = get_logger(__name__, level="DEBUG")

FILENAME = "example_access.csv"
def validate_access(access_id: str, access_code: str) -> bool:
    """STUBBED - Validate the user against the credentials in a local file."""
    try:
        if not os.path.exists(FILENAME):
            print(f"Access file '{FILENAME}' not found.")
            return False

        with open(FILENAME, newline="", encoding="utf-8") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if (
                    row.get("survey_access_id") == access_id
                    and row.get("one_time_passcode") == access_code
                ):
                    return True
        return True
    except Exception as e:
        print(f"Error validating user: {e}")
    return False
