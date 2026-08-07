#!/usr/bin/env python

import json
import logging
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import redis
from packaging.version import parse
from redis.backoff import ExponentialBackoff
from redis.retry import Retry

from howler.odm.models.config import config
from howler.utils.uid import get_random_id

# Add a version warning if redis python client is < 2.10.0. Older versions
# have a connection bug that can manifest with the dispatcher.
if parse(redis.__version__) <= parse("2.10.0"):
    import warnings

    warnings.warn(
        "%s works best with redis > 2.10.0. You're running"
        " redis %s. You should upgrade." % (__name__, redis.__version__)
    )

APP_NAME = os.environ.get("APP_NAME", "howler")

log = logging.getLogger(f"{APP_NAME}.queue")
pool: dict[tuple[str, str, bool], redis.BlockingConnectionPool] = {}

# TCP keepalive tuning so a connection to a primary that has gone away (e.g.
# during an Azure Managed Redis failover) is detected in ~90s instead of the
# Linux default keepalive idle of ~2 hours. This is the mechanism that lets
# *blocking* reads (BLPOP/BZPOPMIN with timeout=0) notice a dead peer, since we
# deliberately do NOT set socket_timeout (see RESILIENCE_CONFIG below). The
# option constants are platform specific, so each is added only if available.
_KEEPALIVE_OPTIONS: dict[int, int] = {
    getattr(socket, name): value
    for name, value in (("TCP_KEEPIDLE", 60), ("TCP_KEEPINTVL", 10), ("TCP_KEEPCNT", 3))
    if hasattr(socket, name)
}

# Connection resilience defaults. These ensure that during a managed Redis
# failover (e.g. Azure Managed Redis) the client quickly detects dead/stale
# connections and reconnects to the new primary instead of hanging on the OS
# level TCP timeout (which can be several minutes).
#   - socket_connect_timeout: cap how long establishing a new connection can
#     block so a dead endpoint surfaces as a (retryable) error in seconds.
#   - socket_keepalive / socket_keepalive_options: enable and tune TCP
#     keepalives so half-open connections (including those blocked in a long
#     BLPOP/BZPOPMIN) are detected and recycled.
#   - health_check_interval: proactively PING idle pooled connections before
#     use so stale connections to the old primary are recycled transparently.
#
# NOTE: socket_timeout is explicitly set to None. It is a per-read socket
# timeout that redis-py also applies to blocking commands, so any positive value
# makes BLPOP/BZPOPMIN/BRPOP with an infinite (timeout=0) wait raise spurious
# TimeoutErrors (see redis-py #2807). This MUST be set explicitly: redis-py 8.0
# changed the default socket_timeout from None to 5 seconds, so simply omitting
# it would silently break the infinite blocking pops the queue consumers in this
# package rely on. With socket_timeout disabled, keepalives + health checks
# handle failover detection instead.
RESILIENCE_CONFIG: dict[str, Any] = {
    "socket_connect_timeout": 5,
    "socket_timeout": None,
    "socket_keepalive": True,
    "health_check_interval": 15,
}
if _KEEPALIVE_OPTIONS:
    RESILIENCE_CONFIG["socket_keepalive_options"] = _KEEPALIVE_OPTIONS

# Maximum wall-clock time (in seconds) that retry_call will keep retrying after
# the first observed Redis connection failure before giving up and re-raising the
# last error. The retry window starts after the first error because blocking
# Redis reads rely on TCP keepalive to notice a dead peer, and that detection can
# take longer than this retry budget.
RETRY_DEADLINE = 60


def now_as_iso():
    s = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
    return f"{s}Z"


def reply_queue_name(prefix=None, suffix=None):
    if prefix:
        components = [prefix]
    else:
        components = []

    components.append(get_random_id())

    if suffix:
        components.append(str(suffix))

    return "-".join(components)


def retry_call(func, *args, **kw):
    maximum = 2
    exponent = -7
    deadline = None

    while True:
        try:
            ret_val = func(*args, **kw)

            if exponent != -7:
                log.info("Reconnected to Redis!")

            return ret_val
        except (redis.ConnectionError, redis.TimeoutError, OSError) as ce:
            # redis.ConnectionError covers BusyLoadingError (node loading after a
            # failover) and most connect-time socket errors. redis.TimeoutError
            # covers Redis read/connect timeouts. OSError covers the builtin socket
            # errors raised while a managed Redis instance is failing over,
            # including its ConnectionResetError and TimeoutError subclasses.
            #
            # Use a monotonic clock for the retry budget so NTP/system clock
            # adjustments can't make retries give up early or run far too long.
            if deadline is None:
                deadline = time.monotonic() + RETRY_DEADLINE
            elif time.monotonic() >= deadline:
                # Give up after RETRY_DEADLINE so a sustained outage fails the
                # request cleanly instead of blocking the worker indefinitely.
                log.exception("No connection to Redis after %ss, giving up.", RETRY_DEADLINE)
                raise

            log.warning("No connection to Redis, reconnecting... [%s]", ce)
            time.sleep(2**exponent)
            exponent = exponent + 1 if exponent < maximum else exponent


