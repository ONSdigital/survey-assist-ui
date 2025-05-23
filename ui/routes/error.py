"""This module defines the generic survey route for the survey assist UI.

This is the generic question page for the Survey Assist UI
"""

from flask import Blueprint, render_template
from survey_assist_utils.logging import get_logger

from utils.session_utils import session_debug

error_blueprint = Blueprint("error", __name__)

logger = get_logger(__name__)

@error_blueprint.errorhandler(404)
@error_blueprint.route("/page-not-found")
@session_debug
def page_not_found(e=None):
    return render_template("404.html"), 404 if e else 200
