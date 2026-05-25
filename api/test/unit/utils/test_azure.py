"""Unit tests for azure_obo provider-selection logic (howler/helper/azure.py lines 23-28).

Covers:
  1. "azure" key present -> that config is used
  2. Only "entraid" key present -> entraid config is used as fallback
  3. Neither present -> HowlerAttributeError is raised
  4. access_token_url not set -> HowlerException
  5. requests.post returns non-ok response -> HowlerException
  6. Happy-path OBO returns the access_token from the JSON response
"""

from unittest.mock import MagicMock, patch  # noqa: I001

import pytest

from howler.common.exceptions import HowlerAttributeError, HowlerException
from howler.helper import azure as azure_module


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_provider(
    client_id="test-client-id",
    client_secret="test-secret",
    access_token_url="https://login.microsoftonline.com/tenant/oauth2/v2.0/token",
):
    cfg = MagicMock()
    cfg.client_id = client_id
    cfg.client_secret = client_secret
    cfg.access_token_url = access_token_url
    return cfg


def _ok_response(access_token="ms-graph-token"):
    resp = MagicMock()
    resp.ok = True
    resp.json.return_value = {"access_token": access_token}
    return resp


def _error_response(content=b"Unauthorized"):
    resp = MagicMock()
    resp.ok = False
    resp.content = content
    return resp


# ---------------------------------------------------------------------------
# Tests: provider selection
# ---------------------------------------------------------------------------


class TestAzureOboProviderSelection:
    """Tests that azure_obo resolves the right provider config."""

    def test_azure_key_is_used_when_present(self):
        """When both 'azure' and 'entraid' exist, 'azure' is preferred."""
        azure_cfg = _make_provider(client_id="azure-client")
        entraid_cfg = _make_provider(client_id="entraid-client")
        providers = {"azure": azure_cfg, "entraid": entraid_cfg}

        with (
            patch.dict(azure_module.config.auth.oauth.providers, providers, clear=True),
            patch("howler.helper.azure.requests.post", return_value=_ok_response()) as mock_post,
        ):
            azure_module.azure_obo("dummy-token")

        # client_id from the azure provider must appear in the POST body
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["data"]["client_id"] == "azure-client"

    def test_entraid_key_used_as_fallback(self):
        """When only 'entraid' is configured, that config is used."""
        entraid_cfg = _make_provider(client_id="entraid-client")
        providers = {"entraid": entraid_cfg}

        with (
            patch.dict(azure_module.config.auth.oauth.providers, providers, clear=True),
            patch("howler.helper.azure.requests.post", return_value=_ok_response()) as mock_post,
        ):
            azure_module.azure_obo("dummy-token")

        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["data"]["client_id"] == "entraid-client"

    def test_neither_azure_nor_entraid_raises_attribute_error(self):
        """When neither provider key exists, HowlerAttributeError is raised."""
        providers = {"google": _make_provider()}

        with (
            patch.dict(azure_module.config.auth.oauth.providers, providers, clear=True),
            patch("howler.helper.azure.requests.post"),
        ):
            with pytest.raises(HowlerAttributeError, match="No azure/entraid-based provider configured"):
                azure_module.azure_obo("dummy-token")

    def test_empty_providers_raises_attribute_error(self):
        """When providers dict is completely empty, HowlerAttributeError is raised."""
        with (
            patch.dict(azure_module.config.auth.oauth.providers, {}, clear=True),
            patch("howler.helper.azure.requests.post"),
        ):
            with pytest.raises(HowlerAttributeError):
                azure_module.azure_obo("dummy-token")


# ---------------------------------------------------------------------------
# Tests: OBO failure paths
# ---------------------------------------------------------------------------


class TestAzureOboFailurePaths:
    """Tests for failure scenarios after provider selection."""

    def _with_azure_provider(self, provider=None):
        return patch.dict(
            azure_module.config.auth.oauth.providers,
            {"azure": provider or _make_provider()},
            clear=True,
        )

    def test_missing_access_token_url_raises_howler_exception(self):
        """When access_token_url is falsy, HowlerException is raised before the POST."""
        provider = _make_provider(access_token_url=None)

        with self._with_azure_provider(provider):
            with pytest.raises(HowlerException, match="access_token_url must be set"):
                azure_module.azure_obo("dummy-token")

    def test_non_ok_response_raises_howler_exception(self):
        """When the OBO POST returns a non-2xx status, HowlerException is raised."""
        with (
            self._with_azure_provider(),
            patch(
                "howler.helper.azure.requests.post",
                return_value=_error_response(b"Bad Request"),
            ),
        ):
            with pytest.raises(HowlerException, match="Azure OBO failed"):
                azure_module.azure_obo("dummy-token")


# ---------------------------------------------------------------------------
# Tests: happy path
# ---------------------------------------------------------------------------


class TestAzureOboSuccess:
    """Tests that a successful OBO exchange returns the access token."""

    def test_returns_access_token_from_response(self):
        """A successful OBO call returns the access_token from the JSON response."""
        providers = {"azure": _make_provider()}

        with (
            patch.dict(azure_module.config.auth.oauth.providers, providers, clear=True),
            patch("howler.helper.azure.requests.post", return_value=_ok_response("new-token")),
        ):
            result = azure_module.azure_obo("my-bearer-token")

        assert result == "new-token"
