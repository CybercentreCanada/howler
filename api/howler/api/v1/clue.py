import sys
import time
from typing import Callable, Optional

import elasticapm
import requests
from flask import request

from howler.api import bad_gateway, make_subapi_blueprint, ok
from howler.common.exceptions import AuthenticationException
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.config import cache, config
from howler.plugins import get_plugins
from howler.security import api_login

SUB_API = "clue"
clue_api = make_subapi_blueprint(SUB_API, api_version=1)
clue_api._doc = "Proxy enrichment requests to clue"

logger = get_logger(__file__)


def skip_cache(*args):
    "Function to skip cache in testing mode"
    return "pytest" in sys.modules


@cache.memoize(15 * 60, unless=skip_cache)
def get_token(access_token: str) -> str:
    """Get a clue token based on the current howler token"""
    get_clue_token: Optional[Callable[[str], str]] = None

    for plugin in get_plugins():
        if get_clue_token := plugin.modules.token_functions.get("clue", None):
            break

    if get_clue_token:
        clue_access_token = get_clue_token(access_token)
    else:
        logger.info("No custom clue token logic provided, continuing with howler credentials")
        clue_access_token = access_token

    return clue_access_token


@generate_swagger_docs()
@clue_api.route("/<path:path>", methods=["GET", "POST"])
@api_login(required_priv=["R"], required_method=["oauth"])
def proxy_to_clue(path, **kwargs):
    """Proxy enrichment requests to Clue

    Variables:
    None

    Arguments:
    None

    Data Block:
    Any

    Result Example:
    Clue Responses
    """
    logger.info("Proxying clue request to path %s/%s?%s", config.core.clue.url, path, request.query_string.decode())

    auth_data: Optional[str] = request.headers.get("Authorization", None, type=str)

    if not auth_data:
        raise AuthenticationException("No Authorization header present")

    auth_token = auth_data.split(" ")[1]

    clue_token = get_token(auth_token)

    start = time.perf_counter()
    with elasticapm.capture_span("clue", span_type="http"):
        if request.method.lower() == "get":
            response = requests.get(
                f"{config.core.clue.url}/{path}",
                headers={"Authorization": f"Bearer {clue_token}", "Accept": "application/json"},
                params=request.args.to_dict(),
                timeout=5 * 60,
            )
        else:
            response = requests.post(
                f"{config.core.clue.url}/{path}",
                json=request.json,
                headers={"Authorization": f"Bearer {clue_token}", "Accept": "application/json"},
                params=request.args.to_dict(),
                timeout=5 * 60,
            )

    logger.debug(f"Request to clue completed in {round(time.perf_counter() - start)}ms")

    if not response.ok:
        return bad_gateway(response.json(), err="Something went wrong when connecting to clue")

    return ok(response.json()["api_response"])
