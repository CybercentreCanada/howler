import importlib

import pytest

import howler_mcp.config as config


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("ftp://localhost/api", "must use http or https"),
        ("https:///api", "must include a hostname"),
        ("http://howler.example/api", "must use https for non-local hosts"),
    ],
)
def test_require_https_for_non_local_rejects_unsafe_urls(url, message):
    with pytest.raises(ValueError, match=message):
        config._require_https_for_non_local(url, "TEST_URL")

    valid_cluster_url = "http://howler.svc.cluster.local"
    assert config._require_https_for_non_local(valid_cluster_url, "TEST_URL") == valid_cluster_url


@pytest.mark.parametrize(
    ("url",),
    [
        ("http://howler-rest.howler.svc.cluster.local:5000/api/v1",),
        ("http://howler.svc.cluster.local",),
    ],
)
def test_require_https_for_non_local_accepts_cluster_urls(url):
    assert config._require_https_for_non_local(url, "TEST_URL") == url


@pytest.mark.parametrize(
    ("timeout", "message"),
    [
        ("not-a-number", "need to be a float"),
        ("0", "require to be higher then 0.0"),
        ("-1", "require to be higher then 0.0"),
    ],
)
def test_auth_timeout_is_validated_at_import(monkeypatch, timeout, message):
    monkeypatch.setenv("AUTH_TIMEOUT", timeout)
    try:
        with pytest.raises(ValueError, match=message):
            importlib.reload(config)
    finally:
        monkeypatch.delenv("AUTH_TIMEOUT", raising=False)
        importlib.reload(config)
