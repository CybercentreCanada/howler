import os
import re

from flask import request
from howler.api import make_subapi_blueprint, ok, unauthorized
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs

SUB_API = "sentinel"
sentinel_api = make_subapi_blueprint(SUB_API, api_version=1)
sentinel_api._doc = "Interact with spellbook"

logger = get_logger(__file__)

SECRET = os.environ["SENTINEL_LINK_KEY"]


@generate_swagger_docs()
@sentinel_api.route("/ingest", methods=["POST"])
def ingest_alert(**kwargs):
    """Ingest a sentinel alert into howler

    Variables:
    None

    Optional Arguments:
    None

    Result Example:
    """
    apikey = request.headers.get("Authorization", "Basic ", type=str).split(" ")[1]

    if not apikey or apikey != SECRET:
        return unauthorized(err="API Key does not match expected value.")

    logger.info("Recieved authorization header with value %s", re.sub(r"^(.{3}).+(.{3})$", r"\1...\2", apikey))

    sentinel_alert = request.json

    logger.info("Sentinel Alert:\n%s", sentinel_alert)

    return ok()
