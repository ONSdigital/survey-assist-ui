"""Maps API responses to the internal representation for Survey Assist.

This module provides functions to convert API responses into the internal model
format required by Survey Assist, including follow-up question generation.
"""


def map_api_response_to_internal(api_response: dict) -> dict:
    """Maps the API response to the internal Survey Assist model representation.

    Args:
        api_response (dict): The raw API response dictionary.

    Returns:
        dict: Internal representation of the survey classification and follow-up questions.
    """

    def create_follow_up_question(
        api_response: dict, q_id: str, response_type: str, select_options: list
    ) -> dict:
        """Creates a follow-up question dictionary for the internal model.

        Args:
            api_response (dict): The raw API response dictionary.
            q_id (str): The identifier for the follow-up question.
            response_type (str): The type of response expected (e.g., 'text', 'select', 'confirm').
            select_options (list): List of options for select-type questions.

        Returns:
            dict: A dictionary representing the follow-up question.
        """
        if response_type == "confirm":
            question_text = f"Does '{select_options[0]}' describe your organisation?"
            select_options[0] = "Yes"
            response_type = "select"
        else:
            question_text = (
                api_response.get("followup", "")
                if response_type == "text"
                else "Which of these best describes your organisation's activities?"
            )

        return {
            "follow_up_id": q_id,
            "question_text": question_text,
            "question_name": "survey_assist_followup",
            "response_type": response_type,
            "select_options": select_options,
        }

    # Map SIC candidates to internal codings format
    codings = [
        {
            "code": candidate["sic_code"],
            "code_description": candidate["sic_descriptive"],
            "confidence": candidate["likelihood"],
        }
        for candidate in api_response.get("sic_candidates", [])
    ]

    internal_representation = {
        "categorisation": {
            "codeable": api_response.get("classified", False),
            "codings": codings,
            "sic_code": api_response.get("sic_code", ""),
            "sic_description": api_response.get("sic_description", ""),
            "justification": api_response.get("reasoning", ""),
        },
        "follow_up": {"questions": []},
    }

    if not api_response.get("classified", False):
        # There is a choice of classifications, create follow-up question
        # list which will be a text based question and a select based question
        if api_response.get("followup"):
            follow_up = internal_representation["follow_up"]
            follow_up["questions"].append(
                create_follow_up_question(api_response, "f1.1", "text", [])
            )

        # Create select follow-up question
        if api_response.get("sic_candidates"):
            select_options = [
                candidate["sic_descriptive"]
                for candidate in api_response["sic_candidates"]
            ]
            select_options.append("None of the above")
            follow_up = internal_representation["follow_up"]
            follow_up["questions"].append(
                create_follow_up_question(
                    api_response, "f1.2", "select", select_options
                )
            )
    else:
        # V3 classify can return classified == True when it
        # is confident a sic mapping has been found
        # In this case, we want to confirm the mapping by asking the user
        # if they agree with organisation classification description
        follow_up = internal_representation["follow_up"]
        follow_up["questions"].append(
            create_follow_up_question(
                api_response,
                "f1.1",
                "confirm",
                [api_response.get("sic_description"), "No"],
            )
        )

    return internal_representation
