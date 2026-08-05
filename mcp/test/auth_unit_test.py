from types import SimpleNamespace
from unittest.mock import patch

import pytest
from howler_mcp.auth import KeycloakTokenVerifier
from jwt.exceptions import InvalidTokenError, PyJWKClientError


@pytest.fixture()
def verifier() -> KeycloakTokenVerifier:
    return KeycloakTokenVerifier(
        issuer="https://issuer.example/realms/howler",
        jwks_uri="https://issuer.example/realms/howler/protocol/openid-connect/certs",
        audience="howlermcp",
        required_scope="howlermcp:access",
        timeout=5.0,
    )


@pytest.mark.asyncio
async def test_verify_token_returns_none_on_jwks_client_error(verifier):
    with patch.object(
        verifier.jwks_client,
        "get_signing_key_from_jwt",
        side_effect=PyJWKClientError("network down"),
    ):
        result = await verifier.verify_token("raw-token")

    assert result is None


@pytest.mark.asyncio
async def test_verify_token_returns_none_on_invalid_token_error(verifier):
    with (
        patch.object(
            verifier.jwks_client,
            "get_signing_key_from_jwt",
            return_value=SimpleNamespace(key="fake-key"),
        ),
        patch(
            "howler_mcp.auth.jwt.decode",
            side_effect=InvalidTokenError("bad signature"),
        ),
    ):
        result = await verifier.verify_token("raw-token")

    assert result is None


@pytest.mark.asyncio
async def test_verify_token_rejects_audience_mismatch(verifier):
    claims = {
        "exp": 9999999999,
        "iat": 1111111111,
        "iss": "https://issuer.example/realms/howler",
        "aud": "other-audience",
        "scope": "howlermcp:access",
        "azp": "cli-a",
    }

    with (
        patch.object(
            verifier.jwks_client,
            "get_signing_key_from_jwt",
            return_value=SimpleNamespace(key="fake-key"),
        ),
        patch("howler_mcp.auth.jwt.decode", return_value=claims),
    ):
        result = await verifier.verify_token("raw-token")

    assert result is None


@pytest.mark.asyncio
async def test_verify_token_rejects_missing_scope(verifier):
    claims = {
        "exp": 9999999999,
        "iat": 1111111111,
        "iss": "https://issuer.example/realms/howler",
        "aud": "howlermcp",
        "scope": "different:scope",
        "azp": "cli-a",
    }

    with (
        patch.object(
            verifier.jwks_client,
            "get_signing_key_from_jwt",
            return_value=SimpleNamespace(key="fake-key"),
        ),
        patch("howler_mcp.auth.jwt.decode", return_value=claims),
    ):
        result = await verifier.verify_token("raw-token")

    assert result is None


@pytest.mark.asyncio
async def test_verify_token_accepts_valid_token(verifier):
    claims = {
        "exp": 9999999999,
        "iat": 1111111111,
        "iss": "https://issuer.example/realms/howler",
        "aud": ["howlermcp", "other"],
        "scope": "openid profile howlermcp:access",
        "azp": "cli-a",
    }

    with (
        patch.object(
            verifier.jwks_client,
            "get_signing_key_from_jwt",
            return_value=SimpleNamespace(key="fake-key"),
        ),
        patch("howler_mcp.auth.jwt.decode", return_value=claims),
    ):
        token = await verifier.verify_token("raw-token")

    assert token is not None
    assert token.token == "raw-token"
    assert token.client_id == "cli-a"
    assert token.resource == "howlermcp"
    assert "howlermcp:access" in token.scopes
