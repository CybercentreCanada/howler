"""Tests for shared safe scroll search projection and token helpers."""

import base64
import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from howler.api.search_utils import (
    InvalidScrollTokenException,
    issue_scroll_token,
    prune_scroll_items,
    resolve_deep_paging_id,
    select_safe_scroll_fields,
    validate_scroll_keep_alive,
)
from howler.datastore.exceptions import SearchException
from howler.services.search_service import clear_owned_scroll, scroll_search


def _search_collection(*stored_fields: str):
    return SimpleNamespace(
        model_class=None,
        stored_fields={field: SimpleNamespace(store=True) for field in stored_fields},
    )


def test_scroll_projection_keeps_requested_fields_inside_compound_lists():
    collection = _search_collection("name", "action.operations.operation_id")
    collection.stored_fields["not_stored"] = SimpleNamespace(store=False)
    collections = {
        "hit": collection,
    }
    source_fields, allowed_fields, include_id = select_safe_scroll_fields(
        collections, ["name", "action.operations.operation_id", "not_stored"]
    )

    assert source_fields == ["name", "action.operations.operation_id"]
    assert allowed_fields == {"hit": ["name", "action.operations.operation_id"]}
    assert include_id is False

    items = [
        {
            "id": "hit-id",
            "__index": "hit",
            "name": "allowed",
            "not_stored": "filtered",
            "action": {
                "operations": [
                    {"operation_id": "add_label", "data_json": "filtered"},
                    {"operation_id": "promote", "data_json": "filtered"},
                ]
            },
        }
    ]

    assert prune_scroll_items(items, allowed_fields, include_id) == [
        {
            "name": "allowed",
            "action": {"operations": [{"operation_id": "add_label"}, {"operation_id": "promote"}]},
            "__index": "hit",
        }
    ]


def test_scroll_projection_uses_the_matching_index_allowlist():
    collections = {
        "hit": _search_collection("shared", "hit_only"),
        "user": _search_collection("shared", "user_only"),
    }
    source_fields, allowed_fields, include_id = select_safe_scroll_fields(
        collections, ["shared", "hit_only", "user_only"]
    )

    assert source_fields == ["shared", "hit_only", "user_only"]
    assert allowed_fields == {"hit": ["shared", "hit_only"], "user": ["shared", "user_only"]}
    assert include_id is False

    items = [
        {"__index": "hit", "shared": "hit-shared", "hit_only": "allowed", "user_only": "filtered"},
        {"__index": "user", "shared": "user-shared", "hit_only": "filtered", "user_only": "allowed"},
    ]

    assert prune_scroll_items(items, allowed_fields, include_id) == [
        {"shared": "hit-shared", "hit_only": "allowed", "__index": "hit"},
        {"shared": "user-shared", "user_only": "allowed", "__index": "user"},
    ]


def test_scroll_projection_drops_items_with_an_unmapped_index():
    """An item must not inherit another index's allowlist when its index is unknown."""
    items = [{"__index": "hit", "user_only": "must not leak"}]

    assert prune_scroll_items(items, {"user": ["user_only"]}, include_id=False) == [{"__index": "hit"}]


def test_scroll_projection_includes_document_ids_by_default():
    source_fields, allowed_fields, include_id = select_safe_scroll_fields({"hit": _search_collection("name")}, None)

    assert source_fields == ["name", "id"]
    assert allowed_fields == {"hit": ["name"]}
    assert include_id is True


@pytest.mark.parametrize("fl", [" name, id ", ["name,id"], [" name ", "id"]])
def test_scroll_projection_normalizes_string_and_list_field_requests(fl):
    assert select_safe_scroll_fields({"hit": _search_collection("name")}, fl) == (
        ["name", "id"],
        {"hit": ["name"]},
        True,
    )


@pytest.mark.parametrize("fl", [{"secret": 1}, 5, ["name", None], [["name"]]])
def test_scroll_projection_rejects_malformed_field_lists(fl):
    with pytest.raises(SearchException, match="Field list must be a string or a list of strings"):
        select_safe_scroll_fields({"hit": _search_collection("name")}, fl)


@pytest.mark.parametrize("fl", [{"secret": 1}, ["name", None]])
def test_scroll_search_rejects_malformed_field_lists_before_search(fl):
    with (
        patch("howler.services.search_service.get_collection") as mock_get_collection,
        patch("howler.services.search_service.search") as mock_search,
    ):
        mock_get_collection.return_value.return_value = _search_collection("name")

        with pytest.raises(SearchException, match="Field list must be a string or a list of strings"):
            scroll_search("hit", "id:*", _user(), {"deep_paging_id": "*", "fl": fl}, None)

    mock_search.assert_not_called()


