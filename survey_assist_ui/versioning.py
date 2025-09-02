"""Application versioning utility for Survey Assist UI.

This module provides a helper to retrieve the installed package version for the
Survey Assist UI application, using the package name defined in pyproject.toml.
"""

from importlib.metadata import PackageNotFoundError, version

PKG_NAME = "survey-assist-ui"  # matches pyproject.toml


def get_app_version() -> str:
    """Get the installed version string for the Survey Assist UI application.

    Returns the version as defined in the installed package metadata, or a fallback
    string if the package is not found.

    Returns:
        str: The version string, or "0.0.0+unknown" if not found.
    """
    try:
        return version(PKG_NAME)
    except PackageNotFoundError:
        return "0.0.0+unknown"
