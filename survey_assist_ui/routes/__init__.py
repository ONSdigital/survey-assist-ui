"""Initialises and registers all blueprints for the Survey Assist UI routes.

This module imports and provides a function to register all route blueprints
with a Flask application instance.
"""

from .error import error_blueprint
from .feedback import feedback_blueprint
from .index import main_blueprint
from .meta import meta_blueprint
from .survey import survey_blueprint
from .survey_assist import survey_assist_blueprint


def register_blueprints(app):
    """Registers all blueprints with the Flask application.

    Args:
        app (Flask): The Flask application instance to register the blueprints with.

    Returns:
        None
    """
    app.register_blueprint(main_blueprint)
    app.register_blueprint(survey_blueprint)
    app.register_blueprint(survey_assist_blueprint)
    app.register_blueprint(error_blueprint)
    app.register_blueprint(meta_blueprint)
    app.register_blueprint(feedback_blueprint)
    # Add more blueprints here as needed
