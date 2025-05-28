# implementation based on this stackoverflow post:
# https://stackoverflow.com/a/67943659


from typing import Any, Optional

import jwt
import requests
from jwt.api_jwk import PyJWK

from howler.common.exceptions import ForbiddenException, HowlerKeyError, HowlerValueError
from howler.common.logging import get_logger
from howler.config import cache, config

logger = get_logger(__file__)


def get_jwk(access_token: str) -> PyJWK:
    """Get the JSON Web Key associated with the given JWT"""
    # "kid" is the JSON Web Key's identifier. It tells us which key was used to validate the token.
    kid = jwt.get_unverified_header(access_token).get("kid")
    jwks, _ = get_jwks()

    try:
        # Check to see if we have it cached
        key = PyJWK(jwks[kid])
    except KeyError:
        # We don't, so we need to refresh the key set
        cache.delete(key="get_jwks")
        try:
            jwks, _ = get_jwks()
            key = jwks[kid]
        except KeyError:
            raise HowlerKeyError("Specified Key Set does not exist.")

    return key


def get_provider(access_token: str) -> str:
    """Get the provider of a given access token

    Args:
        access_token (str): The access token to determine the provider of

    Raises:
        HowlerValueError: The provider of this access token does not match any supported providers

    Returns:
        str: The provider of the token
    """
    # "kid" is the JSON Web Key's identifier. It tells us which key was used to validate the token.
    kid = jwt.get_unverified_header(access_token).get("kid")
    _, providers = get_jwks()

    try:
        # Check to see if we have it cached
        oauth_provider = providers[kid]
    except KeyError:
        # We don't, so we need to refresh the key set
        cache.delete(key="get_jwks")
        try:
            _, providers = get_jwks()
            oauth_provider = providers[kid]
        except KeyError:
            raise HowlerValueError("The provider of this access token does not match any supported providers")

    return oauth_provider


@cache.cached(timeout=60 * 60 * 12, key_prefix="get_jwks")  # Cached for 12hrs
def get_jwks() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Get the JSON Web Key Set for all supported providers

    Returns:
        tuple[dict[str, str], dict[str, str]]: The JWKS and the providers that are included in it
    """
    # JWKS = JSON Web Key Set. We merge the key set from all oauth providers
    jwks: dict[str, dict[str, Any]] = {}
    # Mapping of keys to their provider (i.e. azure, keycloak)
    providers: dict[str, str] = {}

    for (
        provider_name,
        provider_data,
    ) in config.auth.oauth.providers.items():
        # Fetch the JSON Web Key Set for each provider that supports them
        if provider_data.jwks_uri:
            provider_jwks: list[dict[str, Any]] = requests.get(provider_data.jwks_uri, timeout=10).json()["keys"]
            for jwk in provider_jwks:
                jwks[jwk["kid"]] = jwk
                providers[jwk["kid"]] = provider_name

    return (jwks, providers)


def get_audience(oauth_provider: str) -> str:
    """Get the audience for the specified OAuth provider

    Args:
        oauth_provider (str): The OAuth provider to retrieve the audience of

    Raises:
        HowlerValueError: The provider is azure, and is improperly formatted

    Returns:
        str: The audience of the provider
    """
    audience: str = "howler"
    provider_data = config.auth.oauth.providers[oauth_provider]
    if provider_data.audience:
        audience = provider_data.audience
    elif provider_data.client_id:
        audience = provider_data.client_id

    if oauth_provider == "azure" and f"{audience}/.default" not in provider_data.scope:
        raise HowlerValueError("Azure scope must contain the <client_id>/.default claim!")

    return audience


def decode(
    access_token: str,
    key: Optional[str] = None,
    algorithms: Optional[list[str]] = None,
    audience: Optional[str] = None,
    validate_audience: bool = False,
    **kwargs,
) -> dict[str, Any]:
    """Decode an access token into a JSON Web Token dict

    Args:
        access_token (str): The access token to decode
        key (Optional[str], optional): The key used to sign the token. Defaults to None.
        algorithms (Optional[list[str]], optional): The algorithm to use when decoding. Defaults to None.
        audience (Optional[str], optional): The audience to check against, if validating the audience. Defaults to None.
        validate_audience (bool, optional): Should we validate the audience? Defaults to False.

    Returns:
        dict[str, Any]: The decoded JWT, in dict format
    """
    if not key:
        key = get_jwk(access_token).key

    if not algorithms:
        algorithms = [jwt.get_unverified_header(access_token).get("alg", "HS256")]

    if validate_audience and not audience:
        audience = get_audience(get_provider(access_token))

    try:
        logger.debug("Validating token against audience %s", audience)
        return jwt.decode(jwt=access_token, key=key, algorithms=algorithms, audience=audience, **kwargs)  # type: ignore
    except jwt.ExpiredSignatureError as err:
        logger.info("JWT has expired.")
        raise ForbiddenException("Your JWT has expired.", cause=err)
    except jwt.InvalidTokenError as err:
        logger.exception("Error occurred when decoding JWT.")
        raise HowlerValueError("There was an error when decoding your JWT.", cause=err)
