"""Field-safety checks for user-index searches, covering comma strings, JSON lists, wildcards, and defaults."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from howler.api.search_utils import issue_scroll_token
from howler.datastore.exceptions import SearchException
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.services.search_service import (
    USER_STORED_FIELDS,
    SensitiveUserFieldsException,
    facet,
    scroll_search,
    search,
    user_fields_allowed,
)


class _Caller(dict):
    """A dict-backed caller that also exposes attributes, as the ODM user model does."""

    def __getattr__(self, name):
        return self[name]


def _caller(access_control: str | None = None) -> _Caller:
    return _Caller(uname="alice", type=["user"], access_control=access_control, classification=None)


def _collection(model):
    return SimpleNamespace(
        model_class=model,
        stored_fields={name: field for name, field in model.flat_fields().items() if field.store},
    )


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


def test_legacy_user_guard_does_not_allow_other_index_fields():
    assert user_fields_allowed("hit,user", ["howler.id", "uname"]) is False


def test_user_field_allowlist_rejects_unstored_compound_fields():
    assert user_fields_allowed("user", "uname") is True
    assert user_fields_allowed("user", "dashboard") is False
    assert user_fields_allowed("user", "dashboard.unknown") is False


def test_public_synthetic_document_id_is_allowed_for_user_search():
    assert user_fields_allowed("user", "id") is True


def test_mixed_index_search_only_returns_stored_user_fields_from_user_documents():
    hit_collection = SimpleNamespace(
        model_class=None,
        stored_fields={"howler.id": SimpleNamespace(store=True)},
    )
    user_collection = _collection(User)
    collections = {"hit": hit_collection, "user": user_collection}

    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch(
            "howler.services.search_service.get_collection",
            side_effect=lambda index, user: lambda: collections[index],
        ),
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


@pytest.mark.parametrize("fl", [["password"], ["apikeys.token.password"], ["access_control"], ["dashboard.config"]])
def test_search_rejects_non_stored_user_fields_before_querying(fl):
    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch("howler.services.search_service.INDEX_MAP", {"user": lambda: _collection(User)}),
    ):
        with pytest.raises(SearchException, match="not stored"):
            search("user", query="uname:*", fl=fl)

    mock_datastore.assert_not_called()


@pytest.mark.parametrize("fl", [None, "", []])
def test_user_search_without_fields_returns_only_stored_fields(fl):
    collection = _collection(User)
    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch("howler.services.search_service.INDEX_MAP", {"user": lambda: collection}),
    ):
        client = mock_datastore.return_value.ds.client
        client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search("user", query="uname:*", fl=fl)

    source = client.search.call_args.kwargs["_source"]
    assert set(source) == USER_STORED_FIELDS
    assert not {"password", "apikeys", "access_control", "api_quota"} & set(source)


def test_user_search_returns_public_synthetic_document_id_when_requested():
    collection = _collection(User)
    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch("howler.services.search_service.get_collection", return_value=lambda: collection),
    ):
        client = mock_datastore.return_value.ds.client
        client.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [{"_index": "howler-user_hot", "_id": "user-1", "_source": {}}],
            }
        }

        result = search("user", query="uname:alice", fl="id", user=_caller())

    assert client.search.call_args.kwargs["_source"] == []
    assert result["items"] == [{"__index": "user", "id": "user-1"}]


@pytest.mark.parametrize("fl", ["*", "pass*"])
def test_projected_user_wildcards_cannot_return_credentials(fl):
    collection = _collection(User)
    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch("howler.services.search_service.get_collection", return_value=lambda: collection),
    ):
        client = mock_datastore.return_value.ds.client
        client.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_index": "howler-user_hot",
                        "_id": "user-1",
                        "_source": {"uname": "alice", "password": "secret", "apikeys": {"k": "secret"}},
                    }
                ],
            }
        }

        result = search("user", query="uname:alice", fl=fl, user=_caller())

    assert "password" not in result["items"][0]
    assert "apikeys" not in result["items"][0]
    assert set(client.search.call_args.kwargs["_source"]) <= USER_STORED_FIELDS


def test_search_projects_non_user_defaults_to_stored_fields():
    collection = SimpleNamespace(model_class=None, stored_fields={"name": SimpleNamespace(store=True)})
    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch("howler.services.search_service.INDEX_MAP", {"hit": lambda: collection}),
    ):
        client = mock_datastore.return_value.ds.client
        client.search.return_value = {
            "hits": {
                "total": {"value": 1},
                "hits": [
                    {
                        "_index": "howler-hit_hot",
                        "_source": {"name": "stored", "howler": {"data": "not-stored"}},
                    }
                ],
            }
        }

        result = search("hit", query="id:*")

    assert client.search.call_args.kwargs["_source"] == ["name"]
    assert result["items"] == [{"name": "stored", "__index": "hit"}]


def test_projected_search_uses_each_index_schema_for_mixed_fields():
    hit_collection = SimpleNamespace(
        model_class=None,
        stored_fields={
            "shared": SimpleNamespace(store=True),
            "hit_only": SimpleNamespace(store=True),
        },
    )
    event_collection = SimpleNamespace(
        model_class=None,
        stored_fields={
            "shared": SimpleNamespace(store=True),
            "event_only": SimpleNamespace(store=True),
        },
    )
    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch(
            "howler.services.search_service.INDEX_MAP",
            {"hit": lambda: hit_collection, "event": lambda: event_collection},
        ),
    ):
        client = mock_datastore.return_value.ds.client
        client.search.return_value = {
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {
                        "_index": "howler-hit_hot",
                        "_source": {"shared": "hit", "hit_only": "hit-value", "event_only": "filtered"},
                    },
                    {
                        "_index": "howler-event_hot",
                        "_source": {"shared": "event", "hit_only": "filtered", "event_only": "event-value"},
                    },
                ],
            }
        }

        result = search(
            "hit,event",
            query="*:*",
            fl="shared,hit_only,event_only",
        )

    assert client.search.call_args.kwargs["_source"] == ["shared", "hit_only", "event_only"]
    assert result["items"] == [
        {"shared": "hit", "hit_only": "hit-value", "__index": "hit"},
        {"shared": "event", "event_only": "event-value", "__index": "event"},
    ]


def test_mixed_projection_uses_elasticsearch_index_not_source_metadata():
    collection = SimpleNamespace(model_class=None, stored_fields={"shared": SimpleNamespace(store=True)})
    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch(
            "howler.services.search_service.INDEX_MAP",
            {"hit": lambda: collection, "event": lambda: collection},
        ),
    ):
        client = mock_datastore.return_value.ds.client
        client.search.return_value = {
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {"_index": "howler-event_hot", "_source": {"__index": "hit", "shared": "event-value"}},
                    {"_source": {"__index": "hit", "shared": "untrusted-index"}},
                ],
            }
        }

        result = search("hit,event", query="*:*", fl="shared")

    assert result["items"] == [{"shared": "event-value", "__index": "event"}, {}]


def test_mixed_index_search_without_fields_selects_stored_defaults_per_index():
    hit_collection = SimpleNamespace(model_class=None, stored_fields={"howler.id": SimpleNamespace(store=True)})
    user_collection = _collection(User)
    collections = {"hit": hit_collection, "user": user_collection}

    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch(
            "howler.services.search_service.get_collection",
            side_effect=lambda index, user: lambda: collections[index],
        ),
    ):
        client = mock_datastore.return_value.ds.client
        client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        search("hit,user", query="id:*", user=_caller())

    assert set(client.search.call_args.kwargs["_source"]) == USER_STORED_FIELDS | {"howler.id"}


def test_scroll_search_delegates_projection_without_resolving_collections():
    params = {"deep_paging_id": "*", "fl": "uname", "rows": 10}

    with (
        patch("howler.services.search_service.get_collection") as mock_get_collection,
        patch("howler.services.search_service.search") as mock_search,
    ):
        mock_search.return_value = {
            "items": [{"__index": "user", "uname": "alice"}],
            "next_deep_paging_id": "raw-scroll-id",
            "offset": 0,
            "rows": 1,
            "total": 1,
        }

        result = scroll_search("user", "uname:*", _caller(), params, "1m")

    mock_get_collection.assert_not_called()
    assert mock_search.call_args.kwargs["include_id"] is False
    assert "resolved_collections" not in mock_search.call_args.kwargs
    assert result["items"] == [{"__index": "user", "uname": "alice"}]
    assert params == {"deep_paging_id": "*", "fl": "uname", "rows": 10}


@pytest.mark.parametrize("continuation", [False, True])
@pytest.mark.parametrize(
    ("fl", "expected_labels"),
    [
        ("labels.team", {"team": "blue"}),
        ("labels.*", {"team": "blue", "department": "ops", "team.name": "literal"}),
        ("labels.t*", {"team": "blue", "team.name": "literal"}),
        ("*.team", {"team": "blue"}),
        ("*team", {"team": "blue"}),
        ("labels.team.name", {"team.name": "literal"}),
        ("labels.missing*", None),
    ],
)
def test_mixed_user_mapping_selection_uses_common_policy(fl, expected_labels, continuation):
    collections = {"hit": _collection(Hit), "user": _collection(User)}
    caller = _caller()
    with (
        patch("howler.services.search_service.datastore") as mock_datastore,
        patch(
            "howler.services.search_service.get_collection",
            side_effect=lambda index, _user: lambda: collections[index],
        ) as mock_get_collection,
    ):
        client = mock_datastore.return_value.ds.client
        response = {
            "_scroll_id": "next-scroll",
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {
                        "_index": "howler-hit_hot",
                        "_source": {"labels": {"team": "blue", "department": "ops", "team.name": "literal"}},
                    },
                    {
                        "_index": "howler-user_hot",
                        "_source": {"labels": {"team": "must not leak"}, "password": "must not leak"},
                    },
                ],
            },
        }
        client.search.return_value = response
        client.scroll.return_value = response
        if continuation:
            token = issue_scroll_token(caller, "hit,user", "original-scroll", "id:*")
            result = scroll_search("hit,user", "id:*", caller, {"deep_paging_id": token, "fl": fl, "rows": 2}, None)
            client.scroll.assert_called_once_with(scroll_id="original-scroll", scroll="5m")
        else:
            result = search("hit,user", query="id:*", fl=fl, rows=2, user=caller)

    expected_hit = {"__index": "hit"}
    if expected_labels is not None:
        expected_hit["labels"] = expected_labels
    assert result["items"] == [expected_hit, {"__index": "user"}]
    assert mock_get_collection.call_count == 2


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
