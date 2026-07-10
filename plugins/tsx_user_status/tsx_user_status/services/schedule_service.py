"""Schedule retrieval and caching service.

Schedules are stored in Azure Blob Storage but read by multiple parts of the
system. To avoid each consumer pulling from blob storage on every request,
this module caches the schedules as a single JSON-encoded string in Redis
(``SET key value EX <ttl>``) and exposes a single accessor that other modules
can call. Cache freshness is governed entirely by the Redis TTL configured
via ``schedules_cache_ttl`` in the plugin config.
"""

import json
from typing import Optional

import redis as redis_lib
from azure.storage.blob import BlobServiceClient
from howler.common.logging import get_logger
from howler.config import redis
from opentelemetry import trace

logger = get_logger(__file__)
tracer = trace.get_tracer(__name__)


def build_connection_string(account_name: str, account_key: str) -> str:
    """Build an Azure Storage connection string.

    Args:
        account_name: Azure Storage account name.
        account_key: Azure Storage account key.

    Returns:
        A properly formatted Azure Storage connection string.
    """
    return (
        f"DefaultEndpointsProtocol=https;AccountName={account_name};"
        f"AccountKey={account_key};EndpointSuffix=core.windows.net"
    )


@tracer.start_as_current_span("_fetch_schedules_from_blob")
def fetch_schedules_from_blob(config: object) -> dict[str, list[str]]:
    """Fetch and parse schedules from Azure Blob Storage.

    Args:
        config: Plugin config object with ``schedules_account``,
            ``schedules_key``, ``schedules_container`` and ``schedules_blob``
            attributes.

    Returns:
        A dictionary mapping team names to lists of shift strings.

    Raises:
        json.JSONDecodeError: If blob content is not valid JSON.
        ValueError: If schedule format is invalid.
        AzureError: If Azure connectivity fails.
    """
    connection_string = build_connection_string(
        config.schedules_account,
        config.schedules_key,
    )
    blob_client = BlobServiceClient.from_connection_string(connection_string).get_blob_client(
        container=config.schedules_container,
        blob=config.schedules_blob,
    )

    content = blob_client.download_blob().readall().decode("utf-8")
    schedules = json.loads(content)

    if isinstance(schedules, dict) and isinstance(schedules.get("schedule"), dict):
        schedules = schedules["schedule"]

    if not isinstance(schedules, dict):
        raise ValueError("Invalid schedule format in blob")  # noqa: TRY004

    return schedules


def _read_from_cache(config: object) -> Optional[dict[str, list[str]]]:
    """Read schedules from the Redis cache.

    Args:
        config: Plugin config object (used for cache key lookup).

    Returns:
        The cached schedules dict, or ``None`` if the cache key is absent or
        Redis is unreachable. An empty dict is a valid cached value and is
        returned as-is.
    """
    try:
        raw = redis.get(config.schedules_cache_key)
    except (redis_lib.RedisError, ConnectionResetError, OSError):
        logger.exception("Failed to read schedules from Redis cache")
        return None

    if raw is None:
        return None

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError):
        logger.exception("Cached schedules payload is corrupted; ignoring")
        return None

    if not isinstance(parsed, dict):
        logger.warning(
            "Cached schedules payload has unexpected type %s; ignoring",
            type(parsed).__name__,
        )
        return None

    return parsed


def _write_to_cache(config: object, schedules: dict[str, list[str]]) -> None:
    """Populate the Redis cache with the given schedules.

    Args:
        config: Plugin config object (used for cache key and TTL lookup).
        schedules: Schedules dict to cache.
    """
    try:
        redis.set(
            config.schedules_cache_key,
            json.dumps(schedules),
            ex=config.schedules_cache_ttl,
        )
    except (redis_lib.RedisError, ConnectionResetError, OSError):
        logger.exception("Failed to write schedules to Redis cache")


@tracer.start_as_current_span("get_schedules")
def get_schedules(config: object) -> dict[str, list[str]]:
    """Return shift schedules, preferring the Redis cache.

    On a cache miss the schedules are fetched from Azure Blob Storage and the
    cache is populated for subsequent callers. Cache freshness is governed by
    the Redis TTL (``config.schedules_cache_ttl``).

    Args:
        config: Plugin config object.

    Returns:
        A dictionary mapping team names to lists of shift strings.

    Raises:
        json.JSONDecodeError: If blob content is not valid JSON.
        ValueError: If schedule format is invalid.
        AzureError: If Azure connectivity fails on a cold cache.
    """
    cached = _read_from_cache(config)
    if cached is not None:
        logger.debug("Returning schedules from cache (%d teams)", len(cached))
        return cached

    schedules = fetch_schedules_from_blob(config)
    _write_to_cache(config, schedules)
    return schedules


__all__ = [
    "fetch_schedules_from_blob",
    "get_schedules",
]
