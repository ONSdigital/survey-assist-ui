#!/usr/bin/env python3

import argparse
import os
from typing import Optional

from survey_assist_utils.api_token.jwt_utils import check_and_refresh_token
from survey_assist_utils.logging import get_logger

from utils.api_utils import APIClient

logger = get_logger(__name__)


def get_env_var(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise OSError(f"Missing environment variable: {name}")
    return value


def init_api_client() -> APIClient:
    jwt_secret_path = get_env_var("JWT_SECRET")
    sa_email = get_env_var("SA_EMAIL")
    api_base = os.getenv("BACKEND_API_URL", "http://127.0.0.1:5000")

    token_start_time, api_token = check_and_refresh_token(
        0,
        "",
        jwt_secret_path,
        api_base,
        sa_email,
    )

    return APIClient(
        base_url=api_base,
        token=api_token,
        logger=logger,
        redirect_on_error=False,
    )


def get_config(client: APIClient) -> Optional[dict]:
    response = client.get("/survey-assist/config")
    if isinstance(response, dict):
        logger.info("Successfully retrieved config.")
        return response
    logger.error("Failed to retrieve config.")
    return None


def get_lookup(
    client: APIClient, type_: str, org_desc: str, lookup_success: bool
) -> Optional[dict]:
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


def prompt_input(prompt_text: str, default: str) -> str:
    user_input = input(f"{prompt_text} (default: '{default}'): ").strip()
    return user_input or default


def main() -> None:
    parser = argparse.ArgumentParser(description="Run survey assist API tasks.")
    parser.add_argument(
        "--type", choices=["sic", "soc"], help="Type of classification (sic/soc)"
    )
    parser.add_argument(
        "--action", choices=["lookup", "classify", "both"], help="Action to perform"
    )
    args = parser.parse_args()

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
