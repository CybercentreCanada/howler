"""Viewer service for tracking active viewers of entities (hits, cases, observables) in Redis.

Stores viewer presence as ephemeral Redis sets with TTL, replacing the
previous approach of persisting viewers directly in the ODM/ElasticSearch.
"""

from howler.config import redis
from howler.remote.datatypes import retry_call
from howler.services import event_service

VIEWER_KEY_PREFIX = "viewers"
VIEWER_TTL = 3600  # 1 hour


def _key(entity_id: str) -> str:
    return f"{VIEWER_KEY_PREFIX}:{entity_id}"


def add_viewer(entity_id: str, username: str) -> None:
    """Record that a user is viewing the given entity."""
    key = _key(entity_id)
    retry_call(redis.sadd, key, username)
    retry_call(redis.expire, key, VIEWER_TTL)
    _emit_update(entity_id)


def remove_viewer(entity_id: str, username: str) -> None:
    """Record that a user has stopped viewing the given entity."""
    retry_call(redis.srem, _key(entity_id), username)
    _emit_update(entity_id)


def get_viewers(entity_id: str) -> list[str]:
    """Return the list of usernames currently viewing the given entity."""
    members = retry_call(redis.smembers, _key(entity_id))
    return sorted(m.decode() if isinstance(m, bytes) else m for m in members)


def _emit_update(entity_id: str) -> None:
    event_service.emit(
        "viewers_update",
        {"id": entity_id, "viewers": get_viewers(entity_id)},
    )
