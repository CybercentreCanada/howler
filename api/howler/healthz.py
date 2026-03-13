import logging

from flask import Blueprint, abort, make_response

from howler.common.loader import datastore
from howler.plugins import get_plugins

logger = logging.getLogger("howler.healthz")

API_PREFIX = "/api/healthz"
healthz = Blueprint("healthz", __name__, url_prefix=API_PREFIX)


@healthz.route("/live")
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


@healthz.route("/ready")
def readyness(**_):
    """Check if the API is Ready

    Variables:
    None

    Arguments:
    None

    Result Example:
    OK or FAIL
    """
    if not datastore().ds.ping():
        abort(503)

    return make_response("OK")


@healthz.route("/plugins")
def plugins_health(**_):
    """Check the health of all registered plugins

    Variables:
    None

    Arguments:
    None

    Result Example:
    OK or FAIL
    """
    plugins_list = []
    for plugin in get_plugins():
        if plugin.modules.health_check is None:
            logger.debug("Plugin %s has not implemented healthcheck, skipping", plugin.name)
            continue

        is_healthy = False
        try:
            is_healthy = plugin.modules.health_check()
            logger.debug("Plugin %s reported healthy", plugin.name)
        except Exception:
            logger.exception("Health check failed for plugin %s", plugin.name)
        plugins_list.append({"name": plugin.name, "healthy": is_healthy, "importance": plugin.importance.value})
    return make_response(plugins_list)


@healthz.errorhandler(503)
def error(_):
    "Handle errors exposed in healthz routes"
    return "FAIL", 503
