from urllib.parse import urlsplit

import pytest
import requests


@pytest.fixture(autouse=True)
def forbid_unmocked_http(monkeypatch):
    allowed_urls = set()
    original_request = requests.sessions.Session.request

    def guard_request(self, method, url, *args, **kwargs):
        if method.upper() != "POST" or url not in allowed_urls:
            pytest.fail(f"Unexpected HTTP request: {method} {url}")
        return original_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(requests.sessions.Session, "request", guard_request)
    return allowed_urls


@pytest.fixture
def allow_local_http(forbid_unmocked_http):
    def allow_exact_endpoint(endpoint):
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.port is None
            or parsed.path != "/slow-stream"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Only the exact loopback slow-stream endpoint may be allowed")
        forbid_unmocked_http.add(endpoint)

    return allow_exact_endpoint
