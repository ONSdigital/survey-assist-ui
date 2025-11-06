"""Maps API responses to the internal representation for Survey Assist.

This module provides functions to convert API responses into the internal model
format required by Survey Assist, including follow-up question generation.
"""

import random
from typing import cast

from flask import current_app
from survey_assist_utils.logging import get_logger

from utils.app_types import SurveyAssistFlask

logger = get_logger(__name__, level="INFO")


def map_api_response_to_internal(api_response: dict) -> dict:
    """Maps the API response to the internal Survey Assist model representation.

    Args:
        api_response (dict): The raw API response dictionary.

    Returns:
        dict: Internal representation of the survey classification and follow-up questions.
    """

    def create_follow_up_question(
        result: dict,
        q_id: str,
        response_type: str,
        select_options: list,
        name: str = "survey_assist_followup",
    ) -> dict:
        """Creates a follow-up question dictionary for the internal model.

        Args:
            result (dict): The raw API result dictionary.
            q_id (str): The identifier for the follow-up question.
            response_type (str): The type of response expected (e.g., 'text', 'select', 'confirm').
            select_options (list): List of options for select-type questions.
            name (str): Optional. The name to use for the question.

        Returns:
            dict: A dictionary representing the follow-up question.
        """
        if response_type == "confirm":
            question_text = f"Does '{select_options[0]}' describe your organisation?"
            select_options[0] = "Yes"
            response_type = "select"
        else:
            question_text = (
                result.get("followup", "")
                if response_type in ("text", "textarea")
                else "Which of these best describes your organisation's activities?"
            )

        return {
            "follow_up_id": q_id,
            "question_text": question_text,
            "question_name": name,
            "response_type": response_type,
            "select_options": select_options,
        }

    app = cast(SurveyAssistFlask, current_app)
    survey_assist = app.survey_assist
    randomise_options = survey_assist.get("randomise_options", False)
    results = api_response.get("results", [])
    candidates = results[0].get("candidates", [])

    # Map SIC candidates to internal codings format
    codings = [
        {
            "code": candidate["code"],
            "code_description": candidate["descriptive"],
            "confidence": candidate["likelihood"],
        }
        for candidate in candidates
    ]

    # Note - this still uses sic_code for internal representation
    # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    internal_representation = {
        "categorisation": {
            "codeable": api_response.get("classified", False),
            "codings": codings,
            "sic_code": api_response.get("code", ""),
            "sic_description": api_response.get("description", ""),
            "justification": api_response.get("reasoning", ""),
        },
        "follow_up": {"questions": []},
    }

    if results[0].get("classified") is not True:
        # There is a choice of classifications, create follow-up question
        # list which will be a text based question and a select based question
        if results[0].get("followup"):
            follow_up = internal_representation["follow_up"]
            follow_up["questions"].append(
                create_follow_up_question(
                    results[0], "f1.1", "textarea", [], "survey_assist_followup_1"
                )
            )

        # Create select follow-up question
        if candidates:
            select_options = [candidate["descriptive"] for candidate in candidates]
            if randomise_options:
                random.shuffle(select_options)
            select_options.append("None of the above")
            follow_up = internal_representation["follow_up"]
            follow_up["questions"].append(
                create_follow_up_question(
                    results[0],
                    "f1.2",
                    "select",
                    select_options,
                    "survey_assist_followup_2",
                )
            )
    return internal_representation
