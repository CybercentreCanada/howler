"""
now_as_iso - Returns a valid ISO-8601 string ending in Z
reply_queue_name - Default, prefix, suffix, prefix+suffix, uniqueness across 50 calls
decode - Valid dict/list/string JSON, invalid JSON returns None
retry_call - Immediate success, retries on ConnectionError, retries on ConnectionResetError
get_pool - Returns BlockingConnectionPool, caching by host/port, distinct pools for different hosts, SSL uses SSLConnection, SSL kwarg is stripped
get_client – Returns an existing Redis, StrictRedis, or RedisCluster instance unchanged
get_client – private=True → direct StrictRedis, private=False → pool-backed, cluster mode → RedisCluster, None host/port falls back to configured nonpersistent
get_client – auth/TLS -> Password forwarded as username/password, TLS with CA file sets ssl_ca_certs, TLS with CA dir sets ssl_ca_path, missing cert path raises FileNotFoundError

A notable technique used: redis.StrictRedis and redis.RedisCluster are patched with real subclasses (not MagicMock) so the isinstance() guard inside get_client keeps working correctly, while still capturing constructor arguments for assertions."""

import json
from unittest.mock import MagicMock, patch

import pytest
import redis

from howler.remote.datatypes import (
    decode,
    get_client,
    get_pool,
    now_as_iso,
    reply_queue_name,
    retry_call,
)

# ---------------------------------------------------------------------------
# now_as_iso
# ---------------------------------------------------------------------------


def test_now_as_iso_format():
    result = now_as_iso()
    assert isinstance(result, str)
    assert result.endswith("Z")
    from datetime import datetime

    datetime.fromisoformat(result[:-1])


# ---------------------------------------------------------------------------
# reply_queue_name
# ---------------------------------------------------------------------------


def test_reply_queue_name_default():
    name = reply_queue_name()
    assert isinstance(name, str)
    assert len(name) > 0


def test_reply_queue_name_prefix():
    name = reply_queue_name(prefix="myprefix")
    assert name.startswith("myprefix-")


def test_reply_queue_name_suffix():
    name = reply_queue_name(suffix="mysuffix")
    assert name.endswith("-mysuffix")


def test_reply_queue_name_prefix_and_suffix():
    name = reply_queue_name(prefix="pre", suffix="suf")
    assert name.startswith("pre-")
    assert name.endswith("-suf")
    parts = name.split("-")
    assert len(parts) >= 3


def test_reply_queue_name_uniqueness():
    names = {reply_queue_name() for _ in range(50)}
    assert len(names) == 50


# ---------------------------------------------------------------------------
# decode
# ---------------------------------------------------------------------------


def test_decode_valid_json():
    assert decode(json.dumps({"key": "value"})) == {"key": "value"}


def test_decode_valid_list():
    assert decode(json.dumps([1, 2, 3])) == [1, 2, 3]


def test_decode_valid_string():
    assert decode(json.dumps("hello")) == "hello"


def test_decode_invalid_json():
    result = decode("not-valid-json")
    assert result is None


# ---------------------------------------------------------------------------
# retry_call
# ---------------------------------------------------------------------------


def test_retry_call_succeeds_immediately():
    func = MagicMock(return_value=42)
    assert retry_call(func, "arg1", key="val") == 42
    func.assert_called_once_with("arg1", key="val")


def test_retry_call_retries_on_connection_error():
    func = MagicMock(
        side_effect=[
            redis.ConnectionError("conn error"),
            redis.ConnectionError("conn error"),
            "success",
        ]
    )
    with patch("time.sleep"):
        result = retry_call(func)
    assert result == "success"
    assert func.call_count == 3


def test_retry_call_retries_on_connection_reset():
    func = MagicMock(side_effect=[ConnectionResetError(), "ok"])
    with patch("time.sleep"):
        result = retry_call(func)
    assert result == "ok"


# ---------------------------------------------------------------------------
# get_pool
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_pool():
    """Reset the module-level pool dict between tests."""
    import howler.remote.datatypes as dt

    dt.pool.clear()
    yield
    dt.pool.clear()


