"""Helpers for validating scroll lifetimes and authenticated continuation tokens."""

import hashlib
import hmac
import json
import re
from functools import cache
from typing import Any, cast

from authlib.jose import JsonWebEncryption

from howler.common.logging import get_logger
from howler.config import config
from howler.datastore.exceptions import InvalidScrollTokenException, SearchException
from howler.odm.models.user import User

logger = get_logger(__file__)

MAX_SCROLL_KEEP_ALIVE_MS = 10 * 60 * 1000
_KEEP_ALIVE_PATTERN = re.compile(r"([0-9]{1,9})(ms|s|m|h)")
_KEEP_ALIVE_UNIT_MS = {"ms": 1, "s": 1_000, "m": 60_000, "h": 3_600_000}
_SCROLL_TOKEN_LABEL = b"howler.search.scroll-token.v1"
_SCROLL_TOKEN_HEADER = {"alg": "A256GCMKW", "enc": "A256GCM"}
_MAX_SCROLL_TOKEN_LENGTH = 16_384
_jwe = JsonWebEncryption(algorithms=["A256GCMKW", "A256GCM"])


def validate_scroll_keep_alive(scroll: Any) -> str | None:
    """Validate a client-supplied scroll keep-alive, returning None when the client did not request one."""
    if scroll is None:
        return None

    match = _KEEP_ALIVE_PATTERN.fullmatch(scroll) if isinstance(scroll, str) else None
    duration_ms = int(match.group(1)) * _KEEP_ALIVE_UNIT_MS[match.group(2)] if match else 0
    if not 0 < duration_ms <= MAX_SCROLL_KEEP_ALIVE_MS:
        raise SearchException(
            "Scroll keep-alive must be a whole duration in ms, s, m, or h, "
            f"up to {MAX_SCROLL_KEEP_ALIVE_MS // 60_000}m."
        )

    return scroll


@cache
def _warn_if_default_secret() -> None:
    if config.auth.hmac_secret_key == "changeme":  # noqa: S105
        logger.warning("Scroll tokens are protected by the default auth.hmac_secret_key; set a unique secret.")


def _scroll_token_key() -> bytes:
    return hmac.new(config.auth.hmac_secret_key.encode(), _SCROLL_TOKEN_LABEL, hashlib.sha256).digest()


def _access_fingerprint(user: User) -> str:
    return hashlib.sha256(str(user["access_control"] or "").encode()).hexdigest()


def _query_fingerprint(query: str) -> str:
    return hashlib.sha256(query.encode()).hexdigest()


def _normalize_indexes(indexes: str) -> str:
    return ",".join(sorted({index.strip() for index in indexes.split(",") if index.strip()}))


def issue_scroll_token(user: User, indexes: str, scroll_id: str, query: str) -> str:
    """Encrypt a scroll ID with the opener, index set, query, and access-control fingerprint it is bound to."""
    _warn_if_default_secret()
    claims = {
        "a": _access_fingerprint(user),
        "i": _normalize_indexes(indexes),
        "q": _query_fingerprint(query),
        "s": scroll_id,
        "u": user["uname"],
    }
    payload = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()
    return _jwe.serialize_compact(dict(_SCROLL_TOKEN_HEADER), payload, _scroll_token_key()).decode("ascii")


def read_scroll_token(token: str) -> dict[str, str]:
    """Decrypt and authenticate a scroll token, returning its claims without checking who is asking."""
    if not isinstance(token, str) or len(token) > _MAX_SCROLL_TOKEN_LENGTH:
        raise InvalidScrollTokenException("Malformed scroll token.")

    token_key = _scroll_token_key()
    try:
        claims = json.loads(_jwe.deserialize_compact(token, token_key)["payload"])
    except Exception as error:
        raise InvalidScrollTokenException("Malformed scroll token.") from error

    if not isinstance(claims, dict) or not all(isinstance(claims.get(key), str) for key in ("a", "i", "q", "s", "u")):
        raise InvalidScrollTokenException("Malformed scroll token.")

    return cast(dict[str, str], claims)


def resolve_deep_paging_id(user: User, indexes: str, deep_paging_id: str | None, query: str) -> str | None:
    """Translate a client deep-paging value into the scroll ID the search service continues.

    ``None`` and ``*`` pass through unchanged. Any other value must be a token issued to this user for the same
    indexes and query, and the same access-control filter, so tokens cannot be replayed against a different search
    and revoked access cannot continue an existing scroll.
    """
    if deep_paging_id is None or deep_paging_id == "*":
        return deep_paging_id

    claims = read_scroll_token(deep_paging_id)
    if (
        claims["u"] != user["uname"]
        or claims["i"] != _normalize_indexes(indexes)
        or not hmac.compare_digest(claims["q"].encode(), _query_fingerprint(query).encode())
        or not hmac.compare_digest(claims["a"].encode(), _access_fingerprint(user).encode())
    ):
        raise InvalidScrollTokenException(
            "Scroll token is not valid for this user, index set, query, or access control."
        )

    return claims["s"]
