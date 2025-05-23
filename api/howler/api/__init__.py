from sys import exc_info
from traceback import format_tb
from typing import Any, Union

from flask import Blueprint, Response, jsonify, make_response, request
from flask import session as flsk_session
from prometheus_client import Counter

from howler import odm
from howler.common.loader import APP_NAME
from howler.common.logging import get_logger, log_with_traceback
from howler.config import QUOTA_TRACKER, get_version
from howler.utils.str_utils import safe_str

API_PREFIX = "/api"
RAW_API_COUNTER = Counter(
    f"{APP_NAME.replace('-', '_')}_http_requests_total",
    "HTTP Requests broken down by method, path, and status",
    ["method", "path", "status"],
)

logger = get_logger(__file__)


def make_subapi_blueprint(name, api_version=1):
    """Create a flask Blueprint for a subapi in a standard way."""
    return Blueprint(name, name, url_prefix="/".join([API_PREFIX, f"v{api_version}", name]))


def _make_api_response(
    data: Any, err: Union[str, Exception] = "", warnings: list[str] = [], status_code: int = 200, cookies: Any = None
) -> Response:
    quota_user = flsk_session.pop("quota_user", None)
    quota_set = flsk_session.pop("quota_set", False)
    if quota_user and quota_set and not request.path.startswith("/api/v1/borealis"):
        QUOTA_TRACKER.end(quota_user)

    if type(err) is Exception:  # pragma: no cover
        trace = exc_info()[2]
        err = "".join(["\n"] + format_tb(trace) + ["%s: %s\n" % (err.__class__.__name__, str(err))]).rstrip("\n")
        log_with_traceback(trace, "Exception", is_exception=True)

    if isinstance(data, odm.Model):
        data = data.as_primitives()

    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], odm.Model):
        for i in range(len(data)):
            data[i] = data[i].as_primitives()

    resp = make_response(
        jsonify(
            {
                "api_response": data,
                "api_error_message": err,
                "api_warning": warnings,
                "api_server_version": get_version(),
                "api_status_code": status_code,
            }
        ),
        status_code,
    )

    if isinstance(cookies, dict):
        for k, v in cookies.items():
            resp.set_cookie(k, v)

    RAW_API_COUNTER.labels(request.method, str(request.url_rule), status_code).inc()
    logger.info("%s %s - %s", request.method, request.path, status_code)

    return resp


# Some helper functions for make_api_response

DEFAULT_DATA = {True: {"success": True}, False: {"success": False}}


def ok(data=DEFAULT_DATA[True], cookies=None):
    """Returns response with status code 200"""
    return _make_api_response(data, status_code=200, cookies=cookies)


def created(data=DEFAULT_DATA[True], warnings=[], cookies=None):
    """Returns response with status code 201"""
    return _make_api_response(data, warnings=warnings, status_code=201, cookies=cookies)


def accepted(data=DEFAULT_DATA[True], cookies=None):
    """Returns response with status code 202"""
    return _make_api_response(data, status_code=202, cookies=cookies)


def no_content(data=None, cookies=None):
    """Returns response with status code 204"""
    return _make_api_response(data or DEFAULT_DATA[True], status_code=204, cookies=cookies)


def not_modified(data=DEFAULT_DATA[True], cookies=None):
    """Returns response with status code 304"""
    return _make_api_response(data, status_code=304, cookies=cookies)


def bad_request(data=DEFAULT_DATA[False], err="", cookies=None, warnings=None):
    """Returns response with status code ies"""
    return _make_api_response(data, err, status_code=400, cookies=cookies, warnings=warnings)


def unauthorized(data=DEFAULT_DATA[False], err="", cookies=None):
    """Returns response with status code 401"""
    return _make_api_response(data, err, status_code=401, cookies=cookies)


def forbidden(data=DEFAULT_DATA[False], err="", cookies=None):
    """Returns response with status code 403"""
    return _make_api_response(data, err, status_code=403, cookies=cookies)


def not_found(data=DEFAULT_DATA[False], err="", cookies=None):
    """Returns response with status code 404"""
    return _make_api_response(data, err, status_code=404, cookies=cookies)