def test_get_pool_returns_blocking_connection_pool():
    pool = get_pool("localhost", 6379)
    assert isinstance(pool, redis.BlockingConnectionPool)


def test_get_pool_cached():
    pool1 = get_pool("localhost", 6379)
    pool2 = get_pool("localhost", 6379)
    assert pool1 is pool2


def test_get_pool_different_hosts_different_pools():
    pool_a = get_pool("hostA", 6379)
    pool_b = get_pool("hostB", 6379)
    assert pool_a is not pool_b


def test_get_pool_ssl_uses_ssl_connection():
    ssl_pool = get_pool("localhost", 6380, ssl=True, ssl_ca_certs="/dev/null")
    assert isinstance(ssl_pool, redis.BlockingConnectionPool)
    assert ssl_pool.connection_class is redis.SSLConnection


def test_get_pool_ssl_strips_ssl_kwarg():
    """The 'ssl' kwarg must be stripped before passing to SSLConnection."""
    pool = get_pool("localhost", 6381, ssl=True, ssl_ca_certs="/dev/null")
    assert pool is not None


# ---------------------------------------------------------------------------
# get_client – helpers
#
# Patching redis.StrictRedis / redis.RedisCluster with a MagicMock breaks
# isinstance() because a MagicMock is not a type.  We use real subclasses
# that skip the network-connecting __init__ instead.
# ---------------------------------------------------------------------------


def _make_redis_server_mock(
    host="localhost",
    port=6379,
    password=None,
    tls_enabled=False,
    tls_ca_cert=None,
    is_cluster=False,
):
    m = MagicMock()
    m.host = host
    m.port = port
    m.password = password
    m.tls_enabled = tls_enabled
    m.tls_ca_cert = tls_ca_cert
    m.is_cluster = is_cluster
    return m


def _make_fake_strict_redis():
    """
    Return (FakeClass, call_log).
    FakeClass is a real subclass of redis.StrictRedis that records kwargs
    without opening a socket so isinstance() checks remain valid.
    """
    call_log = []

    class FakeStrictRedis(redis.StrictRedis):
        def __init__(self, *args, **kwargs):
            call_log.append({"args": args, "kwargs": kwargs})

    return FakeStrictRedis, call_log


def _make_fake_redis_cluster():
    call_log = []

    class FakeRedisCluster(redis.RedisCluster):
        def __init__(self, *args, **kwargs):
            call_log.append({"args": args, "kwargs": kwargs})

    return FakeRedisCluster, call_log


# ---------------------------------------------------------------------------
# get_client – pass-through of existing client objects
# ---------------------------------------------------------------------------


def test_get_client_returns_existing_redis_instance():
    existing = MagicMock(spec=redis.Redis)
    assert get_client(existing, 6379, False) is existing


def test_get_client_returns_existing_strict_redis_instance():
    existing = MagicMock(spec=redis.StrictRedis)
    assert get_client(existing, 6379, False) is existing


def test_get_client_returns_existing_cluster_instance():
    existing = MagicMock(spec=redis.RedisCluster)
    assert get_client(existing, 6379, False) is existing


# ---------------------------------------------------------------------------
# get_client – connection routing
# ---------------------------------------------------------------------------


