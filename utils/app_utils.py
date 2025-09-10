"""Flask application utility functions.

This module provides helper functions setting up the Flask application.
"""

import json
from pathlib import Path
from typing import Any


def load_survey_definition(flask_app: Any, file_path: str | Path) -> None:
    """Load survey definition from JSON and set attributes on the Flask app.

    Args:
        flask_app: The Flask app instance.
        file_path: Path to the survey definition JSON file.

    Raises:
        FileNotFoundError
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Survey definition file not found: {file_path}")

    # Load the survey definition
    with file_path.open(encoding="utf-8") as file:
        survey_definition = json.load(file)

    flask_app.survey_title = survey_definition.get(
        "survey_title", "Survey Assist Example"
    )

    survey_intro = survey_definition.get("survey_intro", {})
    if isinstance(survey_intro, dict):
        flask_app.survey_intro = survey_intro.get("enabled", False)
    else:
        flask_app.survey_intro = False

    flask_app.questions = survey_definition["questions"]
    flask_app.survey_assist = survey_definition["survey_assist"]

    sa_consent = flask_app.survey_assist.get("consent", {})
    if isinstance(sa_consent, dict):
        flask_app.show_consent = sa_consent.get("required", False)
    else:
        flask_app.show_consent = False
