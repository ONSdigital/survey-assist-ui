"""Module entry point for running the Survey Assist UI Flask application.

This module imports the Flask application instance from `ui.app`
and runs it when executed as a script.

Example:
    To start the application, run:

        make run-ui

"""

from ui import app

if __name__ == "__main__":
    # Run the Flask app directly when the script is executed
    app.run(host="0.0.0.0", port=8000) # noqa: S104
