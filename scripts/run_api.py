#!/usr/bin/env python3
"""Script for running Survey Assist API tasks.

This script provides command-line utilities to interact with the Survey Assist API,
including configuration retrieval, lookups, and classification tasks.

Example usage:
    poetry run python scripts/run_api.py --type sic --action lookup
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, cast
from urllib.parse import urlparse

import firestore_otp_verification_api_client  # type: ignore
from firestore_otp_verification_api_client import GeneralApi, OTPManagementApi
from firestore_otp_verification_api_client.models.health_config_response import (  # type: ignore
    HealthConfigResponse,
)
from firestore_otp_verification_api_client.models.otp_verify_request import (  # type: ignore
    OtpVerifyRequest,
)
from firestore_otp_verification_api_client.models.otp_verify_response import (  # type: ignore
    OtpVerifyResponse,
)
from firestore_otp_verification_api_client.rest import ApiException  # type: ignore
from survey_assist_utils.api_token.jwt_utils import check_and_refresh_token
from survey_assist_utils.logging import get_logger

sys.path.append(str(Path(__file__).resolve().parent.parent))

# Disabling lint error as this is a test script to manually verify endpoints, not used
# in production.
# pylint: disable=wrong-import-position
from models.result_sic_only import (
    Candidate,
    ClassificationResponse,
    FollowUp,
    FollowUpQuestion,
    InputField,
    Response,
    SurveyAssistInteraction,
    SurveyAssistResult,
)
from utils.api_utils import (  # pylint: disable=wrong-import-position
    APIClient,
    get_verification_api_id_token,
)
from utils.feedback_utils import FeedbackSession, feedback_session_to_model
from utils.map_results_utils import (
    translate_session_to_model,
)

# pylint: disable=line-too-long

logger = get_logger(__name__, "DEBUG")

VERIFY_API_URL = os.getenv("VERIFY_API_URL", "http://0.0.0.0:8080")

verify_api_configuration = firestore_otp_verification_api_client.Configuration(
    host=VERIFY_API_URL
)


def parse_z(ts: str) -> datetime:
    """Convert an ISO-8601 'Z' timestamp to a UTC-aware datetime.

    Args:
        ts: Timestamp like '2025-08-19T10:00:00Z'.

    Returns:
        A timezone-aware datetime normalised to UTC.
    """
    return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)


# The API currently uses a model that only expects SIC in results
result_sic_only: SurveyAssistResult = SurveyAssistResult(
    survey_id="test-survey-123",
    case_id="test-case-456",
    user="test.userSA187",
    time_start=parse_z("2025-08-19T10:00:00Z"),
    time_end=parse_z("2025-08-19T10:05:00Z"),
    responses=[
        Response(
            person_id="person-1",
            time_start=parse_z("2025-08-19T10:00:00Z"),
            time_end=parse_z("2025-08-19T10:05:00Z"),
            survey_assist_interactions=[
                # --- classify interaction (SIC) ---
                SurveyAssistInteraction(
                    type="classify",
                    flavour="sic",
                    time_start=parse_z("2025-08-19T10:00:00Z"),
                    time_end=parse_z("2025-08-19T10:01:00Z"),
                    input=[
                        InputField(field="job_title", value="Electrician"),
                        InputField(
                            field="job_description",
                            value="Installing electrical systems",
                        ),
                    ],
                    response=ClassificationResponse(
                        classified=True,
                        code="43210",
                        description="Electrical installation",
                        candidates=[
                            Candidate(
                                code="43210",
                                description="Electrical installation",
                                likelihood=0.9,
                            ),
                            Candidate(
                                code="43220",
                                description="Plumbing, heat and air-conditioning installation",
                                likelihood=0.2,
                            ),
                        ],
                        reasoning="Role and duties align with electrical installation (SIC 43210).",
                        follow_up=FollowUp(
                            questions=[
                                FollowUpQuestion(
                                    id="q1",
                                    text="What type of premises do you mostly work in?",
                                    type="select",
                                    select_options=[
                                        "Domestic",
                                        "Commercial",
                                        "Industrial",
                                    ],
                                    response="Commercial",
                                ),
                                FollowUpQuestion(
                                    id="q2",
                                    text="Do you primarily install or maintain systems?",
                                    type="text",
                                    response="Mostly install new systems.",
                                    select_options=[],
                                ),
                            ]
                        ),
                    ),
                ),
            ],
        )
    ],
)

# The following is mock data used by script, pytests have similar by design
# pylint: disable=duplicate-code
example_session_classify_result = {
    "survey_result": {
        "case_id": "test-case-xyz",
        "responses": [
            {
                "person_id": "user.respondent-a",
                "survey_assist_interactions": [
                    {
                        "flavour": "sic",
                        "input": [
                            {
                                "field": "org_description",
                                "value": "Farm providing food for shops and wholesalers",
                            }
                        ],
                        "response": {
                            "found": False,
                            "potential_codes": [],
                            "potential_codes_count": 0,
                            "potential_divisions": [],
                        },
                        "time_end": "2025-09-05T08:12:21.861831Z",
                        "time_start": "2025-09-05T08:12:18.275881Z",
                        "type": "lookup",
                    },
                    {
                        "flavour": "sic",
                        "input": [
                            {"field": "job_title", "value": "Farm Hand"},
                            {
                                "field": "job_description",
                                "value": "I tend crops on a farm applying fertaliser and harvesting plants",
                            },
                            {
                                "field": "org_description",
                                "value": "Farm providing food for shops and wholesalers",
                            },
                        ],
                        "response": [
                            {
                                "candidates": [
                                    {
                                        "code": "46210",
                                        "descriptive": "Wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                        "likelihood": 0.6,
                                    },
                                    {
                                        "code": "46390",
                                        "descriptive": "Non-specialised wholesale of food, beverages and tobacco",
                                        "likelihood": 0.4,
                                    },
                                ],
                                "classified": False,
                                "code": "46210",
                                "description": "Wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                "follow_up": {
                                    "questions": [
                                        {
                                            "id": "f1.1",
                                            "response": "sells grain and animal feeds",
                                            "select_options": [],
                                            "text": "Does your farm primarily sell grain, seeds, animal feeds, or other types of food products?",
                                            "type": "text",
                                        },
                                        {
                                            "id": "f1.2",
                                            "response": "wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                            "select_options": [
                                                "Wholesale of grain, unmanufactured tobacco, seeds and animal feeds",
                                                "Non-specialised wholesale of food, beverages and tobacco",
                                                "None of the above",
                                            ],
                                            "text": "Which of these best describes your organisation's activities?",
                                            "type": "select",
                                        },
                                    ]
                                },
                                "reasoning": "Follow-up needed to determine most appropriate SIC code.",
                                "type": "sic",
                            }
                        ],
                        "time_end": "2025-09-05T08:12:26.599931Z",
                        "time_start": "2025-09-05T08:12:26.599931Z",
                        "type": "classify",
                    },
                ],
                "time_end": "2025-09-05T08:12:26.599931Z",
                "time_start": "2025-09-05T08:12:06.412975Z",
            }
        ],
        "survey_id": "tlfs_shape_tomorrow_prototype",
        "time_end": "2025-09-05T08:12:26.599931Z",
        "time_start": "2025-09-05T08:12:06.412975Z",
        "user": "user.respondent-a",
    }
}

example_session_lookup_result = {
    "survey_result": {
        "case_id": "test-case-xyz",
        "responses": [
            {
                "person_id": "user.respondent-a",
                "survey_assist_interactions": [
                    {
                        "flavour": "sic",
                        "input": [{"field": "org_description", "value": "pubs"}],
                        "response": {
                            "found": True,
                            "potential_codes": [],
                            "potential_codes_count": 0,
                            "potential_divisions": [],
                        },
                        "time_end": "2025-09-05T09:00:46.000783Z",
                        "time_start": "2025-09-05T09:00:45.864491Z",
                        "type": "lookup",
                    }
                ],
                "time_end": "2025-09-05T09:00:46.000783Z",
                "time_start": "2025-09-05T09:00:28.493081Z",
            }
        ],
        "survey_id": "shape_tomorrow_prototype",
        "time_end": "2025-09-05T09:00:46.000783Z",
        "time_start": "2025-09-05T09:00:28.493081Z",
        "user": "user.respondent-a",
    }
}

example_session_feedback_response = {
    "case_id": "test-case-xyz",
    "person_id": "user.respondent-a",
    "questions": [
        {
            "response": "35-49",
            "response_name": "age-range",
            "response_options": ["18-24", "25-34", "35-49", "50-64", "65 plus"],
        },
        {
            "response": "difficult",
            "response_name": "survey-ease",
            "response_options": [
                "Very easy",
                "Easy",
                "Neither easy or difficult",
                "Difficult",
                "Very difficult",
            ],
        },
        {
            "response": "very irrelevant",
            "response_name": "survey-relevance",
            "response_options": [
                "Very relevant",
                "Relevant",
                "Neither relevant or irrelevant",
                "Irrelevant",
                "Very irrelevant",
            ],
        },
        {
            "response_name": "survey-comfort",
            "response": "very comfortable",
            "response_options": [
                "Very comfortable",
                "Comfortable",
                "Neither comfortable or uncomfortable",
                "Uncomfortable",
                "Very uncomfortable",
            ],
        },
    ],
    "survey_id": "shape_tomorrow_prototype",
}


def get_env_var(name: str) -> str:
    """Retrieves the value of an environment variable or raises an error if missing.

    Args:
        name (str): The name of the environment variable.

    Returns:
        str: The value of the environment variable.

    Raises:
        OSError: If the environment variable is not set.
    """
    value = os.getenv(name)
    if not value:
        raise OSError(f"Missing environment variable: {name}")
    return value


def init_api_client() -> APIClient:
    """Initialises and returns an APIClient instance using environment variables.

    Returns:
        APIClient: Configured API client for Survey Assist API.
    """
    sa_email = get_env_var("SA_EMAIL")
    api_base = os.getenv("BACKEND_API_URL", "http://127.0.0.1:5000")
    api_version = os.getenv("BACKEND_API_VERSION", "/v1")
    base_url = f"{api_base}{api_version}"

    parsed = urlparse(api_base)
    gw_hostname = parsed.netloc.rstrip("/")

    _token_start_time, api_token = check_and_refresh_token(
        0,
        "",
        gw_hostname,
        sa_email,
    )

    return APIClient(
        base_url=base_url,
        token=api_token,
        logger_handle=logger,
        redirect_on_error=False,
    )


def get_config(client: APIClient) -> Optional[dict]:
    """Retrieves the Survey Assist API configuration.

    Args:
        client (APIClient): The API client instance.

    Returns:
        Optional[dict]: The configuration dictionary if successful, else None.
    """
    response = client.get("/survey-assist/config")
    if isinstance(response, dict):
        logger.info("Successfully retrieved config.")
        return response
    logger.error("Failed to retrieve config.")
    return None


def get_lookup(
    client: APIClient, type_: str, org_desc: str, lookup_success: bool
) -> Optional[dict]:
    """Performs a lookup request to the Survey Assist API.

    Args:
        client (APIClient): The API client instance.
        type_ (str): The type of lookup (e.g., "sic", "soc").
        org_desc (str): The organisation description for lookup.
        lookup_success (bool): Whether to use a successful lookup value.

    Returns:
        Optional[dict]: The lookup result dictionary if successful, else None.
    """
    if org_desc is None:
        org_desc = "MOD" if lookup_success else "school"

    endpoint = f"/survey-assist/{type_}-lookup?description={org_desc}&similarity=true"
    response = client.get(endpoint=endpoint)
    if isinstance(response, dict):
        logger.info(f"Successfully retrieved {type_} lookup.")
        return response
    logger.error(f"Failed to retrieve {type_} lookup.")
    return None


def post_classify(
    client: APIClient,
    type_: str,
    job_title: str,
    job_description: str,
    org_description: str,
) -> Optional[dict]:
    """Classifies job and organisation details using the Survey Assist API.

    Args:
        client (APIClient): The API client instance.
        type_ (str): The type of classification (e.g., "sic", "soc").
        job_title (str): The job title to classify.
        job_description (str): The job description to classify.
        org_description (str): The organisation description to classify.

    Returns:
        Optional[dict]: The classification result dictionary if successful, else None.
    """
    response = client.post(
        "/survey-assist/classify",
        body={
            "llm": "gemini",
            "type": type_,
            "job_title": job_title,
            "job_description": job_description,
            "org_description": org_description,
        },
    )
    if isinstance(response, dict):
        logger.info(f"Successfully classified {type_}.")
        return response
    logger.error(f"Failed to classify {type_}.")
    return None


def post_result_sic_only(
    client: APIClient, result: SurveyAssistResult
) -> Optional[dict]:
    """Sends a result to the Survey Assist API.

    Args:
        client (APIClient): The API client instance.
        result (SurveyAssistResult): Pydantic model of result to send.

    Returns:
        Optional[dict]: The result response dictionary if successful, else None.
    """
    # result = translate_session_to_model(example_session_lookup_result)
    result = translate_session_to_model(example_session_classify_result)

    response = client.post(
        "/survey-assist/result",
        body=result.model_dump(mode="json"),  # required for datetime
    )

    if isinstance(response, dict):
        logger.info(f"Successfully saved response {response.get("result_id")}")
        return response
    logger.error("Failed to save result")
    return None


def post_feedback(client: APIClient) -> Optional[dict]:
    """Sends a result to the Survey Assist API.

    Args:
        client (APIClient): The API client instance.

    Returns:
        Optional[dict]: The result response dictionary if successful, else None.
    """
    raw = cast(FeedbackSession, example_session_feedback_response)
    result = feedback_session_to_model(raw)

    response = client.post(
        "/survey-assist/feedback",
        body=result.model_dump(mode="json"),  # required for datetime
    )

    if isinstance(response, dict):
        logger.info(f"Successfully saved feedback {response.get("result_id")}")
        return response
    logger.error("Failed to save feedback")
    return None


def prompt_input(prompt_text: str, default: str) -> str:
    """Prompts the user for input, returning the default if no input is given.

    Args:
        prompt_text (str): The prompt message to display.
        default (str): The default value to use if no input is provided.

    Returns:
        str: The user's input or the default value.
    """
    user_input = input(f"{prompt_text} (default: '{default}'): ").strip()
    return user_input or default


OTP_ID_RE = re.compile(r"^[A-Za-z0-9]{4}(?:-[A-Za-z0-9]{4}){3}$")


def otp_str(value: str) -> str:
    """Validates and formats an OTP string argument for argparse.

    Ensures the value matches the expected OTP format: four alphanumeric groups of
    four characters, separated by hyphens (e.g., wwww-xxxx-yyyy-zzzz). Raises an
    argparse.ArgumentTypeError if the format is invalid.

    Args:
        value (str): The OTP string to validate.

    Returns:
        str: The validated OTP string, converted to upper case.

    Raises:
        argparse.ArgumentTypeError: If the value does not match the expected format.
    """
    if not OTP_ID_RE.fullmatch(value):
        raise argparse.ArgumentTypeError(
            "Invalid --otp format. Expected wwww-xxxx-yyyy-zzzz (alphanumeric groups of 4, separated by hyphens)."
        )
    return value.upper()


def numeric_str(value: str) -> str:
    """Validates and formats an value string argument for argparse.

    Ensures the value matches a string representation of a whole numerical value.
    Raises an argparse.ArgumentTypeError if the format is invalid.

    Args:
        value (str): The OTP string to validate.

    Returns:
        str: The validated OTP string, converted to upper case.

    Raises:
        argparse.ArgumentTypeError: If the value does not match the expected format.
    """
    v = value.strip()
    if not v.isdigit():  # digits only, e.g. "0", "1033"
        raise argparse.ArgumentTypeError("Expected digits only, e.g. '0' or '1033'.")
    return v


# pylint: disable=too-many-locals,too-many-branches,too-many-statements
def main() -> None:  # noqa: C901, PLR0912, PLR0915
    """Main entry point for running Survey Assist API tasks from the command line.

    Parses command-line arguments, prompts for input, and performs lookup and/or
    classification actions using the Survey Assist API.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(description="Run survey assist API tasks.")
    parser.add_argument(
        "--type", choices=["sic", "soc"], help="Type of classification (sic/soc)"
    )
    parser.add_argument(
        "--action",
        choices=[
            "config",
            "lookup",
            "classify",
            "both",
            "result",
            "feedback",
            "root-otp",
            "verify-otp",
            "verify-invalid-otp",
        ],
        help="Action to perform",
    )
    parser.add_argument(
        "--otp",
        type=otp_str,  # validate against regex
        required=False,
        metavar="wwww-xxxx-yyyy-zzzz",
        help="OTP ID to verify (alphanumeric, 4-4-4-4 with hyphens)",
    )
    parser.add_argument(
        "--id_str",
        type=numeric_str,
        required=False,
        metavar="NUMERIC_STRING",
        help="OTP ID as a numeric string, e.g. '0' or '1033'.",
    )

    args = parser.parse_args()

    if args.action == "config":
        api_client = init_api_client()
        config = get_config(api_client)
        if config:
            logger.debug(json.dumps(config))
        return

    if args.action == "result":
        api_client = init_api_client()
        result_resp = post_result_sic_only(api_client, result_sic_only)
        if result_resp:
            logger.debug(json.dumps(result_resp))
        return

    if args.action == "feedback":
        api_client = init_api_client()
        result_resp = post_feedback(api_client)
        if result_resp:
            logger.debug(json.dumps(result_resp))
        return

    if args.action == "root-otp":
        with firestore_otp_verification_api_client.ApiClient(
            verify_api_configuration
        ) as api_client:
            # Create an instance of the API class
            api_instance: GeneralApi = firestore_otp_verification_api_client.GeneralApi(
                api_client
            )

            try:
                token = get_verification_api_id_token()

                # Health Check & Config Info
                api_response: HealthConfigResponse = api_instance.root_get(
                    _headers={"Authorization": f"Bearer {token}"},
                    _request_timeout=(2.0, 5.0),
                )
                logger.debug(f"{api_response.model_dump()}")
            except ApiException as e:
                logger.debug(f"Exception when calling GeneralApi->root_get: {e}\n")
        return

    if args.action == "verify-otp":

        if not args.otp or not args.id_str:
            parser.error("--otp and --id_str are required when --action verify-otp")

        token = get_verification_api_id_token()
        logger.debug(f"id:{args.id_str} otp:{args.otp}")
        verify_body = OtpVerifyRequest(id=args.id_str, otp=args.otp)

        with firestore_otp_verification_api_client.ApiClient(
            verify_api_configuration
        ) as api_client:
            # Create an instance of the API class
            mgmt_api_instance: OTPManagementApi = (
                firestore_otp_verification_api_client.OTPManagementApi(api_client)
            )

            try:
                # Health Check & Config Info
                mgmt_api_response: OtpVerifyResponse = (
                    mgmt_api_instance.verify_verify_post(
                        otp_verify_request=verify_body,
                        _headers={"Authorization": f"Bearer {token}"},
                        _request_timeout=(2.0, 5.0),
                    )
                )
                logger.debug(f"{mgmt_api_response.model_dump()}")
            except ApiException as e:
                logger.debug(f"Exception when calling verify: {e}\n")
        return

    if args.action == "verify-invalid-otp":

        with firestore_otp_verification_api_client.ApiClient(
            verify_api_configuration
        ) as api_client:
            # Create an instance of the API class
            mgmt_api_instance = firestore_otp_verification_api_client.OTPManagementApi(
                api_client
            )

            try:
                token = get_verification_api_id_token()
                verify_body = OtpVerifyRequest(id="0", otp="fred-bobb-geff-abbi")
                # Health Check & Config Info
                mgmt_api_response = mgmt_api_instance.verify_verify_post(
                    otp_verify_request=verify_body,
                    _headers={"Authorization": f"Bearer {token}"},
                    _request_timeout=(2.0, 5.0),
                )
                logger.debug(f"{mgmt_api_response.model_dump()}")
            except ApiException as e:
                logger.debug(f"Exception when calling verify: {e}\n")
        return

    job_title = prompt_input("Enter job title", "Kitchen Assistant")
    job_description = prompt_input(
        "Enter job description",
        "Assisting in the kitchen with food preparation, cleaning, and other tasks as required.",
    )
    org_description = prompt_input("Enter organisation description", "A local school.")

    api_client = init_api_client()
    type_ = args.type or prompt_input("Which type to run? (sic/soc)", "sic").lower()
    action = (
        args.action
        or prompt_input("What action? (lookup/classify/both)", "both").lower()
    )

    if action in ("lookup", "both"):
        get_lookup(api_client, type_, org_desc=org_description, lookup_success=True)

    if action in ("classify", "both"):
        post_classify(api_client, type_, job_title, job_description, org_description)


if __name__ == "__main__":
    main()
