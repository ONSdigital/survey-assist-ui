from typing import Callable, cast

from flask import (
    Blueprint,
    current_app,
    render_template,
)
from survey_assist_utils.logging import get_logger

from utils.app_types import SurveyAssistFlask

feedback_blueprint = Blueprint("feedback", __name__)

logger = get_logger(__name__, level="DEBUG")

@feedback_blueprint.route("/feedback_intro", methods=["GET"])
def intro():
    """Handles displaying an intro page prior to the feedback."""
    app = cast(SurveyAssistFlask, current_app)
    return render_template("feedback_intro.html", survey=app.survey_title)