def get_client(
    host: str | redis.Redis | redis.StrictRedis | redis.RedisCluster | None,
    port: int | None,
    private: bool = False,
) -> redis.Redis | redis.StrictRedis | redis.RedisCluster:
    """
    Get Redis instance.

    Args:
        host: Redis host, defaults to nonpersistent host
        port: Redis port, defaults to nonpersistent port
        private: If true then use standard connection, otherwise use a Pool

    Returns:
        Redis instance
    """
    # In case a structure is passed a client as host
    if isinstance(host, (redis.Redis, redis.StrictRedis, redis.RedisCluster)):
        return host

    if not host or not port:
        host = host or config.core.redis.nonpersistent.host
        port = int(port or config.core.redis.nonpersistent.port)

    extra_conn_config: dict[str, Any] = {}
    host_config = None

    # Apply socket connect timeout / keepalive / health-check defaults so the
    # client can detect and recover from managed Redis failovers instead of
    # hanging.
    extra_conn_config.update(RESILIENCE_CONFIG)

    # Pin RESP2 on the wire. redis-py 8.0 switched the default to RESP3; pinning
    # protocol=2 preserves the exact wire behaviour this codebase was written
    # against so the dependency upgrade is behaviour-neutral. Can be revisited to
    # adopt RESP3 once its response shapes have been validated end to end.
    extra_conn_config["protocol"] = 2

    # Configure connection-level retries using the modern Retry API (the
    # replacement for the deprecated retry_on_timeout flag). A fresh Retry
    # instance is built here per get_client call. Note that for pooled clients
    # (private=False) the underlying connection pool is cached by host/port/ssl
    # in get_pool, so this Retry is only applied when the pool is first created
    # and is then effectively shared (per-pool) by every later client on that
    # pool. The Retry config itself is immutable, so this sharing is benign.
    extra_conn_config["retry"] = Retry(ExponentialBackoff(cap=10, base=0.5), retries=3)
    extra_conn_config["retry_on_error"] = [redis.ConnectionError, redis.TimeoutError]

    if host == config.core.redis.nonpersistent.host and port == config.core.redis.nonpersistent.port:
        host_config = config.core.redis.nonpersistent
    else:
        host_config = config.core.redis.persistent

    if host_config.password:
        extra_conn_config["username"] = "default"
        extra_conn_config["password"] = host_config.password

    if host_config.tls_enabled:
        extra_conn_config["ssl"] = True
        extra_conn_config["ssl_cert_reqs"] = "required"

        if host_config.tls_disable_check_hostname:
            extra_conn_config["ssl_check_hostname"] = False

        if host_config.tls_ca_cert:
            if not Path(host_config.tls_ca_cert).exists():
                raise FileNotFoundError(f"Redis TLS CA cert or path '{host_config.tls_ca_cert}' not found.")

            if Path(host_config.tls_ca_cert).is_file():
                extra_conn_config["ssl_ca_certs"] = host_config.tls_ca_cert
            else:
                extra_conn_config["ssl_ca_path"] = host_config.tls_ca_cert

    if host_config.is_cluster is True:
        return redis.RedisCluster(host=host, port=port, **extra_conn_config)  # type: ignore

    if private:
        return redis.StrictRedis(host=host, port=port, **extra_conn_config)  # type: ignore
    else:
        return redis.StrictRedis(connection_pool=get_pool(host, port, **extra_conn_config))


def get_pool(host, port, **kwargs):
    """
    Get Redis connection pool
    Args:
        host: Redis host
        port: Redis port
        **kwargs: Extra parameters to pass to pool connection class

    Returns:
        Redis BlockingConnectionPool
    """
    key = (host, str(port), kwargs.get("ssl", False))
    connection_pool = pool.get(key, None)

    if not connection_pool:
        if "ssl" in kwargs and kwargs["ssl"]:
            # SSLConnection class doesn't accept 'ssl' parameter as it implicitly uses SSL
            kwargs.pop("ssl")
            connection_pool = redis.BlockingConnectionPool(
                host=host,
                port=port,
                max_connections=200,
                connection_class=redis.SSLConnection,
                **kwargs,
            )
        else:
            connection_pool = redis.BlockingConnectionPool(host=host, port=port, max_connections=200, **kwargs)
        pool[key] = connection_pool

    return connection_pool


def decode(data):
    try:
        return json.loads(data)
    except ValueError:
        log.warning("Invalid data on queue: %s", str(data))
        return None
