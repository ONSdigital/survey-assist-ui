import json
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Any, Optional

from google.auth import default
from google.cloud import iam_credentials_v1
from survey_assist_utils.logging import get_logger

logger = get_logger(__name__, "DEBUG")

TOKEN_EXPIRY: int = 3600  # 1 hour
REFRESH_THRESHOLD: int = 300  # 5 minutes


def current_utc_time() -> datetime:
    """Get the current UTC time.

    Returns:
        datetime: The current time in UTC as a timezone-aware datetime object.
    """
    return datetime.fromtimestamp(time.time(), tz=timezone.utc)


def resolve_jwt_secret_path(jwt_secret_env: str) -> Optional[str]:
    """Resolves the JWT secret environment variable to a file path.
    - If the value is a valid JSON string, writes it to a temp file and returns that path.
    - If it's a path to an existing file, returns it as-is.
    """
    if os.path.isfile(jwt_secret_env):
        return jwt_secret_env  # Local dev case

    try:
        # Try to parse the secret content as JSON
        secret_content = json.loads(jwt_secret_env)
        # Write to temp file
        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".json"
        ) as temp:
            json.dump(secret_content, temp)
        return temp.name
    except json.JSONDecodeError as err:
        raise ValueError(
            "JWT_SECRET must be a valid file path or JSON string."
        ) from err


def generate_jwt(
    sa_email: str,
    audience: str,
    expiry_length: int = 3600,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Mint a service-account–signed JWT using ADC + IAMCredentials.signJwt,
    matching API Gateway config where:
      - x-google-issuer == sa_email
      - x-google-jwks_uri points to SA public keys
      - x-google-audiences == audience.

    Returns:
        The signed JWT string.
    """
    now = int(time.time())
    payload: dict[str, Any] = {
        "iat": now,
        "exp": now + expiry_length,
        "iss": sa_email,
        "sub": sa_email,
        "aud": audience,
        # Optional and often handy for downstream authz:
        "email": sa_email,
    }
    if extra_claims:
        payload.update(extra_claims)

    logger.debug(payload)

    # Get Application Default Credentials to call IAM Credentials API
    adc, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

    # Use the official client to call signJwt
    client = iam_credentials_v1.IAMCredentialsClient(credentials=adc)
    name = f"projects/-/serviceAccounts/{sa_email}"

    resp = client.sign_jwt(
        request={"name": name, "payload": json.dumps(payload, separators=(",", ":"))}
    )
    return resp.signed_jwt


def check_and_refresh_token(
    token_start_time: int,
    current_token: str,
    jwt_secret_path: str,
    api_gateway: str,
    sa_email: str,
) -> tuple[int, str]:
    """Checks if the current JWT token is still valid and refreshes it if necessary.

    If no token exists or the remaining time for the token is below the refresh threshold,
    a new token is generated using the provided JWT secret, API gateway, and service account email.

    Args:
        token_start_time (int): The UTC timestamp when the current token was created.
        current_token (str): The current JWT token.
        jwt_secret_path (str): The file path to the JWT secret used for token generation.
        api_gateway (str): The intended audience for the JWT token (e.g., API gateway URL).
        sa_email (str): The service account email used for token generation.

    Returns:
        tuple: A tuple containing the updated token start time (int)
               and the refreshed or current token (str).
    """
    logger.debug(f"token_start:{token_start_time}, current_token:{current_token}, api_gateway:{api_gateway}, sa_email:{sa_email}")
    if not token_start_time:
        # If no token exists, create one
        token_start_time = int(current_utc_time().timestamp())
        current_token = generate_jwt(
            sa_email=sa_email,
            audience=api_gateway,
            expiry_length=TOKEN_EXPIRY
        )

    elapsed_time = (
        current_utc_time().replace(tzinfo=None)
        - datetime.fromtimestamp(token_start_time)
    ).total_seconds()
    remaining_time = TOKEN_EXPIRY - elapsed_time

    if remaining_time <= REFRESH_THRESHOLD:
        # Refresh the token
        print("Refreshing JWT token...")
        token_start_time = int(current_utc_time().timestamp())

        current_token = generate_jwt(
            sa_email=sa_email,
            audience=api_gateway,
            expiry_length=TOKEN_EXPIRY
        )

        print(f"JWT Token ends with {current_token[-5:]} created at {token_start_time}")

    return token_start_time, current_token


def generate_api_token():
    """Generates an API token using a JWT at the CLI.

    This function retrieves necessary environment variables, such as the API gateway URL,
    service account email, and the path to the JWT secret file. It then generates a JWT
    token with a default expiry of 1 hour.

    Returns:
        str: The generated JWT token.
    """
    api_gateway = os.getenv("API_GATEWAY")
    sa_email = os.getenv("SA_EMAIL")
    jwt_secret_path = os.getenv("JWT_SECRET")

    # Generate JWT (lasts 1 hour - rotate before expiry)
    jwt_token = generate_jwt(
        jwt_secret_path,
        audience=api_gateway,
        sa_email=sa_email,
        expiry_length=TOKEN_EXPIRY,
    )

    print(jwt_token)
