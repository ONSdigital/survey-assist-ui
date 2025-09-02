"""Meta information routes for Survey Assist UI.

This module defines a Flask blueprint that exposes metadata about the Survey Assist
User Interface, including version, build, and runtime details for health and debugging.
"""

import os

from flask import Blueprint, jsonify

from survey_assist_ui.versioning import get_app_version

meta_blueprint = Blueprint("meta", __name__)


@meta_blueprint.route("/__meta", methods=["GET"])
def meta():
    """Return metadata related to the Survey Assist User Interface."""
    # Cloud Run sets these:
    # K_SERVICE, K_REVISION, K_CONFIGURATION
    return jsonify(
        {
            "app_version": get_app_version(),
            "git_sha": os.environ.get("APP_GIT_SHA", "unknown"),
            "build_date": os.environ.get("APP_BUILD_DATE", "unknown"),
            "service": os.environ.get("K_SERVICE", "unknown"),
            "revision": os.environ.get("K_REVISION", "unknown"),
            "configuration": os.environ.get("K_CONFIGURATION", "unknown"),
            "runtime": "cloud-run",
        }
    )
