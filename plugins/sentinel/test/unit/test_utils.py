import json
import logging
from unittest.mock import patch

import pytest
import requests
from howler.common.exceptions import HowlerRuntimeError


def mock_post(url: str, **kwargs):
    res = requests.Response()
    res.status_code = 200
    res.headers["Content-Type"] = "application/json"
    if url.startswith("https://login.microsoftonline.com"):
        res._content = json.dumps({"access_token": "example token"}).encode()

    if "raise" in url:
        res.status_code = 400

    return res


def mock_custom_auth(tenant_id, scope):
    logging.info("It works: %s, %s", tenant_id, scope)
    return "example token"


@patch("requests.post", mock_post)
def test_get_token(caplog):
    from sentinel.config import ClientCredentials, config

    config.auth.client_credentials = ClientCredentials(client_id="client id", client_secret="client secret")

    from sentinel.utils.tenant_utils import get_token

    result = get_token("tenant id", "dummy scope")

    assert result == "example token"

    config.auth.client_credentials = None
    config.auth.custom_auth = mock_custom_auth

    with caplog.at_level(logging.INFO):
        result = get_token("tenant id", "dummy scope")

    assert "It works: tenant id, dummy scope" in caplog.text

    assert result == "example token"

    config.auth.client_credentials = ClientCredentials(client_id="client id", client_secret="client secret")
    config.auth.custom_auth = None

    with pytest.raises(HowlerRuntimeError):
        get_token("tenant id raise exception", "dummy scope")
