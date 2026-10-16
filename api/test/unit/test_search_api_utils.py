"""Tests for bounded scroll keep-alives and authenticated scroll tokens."""

import base64
import json
from unittest.mock import patch

import pytest

from howler.api.search_utils import (
    InvalidScrollTokenException,
    issue_scroll_token,
    resolve_deep_paging_id,
    validate_scroll_keep_alive,
)
from howler.datastore.exceptions import SearchException
from howler.services.search_service import clear_owned_scroll


def _user(uname: str = "alice", access_control: str | None = "group:analysts") -> dict[str, str | None]:
    return {"uname": uname, "access_control": access_control}


def _tamper_part(token: str, index: int) -> str:
    parts = token.split(".")
    segment = parts[index]
    parts[index] = ("A" if segment[0] != "A" else "B") + segment[1:]
    return ".".join(parts)


@pytest.mark.parametrize("scroll", ["1ms", "30s", "5m", "10m", "600000ms", None])
def test_keep_alive_accepts_bounded_durations(scroll):
    assert validate_scroll_keep_alive(scroll) == scroll


@pytest.mark.parametrize(
    "scroll",
    ["11m", "1h", "0s", "0m", "soon", "1.5m", "5 m", "5", "", 60, "9" * 5000 + "s", "9999999999ms"],
)
def test_keep_alive_rejects_unbounded_or_malformed_durations(scroll):
    with pytest.raises(SearchException):
        validate_scroll_keep_alive(scroll)


def test_token_resolves_to_raw_scroll_id_for_the_same_user_and_indexes():
    user = _user()
    token = issue_scroll_token(user, "hit,user", "raw-es-scroll", "id:*")

    assert resolve_deep_paging_id(user, "user, hit", token, "id:*") == "raw-es-scroll"


def test_token_does_not_expose_the_raw_scroll_id_in_any_segment():
    token = issue_scroll_token(_user(), "hit", "raw-es-scroll", "id:*")

    for segment in token.split("."):
        decoded = base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))
        assert b"raw-es-scroll" not in decoded
    assert "raw-es-scroll" not in token


def test_wildcard_and_missing_deep_paging_values_pass_through():
    assert resolve_deep_paging_id(_user(), "hit", "*", "id:*") == "*"
    assert resolve_deep_paging_id(_user(), "hit", None, "id:*") is None


def test_token_rejects_another_user():
    token = issue_scroll_token(_user("alice"), "hit", "raw-es-scroll", "id:*")

    with pytest.raises(InvalidScrollTokenException):
        resolve_deep_paging_id(_user("bob"), "hit", token, "id:*")


def test_token_rejects_a_different_index_set():
    token = issue_scroll_token(_user(), "hit", "raw-es-scroll", "id:*")

    with pytest.raises(InvalidScrollTokenException):
        resolve_deep_paging_id(_user(), "hit,user", token, "id:*")


def test_token_rejects_changed_access_control():
    token = issue_scroll_token(_user(access_control="group:analysts"), "hit", "raw-es-scroll", "id:*")

    with pytest.raises(InvalidScrollTokenException):
        resolve_deep_paging_id(_user(access_control="group:other"), "hit", token, "id:*")


def test_token_rejects_tampered_ciphertext():
    token = issue_scroll_token(_user(), "hit", "raw-es-scroll", "id:*")

    with pytest.raises(InvalidScrollTokenException):
        resolve_deep_paging_id(_user(), "hit", _tamper_part(token, 3), "id:*")


def test_token_rejects_a_forged_authentication_tag():
    token = issue_scroll_token(_user(), "hit", "raw-es-scroll", "id:*")

    with pytest.raises(InvalidScrollTokenException):
        resolve_deep_paging_id(_user(), "hit", _tamper_part(token, 4), "id:*")


def test_token_rejects_a_different_query():
    user = _user()
    token = issue_scroll_token(user, "hit", "raw-es-scroll", "id:*")

    with pytest.raises(InvalidScrollTokenException):
        resolve_deep_paging_id(user, "hit", token, "howler.assignment:alice")


@pytest.mark.parametrize(
    "token",
    ["raw-es-scroll", "", ".", "a.b.c", "!!!.!!!", "\ud800.abc", "_all", 5, {"s": "raw"}],
)
def test_token_rejects_malformed_values(token):
    with pytest.raises(InvalidScrollTokenException):
        resolve_deep_paging_id(_user(), "hit", token, "id:*")


def test_token_rejects_validly_encrypted_claims_with_the_wrong_shape():
    from howler.api.search_utils import _SCROLL_TOKEN_HEADER, _jwe, _scroll_token_key

    payload = json.dumps({"s": "raw-es-scroll", "u": "alice", "i": "hit", "a": "x"}).encode()
    token = _jwe.serialize_compact(_SCROLL_TOKEN_HEADER, payload, _scroll_token_key()).decode("ascii")

    with pytest.raises(InvalidScrollTokenException):
        resolve_deep_paging_id(_user(), "hit", token, "id:*")


def test_clear_owned_scroll_clears_the_raw_scroll_for_its_opener():
    user = _user()
    token = issue_scroll_token(user, "hit", "raw-es-scroll", "id:*")

    with patch("howler.services.search_service.clear_scroll") as mock_clear_scroll:
        mock_clear_scroll.return_value = {"succeeded": True, "num_freed": 1}

        assert clear_owned_scroll(user, token) == {"succeeded": True, "num_freed": 1}
        mock_clear_scroll.assert_called_once_with("raw-es-scroll")


def test_clear_owned_scroll_rejects_another_user_without_clearing():
    token = issue_scroll_token(_user("alice"), "hit", "raw-es-scroll", "id:*")

    with patch("howler.services.search_service.clear_scroll") as mock_clear_scroll:
        with pytest.raises(InvalidScrollTokenException):
            clear_owned_scroll(_user("bob"), token)

        mock_clear_scroll.assert_not_called()


def test_token_rejects_oversized_input_before_decryption():
    user = _user()
    token = issue_scroll_token(user, "hit", "x" * 20_000, "id:*")

    assert resolve_deep_paging_id(user, "hit", issue_scroll_token(user, "hit", "raw-es-scroll", "id:*"), "id:*")
    with pytest.raises(InvalidScrollTokenException):
        resolve_deep_paging_id(user, "hit", token, "id:*")


def test_token_rejects_an_unpinned_key_management_algorithm():
    from authlib.jose import JsonWebEncryption

    from howler.api.search_utils import _access_fingerprint, _scroll_token_key

    user = _user()
    claims = {"a": _access_fingerprint(user), "i": "hit", "q": "x", "s": "raw-es-scroll", "u": "alice"}
    payload = json.dumps(claims, sort_keys=True, separators=(",", ":")).encode()
    token = JsonWebEncryption().serialize_compact({"alg": "dir", "enc": "A256GCM"}, payload, _scroll_token_key())

    with pytest.raises(InvalidScrollTokenException):
        resolve_deep_paging_id(user, "hit", token.decode("ascii"), "id:*")


def test_repeated_issuance_produces_tokens_that_all_resolve():
    user = _user()
    tokens = [issue_scroll_token(user, "hit", f"raw-{index}", "id:*") for index in range(20)]

    assert [resolve_deep_paging_id(user, "hit", token, "id:*") for token in tokens] == [
        f"raw-{index}" for index in range(20)
    ]
