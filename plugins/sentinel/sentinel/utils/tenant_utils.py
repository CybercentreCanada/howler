import json
import os

import requests
from howler.common.exceptions import HowlerRuntimeError
from howler.common.logging import get_logger
from howler.config import cache

logger = get_logger(__file__)


@cache.memoize(15 * 60)
def get_token(tenant_id: str, scope: str) -> tuple[str, dict[str, str]]:
    """Get a borealis token based on the current howler token"""
    # Get bearer token
    try:
        credentials = json.loads(os.environ["HOWLER_SENTINEL_INGEST_CREDENTIALS"])
    except (KeyError, json.JSONDecodeError):
        raise HowlerRuntimeError("Credential data not configured.")

    logger.info("Generating client credential token for client id %s with scope %s", credentials["client_id"], scope)

    token_request_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    response = requests.post(
        token_request_url,
        data={
            "grant_type": "client_credentials",
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
            "scope": scope,
        },
        timeout=5.0,
    )

    if not response.ok:
        raise HowlerRuntimeError(f"Authentication to Azure Monitor API failed with status code {response.status_code}.")

    token = response.json()["access_token"]

    return token, credentials
