import base64
import json
import os
from typing import Any

from flask import Blueprint, request

import howler.services.event_service as event_service
from howler.api import ok, unauthorized
from howler.common.logging import get_logger
from howler.datastore.operations import OdmHelper
from howler.helper.ws import ConnectionClosed, Server
from howler.odm.models.hit import Hit
from howler.security.socket import websocket_auth, ws_response
from howler.utils.socket_utils import check_action

HWL_INTERPOD_COMMS_SECRET = os.getenv("HWL_INTERPOD_COMMS_SECRET", "secret")

socket_api = Blueprint("socket", "socket", url_prefix="/socket/v1")

socket_api._doc = "Endpoints concerning websocket connectivity between the client and server"  # type: ignore

logger = get_logger(__file__)

hit_helper = OdmHelper(Hit)


@socket_api.route("/emit/<event>", methods=["POST"])
def emit(event: str):
    """Emit an event to all listening websockets"""
    if "Authorization" not in request.headers:
        return unauthorized(err="Missing authorization header")

    auth_data = base64.b64decode(request.headers["Authorization"].split(" ")[1]).decode().split(":")[1]

    if HWL_INTERPOD_COMMS_SECRET == "secret":  # noqa: S105
        logger.warning("Using default interpod secret! DO NOT allow this on a production instance.")

    if auth_data != HWL_INTERPOD_COMMS_SECRET:
        logger.warning("Invalid auth secret provided: %s (expected: %s)", auth_data, HWL_INTERPOD_COMMS_SECRET)

        return unauthorized(err="Invalid auth data")

    event_service.emit(event, request.json)

    return ok()


@socket_api.route("/connect", websocket=True)
@websocket_auth(required_priv=["R"])
def connect(ws: Server, *args: Any, ws_id: str, **kwargs):
    """Connect to the server to monitor for updates via websocket

    Variables:
    None

    Optional Arguments:
    None

    Result Example:
    A continuous websocket connection
    """
    outstanding_actions: list[tuple[str, str, bool]] = []

    def send_hit(data: dict[str, Any]):
        logger.debug("Sending hit update: %s", data["hit"]["howler"]["id"])
        ws.send(ws_response("hits", data))

    def send_broadcast(data: dict[str, str]):
        logger.debug("Sending broadcast: %s", data)
        ws.send(ws_response("broadcast", {"event": data}))

    def send_action(data: dict[str, str]):
        logger.debug("Sending action: %s", data)
        ws.send(ws_response("action", data))

    try:
        event_service.on("hits", send_hit)
        event_service.on("broadcast", send_broadcast)
        event_service.on("action", send_action)
        while ws.connected:
            data = ws.receive(10)
            if data:
                obj = json.loads(data)

                if "id" not in obj or "action" not in obj or "broadcast" not in obj:
                    ws.close(
                        1008,
                        ws_response(
                            "error",
                            error=True,
                            status=400,
                            message="Sent data is invalid.",
                        ),
                    )
                    return

                outstanding_actions = check_action(
                    obj["id"], obj["action"], obj["broadcast"], outstanding_actions=outstanding_actions, **kwargs
                )
            else:
                logger.debug(ws_id + " listening")
    except Exception as e:
        if isinstance(e, ConnectionClosed):
            raise
        else:
            logger.exception("Exception on connect.")
    finally:
        event_service.off("hits", send_hit)
        event_service.off("broadcast", send_broadcast)
        event_service.off("action", send_action)

        for id, action, broadcast in outstanding_actions:
            outstanding_actions = check_action(id, action, broadcast, outstanding_actions=outstanding_actions, **kwargs)
