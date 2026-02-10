#!/usr/bin/env python

import json
import logging
import time
from datetime import datetime
from pathlib import Path
import redis
from packaging.version import parse

from howler.common import loader
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


log = logging.getLogger(f"{loader.APP_NAME}.queue")
pool: dict[tuple[str, str], redis.BlockingConnectionPool] = {}


def now_as_iso():
    s = datetime.utcfromtimestamp(time.time()).isoformat()
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

    while True:
        try:
            ret_val = func(*args, **kw)

            if exponent != -7:
                log.info("Reconnected to Redis!")

            return ret_val
        except (redis.ConnectionError, ConnectionResetError) as ce:
            log.warning(f"No connection to Redis, reconnecting... [{ce}]")
            time.sleep(2**exponent)
            exponent = exponent + 1 if exponent < maximum else exponent


def get_client(host, port, private):
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

    extra_conn_config = {}
    host_config = None

    if host == config.core.redis.nonpersistent.host:
        host_config = config.core.redis.nonpersistent
    else:
        host_config = config.core.redis.persistent

    if host_config.password:
        extra_conn_config["username"] = "default"
        extra_conn_config["password"] = host_config.password

    if host_config.tls_enabled:
        extra_conn_config["ssl"] = True
        extra_conn_config["ssl_cert_reqs"] = "required"

        if host_config.tls_ca_cert:
            if not Path(host_config.tls_ca_cert).exists():
                raise FileNotFoundError("Redis TLS CA cert or Path not found.")

            if Path(host_config.tls_ca_cert).is_file():
                extra_conn_config["ssl_ca_certs"] = host_config.tls_ca_cert
            else:
                extra_conn_config["ssl_ca_path"] = host_config.tls_ca_cert

    if host_config.is_cluster is True:
        return redis.RedisCluster(host=host, port=port, **extra_conn_config)

    if private:
        return redis.StrictRedis(host=host, port=port, **extra_conn_config)
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
                host=host, port=port, max_connections=200, connection_class=redis.SSLConnection, **kwargs
            )
        else:
            connection_pool = redis.BlockingConnectionPool(host=host, port=port, max_connections=200)
        pool[key] = connection_pool

    return connection_pool


def decode(data):
    try:
        return json.loads(data)
    except ValueError:
        log.warning("Invalid data on queue: %s", str(data))
        return None
