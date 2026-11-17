from urllib.parse import urlsplit

import pytest
import urllib3


@pytest.fixture(autouse=True)
def forbid_unmocked_http(monkeypatch):
    allowed_urls = set()
    original_request = urllib3.HTTPConnectionPool.urlopen

    def guard_request(self, method, url, *args, **kwargs):
        host = f"[{self.host}]" if ":" in self.host else self.host
        endpoint = f"{self.scheme}://{host}:{self.port}{url}"
        if method.upper() != "POST" or endpoint not in allowed_urls:
            pytest.fail(f"Unexpected HTTP request: {method} {endpoint}")
        return original_request(self, method, url, *args, **kwargs)

    monkeypatch.setattr(urllib3.HTTPConnectionPool, "urlopen", guard_request)
    return allowed_urls


@pytest.fixture
def allow_local_http(forbid_unmocked_http):
    def allow_exact_endpoint(endpoint):
        parsed = urlsplit(endpoint)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in {"127.0.0.1", "::1"}
            or parsed.port is None
            or parsed.path != "/slow-stream"
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Only the exact loopback slow-stream endpoint may be allowed")
        forbid_unmocked_http.add(endpoint)

    return allow_exact_endpoint
