from flask import request
from howler.api import make_subapi_blueprint, ok
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs

SUB_API = "sentinel"
sentinel_api = make_subapi_blueprint(SUB_API, api_version=1)
sentinel_api._doc = "Interact with spellbook"

logger = get_logger(__file__)


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
    sentinel_alert = request.json

    logger.info("Sentinel Alert:\n%s", sentinel_alert)

    return ok()
