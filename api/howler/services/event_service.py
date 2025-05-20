import os
from typing import Any, Callable

import requests
from requests.auth import HTTPBasicAuth

from howler.common.logging import get_logger
from howler.config import DEBUG, HWL_USE_WEBSOCKET_API, config

logger = get_logger(__file__)

handlers: dict[str, list[Callable]] = {}

HWL_INTERPOD_COMMS_SECRET = os.getenv("HWL_INTERPOD_COMMS_SECRET", "secret")


def emit(event: str, data: Any):
    """Emit a new instance of the specified event, with additional data related to that event

    Args:
        event (str): The event id
        data (Any): A JSON-serializable package of data related to the event id
    """
    logger.debug("Recieved emit request for event type %s", event)

    if not DEBUG and not HWL_USE_WEBSOCKET_API:
        res = None
        if config.ui.websocket_url:
            logger.debug("POST %s - event:%s", config.ui.websocket_url, event)

            if HWL_INTERPOD_COMMS_SECRET == "secret":  # noqa: S105
                logger.warning("Using default interpod secret! DO NOT allow this on a production instance.")

            try:
                res = requests.post(
                    f"{config.ui.websocket_url}/{event}",
                    json=data,
                    auth=HTTPBasicAuth("user", HWL_INTERPOD_COMMS_SECRET),
                    timeout=5,
                )
            except Exception:
                logger.exception("Error on connection to websocket server.")

        if res is None or not res.ok:
            logger.fatal(
                "Event propagation failed: %s",
                (
                    "No websocket_url provided"
                    if res is None
                    else f"Status code: {res.status_code}, Error message: {res.json().get('api_error_message', 'None')}"
                ),
            )
    else:
        if event not in handlers:
            return

        logger.debug(f"event:{event} - emitting data")

        for handler in handlers[event]:
            handler(data)


def on(event: str, handler: Callable):
    """Add a new listener to the specified event

    Args:
        event (str): The id of the event to listen for
        handler (Callable): Then function that will handle any instances of this event being emitted
    """
    if event not in handlers:
        handlers[event] = []

    handlers[event].append(handler)

    logger.debug(f"event:{event} - added listener")


def off(event: str, handler: Callable):
    """Remove an existing listener from the specified event

    Args:
        event (str): The id to remove the handler from
        handler (Callable): The handler to remove from the specified id
    """
    if event not in handlers:
        return

    if handler not in handlers[event]:
        return

    handlers[event] = [h for h in handlers[event] if h != handler]

    logger.debug(f"event:{event} - removed listener")
