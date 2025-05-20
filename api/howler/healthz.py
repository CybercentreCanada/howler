from flask import Blueprint, abort, make_response

from howler.common.loader import datastore

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
    if datastore().ds.ping():
        return make_response("OK")
    else:
        abort(503)


@healthz.errorhandler(503)
def error(_):
    "Handle errors exposed in healthz routes"
    return "FAIL", 503
