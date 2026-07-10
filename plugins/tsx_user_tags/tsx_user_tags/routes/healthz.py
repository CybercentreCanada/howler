from flask import make_response
from howler.api import make_subapi_blueprint
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs

SUB_API = "tags/healthz"
healthz_api = make_subapi_blueprint(SUB_API, api_version=1)
healthz_api._doc = "Health check tsx_user_tags Plugin API endpoints"

logger = get_logger(__file__)


@generate_swagger_docs()
@healthz_api.route("/live", methods=["GET"])
def liveness(**_):
    """Check if the API is live

    Variables:
    None

    Arguments:
    None

    Result Example:
    OK or FAIL
    """
    return make_response("OK")


@generate_swagger_docs()
@healthz_api.route("/ready", methods=["GET"])
def readiness(**_):
    """Check if the API is Ready

    Variables:
    None

    Arguments:
    None

    Result Example:
    OK or FAIL
    """
    try:
        from howler.common.loader import datastore

        if not datastore().ds.ping():
            logger.warning("Datastore ping failed")
            return make_response("FAIL", 503)
        return make_response("OK")
    except Exception:
        logger.exception("Readiness check failed")
        return make_response("FAIL", 503)


@healthz_api.errorhandler(503)
def _service_unavailable(_):
    """Handle errors exposed in healthz routes."""
    return "FAIL", 503
