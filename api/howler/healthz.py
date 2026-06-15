from flask import Blueprint, abort, make_response
from redis import RedisError

from howler import config as howler_config
from howler.common.loader import datastore
from howler.common.logging import get_logger

API_PREFIX = "/api/healthz"
healthz = Blueprint("healthz", __name__, url_prefix=API_PREFIX)
logger = get_logger(__file__)


def _is_datastore_healthy() -> bool:
    """Check whether the datastore is reachable."""
    if datastore().ds.ping():
        return True

    logger.warning("Health check failed: datastore ping returned false")
    return False


def _is_redis_healthy() -> bool:
    """Check whether configured Redis clients are reachable."""
    redis_config = howler_config.config.core.redis

    if redis_config.nonpersistent.host:
        try:
            if not howler_config.redis.ping():
                logger.warning("Health check failed: nonpersistent Redis ping returned false")
                return False
        except (ConnectionResetError, OSError, RedisError) as error:
            logger.warning("Health check failed: nonpersistent Redis ping raised %s", error)
            return False

    if redis_config.persistent.host:
        try:
            if not howler_config.redis_persistent.ping():
                logger.warning("Health check failed: persistent Redis ping returned false")
                return False
        except (ConnectionResetError, OSError, RedisError) as error:
            logger.warning("Health check failed: persistent Redis ping raised %s", error)
            return False

    return True


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

    Checks that the datastore and configured Redis connections are alive.

    Variables:
    None

    Arguments:
    None

    Result Example:
    OK or FAIL
    """
    if _is_datastore_healthy() and _is_redis_healthy():
        return make_response("OK")
    else:
        abort(503)


@healthz.errorhandler(503)
def error(_):
    "Handle errors exposed in healthz routes"
    return "FAIL", 503
