from .error import error_blueprint
from .index import main_blueprint
from .survey import survey_blueprint


def register_blueprints(app):
    """Register all blueprints with the Flask application.

    This function registers all the blueprints defined in the `ui.routes` module
    with the provided Flask application instance.

    Args:
        app (Flask): The Flask application instance to register the blueprints with.
    """
    app.register_blueprint(main_blueprint)
    app.register_blueprint(survey_blueprint)
    app.register_blueprint(error_blueprint)
    # Add more blueprints here as needed
