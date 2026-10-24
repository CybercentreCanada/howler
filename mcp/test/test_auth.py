import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from howler_mcp.auth import AuthProvider, JSONWebTokenVerifier


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
async def test_verify_token_fetches_jwks_key_in_worker_thread(verifier):
    with (
        patch.object(
            verifier.jwks_client,
            "get_signing_key_from_jwt",
            return_value=SimpleNamespace(key="fake-key"),
        ) as get_signing_key,
        patch(
            "howler_mcp.auth.asyncio.to_thread",
            new=AsyncMock(return_value=SimpleNamespace(key="fake-key")),
        ) as to_thread,
        patch("howler_mcp.auth.jwt.decode", side_effect=InvalidTokenError("bad signature")),
    ):
        result = await verifier.verify_token("raw-token")

    assert result is None
    to_thread.assert_awaited_once_with(get_signing_key, "raw-token")


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


@pytest.mark.asyncio
async def test_verify_token_accepts_scp_array_scope_claim(verifier):
    claims = {
        "exp": 9999999999,
        "iat": 1111111111,
        "iss": "https://issuer.example/realms/howler",
        "aud": "howler",
        "scp": ["openid", "offline_access", "profile", "", 123],
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
    assert token.scopes == ["openid", "offline_access", "profile"]


@pytest.mark.asyncio
async def test_verify_token_rejects_non_integer_expiry(verifier):
    claims = {
        "exp": "not-a-timestamp",
        "iat": 1111111111,
        "iss": "https://issuer.example/realms/howler",
        "aud": "howler",
        "scope": "openid offline_access",
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

    assert token is None


@pytest.mark.asyncio
async def test_verify_token_returns_none_on_unexpected_error(verifier):
    with patch.object(
        verifier.jwks_client,
        "get_signing_key_from_jwt",
        side_effect=RuntimeError("unexpected failure"),
    ):
        token = await verifier.verify_token("raw-token")

    assert token is None


@pytest.mark.asyncio
async def test_auth_provider_defaults_to_token_passthrough():
    provider = AuthProvider(mode="passthrough")

    assert await provider.get_authorization_header("user-token") == "Bearer user-token"


@pytest.mark.asyncio
async def test_auth_provider_apikey_mode_uses_basic_credentials_from_file(tmp_path):
    key_file = tmp_path / "howler-api-key"
    key_file.write_text("secret-key\n", encoding="utf-8")

    provider = AuthProvider(mode="ApiKey", username="mcp-reader", api_key_file=str(key_file))

    expected = base64.b64encode(b"mcp-reader:secret-key").decode("ascii")
    assert await provider.get_authorization_header("user-token") == f"Basic {expected}"


@pytest.mark.asyncio
async def test_auth_provider_apikey_mode_does_not_forward_user_token():
    provider = AuthProvider(mode="apikey", username="mcp-reader", api_key="secret-key")

    header = await provider.get_authorization_header("user-token")

    assert "user-token" not in base64.b64decode(header.removeprefix("Basic ")).decode()


def test_auth_provider_rejects_unknown_mode():
    with pytest.raises(ValueError, match="Unsupported HOWLER_API_AUTH_MODE"):
        AuthProvider(mode="exchange")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"username": "mcp-reader"},
        {"api_key": "secret-key"},
        {"username": "mcp-reader", "api_key": ""},
    ],
)
def test_auth_provider_apikey_mode_requires_username_and_key(kwargs):
    with (
        patch("howler_mcp.auth.HOWLER_API.USERNAME", None),
        patch("howler_mcp.auth.HOWLER_API.API_KEY_FILE", None),
        pytest.raises(ValueError, match="requires HOWLER_API_USERNAME"),
    ):
        AuthProvider(mode="apikey", **kwargs)


def test_auth_provider_apikey_mode_rejects_two_key_sources(tmp_path):
    key_file = tmp_path / "howler-api-key"
    key_file.write_text("secret-key", encoding="utf-8")

    with pytest.raises(ValueError, match="either a Howler API key or a key file"):
        AuthProvider(mode="apikey", username="mcp-reader", api_key="secret-key", api_key_file=str(key_file))


def test_auth_provider_apikey_mode_rejects_missing_key_file(tmp_path):
    with pytest.raises(ValueError, match="HOWLER_API_KEY_FILE must point to a readable file"):
        AuthProvider(mode="apikey", username="mcp-reader", api_key_file=str(tmp_path / "missing"))


def test_auth_provider_reads_mode_from_configuration():
    with (
        patch("howler_mcp.auth.HOWLER_API.AUTH_MODE", "apikey"),
        patch("howler_mcp.auth.HOWLER_API.USERNAME", "mcp-reader"),
        patch("howler_mcp.auth.HOWLER_API.API_KEY_FILE", None),
    ):
        provider = AuthProvider(api_key="secret-key")

    assert provider.mode == "apikey"
