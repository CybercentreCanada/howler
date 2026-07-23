import logging
from typing import Any

import jwt
from jwt import PyJWKClient

from mcp.server.auth.provider import AccessToken, TokenVerifier

logger = logging.getLogger(__name__)


class KeycloakTokenVerifier(TokenVerifier):
    def __init__(self, issuer: str, jwks_uri: str, audience: str, required_scope: str):
        self.issuer = issuer
        self.audience = audience
        self.required_scope = required_scope
        self.jwks_client = PyJWKClient(jwks_uri)

    async def verify_token(self, token: str) -> AccessToken | None:
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

        except Exception:
            logger.exception("TOKEN REJECTED: Exception during verification.")
            return None

    def _audience_matches(self, claims: dict[str, Any]) -> bool:
        aud = claims.get("aud")

        if isinstance(aud, str):
            return aud == self.audience

        if isinstance(aud, list):
            return self.audience in aud

        return False

    def _extract_scopes(self, claims: dict[str, Any]) -> list[str]:
        scope_value = claims.get("scope", claims.get("scp", ""))
        if isinstance(scope_value, str) and scope_value.strip():
            return scope_value.strip().split()
        return []

    def _extract_client_id(self, claims: dict[str, Any]) -> str:
        azp = claims.get("azp")
        if isinstance(azp, str) and azp:
            return azp

        client_id = claims.get("client_id")
        if isinstance(client_id, str) and client_id:
            return client_id

        return "unknown-client"


class AuthProvider:
    """
    Responsible for managing backend API access tokens.
    Using Token Pass-through since the MCP client token already contains
    the necessary 'howler' audience and roles.
    """

    async def get_howler_token(self, user_token: str) -> str:
        # Token Pass-through: The token verified by KeycloakTokenVerifier
        # is already fully qualified for the downstream backend API.
        return user_token
