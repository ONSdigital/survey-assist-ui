"""Flask application setup for the Survey Assist UI.

This module initializes the Flask application, configures extensions,
and defines the main route for rendering the index page.

Attributes:
    app (Flask): The Flask application instance.
"""

import os

from flask import Flask, json, session
from flask_misaka import Misaka
from survey_assist_utils.logging import get_logger

from ui.routes import register_blueprints

logger = get_logger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

Misaka(app)

app.jinja_env.add_extension("jinja2.ext.do")
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.config["FREEZER_IGNORE_404_NOT_FOUND"] = True
app.config["FREEZER_DEFAULT_MIMETYPE"] = "text/html"
app.config["FREEZER_DESTINATION"] = "../build"
app.config["SESSION_DEBUG"] = os.getenv("SESSION_DEBUG", "false").lower() == "true"

# Load the survey definition
with open("ui/survey/survey_definition.json") as file:
    survey_definition = json.load(file)
    app.questions = survey_definition["questions"]
    app.survey_assist = survey_definition["survey_assist"]

# Initialise an iteration of the survey
app.survey_iteration = {
    "user": "",
    "questions": [],
    "time_start": None,
    "time_end": None,
    "survey_assist_time_start": None,
    "survey_assist_time_end": None,
}

register_blueprints(app)

logger.info("Flask app initialized with Misaka and Jinja2 extensions.")

# Method provides a dictionary to the jinja templates, allowing variables
# inside the dictionary to be directly accessed within the template files
# This saves defining navigation variables in each route
@app.context_processor
def set_variables():
    """Provides a dictionary to Jinja templates for global navigation variables.

    This function adds a `navigation` dictionary to the Jinja template context,
    allowing templates to directly access navigation variables without needing
    to define them in each route.

    Returns:
        dict: A dictionary containing the `navigation` object.
    """
    navigation = {"navigation": {}}
    return {"navigation": navigation}
