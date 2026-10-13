"""Shared helpers for safely selecting, projecting, and continuing scroll search results."""

import hashlib
import hmac
import json
import re
from collections.abc import Mapping
from functools import cache
from typing import Any, cast

from authlib.jose import JsonWebEncryption

from howler.common.logging import get_logger
from howler.config import config
from howler.datastore.collection import ESCollection
from howler.datastore.exceptions import InvalidScrollTokenException, SearchException
from howler.datastore.utils import expand_field_patterns, prune_to_paths
from howler.odm.base import BANNED_FIELDS
from howler.odm.models.user import User

logger = get_logger(__file__)

MAX_SCROLL_KEEP_ALIVE_MS = 10 * 60 * 1000
_KEEP_ALIVE_PATTERN = re.compile(r"([0-9]{1,9})(ms|s|m|h)")
_KEEP_ALIVE_UNIT_MS = {"ms": 1, "s": 1_000, "m": 60_000, "h": 3_600_000}
_SCROLL_TOKEN_LABEL = b"howler.search.scroll-token.v1"
_SCROLL_TOKEN_HEADER = {"alg": "A256GCMKW", "enc": "A256GCM"}
_MAX_SCROLL_TOKEN_LENGTH = 16_384
_jwe = JsonWebEncryption(algorithms=["A256GCMKW", "A256GCM"])


def select_safe_scroll_fields(
    search_collections: Mapping[str, ESCollection], fl: Any
) -> tuple[list[str], dict[str, list[str]], bool]:
    """Build the Elasticsearch source projection and per-index stored-field allowlists."""
    if isinstance(fl, str):
        fl = [fl]
    elif not isinstance(fl, list):
        fl = []
    requested_fields = [
        field.strip() for value in fl if isinstance(value, str) for field in value.split(",") if field.strip()
    ]

    allowed_fields_by_index: dict[str, list[str]] = {}
    include_all = not requested_fields or "*" in requested_fields
    include_id = not requested_fields

    for index, search_collection in search_collections.items():
        expanded_fields = (
            expand_field_patterns(search_collection.model_class, requested_fields, preserve_all=True)
            if not include_all
            else set()
        )
        allowed_fields_by_index[index] = [
            field_name
            for field_name, field in search_collection.stored_fields.items()
            if field.store and field_name not in BANNED_FIELDS and (include_all or field_name in expanded_fields)
        ]
        include_id = include_id or include_all or "id" in expanded_fields

    source_fields = list(dict.fromkeys(field for fields in allowed_fields_by_index.values() for field in fields))
    if include_id and "id" not in source_fields:
        source_fields.append("id")

    return source_fields, allowed_fields_by_index, include_id


def _remove_banned_scroll_fields(value: Any) -> Any:
    """Remove banned field names at every level of a scroll result."""
    if isinstance(value, dict):
        return {key: _remove_banned_scroll_fields(item) for key, item in value.items() if key not in BANNED_FIELDS}
    if isinstance(value, list):
        return [_remove_banned_scroll_fields(item) for item in value]
    return value


def prune_scroll_items(
    items: list[dict[str, Any]], allowed_fields_by_index: Mapping[str, list[str]], include_id: bool
) -> list[dict[str, Any]]:
    """Project scroll items to stored fields, applying the correct allowlist per index."""
    safe_items: list[dict[str, Any]] = []
    default_fields = next(iter(allowed_fields_by_index.values())) if len(allowed_fields_by_index) == 1 else []

    for item in items:
        item_index = item.get("__index")
        selected_fields = allowed_fields_by_index.get(item_index, []) if isinstance(item_index, str) else default_fields

        source = {key: value for key, value in item.items() if key not in {"__index", "id"}}
        # Selected mappings may still contain internal fields; strip them after projection.
        safe_item: dict[str, Any] = _remove_banned_scroll_fields(prune_to_paths(source, set(selected_fields)))

        if include_id and item.get("id") is not None:
            safe_item["id"] = item["id"]
        if "__index" in item:
            safe_item["__index"] = item["__index"]

        safe_items.append(safe_item)

    return safe_items


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


def _normalize_indexes(indexes: str) -> str:
    return ",".join(sorted({index.strip() for index in indexes.split(",") if index.strip()}))


def issue_scroll_token(user: User, indexes: str, scroll_id: str) -> str:
    """Encrypt a scroll ID with the opener, index set, and access-control fingerprint it is bound to."""
    _warn_if_default_secret()
    claims = {"a": _access_fingerprint(user), "i": _normalize_indexes(indexes), "s": scroll_id, "u": user["uname"]}
    payload = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()
    return _jwe.serialize_compact(dict(_SCROLL_TOKEN_HEADER), payload, _scroll_token_key()).decode("ascii")


def read_scroll_token(token: Any) -> dict[str, str]:
    """Decrypt and authenticate a scroll token, returning its claims without checking who is asking."""
    if not isinstance(token, str) or len(token) > _MAX_SCROLL_TOKEN_LENGTH:
        raise InvalidScrollTokenException("Malformed scroll token.")

    token_key = _scroll_token_key()
    try:
        claims = json.loads(_jwe.deserialize_compact(token, token_key)["payload"])
    except Exception as error:
        raise InvalidScrollTokenException("Malformed scroll token.") from error

    if not isinstance(claims, dict) or not all(isinstance(claims.get(key), str) for key in ("a", "i", "s", "u")):
        raise InvalidScrollTokenException("Malformed scroll token.")

    return cast(dict[str, str], claims)


def resolve_deep_paging_id(user: User, indexes: str, deep_paging_id: Any) -> str | None:
    """Translate a client deep-paging value into the scroll ID the search service continues.

    ``None`` and ``*`` pass through unchanged. Any other value must be a token issued to this user for the same
    indexes and the same access-control filter, so revoked access cannot continue an existing scroll.
    """
    if deep_paging_id is None or deep_paging_id == "*":
        return deep_paging_id

    claims = read_scroll_token(deep_paging_id)
    if (
        claims["u"] != user["uname"]
        or claims["i"] != _normalize_indexes(indexes)
        or not hmac.compare_digest(claims["a"].encode(), _access_fingerprint(user).encode())
    ):
        raise InvalidScrollTokenException("Scroll token is not valid for this user, index set, or access control.")

    return claims["s"]
