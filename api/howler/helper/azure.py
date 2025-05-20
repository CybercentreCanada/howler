import requests

from howler.common.exceptions import HowlerException
from howler.common.logging import get_logger
from howler.config import config
from howler.utils.str_utils import default_string_value

logger = get_logger(__file__)


def azure_obo(token: str) -> str:
    """OBO an azure access token to MS Graph

    Args:
        token (str): The azure access token

    Raises:
        HowlerException: OBO failed

    Returns:
        str: The new access token with updated privileges
    """
    azure_provider_config = config.auth.oauth.providers["azure"]

    logger.debug("OBOing to MS Graph")
    # Azure is a special case here, as we need to OBO to MS Graph
    data = {
        "client_id": default_string_value(
            azure_provider_config.client_id,
            env_name="AZURE_CLIENT_ID",
        ),
        "scope": "https://graph.microsoft.com/user.read",
        "assertion": token,
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "client_secret": default_string_value(
            azure_provider_config.client_secret,
            env_name="AZURE_CLIENT_SECRET",
        ),
        "requested_token_use": "on_behalf_of",
    }

    if not azure_provider_config.access_token_url:
        raise HowlerException("Azure OBO failed - access_token_url must be set!")

    resp = requests.post(azure_provider_config.access_token_url, data=data, timeout=10)

    if not resp.ok:
        raise HowlerException(f"Azure OBO failed. Reason: {resp.content!r}")

    return resp.json()["access_token"]