def test_user_scroll_allows_public_document_id_without_internal_include_flag():
    user = _user()
    with (
        patch("howler.services.search_service.get_collection") as mock_get_collection,
        patch("howler.services.search_service.search") as mock_search,
    ):
        mock_get_collection.return_value.return_value = _search_collection("name")
        mock_search.return_value = {
            "items": [{"__index": "user", "id": "user-id", "uname": "alice"}],
            "next_deep_paging_id": None,
            "offset": 0,
            "rows": 1,
            "total": 1,
        }

        result = scroll_search("user", "id:*", user, {"deep_paging_id": "*", "fl": "id"}, None)

    assert mock_search.call_args.kwargs["include_id"] is True
    assert result["items"] == [{"id": "user-id", "__index": "user"}]


@pytest.mark.parametrize("fl", [None, "", [], "*", ["*", "not_stored"]])
def test_scroll_projection_selects_only_safe_stored_fields_for_all_fields(fl):
    collection = _search_collection("name", "__access_lvl__")
    collection.stored_fields["not_stored"] = SimpleNamespace(store=False)

    assert select_safe_scroll_fields({"hit": collection}, fl) == (["name", "id"], {"hit": ["name"]}, True)


def test_scroll_projection_expands_wildcards_and_preserves_expanded_ids():
    collection = _search_collection("name", "nested.name", "id")
    collection.model_class = SimpleNamespace(flat_fields=collection.stored_fields.copy)

    assert select_safe_scroll_fields({"hit": collection}, "n*") == (
        ["name", "nested.name"],
        {"hit": ["name", "nested.name"]},
        False,
    )
    assert select_safe_scroll_fields({"hit": collection}, "i*") == (["id"], {"hit": ["id"]}, True)


@pytest.mark.parametrize("item_index", [None, 1])
def test_scroll_projection_uses_single_index_fields_without_index_metadata(item_index):
    item = {"name": "allowed", "not_stored": "filtered", "id": "hit-id"}
    if item_index is not None:
        item["__index"] = item_index

    expected = {key: value for key, value in item.items() if key != "not_stored"}
    assert prune_scroll_items([item], {"hit": ["name"]}, include_id=True) == [expected]


def test_scroll_projection_fails_closed_without_index_metadata_for_multiple_indexes():
    items = [{"name": "must not leak", "id": "hit-id"}]

    assert prune_scroll_items(items, {"hit": ["name"], "user": ["name"]}, include_id=False) == [{}]


def test_scroll_projection_removes_banned_fields_from_selected_subtrees():
    items = [
        {
            "nested": {
                "name": "allowed",
                "__access_lvl__": "filtered",
                "entries": [{"name": "allowed", "__access_req__": "filtered"}],
            },
            "__access_grp1__": "filtered",
        }
    ]

    assert prune_scroll_items(items, {"hit": ["nested", "__access_grp1__"]}, include_id=False) == [
        {"nested": {"name": "allowed", "entries": [{"name": "allowed"}]}}
    ]


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


def test_scroll_search_preserves_request_params_and_wraps_the_next_scroll_id():
    user = _user()
    params = {"deep_paging_id": "*", "fl": "name", "rows": 10}
    original_params = params.copy()

    with (
        patch("howler.services.search_service.get_collection") as mock_get_collection,
        patch("howler.services.search_service.search") as mock_search,
    ):
        mock_get_collection.return_value.return_value = _search_collection("name")
        mock_search.return_value = {
            "items": [{"__index": "hit", "name": "allowed", "not_stored": "filtered"}],
            "next_deep_paging_id": "raw-es-scroll",
            "offset": 0,
            "rows": 1,
            "total": 1,
        }

        result = scroll_search("hit", "id:*", user, params, "1m")

        mock_search.assert_called_once_with(
            "hit", "id:*", user=user, deep_paging_id="*", fl=["name"], rows=10, scroll="1m", include_id=False
        )

    assert params == original_params
    assert result["items"] == [{"__index": "hit", "name": "allowed"}]
    assert resolve_deep_paging_id(user, "hit", result["next_deep_paging_id"], "id:*") == "raw-es-scroll"
