import functools
import json
import uuid
from typing import Any, Optional, cast

from flask import request
from jwt import InvalidTokenError

import howler.services.auth_service as auth_service
from howler.api import forbidden, ok, unauthorized
from howler.common.exceptions import AuthenticationException
from howler.common.logging import get_logger
from howler.helper.ws import ConnectionClosed, Server

logger = get_logger(__file__)


def ws_response(type, data={}, error=False, status=200, message=""):
    "Create a formatted websocket response"
    return json.dumps({"error": error, "status": status, "message": message, "type": type, **data})


def websocket_auth(required_type: Optional[list[str]] = None, required_priv: Optional[list[str]] = None):  # noqa: C901
    """Authentication for a new websocket connection.

    Args:
        required_type (Optional[list[str]], optional): The type required to access this websocket endpoint.
            Defaults to None.
        required_priv (Optional[list[str]], optional): The privileges required to access this websocket endpoint.
            Defaults to None.
    """
    if required_type is None:
        required_type = ["user"]

    if required_priv is None:
        required_priv = ["R", "W"]

    def wrapper(f):
        @functools.wraps(f)
        def auth(*args, **kwargs):
            ws_id = str(uuid.uuid4())
            ws = None
            try:
                logger.info("%s: Incoming websocket request", ws_id)
                handshake_ctx: dict[str, Any] = {
                    "remote_addr": request.environ.get("REMOTE_ADDR"),
                    "remote_port": request.environ.get("REMOTE_PORT"),
                    "x_forwarded_for": request.environ.get("HTTP_X_FORWARDED_FOR"),
                    "x_forwarded_proto": request.environ.get("HTTP_X_FORWARDED_PROTO"),
                    "host": request.environ.get("HTTP_HOST"),
                    "connection": request.environ.get("HTTP_CONNECTION"),
                    "upgrade": request.environ.get("HTTP_UPGRADE"),
                    "sec_websocket_key": request.environ.get("HTTP_SEC_WEBSOCKET_KEY"),
                    "sec_websocket_version": request.environ.get("HTTP_SEC_WEBSOCKET_VERSION"),
                    "sec_websocket_protocol": request.environ.get("HTTP_SEC_WEBSOCKET_PROTOCOL"),
                    "path_info": request.environ.get("PATH_INFO"),
                    "request_id": request.environ.get("HTTP_X_REQUEST_ID"),
                }
                logger.debug("%s: Websocket request context: %s", ws_id, handshake_ctx)
                ws = Server(request.environ, ping_interval=5)
                logger.info("%s: Websocket upgrade established", ws_id)

                auth_header = cast(str, ws.receive())
                logger.debug(
                    "%s: Received auth header; bearer_prefix=%s; length=%s",
                    ws_id,
                    bool(auth_header and auth_header.strip().lower().startswith("bearer ")),
                    len(auth_header) if auth_header is not None else 0,
                )

                user, privs = auth_service.bearer_auth(auth_header)

                if not user or not privs:
                    raise AuthenticationException()  # noqa: TRY301

                if not set(required_priv) & set(privs):
                    logger.warning("%s: Authentication header is invalid", ws_id)
                    ws.close(
                        1008,
                        ws_response(
                            "error",
                            error=True,
                            status=403,
                            message="The method you've used to login does not give you access to this API.",
                        ),
                    )
                    return forbidden()

                logger.info("%s authenticated as %s", ws_id, user.uname)
                ws.send(
                    ws_response(
                        "info",
                        {
                            "message": f"Listener authenticated as {user.uname}",
                            "id": ws_id,
                            "username": user.uname,
                        },
                    )
                )
                logger.debug("%s: Privileges: %s", ws_id, privs)

                f(ws, *args, ws_id=ws_id, user=user, privs=privs, **kwargs)
            except ConnectionClosed:
                logger.info("%s: Client closed connection", ws_id)
            except (
                AuthenticationException,
                ValueError,
                InvalidTokenError,
            ):
                logger.warning("%s: Authentication header is invalid", ws_id)
                if ws:
                    ws.close(
                        1008,
                        ws_response(
                            "error",
                            error=True,
                            status=401,
                            message="Authentication header is invalid.",
                        ),
                    )

                return unauthorized()
            finally:
                if ws:
                    try:
                        ws.close()
                    except Exception as e:
                        logger.debug("%s: Exception on WS close: %s", ws_id, str(e))
                    finally:
                        ws.connected = False

                logger.info("%s: Websocket request finished", ws_id)
                return ok()

        return auth

    return wrapper
