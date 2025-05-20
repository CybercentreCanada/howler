from sys import exc_info
from traceback import format_tb

from flask import Blueprint, request
from werkzeug.exceptions import BadRequest, Forbidden, Unauthorized

from howler.api import bad_request, forbidden, internal_error, not_found, unauthorized
from howler.common.exceptions import AccessDeniedException, AuthenticationException
from howler.common.logging import get_logger, log_with_traceback
from howler.common.logging.audit import AUDIT
from howler.config import config

errors = Blueprint("errors", __name__)

logger = get_logger(__file__)


######################################
# Custom Error page
@errors.app_errorhandler(400)
def handle_400(e):
    """Handle bad request errors"""
    if isinstance(e, BadRequest):
        error_message = "No data block provided or data block not in JSON format.'"
    else:
        error_message = str(e)
    return bad_request(err=error_message)


@errors.app_errorhandler(401)
def handle_401(e):
    """Handle unauthorized errors"""
    if isinstance(e, Unauthorized):
        msg = e.description
    else:
        msg = str(e)

    data = {
        "oauth_providers": [name for name in config.auth.oauth.providers.keys()],
        "allow_userpass_login": config.auth.internal.enabled,
    }
    res = unauthorized(data, err=msg)
    res.set_cookie("XSRF-TOKEN", "", max_age=0)
    return res


@errors.app_errorhandler(403)
def handle_403(e):
    """Handle bad forbidden errors"""
    if isinstance(e, Forbidden):
        error_message = e.description
    else:
        error_message = str(e)

    trace = exc_info()[2]
    if AUDIT:
        uname = "(None)"
        ip = request.remote_addr

        log_with_traceback(trace, f"Access Denied. (U:{uname} - IP:{ip}) [{error_message}]", audit=True)

    config_block = {
        "auth": {
            "allow_apikeys": config.auth.allow_apikeys,
        }
    }
    return forbidden(config_block, err=f"Access Denied ({request.path}) [{error_message}]")


@errors.app_errorhandler(404)
def handle_404(_):
    """Handle not found errors"""
    return not_found(err=f"Api does not exist ({request.path})")


@errors.app_errorhandler(500)
def handle_500(e):
    """Handle internal server errors"""
    if isinstance(e.original_exception, AccessDeniedException):
        return handle_403(e.original_exception)

    if isinstance(e.original_exception, AuthenticationException):
        return handle_401(e.original_exception)

    oe = e.original_exception or e

    trace = exc_info()[2]
    log_with_traceback(trace, "Exception", is_exception=True)

    message = "".join(["\n"] + format_tb(exc_info()[2]) + ["%s: %s\n" % (oe.__class__.__name__, str(oe))]).rstrip("\n")
    return internal_error(err=message)
