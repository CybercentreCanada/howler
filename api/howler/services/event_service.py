import os
from typing import Any, Callable

from opentelemetry import trace

from howler.common.logging import get_logger
from howler.config import DEBUG, config
from howler.remote.datatypes.events import EventSender, EventWatcher

logger = get_logger(__file__)
tracer = trace.get_tracer(__name__)

handlers: dict[str, list[Callable]] = {}

HWL_INTERPOD_COMMS_SECRET = os.getenv("HWL_INTERPOD_COMMS_SECRET", "secret")

# Lazily initialised — call _get_sender() to obtain the singleton.
_sender: EventSender[dict[str, Any]] | None = None
_watcher: EventWatcher[dict[str, Any]] | None = None
_watcher_started = False


def _get_sender():
    """Return the shared EventSender, creating it on first use."""
    global _sender
    if _sender is None:
        _sender = EventSender(
            "howler.events",
            host=config.core.redis.nonpersistent.host,
            port=config.core.redis.nonpersistent.port,
            private=False,
        )

    return _sender


def _dispatch(data: dict[str, Any]):
    """Unpack a pubsub message and dispatch to registered handlers."""
    event_type = data.get("__event__")
    payload = data.get("__payload__")
    if not event_type or payload is None:
        logger.warning("Received malformed pubsub message: %s", data)
        return

    if event_type not in handlers:
        return

    for handler in handlers[event_type]:
        try:
            handler(payload)
        except Exception:
            logger.exception("Error in event handler for %s", event_type)


def start_watcher():
    """Start the Redis pubsub watcher that routes incoming events to local handlers.

    Safe to call multiple times — only the first invocation has an effect.
    Must be called after the Flask app is initialised (e.g. in app.py).
    """
    global _watcher, _watcher_started

    if _watcher_started:
        return

    watcher = EventWatcher[dict[str, Any]](
        host=config.core.redis.nonpersistent.host,
        port=config.core.redis.nonpersistent.port,
        private=False,
    )

    watcher.register("howler.events.*", _dispatch)
    watcher.start()
    _watcher = watcher
    _watcher_started = True
    logger.info("Redis pubsub event watcher started")


@tracer.start_as_current_span(f"{__name__}.emit")
def emit(event: str, data: Any):
    """Emit a new instance of the specified event, with additional data related to that event

    Args:
        event (str): The event id
        data (Any): A JSON-serializable package of data related to the event id
    """
    logger.debug("Recieved emit request for event type %s", event)

    if DEBUG and not _watcher_started:
        # In debug/single-process mode without a watcher, call handlers
        # directly for immediate feedback.
        if event in handlers:
            logger.debug("event:%s - emitting data (in-process)", event)
            for handler in handlers[event]:
                handler(data)

    # Always publish to Redis so other pods receive the event.
    try:
        _get_sender().send(event, {"__event__": event, "__payload__": data})
    except Exception:
        logger.exception("Failed to publish event %s to Redis", event)


def on(event: str, handler: Callable):
    """Add a new listener to the specified event

    Args:
        event (str): The id of the event to listen for
        handler (Callable): Then function that will handle any instances of this event being emitted
    """
    if event not in handlers:
        handlers[event] = []

    handlers[event].append(handler)

    logger.debug("event:%s - added listener", event)


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

    logger.debug("event:%s - removed listener", event)
