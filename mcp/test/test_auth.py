from types import SimpleNamespace
from unittest.mock import patch

import pytest
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from howler_mcp.auth import JSONWebTokenVerifier


@pytest.fixture()
def verifier() -> JSONWebTokenVerifier:
    return JSONWebTokenVerifier(
        issuer="https://issuer.example/realms/howler",
        jwks_uri="https://issuer.example/realms/howler/protocol/openid-connect/certs",
        audience="howler",
        required_scopes=["openid", "offline_access"],
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
        "scope": "offline_access",
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
        "aud": "howler",
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
        "aud": ["howler", "other"],
        "scope": "openid profile offline_access",
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
    assert token.resource == "howler"
    assert "offline_access" in token.scopes


@pytest.mark.asyncio
async def test_verify_token_accepts_all_required_scopes():
    verifier = JSONWebTokenVerifier(
        issuer="https://issuer.example/realms/howler",
        jwks_uri="https://issuer.example/realms/howler/protocol/openid-connect/certs",
        audience="howler",
        required_scopes=["openid", "offline_access"],
        timeout=5.0,
    )
    claims = {
        "exp": 9999999999,
        "iat": 1111111111,
        "iss": "https://issuer.example/realms/howler",
        "aud": "howler",
        "scope": "openid offline_access profile email",
        "azp": "howler",
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
    assert token.scopes == ["openid", "offline_access", "profile", "email"]