def conflict(data=DEFAULT_DATA[False], err="", cookies=None):
    """Returns response with status code 409"""
    return _make_api_response(data, err, status_code=409, cookies=cookies)


def precondition_failed(data=DEFAULT_DATA[False], err="", cookies=None):
    """Returns response with status code 412"""
    return _make_api_response(data, err, status_code=412, cookies=cookies)


def teapot(data={**DEFAULT_DATA[False], "teapot": True}, err="", cookies=None):
    """Returns response with status code 418"""
    return _make_api_response(data, err, status_code=418, cookies=cookies)


def too_many_requests(data=DEFAULT_DATA[False], err="", cookies=None):
    """Returns response with status code 429"""
    return _make_api_response(data, err, status_code=429, cookies=cookies)


def internal_error(
    data={**DEFAULT_DATA[False]},
    err="Something went wrong. Contact an administrator.",
    cookies=None,
):
    """Returns response with status code 500"""
    return _make_api_response(data, err, status_code=500, cookies=cookies)


def not_implemented(
    data={**DEFAULT_DATA[False]},
    err="Something went wrong. Contact an administrator.",
    cookies=None,
):
    """Returns response with status code 501"""
    return _make_api_response(data, err, status_code=501, cookies=cookies)


def bad_gateway(
    data={**DEFAULT_DATA[False]},
    err="Something went wrong. Contact an administrator.",
    cookies=None,
):
    """Returns response with status code 502"""
    return _make_api_response(data, err, status_code=502, cookies=cookies)


def service_unavailable(
    data={**DEFAULT_DATA[False]},
    err="Something went wrong. Contact an administrator.",
    cookies=None,
):
    """Returns response with status code 503"""
    return _make_api_response(data, err, status_code=503, cookies=cookies)


def make_file_response(data, name, size, status_code=200, content_type="application/octet-stream"):
    """Returns file response with arbitrary status code"""
    quota_user = flsk_session.pop("quota_user", None)
    quota_set = flsk_session.pop("quota_set", False)
    if quota_user and quota_set:
        QUOTA_TRACKER.end(quota_user)

    response = make_response(data, status_code)
    response.headers["Content-Type"] = content_type
    response.headers["Content-Length"] = size
    response.headers["Content-Disposition"] = 'attachment; filename="%s"' % safe_str(name)
    return response


def stream_file_response(reader, name, size, status_code=200):
    """Returns stream response with arbitrary status code"""
    quota_user = flsk_session.pop("quota_user", None)
    quota_set = flsk_session.pop("quota_set", False)
    if quota_user and quota_set:
        QUOTA_TRACKER.end(quota_user)

    chunk_size = 65535

    def generate():
        reader.seek(0)
        while True:
            data = reader.read(chunk_size)
            if not data:
                break
            yield data
        reader.close()

    headers = {
        "Content-Type": "application/octet-stream",
        "Content-Length": size,
        "Content-Disposition": 'attachment; filename="%s"' % safe_str(name),
    }
    return Response(generate(), status=status_code, headers=headers)


def make_binary_response(data, size, status_code=200):
    """Returns binary response with arbitrary status code"""
    quota_user = flsk_session.pop("quota_user", None)
    quota_set = flsk_session.pop("quota_set", False)
    if quota_user and quota_set:
        QUOTA_TRACKER.end(quota_user)

    response = make_response(data, status_code)
    response.headers["Content-Type"] = "application/octet-stream"
    response.headers["Content-Length"] = size
    return response


def stream_binary_response(reader, status_code=200):
    """Returns streamed binary response with arbitrary status code"""
    quota_user = flsk_session.pop("quota_user", None)
    quota_set = flsk_session.pop("quota_set", False)
    if quota_user and quota_set:
        QUOTA_TRACKER.end(quota_user)

    chunk_size = 4096

    def generate():
        reader.seek(0)
        while True:
            data = reader.read(chunk_size)
            if not data:
                break
            yield data

    return Response(generate(), status=status_code, mimetype="application/octet-stream")
