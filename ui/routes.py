"""This module defines the routes for the survey assist UI.

The routes in this module handle requests to the UI and return the appropriate responses.
"""

from flask import Blueprint, render_template

from utils.survey import add_numbers

main_blueprint = Blueprint("main", __name__)


# Method to render the index page
@main_blueprint.route("/")
def index():
    """Renders the index page.

    This route handles requests to the root URL ("/") and serves the `index.html` template.

    Returns:
        str: Rendered HTML content of the index page.
    """
    add_numbers(1, 2)
    return render_template("index.html")
