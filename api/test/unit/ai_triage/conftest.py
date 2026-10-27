import pytest
import requests


@pytest.fixture(autouse=True)
def forbid_unmocked_http(monkeypatch):
    def fail_request(_self, method, url, **_kwargs):
        pytest.fail(f"Unexpected HTTP request: {method} {url}")

    monkeypatch.setattr(requests.sessions.Session, "request", fail_request)
