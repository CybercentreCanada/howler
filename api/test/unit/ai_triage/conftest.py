import pytest
import urllib3


@pytest.fixture(autouse=True)
def forbid_external_http(monkeypatch):
    original = urllib3.HTTPConnectionPool.urlopen

    def guard(self, method, url, *args, **kwargs):
        if self.host != "127.0.0.1":
            pytest.fail(f"Unexpected HTTP request: {method} {self.scheme}://{self.host}{url}")
        return original(self, method, url, *args, **kwargs)

    monkeypatch.setattr(urllib3.HTTPConnectionPool, "urlopen", guard)
