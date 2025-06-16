import sys
from typing import Optional

import requests
from howler.common.exceptions import HowlerRuntimeError
from howler.common.logging import get_logger
from howler.config import cache

logger = get_logger(__file__)


def skip_cache(*args):
    "Function to skip cache in testing mode"
    return "pytest" in sys.modules


@cache.memoize(15 * 60, unless=skip_cache)
def get_token(tenant_id: str, scope: str) -> Optional[str]:
    """Get a borealis token based on the current howler token"""
    from sentinel.config import config

    token = None

    if config.auth.client_credentials:
        logger.info(
            "Using client_credentials flow for client id %s with scope %s",
            config.auth.client_credentials.client_id,
            scope,
        )

        token_request_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        response = requests.post(
            token_request_url,
            data={
                "grant_type": "client_credentials",
                "client_id": config.auth.client_credentials.client_id,
                "client_secret": config.auth.client_credentials.client_secret,
                "scope": scope,
            },
            timeout=5.0,
        )

        if not response.ok:
            raise HowlerRuntimeError(
                "Authentication to Azure Monitor API using client_credentials flow failed with status code"
                f" {response.status_code}. Response:\n{response.text}"
            )

        token = response.json()["access_token"]
    elif config.auth.custom_auth:
        token = config.auth.custom_auth(tenant_id, scope)

    if not token:
        logger.warning("No access token received")

    return token
