"""Unit tests for jwt_service.get_audience.

Covers the three selection paths and the Azure/Entra ID scope validation guard:
  - audience field set explicitly -> use it
  - audience not set, client_id set -> fall back to client_id
  - neither set -> default to "howler"
  - azure/entraid provider without <client_id>/.default in scope -> HowlerValueError
"""

from unittest.mock import patch

import pytest

from howler.common.exceptions import HowlerValueError
from howler.odm.models.config import OAuthProvider
from howler.services import jwt_service


def _provider(**overrides) -> OAuthProvider:
    defaults = {
        "scope": "openid",
        "jwks_uri": "https://example.com/.well-known/jwks.json",
    }
    defaults.update(overrides)
    return OAuthProvider(**defaults)


def _patch_provider(name: str, provider: OAuthProvider):
    """Return a context-manager that replaces config.auth.oauth.providers[name]."""
    return patch.dict(jwt_service.config.auth.oauth.providers, {name: provider})


class TestGetAudience:
    def test_explicit_audience_is_returned(self):
        """When audience is set, it is returned verbatim."""
        provider = _provider(audience="my-explicit-audience")
        with _patch_provider("keycloak", provider):
            assert jwt_service.get_audience("keycloak") == "my-explicit-audience"

    def test_falls_back_to_client_id_when_no_audience(self):
        """With no audience but a client_id, the client_id is used as the audience."""
        provider = _provider(client_id="my-app-client-id")
        with _patch_provider("keycloak", provider):
            assert jwt_service.get_audience("keycloak") == "my-app-client-id"

    def test_defaults_to_howler_when_neither_set(self):
        """With neither audience nor client_id, the audience defaults to 'howler'."""
        provider = _provider()
        with _patch_provider("keycloak", provider):
            assert jwt_service.get_audience("keycloak") == "howler"

    def test_azure_valid_scope_returns_client_id(self):
        """For the 'azure' provider, a scope containing '<client_id>/.default' is accepted."""
        client_id = "azure-client-id"
        provider = _provider(client_id=client_id, scope=f"{client_id}/.default openid")
        with _patch_provider("azure", provider):
            assert jwt_service.get_audience("azure") == client_id

    def test_entraid_valid_scope_returns_client_id(self):
        """For the 'entraid' provider, a scope containing '<client_id>/.default' is accepted."""
        client_id = "entraid-client-id"
        provider = _provider(client_id=client_id, scope=f"{client_id}/.default openid")
        with _patch_provider("entraid", provider):
            assert jwt_service.get_audience("entraid") == client_id

    def test_azure_missing_default_scope_raises(self):
        """For 'azure', a scope that lacks '<client_id>/.default' raises HowlerValueError."""
        client_id = "azure-client-id"
        provider = _provider(client_id=client_id, scope="openid profile")
        with _patch_provider("azure", provider):
            with pytest.raises(HowlerValueError, match="scope must contain"):
                jwt_service.get_audience("azure")

    def test_entraid_missing_default_scope_raises(self):
        """For 'entraid', a scope that lacks '<client_id>/.default' raises HowlerValueError."""
        client_id = "entraid-client-id"
        provider = _provider(client_id=client_id, scope="openid profile")
        with _patch_provider("entraid", provider):
            with pytest.raises(HowlerValueError, match="scope must contain"):
                jwt_service.get_audience("entraid")

    def test_non_azure_provider_does_not_require_default_scope(self):
        """A non-azure/entraid provider is not subject to the /.default scope check."""
        provider = _provider(client_id="some-client", scope="openid profile")
        with _patch_provider("keycloak", provider):
            assert jwt_service.get_audience("keycloak") == "some-client"

    def test_explicit_audience_used_in_scope_check_for_azure(self):
        """When an explicit audience is set for azure, the scope check uses that audience value."""
        provider = _provider(audience="override-audience", scope="override-audience/.default openid")
        with _patch_provider("azure", provider):
            # scope contains override-audience/.default, so the check passes and the explicit audience is returned
            assert jwt_service.get_audience("azure") == "override-audience"
