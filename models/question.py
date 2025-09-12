"""Defines the Question class for Survey Assist UI.

This module provides a class to represent survey questions and their attributes,
including formatting and conversion to dictionary for rendering in templates.
"""

from typing import Any


class Question:  # pylint: disable=too-many-instance-attributes
    """Represents a survey question for Survey Assist UI.

    This class encapsulates all attributes and methods required to define,
    format, and render a survey question, including its options and metadata.
    """

    def __init__(  # noqa: PLR0913 pylint: disable=too-many-arguments, too-many-positional-arguments
        self,
        question_id: str,
        question_name: str,
        question_title: str,
        question_text: str,
        question_description: str,
        response_type: str,
        response_options: list[dict[str, Any]],
    ):
        """Initialises a Question instance with all required attributes.

        Args:
            question_id: Unique identifier for the question.
            question_name: Name of the question.
            question_title: Title of the question.
            question_text: Main text content of the question.
            question_description: Description or help text for the question.
            response_type: Type of response expected (e.g., radio, select, text).
            response_options: List of response options for the question.
        """
        self.question_id = question_id
        self.question_name = question_name
        self.title = question_title
        self.question_text = question_text
        self.question_description = f"<p>{question_description}</p>"
        self.response_type = "radio" if response_type == "select" else response_type
        self.response_name = f"resp-{question_name.replace('_', '-')}"
        self.response_options = self.format_response_options(response_options)
        self.justification_text = "<p>Placeholder text</p>"
        self.placeholder_field = ""
        self.button_text = "Save and continue"

    @staticmethod
    def format_response_options(response_options):
        """Formats the select options into the required response_options structure.

        Args:
            response_options (list): List of option dictionaries to format.

        Returns:
            list: List of formatted option dictionaries.
        """
        formatted_options = []
        for option in response_options:
            formatted_options.append(
                {
                    "id": f"{option['id'].lower().replace(' ', '-')}",
                    "label": option["label"],
                    "value": option["value"].lower(),
                }
            )

        # Ensure respondents must provide an answer for closed questions
        # from Survey Assist.
        if formatted_options:
            formatted_options[0]["attributes"] = {"required": True}

        return formatted_options

    def to_dict(self):
        """Returns the question instance as a dictionary for template rendering.

        Returns:
            dict: Dictionary representation of the question instance.
        """
        return {
            "question_id": self.question_id,
            "question_name": self.question_name,
            "title": self.title,
            "question_text": self.question_text,
            "question_description": self.question_description,
            "response_type": self.response_type,
            "response_name": self.response_name,
            "response_options": self.response_options,
            "justification_text": self.justification_text,
            "placeholder_field": self.placeholder_field,
            "button_text": self.button_text,
        }
