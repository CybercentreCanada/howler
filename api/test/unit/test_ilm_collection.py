"""Unit tests for ILM methods on ESCollection.

These tests mock the Elasticsearch client to verify the correct ILM policy,
index template, and _ensure_collection_ilm logic without requiring a running ES.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import elasticsearch
import pytest
from elastic_transport import ApiResponseMeta

from howler.datastore.collection import ESCollection
from howler.datastore.exceptions import DataStoreException, SearchException
from howler.models import HowlerModelValidationError
from howler.models import schema as new_schema
from howler.models.action import Action as SchemaAction
from howler.models.analytic import Analytic as SchemaAnalytic
from howler.models.case import Case as SchemaCase
from howler.models.event import Event as SchemaEvent
from howler.models.hit import Hit as SchemaHit
from howler.models.user import User as SchemaUser
from howler.odm.models.action import Action as LegacyAction
from howler.odm.models.config import ILMConfig, ILMIndexConfig


@pytest.fixture(autouse=True)
def skip_ensure_collection():
    """Prevent ESCollection from calling _ensure_collection on init."""
    ESCollection.IGNORE_ENSURE_COLLECTION = True
    yield
    ESCollection.IGNORE_ENSURE_COLLECTION = False


@pytest.fixture()
def mock_datastore():
    """Create a mock ESStore with a mock ES client."""
    ds = MagicMock()
    ds.client = MagicMock()
    ds.client.ilm = MagicMock()
    ds.client.indices = MagicMock()
    ds.DEFAULT_SORT = "id asc"
    return ds


@pytest.fixture()
def ilm_global():
    """Default global ILM config for tests."""
    return ILMConfig(
        enabled=True,
        rollover_max_age="30d",
        rollover_max_size="50gb",
        indices={"testcol": ILMIndexConfig(warm="30d", cold="90d")},
    )


def _make_collection(mock_datastore, ilm_config=None, schema_model=None, model_class=None):
    """Helper to create an ESCollection with the given ILM config."""
    mock_datastore._models = {"testcol": None}
    col = ESCollection(
        mock_datastore,
        "testcol",
        model_class=model_class,
        ilm_config=ilm_config,
        schema_model=schema_model,
    )
    return col


def _action_data() -> dict:
    return {
        "action_id": "action-1",
        "owner_id": "user-1",
        "name": "Test Action",
        "query": "id:*",
        "triggers": ["create"],
        "operations": [],
    }


class TestPydanticPersistence:
    """Focused registered-model persistence and projection behavior."""

    def test_normalize_full_document_strips_stored_helpers_and_sets_metadata(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)

        action = col.normalize(
            {
                **_action_data(),
                "id": "stored-id",
                "__access_lvl__": 100,
            },
            doc_id="document-id",
            index="howler-action_hot",
        )

        assert isinstance(action, SchemaAction)
        assert action.meta.id == "document-id"
        assert action.meta.index == "howler-action_hot"
        assert action.as_primitives() == _action_data()

    def test_projected_search_object_validates_only_selected_fields(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)

        action = col._format_output(
            {
                "_id": "document-id",
                "_index": "howler-action_hot",
                "_score": 1.5,
                "_source": {"name": "Projected", "id": "document-id"},
            },
            ["name", "id"],
            as_obj=True,
        )

        assert action.name == "Projected"
        assert "action_id" not in action.__dict__
        assert action.meta.id == "document-id"
        assert action.meta.score == 1.5
        assert action.as_primitives() == {"name": "Projected"}

    def test_save_validates_full_model_and_preserves_stored_request(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)

        assert col.save("document-id", _action_data(), refresh="wait_for") is True

        call = mock_datastore.client.index.call_args.kwargs
        assert call["index"] == col.name
        assert call["id"] == "document-id"
        assert call["refresh"] == "wait_for"
        assert call["op_type"] == "index"
        assert json.loads(call["document"]) == {**_action_data(), "id": "document-id"}

        with pytest.raises(HowlerModelValidationError):
            col.save("document-id", {"name": "Incomplete"})
        with pytest.raises(HowlerModelValidationError):
            col.save("document-id", {**_action_data(), "unknown": True})

    def test_save_accepts_legacy_model_during_step_8_handoff(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)
        action = LegacyAction(_action_data())

        assert col.save("document-id", action) is True
        assert json.loads(mock_datastore.client.index.call_args.kwargs["document"]) == {
            **_action_data(),
            "id": "document-id",
        }

    def test_projected_model_cannot_be_saved_as_full_replacement(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)
        projected = col._format_output(
            {
                "_id": "document-id",
                "_index": "howler-action_hot",
                "_source": {"name": "Projected", "id": "document-id"},
            },
            ["name", "id"],
            as_obj=True,
        )

        with pytest.raises(HowlerModelValidationError):
            col.save("document-id", projected)

        mock_datastore.client.index.assert_not_called()

    def test_multiget_does_not_mutate_keys_and_returns_models(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)
        keys = ["document-id"]
        mock_datastore.client.mget.return_value = {
            "docs": [
                {
                    "_id": "document-id",
                    "_index": "howler-action_hot",
                    "found": True,
                    "_source": {**_action_data(), "id": "document-id"},
                }
            ]
        }

        result = col.multiget(keys)

        assert keys == ["document-id"]
        assert isinstance(result["document-id"], SchemaAction)
        assert result["document-id"].meta.id == "document-id"

    def test_get_preserves_elasticsearch_metadata(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)
        mock_datastore.client.get.return_value = {
            "_id": "document-id",
            "_index": "howler-action_hot",
            "_seq_no": 7,
            "_primary_term": 3,
            "_version": 8,
            "_source": {
                **_action_data(),
                "id": "document-id",
                "removed_plugin_field": {"value": "legacy"},
            },
        }

        action = col.get_if_exists("document-id")

        assert action.meta.id == "document-id"
        assert action.meta.index == "howler-action_hot"
        assert action.meta.seq_no == 7
        assert action.meta.primary_term == 3
        assert action.meta.version == 8
        assert "removed_plugin_field" not in action.__dict__

    def test_update_validation_uses_registry_fields_and_stored_primitives(self, mock_datastore):
        action_col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)
        assert action_col._validate_operations([("SET", "name", 123)]) == [("SET", "name", "123")]
        assert action_col._validate_operations([("APPEND", "triggers", "create")]) == [("APPEND", "triggers", "create")]
        with pytest.raises(DataStoreException, match="Invalid field"):
            action_col._validate_operations([("SET", "missing", "value")])

        event_col = _make_collection(mock_datastore, schema_model=SchemaEvent, model_class=SchemaEvent)
        operations = event_col._validate_operations(
            [
                ("SET", "timestamp", "2024-01-02T03:04:05.000000Z"),
                ("SET", "source.ip", "127.0.0.1"),
                ("SET", "classification", "UNRESTRICTED"),
            ]
        )
        assert operations == [
            ("SET", "timestamp", "2024-01-02T03:04:05+00:00"),
            ("SET", "source.ip", "127.0.0.1"),
            ("SET", "classification", "UNRESTRICTED"),
            ("SET", "__access_lvl__", 100),
            ("SET", "__access_req__", []),
            ("SET", "__access_grp1__", ["__EMPTY__"]),
            ("SET", "__access_grp2__", ["__EMPTY__"]),
        ]

        hit_col = _make_collection(mock_datastore, schema_model=SchemaHit, model_class=SchemaHit)
        assert hit_col._validate_operations(
            [
                (
                    "APPEND",
                    "howler.log",
                    {
                        "timestamp": "2024-01-02T03:04:05.000000Z",
                        "user": "user-1",
                        "explanation": "Updated",
                    },
                )
            ]
        ) == [
            (
                "APPEND",
                "howler.log",
                {
                    "timestamp": "2024-01-02T03:04:05.000000Z",
                    "user": "user-1",
                    "explanation": "Updated",
                },
            )
        ]

    def test_delete_update_validates_mapping_path_and_generates_safe_script(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAnalytic, model_class=SchemaAnalytic)

        operations = col._validate_operations([("DELETE", "comment.reactions", "user-1")])
        assert operations == [("DELETE", "comment.reactions", "user-1")]
        assert col._create_scripts_from_operations(operations) == {
            "lang": "painless",
            "source": 'ctx._source["comment"]["reactions"].remove(params.value0)',
            "params": {"value0": "user-1"},
        }

        with pytest.raises(DataStoreException, match="Invalid field"):
            col._validate_operations([("DELETE", 'comment.reactions);ctx.op="delete";ctx._source.comment', "user-1")])
        with pytest.raises(DataStoreException, match="Invalid field"):
            col._validate_operations([("SET", 'comment.reactions.safe"];ctx.op="delete";ctx._source["comment', True)])
        with pytest.raises(DataStoreException, match="DELETE operation"):
            col._validate_operations([("DELETE", "comment", "user-1")])

    @pytest.mark.parametrize(
        "field",
        ["__access_lvl__", "__access_req__", "__access_grp1__", "__access_grp2__"],
    )
    def test_hidden_access_fields_cannot_be_updated_directly(self, mock_datastore, field):
        col = _make_collection(mock_datastore, schema_model=SchemaEvent, model_class=SchemaEvent)

        with pytest.raises(DataStoreException, match="derived from classification"):
            col._validate_operations(
                [
                    ("SET", "classification", "UNRESTRICTED"),
                    ("SET", field, [] if field != "__access_lvl__" else 0),
                ]
            )

    def test_classification_set_updates_hidden_fields_for_both_atomic_paths(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaEvent, model_class=SchemaEvent)
        mock_datastore.client.update.return_value = {
            "result": "updated",
            "_index": col.index_name,
            "_seq_no": 1,
            "_primary_term": 1,
        }
        col._update_async = MagicMock(return_value={"updated": 2})

        assert col.update("event-1", [("SET", "classification", "UNRESTRICTED")])[0] is True
        assert col.update_by_query("event.kind:alert", [("SET", "classification", "UNRESTRICTED")]) == 2

        expected_params = {
            "value0": "UNRESTRICTED",
            "value1": 100,
            "value2": [],
            "value3": ["__EMPTY__"],
            "value4": ["__EMPTY__"],
        }
        assert mock_datastore.client.update.call_args.kwargs["script"]["params"] == expected_params
        assert col._update_async.call_args.kwargs["script"]["params"] == expected_params


class TestEQLSearch:
    """Elasticsearch 9 complete and partial EQL responses."""

    def test_complete_response_preserves_public_shape_and_partial_settings(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)
        mock_datastore.client.eql.search.return_value = SimpleNamespace(
            body={
                "is_running": False,
                "is_partial": False,
                "hits": {
                    "total": 1,
                    "events": [
                        {
                            "_id": "document-id",
                            "_index": "howler-action_hot",
                            "_source": {"name": "Projected"},
                        }
                    ],
                    "sequences": [],
                },
            }
        )

        result = col.raw_eql_search("any where true", fl="name")

        assert result["rows"] == 5
        assert result["total"] == 1
        assert result["sequences"] == []
        assert len(result["items"]) == 1
        assert result["items"][0].name == "Projected"
        assert result["items"][0].meta.id == "document-id"
        call = mock_datastore.client.eql.search.call_args.kwargs
        assert call["allow_partial_search_results"] is True
        assert call["allow_partial_sequence_results"] is False

    def test_partial_response_is_not_presented_as_complete(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)
        mock_datastore.client.eql.search.return_value = {
            "is_running": False,
            "is_partial": True,
            "hits": {"total": {"value": 1}, "events": [], "sequences": []},
        }

        with pytest.raises(SearchException, match="incomplete EQL"):
            col.raw_eql_search("any where true", fl="name")

    @pytest.mark.parametrize(
        "incomplete_fields",
        [
            {"timed_out": True},
            {"shard_failures": [{"reason": "failed"}]},
            {"_shards": {"total": 2, "successful": 1, "skipped": 0, "failed": 1}},
            {"_shards": {"total": 2, "successful": 1, "skipped": 0, "failed": 0}},
        ],
    )
    def test_incomplete_shard_or_timeout_response_is_rejected(self, mock_datastore, incomplete_fields):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)
        mock_datastore.client.eql.search.return_value = {
            "is_running": False,
            "is_partial": False,
            "hits": {"total": {"value": 0}, "events": [], "sequences": []},
            **incomplete_fields,
        }

        with pytest.raises(SearchException, match="incomplete EQL"):
            col.raw_eql_search("any where true", fl="name")


class TestSearchConstruction:
    """Public DSL builders must retain existing emitted request semantics."""

    def test_collection_search_request_shape_is_stable(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaAction, model_class=SchemaAction)
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

        result = col._search(
            [
                ("query", "name:test"),
                ("filters", ["owner_id:user-1"]),
                ("field_list", ["name"]),
                ("start", 2),
                ("rows", 3),
                ("sort", [{"name": "desc"}]),
                ("facet_active", True),
                ("facet_fields", ["owner_id"]),
                ("facet_mincount", 2),
            ]
        )

        assert result["hits"]["hits"] == []
        assert mock_datastore.client.search.call_args.kwargs == {
            "index": col.name,
            "query": {
                "bool": {
                    "must": {"query_string": {"query": "name:test"}},
                    "filter": [{"query_string": {"query": "owner_id:user-1"}}],
                }
            },
            "from_": 2,
            "size": 3,
            "sort": [{"name": "desc"}],
            "_source": ["name"],
            "aggregations": {
                "owner_id": {
                    "terms": {
                        "field": "owner_id",
                        "min_doc_count": 2,
                        "size": 3,
                    }
                }
            },
        }

    def test_dictionary_projection_preserves_legacy_list_item_shape(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaCase, model_class=SchemaCase)

        result = col._format_output(
            {
                "_id": "case-1",
                "_source": {
                    "items": [
                        {
                            "id": "item-1",
                            "type": "hit",
                            "value": "hit-1",
                            "name": "Hit",
                        }
                    ]
                },
            },
            ["items.type"],
            as_obj=False,
        )

        assert result == {
            "items": [
                {
                    "id": "item-1",
                    "type": "hit",
                    "value": "hit-1",
                    "name": "Hit",
                }
            ]
        }

    def test_implicit_stored_field_object_projection_is_partial(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaUser, model_class=SchemaUser)

        user = col._format_output(
            {
                "_id": "user-1",
                "_source": {
                    "uname": "user-1",
                    "name": "Test User",
                    "classification": "UNRESTRICTED",
                },
            },
            as_obj=True,
        )

        assert user.uname == "user-1"
        assert user.name == "Test User"
        assert "password" not in user.__dict__

    def test_nested_declared_ids_survive_partial_object_projection(self, mock_datastore):
        col = _make_collection(mock_datastore, schema_model=SchemaHit, model_class=SchemaHit)

        hit = col._format_output(
            {
                "_id": "hit-1",
                "_source": {
                    "howler": {
                        "id": "hit-1",
                    }
                },
            },
            ["howler.id"],
            as_obj=True,
        )

        assert hit.howler.id == "hit-1"


class TestElasticsearchErrors:
    """Elasticsearch 9 structured errors retain retry behavior."""

    def test_task_polling_retries_timeout_error_types(self, mock_datastore):
        col = _make_collection(mock_datastore)
        meta = ApiResponseMeta(status=500, http_version="1.1", headers={}, duration=0.0, node=None)
        timeout = elasticsearch.ApiError(
            "timeout",
            meta,
            {
                "error": {
                    "type": "timeout_exception",
                    "reason": "Timed out waiting for completion",
                    "root_cause": [
                        {
                            "type": "timeout_exception",
                            "reason": "Timed out waiting for completion",
                        }
                    ],
                }
            },
        )
        mock_datastore.client.tasks.get.side_effect = [
            timeout,
            {"response": {"updated": 1, "version_conflicts": 0}},
        ]

        assert col._get_task_results({"task": "task-id"}) == {
            "updated": 1,
            "version_conflicts": 0,
        }
        assert mock_datastore.client.tasks.get.call_count == 2


class TestExists:
    """Tests for alias-safe document existence checks."""

    def test_ilm_exists_uses_search_instead_of_single_document_endpoint(self, mock_datastore):
        """ILM aliases can resolve to multiple indexes, so use an ids search."""
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 1, "relation": "eq"}}}

        assert col.exists("document-id") is True

        mock_datastore.client.exists.assert_not_called()
        mock_datastore.client.search.assert_called_once_with(
            index=col.name,
            query={"ids": {"values": ["document-id"]}},
            size=0,
            track_total_hits=True,
        )

    def test_exists_falls_back_to_search_after_bad_request(self, mock_datastore, caplog):
        """Unexpected multi-index alias errors recover through the alias-safe search."""
        col = _make_collection(mock_datastore)
        meta = ApiResponseMeta(status=400, http_version="1.1", headers={}, duration=0.0, node=None)
        mock_datastore.client.exists.side_effect = elasticsearch.exceptions.BadRequestError("bad_request", meta, {})
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 0, "relation": "eq"}}}

        with caplog.at_level("ERROR", logger="howler.api.datastore"):
            assert col.exists("document-id") is False

        assert "falling back to an alias-safe search" in caplog.text
        mock_datastore.client.search.assert_called_once_with(
            index=col.name,
            query={"ids": {"values": ["document-id"]}},
            size=0,
            track_total_hits=True,
        )


class TestILMAliasDocumentOperations:
    """Alias-wide logical ID operations target concrete rollover indices."""

    def test_multiget_locates_ids_then_groups_concrete_index_requests(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        old_index = f"{col.name}-000001"
        new_index = f"{col.name}-000002"
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "hits": [
                    {"_id": "old-id", "_index": old_index},
                    {"_id": "new-id", "_index": new_index},
                ],
            }
        }

        def mget(*, ids, index):
            return {
                "docs": [
                    {
                        "_id": data_id,
                        "_index": index,
                        "_seq_no": 7,
                        "_primary_term": 3,
                        "found": True,
                        "_source": {**_action_data(), "action_id": data_id, "id": data_id},
                    }
                    for data_id in ids
                ]
            }

        mock_datastore.client.mget.side_effect = mget

        result = col.multiget(["old-id", "new-id"])

        assert set(result) == {"old-id", "new-id"}
        assert result["old-id"].meta.index == old_index
        assert result["old-id"].meta.seq_no == 7
        assert result["old-id"].meta.primary_term == 3
        assert result["new-id"].meta.index == new_index
        mock_datastore.client.search.assert_called_once_with(
            index=col.name,
            query={"ids": {"values": ["old-id", "new-id"]}},
            size=10000,
            _source=False,
            sort=[{"_index": "desc"}],
            track_total_hits=True,
        )
        assert mock_datastore.client.mget.call_args_list == [
            call(ids=["old-id"], index=old_index),
            call(ids=["new-id"], index=new_index),
        ]

    def test_multiget_duplicate_id_uses_newest_generation_regardless_of_other_ids(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        old_index = f"{col.name}-000001"
        new_index = f"{col.name}-000002"
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 3, "relation": "eq"},
                "hits": [
                    {"_id": "old-only", "_index": old_index},
                    {"_id": "duplicate", "_index": new_index},
                    {"_id": "duplicate", "_index": old_index},
                ],
            }
        }

        def mget(*, ids, index):
            return {
                "docs": [
                    {
                        "_id": data_id,
                        "_index": index,
                        "found": True,
                        "_source": {**_action_data(), "action_id": data_id, "id": data_id},
                    }
                    for data_id in ids
                ]
            }

        mock_datastore.client.mget.side_effect = mget

        result = col.multiget(["old-only", "duplicate"])

        assert result["old-only"].meta.index == old_index
        assert result["duplicate"].meta.index == new_index
        assert mock_datastore.client.mget.call_args_list == [
            call(ids=["old-only"], index=old_index),
            call(ids=["duplicate"], index=new_index),
        ]

    def test_delete_removes_every_matching_concrete_rollover_document(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        old_index = f"{col.name}-000001"
        new_index = f"{col.name}-000002"
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "hits": [
                    {"_id": "document-id", "_index": new_index},
                    {"_id": "document-id", "_index": old_index},
                ],
            }
        }
        mock_datastore.client.delete.side_effect = [
            {"result": "deleted"},
            {"result": "deleted"},
        ]

        assert col.delete("document-id", refresh="wait_for") is True

        assert mock_datastore.client.delete.call_args_list == [
            call(id="document-id", index=new_index, refresh="wait_for"),
            call(id="document-id", index=old_index, refresh="wait_for"),
        ]

    def test_delete_missing_ilm_document_returns_false_without_alias_delete(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

        assert col.delete("missing") is False
        mock_datastore.client.delete.assert_not_called()


class TestILMVersionedOperations:
    """Tests for alias-safe ILM reads followed by optimistic-concurrency writes."""

    def test_versioned_get_uses_search_and_returns_concrete_index(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        concrete_index = f"{col.name}-000001"
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [
                    {
                        "_id": "document-id",
                        "_index": concrete_index,
                    }
                ],
            }
        }
        mock_datastore.client.get.return_value = {
            "_id": "document-id",
            "_index": concrete_index,
            "_seq_no": 5,
            "_primary_term": 2,
            "_source": {"id": "document-id", "value": "original"},
        }

        data, version = col.get_if_exists("document-id", as_obj=False, version=True)

        assert data == {"value": "original"}
        assert version == f"{concrete_index}---5---2"
        mock_datastore.client.search.assert_called_once_with(
            index=col.name,
            query={"ids": {"values": ["document-id"]}},
            size=10000,
            _source=False,
            sort=[{"_index": "desc"}],
            track_total_hits=True,
        )
        mock_datastore.client.get.assert_called_once_with(index=concrete_index, id="document-id")

    def test_versioned_get_returns_create_token_for_missing_ilm_document(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        mock_datastore.client.search.return_value = {"hits": {"hits": []}}

        data, version = col.get_if_exists("missing-document", as_obj=False, version=True)

        assert data is None
        assert version == "create"

    def test_versioned_writes_target_the_concrete_ilm_index(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        concrete_index = f"{col.name}-000001"
        version = f"{concrete_index}---5---2"
        mock_datastore.client.update.return_value = {
            "result": "updated",
            "_index": concrete_index,
            "_seq_no": 6,
            "_primary_term": 2,
        }

        col.save("document-id", {"value": "updated"}, version=version)
        updated, new_version = col.update("document-id", [(col.UPDATE_SET, "value", "updated")], version=version)

        assert mock_datastore.client.index.call_args.kwargs["index"] == concrete_index
        assert mock_datastore.client.update.call_args.kwargs["index"] == concrete_index
        assert mock_datastore.client.index.call_args.kwargs["if_seq_no"] == "5"
        assert mock_datastore.client.index.call_args.kwargs["if_primary_term"] == "2"
        assert updated is True
        assert new_version == f"{concrete_index}---6---2"

    def test_unversioned_save_resolves_the_existing_ilm_document_version(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        concrete_index = f"{col.name}-000001"
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [
                    {
                        "_id": "document-id",
                        "_index": concrete_index,
                    }
                ],
            }
        }
        mock_datastore.client.get.return_value = {
            "_id": "document-id",
            "_index": concrete_index,
            "_seq_no": 5,
            "_primary_term": 2,
            "_source": {"id": "document-id", "value": "original"},
        }

        col.save("document-id", {"value": "updated"})

        assert mock_datastore.client.index.call_args.kwargs["index"] == concrete_index
        assert mock_datastore.client.index.call_args.kwargs["if_seq_no"] == "5"
        assert mock_datastore.client.index.call_args.kwargs["if_primary_term"] == "2"

    def test_unversioned_save_creates_a_missing_ilm_document(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        mock_datastore.client.search.return_value = {"hits": {"hits": []}}

        col.save("document-id", {"value": "new"})

        assert mock_datastore.client.index.call_args.kwargs["index"] == col.name
        assert mock_datastore.client.index.call_args.kwargs["op_type"] == "create"

    def test_unversioned_update_returns_false_for_missing_ilm_document(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        mock_datastore.client.search.return_value = {"hits": {"hits": []}}

        assert col.update("missing-document", [(col.UPDATE_SET, "name", "updated")]) is False
        mock_datastore.client.update.assert_not_called()

    def test_duplicate_ids_use_newest_canonical_generation(self, mock_datastore, caplog):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        old_index = f"{col.name}-000001"
        new_index = f"{col.name}-000002"
        temp_index = f"{col.name}-000003__reindex"
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 3, "relation": "eq"},
                "hits": [
                    {"_id": "document-id", "_index": temp_index},
                    {"_id": "document-id", "_index": old_index},
                    {"_id": "document-id", "_index": new_index},
                ],
            }
        }
        mock_datastore.client.get.return_value = {
            "_id": "document-id",
            "_index": new_index,
            "_seq_no": 8,
            "_primary_term": 3,
            "_source": {"id": "document-id", "value": "newest"},
        }

        with caplog.at_level("WARNING", logger="howler.api.datastore"):
            data, version = col.get_if_exists("document-id", as_obj=False, version=True)

        assert data == {"value": "newest"}
        assert version == f"{new_index}---8---3"
        mock_datastore.client.get.assert_called_once_with(index=new_index, id="document-id")
        assert "duplicate document id document-id" in caplog.text


class TestILMBulkRouting:
    """Bulk writes remain alias-safe across automatic rollover."""

    def test_new_documents_use_write_alias_after_rollover_without_restart(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        col.index_name = f"{col.name}-000001"

        plan = col.get_bulk_plan()
        plan.add_insert_operation("action-1", _action_data())

        assert json.loads(plan.operations[0][0]) == {"create": {"_index": col.name, "_id": "action-1"}}

    @pytest.mark.parametrize(
        ("operation", "action"),
        [("index", "index"), ("upsert", "update"), ("update", "update")],
    )
    def test_existing_documents_route_to_older_backing_index(self, mock_datastore, operation, action):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        old_index = f"{col.name}-000001"
        col.index_name = f"{col.name}-000002"
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [{"_id": "action-1", "_index": old_index}],
            }
        }

        plan = col.get_bulk_plan()
        getattr(plan, f"add_{operation}_operation")("action-1", _action_data())
        plan.get_plan_data()

        assert json.loads(plan.operations[0][0])[action]["_index"] == old_index

    def test_model_metadata_routes_without_alias_lookup_when_index_is_valid(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        old_index = f"{col.name}-000001"
        mock_datastore.client.indices.get.return_value = {
            old_index: {},
            f"{col.name}-000002": {},
            f"{col.name}-000003__reindex": {},
        }
        action = SchemaAction.model_validate({"meta": {"index": old_index}, **_action_data()})

        plan = col.get_bulk_plan()
        plan.add_index_operation("action-1", action)
        plan.add_update_operation("action-2", action, fields=["name"])

        assert json.loads(plan.operations[0][0])["index"]["_index"] == old_index
        assert json.loads(plan.operations[1][0])["update"]["_index"] == old_index
        mock_datastore.client.search.assert_not_called()
        mock_datastore.client.indices.get.assert_called_once_with(
            index=f"{col.name}-0*",
            ignore_unavailable=True,
            filter_path="*.aliases",
        )

    def test_invalid_model_metadata_cannot_select_arbitrary_index(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        old_index = f"{col.name}-000001"
        mock_datastore.client.indices.get.return_value = {old_index: {}}
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [{"_id": "action-1", "_index": old_index}],
            }
        }
        action = SchemaAction.model_validate({"meta": {"index": "unrelated-secret-index"}, **_action_data()})

        plan = col.get_bulk_plan()
        plan.add_index_operation("action-1", action)
        plan.get_plan_data()

        assert json.loads(plan.operations[0][0])["index"]["_index"] == old_index
        assert "unrelated-secret-index" not in plan.get_plan_data()

    def test_new_upsert_uses_write_alias(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

        plan = col.get_bulk_plan()
        plan.add_upsert_operation("action-1", _action_data())
        plan.get_plan_data()

        assert json.loads(plan.operations[0][0]) == {"update": {"_index": col.name, "_id": "action-1"}}

    def test_location_resolution_is_batched_once_for_all_queued_documents(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        old_index = f"{col.name}-000001"
        new_index = f"{col.name}-000002"
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "hits": [
                    {"_id": "action-1", "_index": old_index},
                    {"_id": "action-2", "_index": new_index},
                ],
            }
        }

        plan = col.get_bulk_plan()
        plan.add_index_operation("action-1", _action_data())
        plan.add_update_operation("action-2", {"name": "Updated"}, fields=["name"])
        plan.get_plan_data()

        mock_datastore.client.search.assert_called_once_with(
            index=col.name,
            query={"ids": {"values": ["action-1", "action-2"]}},
            size=10000,
            _source=False,
            sort=[{"_index": "desc"}],
            track_total_hits=True,
        )
        assert json.loads(plan.operations[0][0])["index"]["_index"] == old_index
        assert json.loads(plan.operations[1][0])["update"]["_index"] == new_index

    @pytest.mark.parametrize(("operation", "action"), [("update", "update"), ("delete", "delete")])
    def test_missing_update_or_delete_is_not_silently_dropped(self, mock_datastore, operation, action):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

        plan = col.get_bulk_plan()
        if operation == "update":
            plan.add_update_operation("missing", {"name": "Updated"}, fields=["name"])
        else:
            plan.add_delete_operation("missing")
        plan.get_plan_data()

        assert len(plan.operations) == 1
        assert json.loads(plan.operations[0][0]) == {action: {"_index": col.name, "_id": "missing"}}

    def test_explicit_invalid_index_is_rejected(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            schema_model=SchemaAction,
            model_class=SchemaAction,
        )
        mock_datastore.client.indices.get.return_value = {f"{col.name}-000001": {}}

        with pytest.raises(DataStoreException, match="not a physical member"):
            col.get_bulk_plan().add_index_operation(
                "action-1",
                _action_data(),
                index="unrelated-secret-index",
            )


class TestCreateILMPolicy:
    """Tests for _create_ilm_policy."""

    def test_hot_only(self, mock_datastore):
        """No warm or cold phases configured — only hot with rollover."""
        ilm_index = ILMIndexConfig()  # no warm/cold
        col = _make_collection(mock_datastore, ilm_config=ilm_index)
        ilm_global = ILMConfig(enabled=True, rollover_max_age="7d", rollover_max_size="25gb")

        col._create_ilm_policy(ilm_global)

        mock_datastore.client.ilm.put_lifecycle.assert_called_once()
        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "hot" in policy["phases"]
        assert policy["phases"]["hot"]["actions"]["rollover"]["max_age"] == "7d"
        assert policy["phases"]["hot"]["actions"]["rollover"]["max_primary_shard_size"] == "25gb"
        assert "warm" not in policy["phases"]
        assert "cold" not in policy["phases"]
        assert "delete" not in policy["phases"]

    def test_warm_and_cold(self, mock_datastore, ilm_global):
        """Both warm and cold phases configured with default forcemerge segments."""
        ilm_index = ILMIndexConfig(warm="30d", cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "hot" in policy["phases"]
        assert "warm" in policy["phases"]
        assert policy["phases"]["warm"]["min_age"] == "30d"
        assert policy["phases"]["warm"]["actions"]["forcemerge"]["max_num_segments"] == 3  # default
        assert "cold" in policy["phases"]
        assert policy["phases"]["cold"]["min_age"] == "90d"
        assert policy["phases"]["cold"]["actions"] == {}  # no forcemerge allowed in cold
        assert "delete" not in policy["phases"]

    def test_custom_forcemerge_segments(self, mock_datastore, ilm_global):
        """Custom forcemerge segment count in warm phase."""
        ilm_index = ILMIndexConfig(warm="30d", warm_forcemerge_segments=5, cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert policy["phases"]["warm"]["actions"]["forcemerge"]["max_num_segments"] == 5
        assert policy["phases"]["cold"]["actions"] == {}  # no forcemerge in cold

    def test_skip_forcemerge_with_none(self, mock_datastore, ilm_global):
        """Setting forcemerge segments to None skips forcemerge action in warm."""
        ilm_index = ILMIndexConfig(warm="30d", warm_forcemerge_segments=None, cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "warm" in policy["phases"]
        assert "forcemerge" not in policy["phases"]["warm"]["actions"]
        assert "cold" in policy["phases"]
        assert policy["phases"]["cold"]["actions"] == {}

    def test_warm_only_no_cold(self, mock_datastore, ilm_global):
        """Warm phase configured but no cold phase."""
        ilm_index = ILMIndexConfig(warm="14d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "warm" in policy["phases"]
        assert "cold" not in policy["phases"]

    def test_cold_only_no_warm(self, mock_datastore, ilm_global):
        """Cold phase configured but no warm phase."""
        ilm_index = ILMIndexConfig(cold="60d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "warm" not in policy["phases"]
        assert "cold" in policy["phases"]
        assert policy["phases"]["cold"]["min_age"] == "60d"

    def test_policy_name(self, mock_datastore, ilm_global):
        """Policy name follows the {APP_NAME}-{collection}_policy convention."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        assert call_kwargs.kwargs["name"] == f"{col.name}_policy"

    def test_no_readonly_in_warm(self, mock_datastore, ilm_global):
        """Warm phase must NOT have readonly — retention cronjob needs write access."""
        ilm_index = ILMIndexConfig(warm="30d", cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "readonly" not in policy["phases"]["warm"]["actions"]
        assert "readonly" not in policy["phases"]["cold"].get("actions", {})

    def test_no_delete_phase(self, mock_datastore, ilm_global):
        """Delete phase must never be present — retention cronjob handles deletion."""
        ilm_index = ILMIndexConfig(warm="30d", cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_ilm_policy(ilm_global)

        call_kwargs = mock_datastore.client.ilm.put_lifecycle.call_args
        policy = call_kwargs.kwargs["policy"]

        assert "delete" not in policy["phases"]


class TestCreateIndexTemplate:
    """Tests for _create_index_template."""

    def test_template_name_and_pattern(self, mock_datastore, ilm_global):
        """Template name and index pattern follow naming convention."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_index_template(ilm_global)

        call_kwargs = mock_datastore.client.indices.put_index_template.call_args
        assert call_kwargs.kwargs["name"] == f"{col.name}_template"
        assert call_kwargs.kwargs["index_patterns"] == [f"{col.name}-*"]

    def test_template_includes_ilm_settings(self, mock_datastore, ilm_global):
        """Template includes lifecycle.name and lifecycle.rollover_alias."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_index_template(ilm_global)

        call_kwargs = mock_datastore.client.indices.put_index_template.call_args
        template = call_kwargs.kwargs["template"]

        assert template["settings"]["index"]["lifecycle.name"] == f"{col.name}_policy"
        assert template["settings"]["index"]["lifecycle.rollover_alias"] == col.name

    def test_template_includes_mappings(self, mock_datastore, ilm_global):
        """Template includes the mappings (id field at minimum)."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        col._create_index_template(ilm_global)

        call_kwargs = mock_datastore.client.indices.put_index_template.call_args
        template = call_kwargs.kwargs["template"]

        assert "mappings" in template
        assert "id" in template["mappings"]["properties"]

    def test_schema_template_uses_canonical_builder(self, mock_datastore, ilm_global):
        """The production ILM path uploads the schema builder's tested payload."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index, schema_model=SchemaAction)

        col._create_index_template(ilm_global)

        template = mock_datastore.client.indices.put_index_template.call_args.kwargs["template"]
        assert template == new_schema.ilm_template_body(
            SchemaAction,
            shards=col.shards,
            replicas=col.replicas,
            policy_name=f"{col.name}_policy",
            rollover_alias=col.name,
        )


class TestEnsureCollectionILM:
    """Tests for _ensure_collection_ilm bootstrap logic."""

    def test_refresh_ilm_index_name_uses_latest_existing_index(self, mock_datastore):
        """Maintenance commands select the active ILM index when bootstrap is skipped."""
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        mock_datastore.client.indices.get.return_value = {
            f"{col.name}-000001": {},
            f"{col.name}-000002": {},
            f"{col.name}-000002__reindex": {},
        }

        col._refresh_ilm_index_name()

        assert col.index_name == f"{col.name}-000002"
        assert col.index_list_full == [f"{col.name}-000002", f"{col.name}-000001"]

    def test_reindex_uses_discovered_ilm_indexes_when_ilm_is_disabled(self, mock_datastore):
        """Reindex must migrate existing rollover indexes even if ILM is no longer configured."""
        col = _make_collection(mock_datastore)
        ilm_index_name = f"{col.name}-000001"

        mock_datastore.client.indices.get.side_effect = [
            {ilm_index_name: {}},
            {ilm_index_name: {"aliases": {}}},
        ]
        mock_datastore.client.indices.exists.side_effect = [False, False, True, False, False, True]

        with (
            patch.object(col, "_index_doc_count", side_effect=[1, 1]),
            patch.object(col, "_get_task_results", return_value={"failures": [], "version_conflicts": 0}),
            patch.object(col, "_safe_index_copy"),
        ):
            assert col.reindex() is True

        assert mock_datastore.client.reindex.call_args.kwargs["source"] == {"index": ilm_index_name}

    def test_reindex_settings_preserve_ilm_lifecycle(self, mock_datastore):
        """Reindex targets retain lifecycle settings from the physical source index."""
        col = _make_collection(mock_datastore)
        lifecycle = {"name": "howler-testcol_policy", "rollover_alias": col.name}

        settings = col._get_reindex_settings({"settings": {"index": {"lifecycle": lifecycle}}})

        assert settings["index"]["lifecycle"] == lifecycle

    def test_refresh_ilm_index_name_does_not_bootstrap_when_indices_are_missing(self, mock_datastore):
        """Maintenance probes tolerate missing ILM indexes without ensuring the collection."""
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        mock_datastore.client.indices.get.side_effect = elasticsearch.exceptions.NotFoundError(
            "404", "index not found", {"error": {"type": "index_not_found_exception"}}
        )

        with patch.object(col, "_ensure_collection") as mock_ensure:
            col._refresh_ilm_index_name()

        assert col.index_name == f"{col.name}_hot"
        mock_ensure.assert_not_called()

    def test_fresh_install_creates_initial_index(self, mock_datastore, ilm_global):
        """On a fresh install, creates {name}-000001 with alias and ILM settings."""
        ilm_index = ILMIndexConfig(warm="30d", cold="90d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        # No ILM indices exist, no legacy _hot index
        mock_datastore.client.indices.get.return_value = {}
        mock_datastore.client.indices.exists.return_value = False
        mock_datastore.client.indices.exists_alias.return_value = False

        with (
            patch.object(col, "_create_ilm_policy") as mock_policy,
            patch.object(col, "_create_index_template") as mock_template,
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

            mock_policy.assert_called_once()
            mock_template.assert_called_once()

            # Should create the initial index
            mock_datastore.client.indices.create.assert_called_once()
            create_kwargs = mock_datastore.client.indices.create.call_args.kwargs
            assert create_kwargs["index"] == f"{col.name}-000001"
            assert col.name in create_kwargs["aliases"]
            assert create_kwargs["aliases"][col.name]["is_write_index"] is True
            assert "lifecycle.name" in create_kwargs["settings"]["index"]

        # index_name should be updated
        assert col.index_name == f"{col.name}-000001"

    def test_existing_ilm_indices_skips_creation(self, mock_datastore, ilm_global):
        """When ILM indices already exist, no new index is created."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        mock_datastore.client.indices.get.return_value = {
            f"{col.name}-000001": {},
            f"{col.name}-000002": {},
        }
        mock_datastore.client.indices.exists_alias.return_value = True

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_create_index_template"),
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

            # Should not create or clone any index
            mock_datastore.client.indices.create.assert_not_called()
            mock_datastore.client.indices.clone.assert_not_called()

        # index_name should be updated to the latest ILM index
        assert col.index_name == f"{col.name}-000002"

    def test_existing_ilm_template_updates_only_after_reconciliation(self, mock_datastore, ilm_global):
        """A refused mapping check cannot update the composable template first."""
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        mock_datastore.client.indices.get.return_value = {f"{col.name}-000001": {}}
        mock_datastore.client.indices.exists_alias.return_value = False
        calls = []

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_check_fields", side_effect=lambda: calls.append("check")),
            patch.object(col, "_create_index_template", side_effect=lambda _config: calls.append("template")),
        ):
            col._ensure_collection_ilm()

        assert calls == ["check", "template"]

    def test_existing_ilm_indices_without_alias_creates_alias(self, mock_datastore, ilm_global):
        """When ILM indices exist but alias is missing, creates the alias."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        mock_datastore.client.indices.get.return_value = {
            f"{col.name}-000001": {},
            f"{col.name}-000002": {},
        }
        mock_datastore.client.indices.exists_alias.return_value = False

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_create_index_template"),
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

            # Should put alias on the latest index
            mock_datastore.client.indices.put_alias.assert_called_once()
            put_alias_kwargs = mock_datastore.client.indices.put_alias.call_args.kwargs
            assert put_alias_kwargs["index"] == f"{col.name}-000002"
            assert put_alias_kwargs["name"] == col.name
            assert put_alias_kwargs["is_write_index"] is True

        # index_name should be updated to the latest ILM index
        assert col.index_name == f"{col.name}-000002"

    def test_existing_ilm_indices_replace_legacy_hot_alias(self, mock_datastore, ilm_global):
        """An existing legacy write alias is moved to the latest ILM index."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)
        hot_index_name = col.index_name
        latest_index_name = f"{col.name}-000001"

        mock_datastore.client.indices.get.return_value = {latest_index_name: {}}
        mock_datastore.client.indices.exists_alias.return_value = True
        mock_datastore.client.indices.get_alias.return_value = {
            hot_index_name: {"aliases": {col.name: {"is_write_index": True}}}
        }

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_create_index_template"),
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

        alias_actions = mock_datastore.client.indices.update_aliases.call_args.kwargs["actions"]
        assert {"remove": {"index": hot_index_name, "alias": col.name}} in alias_actions
        assert {"add": {"index": latest_index_name, "alias": col.name, "is_write_index": True}} in alias_actions
        assert col.index_name == latest_index_name

    def test_existing_ilm_indices_remove_legacy_alias_after_reentry(self, mock_datastore, ilm_global):
        """Re-entering ensure does not remove the alias from the active ILM index."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)
        legacy_hot_index = f"{col.name}_hot"
        latest_index_name = f"{col.name}-000001"
        col.index_name = latest_index_name

        mock_datastore.client.indices.get.return_value = {latest_index_name: {}}
        mock_datastore.client.indices.exists_alias.return_value = True
        mock_datastore.client.indices.get_alias.return_value = {
            legacy_hot_index: {"aliases": {col.name: {}}},
            latest_index_name: {"aliases": {col.name: {"is_write_index": True}}},
        }

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_create_index_template"),
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

        alias_actions = mock_datastore.client.indices.update_aliases.call_args.kwargs["actions"]
        assert {"remove": {"index": legacy_hot_index, "alias": col.name}} in alias_actions
        assert {"remove": {"index": latest_index_name, "alias": col.name}} not in alias_actions

    def test_existing_ilm_indices_preserve_alias_metadata_when_updating_write_index(self, mock_datastore, ilm_global):
        """Write-index corrections retain alias filters and routing settings."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)
        old_index_name = f"{col.name}-000001"
        latest_index_name = f"{col.name}-000002"
        old_alias_data = {
            "filter": {"term": {"tenant": "alpha"}},
            "routing": "alpha",
            "is_write_index": True,
        }
        latest_alias_data = {
            "filter": {"term": {"tenant": "alpha"}},
            "search_routing": "alpha",
        }

        mock_datastore.client.indices.get.return_value = {
            old_index_name: {},
            latest_index_name: {},
        }
        mock_datastore.client.indices.exists_alias.return_value = True
        mock_datastore.client.indices.get_alias.return_value = {
            old_index_name: {"aliases": {col.name: old_alias_data}},
            latest_index_name: {"aliases": {col.name: latest_alias_data}},
        }

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_create_index_template"),
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

        alias_actions = mock_datastore.client.indices.update_aliases.call_args.kwargs["actions"]
        assert {
            "add": {
                "index": old_index_name,
                "alias": col.name,
                "filter": {"term": {"tenant": "alpha"}},
                "routing": "alpha",
                "is_write_index": False,
            }
        } in alias_actions
        assert {
            "add": {
                "index": latest_index_name,
                "alias": col.name,
                "filter": {"term": {"tenant": "alpha"}},
                "search_routing": "alpha",
                "is_write_index": True,
            }
        } in alias_actions

    def test_reindex_cleanup_does_not_restore_missing_collection_alias(self, mock_datastore):
        """Cleanup must not make an alias writable when the source did not own it."""
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        col.index_name = f"{col.name}-000001"
        reindex_index_name = f"{col.index_name}__reindex"

        mock_datastore.client.indices.exists.side_effect = [True, True]
        mock_datastore.client.indices.get.side_effect = [
            {col.index_name: {}},
            {col.index_name: {"aliases": {}}},
            {reindex_index_name: {"aliases": {}}},
        ]

        assert col.reindex_cleanup() is True
        mock_datastore.client.indices.update_aliases.assert_not_called()
        mock_datastore.client.indices.delete.assert_called_once_with(index=reindex_index_name)

    def test_legacy_hot_index_migration(self, mock_datastore, ilm_global):
        """Legacy _hot index gets cloned to -000001 and alias is swapped."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)
        hot_index_name = col.index_name  # e.g. howler-testcol_hot

        # No ILM indices, but legacy _hot exists
        mock_datastore.client.indices.get.return_value = {}
        mock_datastore.client.indices.exists.return_value = True  # _hot exists
        mock_datastore.client.indices.exists_alias.return_value = True  # alias on _hot

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_create_index_template"),
            patch.object(col, "_safe_index_copy") as mock_copy,
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

            # Should block writes on _hot
            mock_datastore.client.indices.put_settings.assert_any_call(
                index=hot_index_name,
                settings={"index.blocks.write": True},
            )

            # Should clone _hot to -000001
            mock_copy.assert_called_once()
            clone_args = mock_copy.call_args
            assert clone_args.args[1] == hot_index_name
            assert clone_args.args[2] == f"{col.name}-000001"

            # Should update aliases
            mock_datastore.client.indices.update_aliases.assert_called_once()
            alias_actions = mock_datastore.client.indices.update_aliases.call_args.kwargs["actions"]
            # Should have an add action for the new index
            add_action = [a for a in alias_actions if "add" in a][0]
            assert add_action["add"]["index"] == f"{col.name}-000001"
            assert add_action["add"]["is_write_index"] is True

        assert col.index_name == f"{col.name}-000001"


class TestEnsureCollectionILMDispatch:
    """Tests that _ensure_collection dispatches to ILM path when ilm_config is set."""

    def test_dispatches_to_ilm_when_configured(self, mock_datastore):
        """When ilm_config is set, _ensure_collection calls _ensure_collection_ilm."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)

        with patch.object(col, "_ensure_collection_ilm") as mock_ilm, patch.object(col, "_check_fields"):
            col._ensure_collection()
            mock_ilm.assert_called_once()

    def test_does_not_dispatch_without_ilm(self, mock_datastore):
        """When ilm_config is None, _ensure_collection uses legacy path."""
        col = _make_collection(mock_datastore, ilm_config=None)

        # Mock away the ES calls for the legacy path
        mock_datastore.client.indices.exists.return_value = True
        mock_datastore.client.indices.exists_alias.return_value = True

        with patch.object(col, "_ensure_collection_ilm") as mock_ilm, patch.object(col, "_check_fields"):
            col._ensure_collection()
            mock_ilm.assert_not_called()

    def test_legacy_creation_includes_alias(self, mock_datastore):
        """Legacy collection creation creates its hot index and alias atomically."""
        col = _make_collection(mock_datastore, ilm_config=None)
        mock_datastore.client.indices.exists.return_value = False

        with patch.object(col, "_check_fields"):
            col._ensure_collection()

        create_kwargs = mock_datastore.client.indices.create.call_args.kwargs
        assert create_kwargs["index"] == col.index_name
        assert create_kwargs["aliases"] == {col.name: {}}
        mock_datastore.client.indices.put_alias.assert_not_called()


class TestAddFieldsILMTemplateSync:
    """Tests that _add_fields updates the index template when ILM is active."""

    def test_add_fields_updates_template_when_ilm(self, mock_datastore, ilm_global):
        """When ILM is configured, _add_fields re-creates the index template."""
        ilm_index = ILMIndexConfig(warm="30d")
        col = _make_collection(mock_datastore, ilm_config=ilm_index)
        col._index_list = []

        # Mock the fields that need to be added
        mock_field = MagicMock()
        mock_field.name = None

        # Make build_mapping return valid properties
        with (
            patch("howler.datastore.collection.build_mapping", return_value=({"new_field": {"type": "keyword"}}, [])),
            patch.object(col, "_create_index_template") as mock_template,
            patch.object(
                ESCollection, "index_list_full", new_callable=lambda: property(lambda self: [self.index_name])
            ),
        ):
            col._add_fields({"test_field": mock_field})

            # Should have updated the template
            mock_template.assert_called_once()

    def test_add_fields_does_not_update_template_without_ilm(self, mock_datastore):
        """Without ILM, _add_fields does not touch any index template."""
        col = _make_collection(mock_datastore, ilm_config=None)
        col._index_list = []

        mock_field = MagicMock()
        mock_field.name = None

        with (
            patch("howler.datastore.collection.build_mapping", return_value=({"new_field": {"type": "keyword"}}, [])),
            patch.object(
                ESCollection, "index_list_full", new_callable=lambda: property(lambda self: [self.index_name])
            ),
        ):
            # Ensure no legacy template exists
            mock_datastore.client.indices.exists_template.return_value = False

            col._add_fields({"test_field": mock_field})

            mock_datastore.client.indices.put_index_template.assert_not_called()
