"""Module that provides example test functions for the survey assist UI.

Unit tests for utility functions in the survey assist UI.
"""

import pytest

from utils.survey import add_numbers


@pytest.mark.example
def test_add_numbers():
    """Tests the add_numbers function with various inputs."""
    assert add_numbers(1, 2) == 3  # noqa: PLR2004
    assert add_numbers(0, 0) == 0
    assert add_numbers(-1, 1) == 0
