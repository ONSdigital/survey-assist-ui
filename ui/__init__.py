"""Flask application setup for the Survey Assist UI.

This module initializes the Flask application, configures extensions,
and defines the main route for rendering the index page.

Attributes:
    app (Flask): The Flask application instance.
"""

import os

from flask import Flask
from flask_misaka import Misaka

from ui.routes import main_blueprint

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", os.urandom(24))

Misaka(app)

app.jinja_env.add_extension("jinja2.ext.do")
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True
app.config["FREEZER_IGNORE_404_NOT_FOUND"] = True
app.config["FREEZER_DEFAULT_MIMETYPE"] = "text/html"
app.config["FREEZER_DESTINATION"] = "../build"
app.register_blueprint(main_blueprint)


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