def test_get_client_private_creates_strict_redis():
    """private=True must create a StrictRedis directly (no pool)."""
    FakeStrictRedis, log = _make_fake_strict_redis()

    with (
        patch("howler.remote.datatypes.redis.StrictRedis", new=FakeStrictRedis),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock()
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        result = get_client("localhost", 6379, private=True)

    assert isinstance(result, redis.StrictRedis)
    assert log[-1]["kwargs"] == {"host": "localhost", "port": 6379}


def test_get_client_non_private_uses_pool():
    """private=False must create a StrictRedis backed by a connection pool."""
    FakeStrictRedis, log = _make_fake_strict_redis()
    mock_pool = MagicMock()

    with (
        patch("howler.remote.datatypes.redis.StrictRedis", new=FakeStrictRedis),
        patch("howler.remote.datatypes.get_pool", return_value=mock_pool) as mock_get_pool,
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock()
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        result = get_client("localhost", 6379, private=False)

    mock_get_pool.assert_called_once()
    assert isinstance(result, redis.StrictRedis)
    assert log[-1]["kwargs"] == {"connection_pool": mock_pool}


def test_get_client_cluster_mode():
    """When is_cluster=True a RedisCluster must be returned."""
    FakeRedisCluster, log = _make_fake_redis_cluster()
    host, port = "127.0.0.1", 6379

    with (
        patch("howler.remote.datatypes.redis.RedisCluster", new=FakeRedisCluster),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(host=host, port=port, is_cluster=True)
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        result = get_client(host, port, private=False)

    assert isinstance(result, redis.RedisCluster)
    assert log[-1]["kwargs"] == {"host": host, "port": port}


def test_get_client_defaults_to_nonpersistent_when_no_host_port():
    """Passing host=None/port=None must fall back to the configured nonpersistent host."""
    FakeStrictRedis, log = _make_fake_strict_redis()
    mock_pool = MagicMock()

    with (
        patch("howler.remote.datatypes.redis.StrictRedis", new=FakeStrictRedis),
        patch("howler.remote.datatypes.get_pool", return_value=mock_pool) as mock_get_pool,
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(host="redis-default", port=6379)
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        result = get_client(None, None, private=False)

    mock_get_pool.assert_called_once()
    assert isinstance(result, redis.StrictRedis)


# ---------------------------------------------------------------------------
# get_client – auth / TLS options
# ---------------------------------------------------------------------------


def test_get_client_with_password():
    """Password must be forwarded as username/password kwargs."""
    FakeStrictRedis, log = _make_fake_strict_redis()

    with (
        patch("howler.remote.datatypes.redis.StrictRedis", new=FakeStrictRedis),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(password="secret")
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        get_client("localhost", 6379, private=True)

    kw = log[-1]["kwargs"]
    assert kw.get("username") == "default"
    assert kw.get("password") == "secret"


def test_get_client_tls_enabled_with_ca_file(tmp_path):
    """TLS + a CA cert *file* must set ssl=True and ssl_ca_certs."""
    FakeStrictRedis, log = _make_fake_strict_redis()
    ca_cert = tmp_path / "ca.pem"
    ca_cert.write_text("CERT")

    with (
        patch("howler.remote.datatypes.redis.StrictRedis", new=FakeStrictRedis),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(tls_enabled=True, tls_ca_cert=str(ca_cert))
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        get_client("localhost", 6379, private=True)

    kw = log[-1]["kwargs"]
    assert kw.get("ssl") is True
    assert kw.get("ssl_cert_reqs") == "required"
    assert kw.get("ssl_ca_certs") == str(ca_cert)
    assert "ssl_ca_path" not in kw


def test_get_client_tls_enabled_with_ca_dir(tmp_path):
    """TLS + a CA cert *directory* must set ssl_ca_path (not ssl_ca_certs)."""
    FakeStrictRedis, log = _make_fake_strict_redis()

    with (
        patch("howler.remote.datatypes.redis.StrictRedis", new=FakeStrictRedis),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(tls_enabled=True, tls_ca_cert=str(tmp_path))
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        get_client("localhost", 6379, private=True)

    kw = log[-1]["kwargs"]
    assert kw.get("ssl_ca_path") == str(tmp_path)
    assert "ssl_ca_certs" not in kw


def test_get_client_tls_enabled_cert_not_found():
    """TLS with a non-existent CA cert path must raise FileNotFoundError."""
    with patch("howler.remote.datatypes.config") as mock_config:
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(
            tls_enabled=True, tls_ca_cert="/nonexistent/path/ca.pem"
        )
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        with pytest.raises(FileNotFoundError, match="not found"):
            get_client("localhost", 6379, private=True)


# ---------------------------------------------------------------------------
# get_client – private=False (pooled) with password / TLS
#
# When private=False the auth/TLS kwargs must flow from get_client into
# get_pool, which forwards them to BlockingConnectionPool.  We let get_pool
# run for real (no mock) so we can inspect the pool that was actually built.
# ---------------------------------------------------------------------------


def test_get_client_non_private_with_password():
    """private=False + password: credentials must be forwarded to get_pool and
    on to BlockingConnectionPool."""
    FakeStrictRedis, log = _make_fake_strict_redis()

    with (
        patch("howler.remote.datatypes.redis.StrictRedis", new=FakeStrictRedis),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(password="poolpass")
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        get_client("localhost", 6379, private=False)

    # StrictRedis must be called with a connection_pool, not bare host/port
    kw = log[-1]["kwargs"]
    assert "connection_pool" in kw
    pool_obj = kw["connection_pool"]
    assert isinstance(pool_obj, redis.BlockingConnectionPool)
    # The pool must carry the credentials so new connections authenticate
    assert pool_obj.connection_kwargs.get("username") == "default"
    assert pool_obj.connection_kwargs.get("password") == "poolpass"


def test_get_client_non_private_with_tls_ca_file(tmp_path):
    """private=False + TLS CA file: ssl kwargs must be forwarded to get_pool,
    which must create an SSLConnection-backed pool carrying ssl_ca_certs."""
    FakeStrictRedis, log = _make_fake_strict_redis()
    ca_cert = tmp_path / "ca.pem"
    ca_cert.write_text("CERT")

    with (
        patch("howler.remote.datatypes.redis.StrictRedis", new=FakeStrictRedis),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(tls_enabled=True, tls_ca_cert=str(ca_cert))
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        get_client("localhost", 6379, private=False)

    pool_obj = log[-1]["kwargs"]["connection_pool"]
    assert isinstance(pool_obj, redis.BlockingConnectionPool)
    assert pool_obj.connection_class is redis.SSLConnection
    # 'ssl' is stripped by get_pool before creating an SSLConnection pool
    assert "ssl" not in pool_obj.connection_kwargs
    assert pool_obj.connection_kwargs.get("ssl_cert_reqs") == "required"
    assert pool_obj.connection_kwargs.get("ssl_ca_certs") == str(ca_cert)


def test_get_client_non_private_with_tls_ca_dir(tmp_path):
    """private=False + TLS CA directory: ssl_ca_path must be forwarded to
    get_pool and carried by the SSLConnection-backed pool."""
    FakeStrictRedis, log = _make_fake_strict_redis()

    with (
        patch("howler.remote.datatypes.redis.StrictRedis", new=FakeStrictRedis),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(tls_enabled=True, tls_ca_cert=str(tmp_path))
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        get_client("localhost", 6379, private=False)

    pool_obj = log[-1]["kwargs"]["connection_pool"]
    assert isinstance(pool_obj, redis.BlockingConnectionPool)
    assert pool_obj.connection_class is redis.SSLConnection
    assert "ssl" not in pool_obj.connection_kwargs
    assert pool_obj.connection_kwargs.get("ssl_ca_path") == str(tmp_path)
    assert "ssl_ca_certs" not in pool_obj.connection_kwargs


def test_get_client_non_private_with_password_and_tls(tmp_path):
    """private=False + password + TLS: all kwargs must arrive together in the
    pool's connection_kwargs."""
    FakeStrictRedis, log = _make_fake_strict_redis()
    ca_cert = tmp_path / "ca.pem"
    ca_cert.write_text("CERT")

    with (
        patch("howler.remote.datatypes.redis.StrictRedis", new=FakeStrictRedis),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(
            password="poolsecret", tls_enabled=True, tls_ca_cert=str(ca_cert)
        )
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        get_client("localhost", 6379, private=False)

    pool_obj = log[-1]["kwargs"]["connection_pool"]
    assert isinstance(pool_obj, redis.BlockingConnectionPool)
    assert pool_obj.connection_class is redis.SSLConnection
    ck = pool_obj.connection_kwargs
    assert ck.get("username") == "default"
    assert ck.get("password") == "poolsecret"
    assert ck.get("ssl_cert_reqs") == "required"
    assert ck.get("ssl_ca_certs") == str(ca_cert)
    assert "ssl" not in ck


# ---------------------------------------------------------------------------
# get_client – RedisCluster with password / TLS
# ---------------------------------------------------------------------------


def test_get_client_cluster_with_password():
    """When is_cluster=True and a password is configured, credentials must be
    forwarded to RedisCluster."""
    FakeRedisCluster, log = _make_fake_redis_cluster()
    host, port = "127.0.0.1", 6379

    with (
        patch("howler.remote.datatypes.redis.RedisCluster", new=FakeRedisCluster),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(
            host=host, port=port, password="clusterpass", is_cluster=True
        )
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        result = get_client(host, port, private=False)

    assert isinstance(result, redis.RedisCluster)
    kw = log[-1]["kwargs"]
    assert kw["host"] == host
    assert kw["port"] == port
    assert kw["username"] == "default"
    assert kw["password"] == "clusterpass"


def test_get_client_cluster_with_tls_ca_file(tmp_path):
    """When is_cluster=True and TLS is enabled with a CA cert file, ssl kwargs
    must be forwarded to RedisCluster."""
    FakeRedisCluster, log = _make_fake_redis_cluster()
    host, port = "127.0.0.1", 6379
    ca_cert = tmp_path / "ca.pem"
    ca_cert.write_text("CERT")

    with (
        patch("howler.remote.datatypes.redis.RedisCluster", new=FakeRedisCluster),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(
            host=host, port=port, tls_enabled=True, tls_ca_cert=str(ca_cert), is_cluster=True
        )
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        result = get_client(host, port, private=False)

    assert isinstance(result, redis.RedisCluster)
    kw = log[-1]["kwargs"]
    assert kw["ssl"] is True
    assert kw["ssl_cert_reqs"] == "required"
    assert kw["ssl_ca_certs"] == str(ca_cert)
    assert "ssl_ca_path" not in kw


def test_get_client_cluster_with_tls_ca_dir(tmp_path):
    """When is_cluster=True and TLS is enabled with a CA cert directory,
    ssl_ca_path must be forwarded to RedisCluster."""
    FakeRedisCluster, log = _make_fake_redis_cluster()
    host, port = "127.0.0.1", 6379

    with (
        patch("howler.remote.datatypes.redis.RedisCluster", new=FakeRedisCluster),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(
            host=host, port=port, tls_enabled=True, tls_ca_cert=str(tmp_path), is_cluster=True
        )
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        result = get_client(host, port, private=False)

    assert isinstance(result, redis.RedisCluster)
    kw = log[-1]["kwargs"]
    assert kw["ssl"] is True
    assert kw["ssl_cert_reqs"] == "required"
    assert kw["ssl_ca_path"] == str(tmp_path)
    assert "ssl_ca_certs" not in kw


def test_get_client_cluster_with_password_and_tls(tmp_path):
    """When is_cluster=True with both password and TLS configured, all kwargs
    must be forwarded together."""
    FakeRedisCluster, log = _make_fake_redis_cluster()
    host, port = "127.0.0.1", 6379
    ca_cert = tmp_path / "ca.pem"
    ca_cert.write_text("CERT")

    with (
        patch("howler.remote.datatypes.redis.RedisCluster", new=FakeRedisCluster),
        patch("howler.remote.datatypes.config") as mock_config,
    ):
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(
            host=host, port=port, password="secret", tls_enabled=True, tls_ca_cert=str(ca_cert), is_cluster=True
        )
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        result = get_client(host, port, private=False)

    assert isinstance(result, redis.RedisCluster)
    kw = log[-1]["kwargs"]
    assert kw["username"] == "default"
    assert kw["password"] == "secret"
    assert kw["ssl"] is True
    assert kw["ssl_cert_reqs"] == "required"
    assert kw["ssl_ca_certs"] == str(ca_cert)


def test_get_client_cluster_tls_cert_not_found():
    """When is_cluster=True and the TLS cert path does not exist, a
    FileNotFoundError must be raised before RedisCluster is called."""
    with patch("howler.remote.datatypes.config") as mock_config:
        mock_config.core.redis.nonpersistent = _make_redis_server_mock(
            host="127.0.0.1",
            port=6379,
            tls_enabled=True,
            tls_ca_cert="/nonexistent/cluster-ca.pem",
            is_cluster=True,
        )
        mock_config.core.redis.persistent = _make_redis_server_mock(port=6380)

        with pytest.raises(FileNotFoundError, match="not found"):
            get_client("127.0.0.1", 6379, private=False)
