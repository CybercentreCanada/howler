import logging
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    InvalidIssuedAtError,
    InvalidIssuerError,
    InvalidTokenError,
    MissingRequiredClaimError,
    PyJWKClientError,
)
from mcp.server.auth.provider import AccessToken, TokenVerifier

logger = logging.getLogger(__name__)


class KeycloakTokenVerifier(TokenVerifier):
    """Verify JWTs issued by a Keycloak realm.

    Validates the signature, issuer, audience, and required scope of incoming
    MCP user tokens before allowing tool calls.
    """

    def __init__(self, issuer: str, jwks_uri: str, audience: str, required_scope: str):
        """Initialise the verifier.

        Args:
            issuer: Expected ``iss`` claim value, typically the Keycloak realm URL.
            jwks_uri: URL of the Keycloak JWKS endpoint used to fetch signing keys.
            audience: Expected ``aud`` claim value for this resource server.
            required_scope: Scope string that must be present in the token.
        """
        self.issuer = issuer
        self.audience = audience
        self.required_scope = required_scope
        self.jwks_client = PyJWKClient(jwks_uri)

    async def verify_token(self, token: str) -> AccessToken | None:
        """Verify a raw JWT string and return an ``AccessToken`` on success.

        Validates the signature, issuer, audience, expiry, and required scope.
        Returns ``None`` for any invalid or rejected token rather than raising,
        so the MCP framework can respond with an appropriate 401.

        Args:
            token: Raw JWT bearer token string to verify.

        Returns:
            AccessToken | None: A populated ``AccessToken`` if the token is
            valid, or ``None`` if validation fails for any reason.
        """
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256", "RS384", "RS512", "PS256", "PS384", "PS512"],
                issuer=self.issuer,
                options={
                    "require": ["exp", "iat", "iss"],
                    "verify_aud": False,
                },
            )

            if not self._audience_matches(claims):
                logger.warning(
                    "TOKEN REJECTED: audience mismatch. EXPECTED AUD: %s, ACTUAL AUD: %s",
                    self.audience,
                    claims.get("aud"),
                )
                return None

            scopes = self._extract_scopes(claims)

            if self.required_scope not in scopes:
                logger.warning(
                    "TOKEN REJECTED: missing required scope. REQUIRED SCOPE: %s, TOKEN SCOPES: %s",
                    self.required_scope,
                    scopes,
                )
                return None

            expires_at = claims.get("exp")
            if not isinstance(expires_at, int):
                logger.warning("TOKEN REJECTED: exp missing or invalid")
                return None

            client_id = self._extract_client_id(claims)

            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=scopes,
                expires_at=expires_at,
                resource=self.audience,
            )

        except PyJWKClientError as exc:
            logger.warning(
                "TOKEN REJECTED: unable to fetch/resolve JWKS signing key: %s", exc
            )
            return None
        except (
            ExpiredSignatureError,
            InvalidIssuerError,
            InvalidIssuedAtError,
            MissingRequiredClaimError,
            DecodeError,
            InvalidTokenError,
        ) as exc:
            logger.warning("TOKEN REJECTED: invalid token claims/signature: %s", exc)
            return None
        except Exception:
            logger.exception(
                "TOKEN REJECTED: unexpected exception during verification."
            )
            return None

    def _audience_matches(self, claims: dict[str, Any]) -> bool:
        """Check whether the token audience matches the configured audience.

        Args:
            claims: Decoded JWT claims dictionary.

        Returns:
            bool: ``True`` if the ``aud`` claim equals or contains the
            configured audience value.
        """
        aud = claims.get("aud")

        if isinstance(aud, str):
            return aud == self.audience

        if isinstance(aud, list):
            return self.audience in aud

        return False

    def _extract_scopes(self, claims: dict[str, Any]) -> list[str]:
        """Extract scopes from JWT claims.

        Handles both ``scope`` (space-separated string) and ``scp`` claim
        shapes produced by different Keycloak configurations.

        Args:
            claims: Decoded JWT claims dictionary.

        Returns:
            list[str]: List of individual scope strings, or an empty list if
            no scope claim is present.
        """
        scope_value = claims.get("scope", claims.get("scp", ""))
        if isinstance(scope_value, str) and scope_value.strip():
            return scope_value.strip().split()
        return []

    def _extract_client_id(self, claims: dict[str, Any]) -> str:
        """Extract the client identifier from JWT claims.

        Checks ``azp`` (authorised party) first, then falls back to
        ``client_id``, and returns ``"unknown-client"`` if neither is present.

        Args:
            claims: Decoded JWT claims dictionary.

        Returns:
            str: Client identifier string.
        """
        azp = claims.get("azp")
        if isinstance(azp, str) and azp:
            return azp

        client_id = claims.get("client_id")
        if isinstance(client_id, str) and client_id:
            return client_id

        return "unknown-client"


class AuthProvider:
    """Manage backend API access tokens using token pass-through.

    The MCP client token verified by ``KeycloakTokenVerifier`` is already
    fully qualified for the downstream Howler API, so no additional token
    exchange is required.
    """

    async def get_howler_token(self, user_token: str) -> str:
        """Return the Howler-compatible bearer token for a given user token.

        Args:
            user_token: The raw JWT bearer token from the MCP client session.

        Returns:
            str: Token to use as the ``Authorization`` header value when
            calling the Howler API.
        """
        # Token Pass-through: The token verified by KeycloakTokenVerifier
        # is already fully qualified for the downstream backend API.
        return user_token
