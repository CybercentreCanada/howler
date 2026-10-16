"""Field-safety checks for user-index searches, covering comma strings, JSON lists, wildcards, and defaults."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from howler.datastore.exceptions import SearchException
from howler.services.search_service import (
    USER_STORED_FIELDS,
    SensitiveUserFieldsException,
    _field_paths_with_compound_parents,
    _project_user_index_items,
    facet,
    search,
    user_fields_allowed,
)


class _Caller(dict):
    """A dict-backed caller that also exposes attributes, as the ODM user model does."""

    def __getattr__(self, name):
        return self[name]


def _caller(access_control: str | None = None) -> _Caller:
    return _Caller(uname="alice", type=["user"], access_control=access_control, classification=None)


@pytest.mark.parametrize(
    ("indexes", "fl"),
    [
        ("user", "password"),
        ("user", "apikeys"),
        ("user", "*"),
        ("user", ["*"]),
        ("user", ["pass*"]),
        ("user", ["apik*"]),
        ("user", ["*word"]),
        ("user", "uname,pass*"),
        ("user", ["uname", "password"]),
        ("user", ["password.hash"]),
        ("user", ["apikeys.name.password"]),
        ("user", "access_control"),
        ("user", ["uname", "api_quota"]),
        ("user", "dashboard.config"),
        ("user", "dashboard.unknown"),
        ("user", "unknown_field"),
        ("user", "name.internal"),
        ("user", "__access_lvl__"),
        ("user", {"password": 1}),
        ("user", {"password"}),
        ("user", 5),
        ("user", [["password"]]),
        ("user", [5]),
        ("hit,user", ["*"]),
        ("hit, user", ["apikeys"]),
        ("hit,user", ["uname", "access_control"]),
    ],
)
def test_user_index_rejects_credential_wildcard_or_non_stored_fields(indexes, fl):
    assert user_fields_allowed(indexes, fl) is False


@pytest.mark.parametrize(
    ("indexes", "fl"),
    [
        ("user", None),
        ("user", ""),
        ("user", []),
        ("user", "uname,email"),
        ("user", ["uname", "groups"]),
        ("hit", ["*"]),
        ("hit,event", ["password"]),
    ],
)
def test_safe_or_non_user_requests_are_allowed(indexes, fl):
    assert user_fields_allowed(indexes, fl) is True


def test_mixed_index_fields_must_belong_to_a_requested_index_schema():
    hit_collection = SimpleNamespace(stored_fields={"howler.id": SimpleNamespace(store=True)})

    with patch("howler.services.search_service.INDEX_MAP", {"hit": lambda: hit_collection}):
        assert user_fields_allowed("hit,user", ["howler.id", "uname"]) is False
        assert user_fields_allowed("hit,user", ["howler.id", "uname"], allow_other_index_fields=True) is True
        assert user_fields_allowed("hit,user", ["unknown_field", "uname"], allow_other_index_fields=True) is False


def test_field_allowlist_includes_only_compound_parents_of_stored_paths():
    allowed_paths = _field_paths_with_compound_parents({"settings.theme", "username"})
    assert allowed_paths == {
        "settings",
        "settings.theme",
        "username",
    }

    with (
        patch("howler.services.search_service._USER_ALLOWED_FIELD_PATHS", frozenset(allowed_paths)),
        patch("howler.services.search_service._USER_DENIED_ROOTS", frozenset()),
    ):
        assert user_fields_allowed("user", "settings") is True
        assert user_fields_allowed("user", "settings.theme") is True
        assert user_fields_allowed("user", "settings.unknown") is False

    assert user_fields_allowed("user", "id") is False
    assert user_fields_allowed("user", "id", include_id=True) is True


def test_mixed_search_prunes_non_user_fields_and_unknown_source_values_from_user_items():
    items = [
        {
            "__index": "user",
            "uname": "alice",
            "howler": {"id": "not-a-user-field"},
            "dashboard": [{"config": "safe", "unexpected": "not-stored"}],
        },
        {"__index": "hit", "howler": {"id": "hit-1"}},
    ]

    assert _project_user_index_items(items, ["hit", "user"], ["uname", "howler.id"]) == [
        {"__index": "user", "uname": "alice"},
        {"__index": "hit", "howler": {"id": "hit-1"}},
    ]


def test_user_projection_keeps_document_id_when_scroll_requests_it():
    item = {"__index": "user", "id": "user-id", "uname": "alice"}

    assert _project_user_index_items([item], ["user"], None, include_id=True) == [item]


def test_mixed_index_search_only_returns_stored_user_fields_from_user_documents():
    hit_collection = SimpleNamespace(stored_fields={"howler.id": SimpleNamespace(store=True)})

    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch("howler.services.search_service.get_collection", return_value=lambda: hit_collection),
    ):
        storage = mock_datastore.return_value
        client = storage.ds.client
        client.search.return_value = {
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {
                        "_index": "howler-user_hot",
                        "_source": {"uname": "alice", "howler": {"id": "unexpected-user-data"}},
                    },
                    {"_index": "howler-hit_hot", "_source": {"howler": {"id": "hit-1"}}},
                ],
            }
        }

        result = search(["hit", "user"], query="*:*", fl=["howler.id", "uname"], user=_caller())

    assert result["items"] == [
        {"__index": "user", "uname": "alice"},
        {"__index": "hit", "howler": {"id": "hit-1"}},
    ]


def test_mixed_index_facet_rejects_fields_without_a_user_allowlist_entry():
    with patch("howler.services.search_service.datastore") as mock_datastore:
        with pytest.raises(SensitiveUserFieldsException):
            facet(["hit", "user"], ["howler.id"], user=_caller())

    mock_datastore.assert_not_called()


def test_stored_user_fields_exclude_credentials_and_non_stored_fields():
    assert {"uname", "email", "groups"} <= USER_STORED_FIELDS
    assert not {"password", "apikeys", "access_control", "api_quota"} & USER_STORED_FIELDS


@pytest.mark.parametrize(
    "fl",
    [
        ["apik*"],
        ["pass*"],
        "*",
        {"password": 1},
        ["access_control"],
        ["unknown_field"],
        ["dashboard.unknown"],
    ],
)
def test_search_rejects_credential_wildcards_before_querying(fl):
    with patch("howler.services.search_service.datastore") as mock_datastore:
        with pytest.raises(SensitiveUserFieldsException):
            search("user", query="uname:*", fl=fl)

    mock_datastore.assert_not_called()


@pytest.mark.parametrize("fl", [None, "", []])
def test_user_search_without_fields_returns_only_stored_fields(fl):
    with patch("howler.services.search_service.datastore") as mock_datastore:
        client = mock_datastore.return_value.ds.client
        client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search("user", query="uname:*", fl=fl)

    source = client.search.call_args.kwargs["_source"]
    assert source == sorted(USER_STORED_FIELDS)
    assert not {"password", "apikeys", "access_control", "api_quota"} & set(source)


def test_mixed_index_search_without_fields_is_rejected_before_querying():
    with patch("howler.services.search_service.datastore") as mock_datastore:
        with pytest.raises(SensitiveUserFieldsException, match="Specify fl"):
            search("hit,user", query="id:*")

    mock_datastore.assert_not_called()


@pytest.mark.parametrize("fields", [["password"], ["apikeys"], ["access_control"], ["pass*"]])
def test_facet_on_credential_or_non_stored_user_fields_is_rejected(fields):
    with patch("howler.services.search_service.datastore") as mock_datastore:
        with pytest.raises(SensitiveUserFieldsException):
            facet("user", fields)

    mock_datastore.assert_not_called()


@pytest.mark.parametrize(
    "indexes",
    ["howler-user", "howler-user_hot", "*", "_all", "*user*", "howler-*", "hit,howler-user", ""],
)
@pytest.mark.parametrize("fl", [None, ["password"], ["uname"]])
def test_physical_alias_and_wildcard_indexes_are_refused_before_querying(indexes, fl):
    with patch("howler.services.search_service.datastore") as mock_datastore:
        with pytest.raises(SearchException):
            search(indexes, query="uname:*", fl=fl, user=_caller())

    mock_datastore.assert_not_called()


def test_leading_space_index_still_applies_the_access_control_filter():
    """An index segment with stray whitespace must not disable the access-control filter."""
    with patch("howler.services.search_service.datastore") as mock_datastore:
        client = mock_datastore.return_value.ds.client
        client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search(" hit", query="id:*", rows=1, user=_caller(access_control="group:analysts"))

    filters = client.search.call_args.kwargs["query"]["bool"]["filter"]
    assert {"query_string": {"query": "group:analysts"}} in filters
