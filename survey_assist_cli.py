"""Simple CLI util for running the Survey Assist API.

This module imports and executes the main function from scripts.run_api
when run as a script.
"""

from scripts.run_api import main


def run_main() -> None:
    """Runs the main function from scripts.run_api.

    This function serves as the entry point when the script is executed directly.
    In project root directory, run:

    poetry run python -m survey_assist_cli
    """
    main()


if __name__ == "__main__":
    run_main()
