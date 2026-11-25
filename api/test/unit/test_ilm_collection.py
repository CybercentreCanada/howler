"""Unit tests for ILM methods on ESCollection.

These tests mock the Elasticsearch client to verify the correct ILM policy,
index template, and _ensure_collection_ilm logic without requiring a running ES.
"""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import elasticsearch
import pytest
from elastic_transport import ApiResponseMeta, ObjectApiResponse

from howler.common.exceptions import HowlerRuntimeError, HowlerValueError
from howler.config_models import ILMConfig, ILMIndexConfig
from howler.datastore.collection import ESCollection
from howler.datastore.exceptions import DataStoreException, HowlerScanError, SearchException, VersionConflictException
from howler.datastore.ilm_contract import shadowed_dynamic_templates
from howler.models import (
    HowlerESModel,
    HowlerModelValidationError,
    enum,
    keyword,
    mapping,
    register_model,
    schema,
    validated_keyword,
)
from howler.models.action import Action
from howler.models.analytic import Analytic
from howler.models.case import Case
from howler.models.event import Event
from howler.models.hit import Hit
from howler.models.user import User


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
    ds.client.indices.get_alias.return_value = {}
    ds.client.indices.get.return_value = {}
    ds.client.indices.exists_template.return_value = False
    ds.client.field_caps.return_value = {"fields": {}}
    ds.client.cluster.health.return_value = {"timed_out": False}
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


def _make_collection(mock_datastore, ilm_config=None, model_class=None):
    """Helper to create an ESCollection with the given ILM config."""
    mock_datastore._models = {"testcol": None}
    col = ESCollection(
        mock_datastore,
        "testcol",
        model_class=model_class,
        ilm_config=ilm_config,
    )
    return col


@register_model(index=True, store=True, id_field="key")
class ReconcileDoc(HowlerESModel):
    """Small model used to exercise field discovery and reconciliation."""

    key: keyword()
    name: keyword(description="A plain, statically typed field.")
    tags: mapping(keyword(), default={}, description="A dynamic-key mapping field.")


class TestAsyncTaskOperations:
    """Tests for asynchronous Elasticsearch query task handling."""

    @staticmethod
    def _query_result(updated=1, version_conflicts=0, **kwargs):
        return {
            "timed_out": False,
            "failures": [],
            "updated": updated,
            "version_conflicts": version_conflicts,
            **kwargs,
        }

    def test_get_task_results_polls_until_completed(self, mock_datastore, monkeypatch):
        col = _make_collection(mock_datastore)
        mock_datastore.client.tasks.get.side_effect = [
            {"completed": False},
            {"completed": True, "response": self._query_result()},
        ]
        monkeypatch.setattr("howler.datastore.collection.time.sleep", lambda _: None)

        assert col._get_task_results({"task": "node:1"}) == self._query_result()

        assert mock_datastore.client.tasks.get.call_count == 2
        assert mock_datastore.client.tasks.get.call_args.kwargs == {
            "task_id": "node:1",
            "wait_for_completion": False,
        }

    def test_get_task_results_accepts_elasticsearch_response_wrapper(self, mock_datastore):
        col = _make_collection(mock_datastore)
        meta = ApiResponseMeta(status=200, http_version="1.1", headers={}, duration=0.0, node=None)
        mock_datastore.client.tasks.get.return_value = ObjectApiResponse(
            meta=meta,
            body={"completed": True, "response": self._query_result()},
        )

        assert col._get_task_results({"task": "node:1"}) == self._query_result()

    def test_get_task_results_rejects_task_error(self, mock_datastore):
        col = _make_collection(mock_datastore)
        mock_datastore.client.tasks.get.return_value = {"completed": True, "error": {"reason": "failed"}}

        with pytest.raises(DataStoreException, match="task node:1 failed"):
            col._get_task_results({"task": "node:1"})

    @pytest.mark.parametrize(
        "response",
        [
            {"completed": True, "response": {"timed_out": True, "failures": []}},
            {"completed": True, "response": {"timed_out": False, "failures": [{"reason": "failed"}]}},
        ],
    )
    def test_get_task_results_rejects_strict_query_failures(self, mock_datastore, response):
        col = _make_collection(mock_datastore)
        mock_datastore.client.tasks.get.return_value = response

        with pytest.raises(DataStoreException):
            col._get_task_results({"task": "node:1"})

    def test_get_task_results_can_preserve_reindex_failures(self, mock_datastore):
        col = _make_collection(mock_datastore)
        response = {"completed": True, "response": {"failures": [{"reason": "bad document"}]}}
        mock_datastore.client.tasks.get.return_value = response

        assert col._get_task_results({"task": "node:1"}, strict=False) == response["response"]

    def test_get_task_results_times_out(self, mock_datastore, monkeypatch):
        col = _make_collection(mock_datastore)
        col.TASK_POLL_TIMEOUT = 1
        mock_datastore.client.tasks.get.return_value = {"completed": False}
        monotonic_values = iter([0, 0, 1])
        monkeypatch.setattr("howler.datastore.collection.time.monotonic", lambda: next(monotonic_values))
        monkeypatch.setattr("howler.datastore.collection.time.sleep", lambda _: None)

        with pytest.raises(HowlerRuntimeError, match="Timed out waiting"):
            col._get_task_results({"task": "node:1"})

    @pytest.mark.parametrize(
        "task,response",
        [
            ({}, None),
            ({"task": "node:1"}, {"completed": True}),
            ({"task": "node:1"}, {"completed": None, "response": {}}),
            ({"task": "node:1"}, {"completed": True, "response": []}),
        ],
    )
    def test_get_task_results_rejects_malformed_responses(self, mock_datastore, task, response):
        col = _make_collection(mock_datastore)
        mock_datastore.client.tasks.get.return_value = response

        with pytest.raises(DataStoreException):
            col._get_task_results(task)

    @pytest.mark.parametrize(
        ("refresh", "expected"),
        [(None, None), (True, True), (False, False), ("true", True), ("false", False), ("wait_for", True)],
    )
    def test_update_async_normalizes_refresh(self, mock_datastore, refresh, expected):
        col = _make_collection(mock_datastore)
        monkeypatch_result = self._query_result()
        with patch.object(col, "_get_task_results", return_value=monkeypatch_result):
            col._update_async("test-index", {"source": ""}, {"match_all": {}}, refresh=refresh)

        assert mock_datastore.client.update_by_query.call_args.kwargs["refresh"] is expected

    def test_delete_async_normalizes_wait_for_refresh(self, mock_datastore):
        col = _make_collection(mock_datastore)
        result = {"timed_out": False, "failures": [], "deleted": 1, "version_conflicts": 0}
        with patch.object(col, "_get_task_results", return_value=result):
            col._delete_async("test-index", {"match_all": {}}, refresh="wait_for")

        assert mock_datastore.client.delete_by_query.call_args.kwargs["refresh"] is True

    def test_delete_async_rejects_partial_results(self, mock_datastore):
        col = _make_collection(mock_datastore)
        result = {"timed_out": False, "failures": [{"reason": "failed"}], "deleted": 1, "version_conflicts": 0}
        with patch.object(col, "_get_task_results", return_value=result):
            with pytest.raises(DataStoreException):
                col._delete_async("test-index", {"match_all": {}})

    @pytest.mark.parametrize(
        "result",
        [
            {"timed_out": True, "failures": [], "updated": 1, "version_conflicts": 0},
            {"timed_out": False, "failures": [{"reason": "failed"}], "updated": 1, "version_conflicts": 0},
        ],
    )
    def test_update_async_rejects_partial_results(self, mock_datastore, result):
        col = _make_collection(mock_datastore)
        with patch.object(col, "_get_task_results", return_value=result):
            with pytest.raises(DataStoreException):
                col._update_async("test-index", {"source": ""}, {"match_all": {}})

    def test_update_async_preserves_counts_across_conflict_retry(self, mock_datastore):
        col = _make_collection(mock_datastore)
        results = [self._query_result(updated=2, version_conflicts=1), self._query_result(updated=3)]
        with patch.object(col, "_get_task_results", side_effect=results):
            result = col._update_async("test-index", {"source": ""}, {"match_all": {}})

        assert result["updated"] == 5
        assert mock_datastore.client.update_by_query.call_count == 2

    def test_update_async_bounds_conflict_retries(self, mock_datastore):
        col = _make_collection(mock_datastore)
        col.MAX_VERSION_CONFLICT_ATTEMPTS = 2
        with patch.object(col, "_get_task_results", return_value=self._query_result(version_conflicts=1)):
            with pytest.raises(DataStoreException, match="2 version-conflict"):
                col._update_async("test-index", {"source": ""}, {"match_all": {}})

        assert mock_datastore.client.update_by_query.call_count == 2


def _action_data() -> dict:
    return {
        "action_id": "action-1",
        "owner": "user-1",
        "admins": [],
        "members": [],
        "name": "Test Action",
        "query": "id:*",
        "triggers": ["create"],
        "operations": [],
    }


class TestModelPersistence:
    """Focused registered-model persistence and projection behavior."""

    def test_normalize_full_document_strips_stored_helpers_and_sets_metadata(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Action)

        action = col.normalize(
            {
                **_action_data(),
                "id": "stored-id",
                "__access_lvl__": 100,
            },
            doc_id="document-id",
            index="howler-action_hot",
        )

        assert isinstance(action, Action)
        assert action.meta.id == "document-id"
        assert action.meta.index == "howler-action_hot"
        assert action.as_primitives() == _action_data()

    def test_projected_search_object_validates_only_selected_fields(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Action)

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
        col = _make_collection(mock_datastore, model_class=Action)

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

    def test_save_accepts_native_model_instance(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Action)
        action = Action.model_validate(_action_data())

        assert col.save("document-id", action) is True
        assert json.loads(mock_datastore.client.index.call_args.kwargs["document"]) == {
            **_action_data(),
            "id": "document-id",
        }

    def test_projected_model_cannot_be_saved_as_full_replacement(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Action)
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
        col = _make_collection(mock_datastore, model_class=Action)
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
        assert isinstance(result["document-id"], Action)
        assert result["document-id"].meta.id == "document-id"

    def test_get_preserves_elasticsearch_metadata(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Action)
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
        action_col = _make_collection(mock_datastore, model_class=Action)
        assert action_col._validate_operations([("SET", "name", 123)]) == [("SET", "name", "123")]
        assert action_col._validate_operations([("APPEND", "triggers", "create")]) == [("APPEND", "triggers", "create")]
        with pytest.raises(DataStoreException, match="Invalid field"):
            action_col._validate_operations([("SET", "missing", "value")])

        event_col = _make_collection(mock_datastore, model_class=Event)
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

        hit_col = _make_collection(mock_datastore, model_class=Hit)
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
        col = _make_collection(mock_datastore, model_class=Analytic)

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
        col = _make_collection(mock_datastore, model_class=Event)

        with pytest.raises(DataStoreException, match="derived from classification"):
            col._validate_operations(
                [
                    ("SET", "classification", "UNRESTRICTED"),
                    ("SET", field, [] if field != "__access_lvl__" else 0),
                ]
            )

    def test_classification_set_updates_hidden_fields_for_both_atomic_paths(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Event)
        mock_datastore.client.update.return_value = {
            "result": "updated",
            "_index": col.index_name,
            "_seq_no": 1,
            "_primary_term": 1,
        }
        col._update_async = MagicMock(return_value={"updated": 2})

        assert col.update("event-1", [("SET", "classification", "UNRESTRICTED")]) == (True, "1---1")
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
        col = _make_collection(mock_datastore, model_class=Action)
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
        col = _make_collection(mock_datastore, model_class=Action)
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
        col = _make_collection(mock_datastore, model_class=Action)
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
        col = _make_collection(mock_datastore, model_class=Action)
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

        result = col._search(
            [
                ("query", "name:test"),
                ("filters", ["owner:user-1"]),
                ("field_list", ["name"]),
                ("start", 2),
                ("rows", 3),
                ("sort", [{"name": "desc"}]),
                ("facet_active", True),
                ("facet_fields", ["owner"]),
                ("facet_mincount", 2),
            ]
        )

        assert result["hits"]["hits"] == []
        assert mock_datastore.client.search.call_args.kwargs == {
            "index": col.name,
            "query": {
                "bool": {
                    "must": {"query_string": {"query": "name:test"}},
                    "filter": [{"query_string": {"query": "owner:user-1"}}],
                }
            },
            "from_": 2,
            "size": 3,
            "sort": [{"name": "desc"}],
            "_source": ["name"],
            "aggregations": {
                "owner": {
                    "terms": {
                        "field": "owner",
                        "min_doc_count": 2,
                        "size": 3,
                    }
                }
            },
        }

    def test_dictionary_projection_preserves_list_item_shape(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Case)

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
        col = _make_collection(mock_datastore, model_class=User)

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
        col = _make_collection(mock_datastore, model_class=Hit)

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
        timeout = elasticsearch.ConnectionTimeout("Timed out waiting for completion")
        mock_datastore.client.tasks.get.__name__ = "tasks.get"
        mock_datastore.client.tasks.get.side_effect = [
            timeout,
            {
                "completed": True,
                "response": {"updated": 1, "version_conflicts": 0, "timed_out": False, "failures": []},
            },
        ]

        assert col._get_task_results({"task": "task-id"}) == {
            "updated": 1,
            "version_conflicts": 0,
            "timed_out": False,
            "failures": [],
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

    def test_exists_applies_access_control_filter(self, mock_datastore):
        """ACL-filtered existence checks only match documents visible to the user."""
        col = _make_collection(mock_datastore)
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 0, "relation": "eq"}}}

        assert col.exists("document-id", access_control="__access_lvl__:[0 TO 100]") is False

        mock_datastore.client.search.assert_called_once_with(
            index=col.name,
            query={
                "bool": {
                    "must": {"ids": {"values": ["document-id"]}},
                    "filter": [{"query_string": {"query": "__access_lvl__:[0 TO 100]"}}],
                }
            },
            size=0,
            track_total_hits=True,
        )


class TestILMAliasDocumentOperations:
    """Alias-wide logical ID operations target concrete rollover indices."""

    def test_multiget_locates_ids_then_groups_concrete_index_requests(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            model_class=Action,
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
            size=col.MAX_SEARCH_ROWS,
            _source=False,
            stored_fields=["_routing"],
            allow_partial_search_results=False,
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
            model_class=Action,
        )
        old_index = f"{col.name}-000001"
        new_index = f"{col.name}-000002"
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 3, "relation": "eq"},
                "hits": [
                    {"_id": "old-only", "_index": old_index, "fields": {"_routing": ["legacy"]}},
                    {"_id": "duplicate", "_index": new_index, "_routing": "blue"},
                    {"_id": "duplicate", "_index": old_index, "_routing": "legacy"},
                ],
            }
        }

        def mget(*, ids, index, routing):
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
            call(ids=["old-only"], index=old_index, routing="legacy"),
            call(ids=["duplicate"], index=new_index, routing="blue"),
        ]

    def test_delete_removes_every_matching_concrete_rollover_document(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        old_index = f"{col.name}-000001"
        new_index = f"{col.name}-000002"
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 2, "relation": "eq"},
                "hits": [
                    {"_id": "document-id", "_index": new_index, "_routing": "blue"},
                    {"_id": "document-id", "_index": old_index, "_routing": "legacy"},
                ],
            }
        }
        mock_datastore.client.delete.side_effect = [
            {"result": "deleted"},
            {"result": "deleted"},
        ]

        result = col.delete("document-id", refresh="wait_for")
        assert result is True

        assert mock_datastore.client.delete.call_args_list == [
            call(id="document-id", index=new_index, routing="blue", refresh="wait_for"),
            call(id="document-id", index=old_index, routing="legacy", refresh="wait_for"),
        ]

    def test_delete_missing_ilm_document_returns_false_without_alias_delete(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

        result = col.delete("missing")
        assert result is False
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
            size=col.MAX_SEARCH_ROWS,
            _source=False,
            stored_fields=["_routing"],
            allow_partial_search_results=False,
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

    def test_versioned_delete_uses_optimistic_concurrency(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        concrete_index = f"{col.name}-000001"
        mock_datastore.client.delete.return_value = {"result": "not_found"}

        deleted = col.delete("document-id", version=f"{concrete_index}---5---2")
        assert deleted is False

        delete_kwargs = mock_datastore.client.delete.call_args.kwargs
        assert delete_kwargs["index"] == concrete_index
        assert delete_kwargs["if_seq_no"] == "5"
        assert delete_kwargs["if_primary_term"] == "2"

    def test_unversioned_update_returns_false_for_missing_ilm_document(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            model_class=Action,
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

    def test_read_update_save_and_atomic_delete_remain_on_the_read_shard(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        older, newer = f"{col.name}-000001", f"{col.name}-000002"
        routing = "blue---é"
        client = mock_datastore.client
        client.search.return_value = {
            "hits": {
                "hits": [
                    {"_id": "dup", "_index": older, "_routing": "legacy"},
                    {"_id": "dup", "_index": newer, "_routing": routing},
                ]
            }
        }
        client.get.return_value = {"_index": newer, "_seq_no": 4, "_primary_term": 1, "_source": {"value": "new"}}
        client.update.return_value = {"_index": newer, "_seq_no": 5, "_primary_term": 1, "result": "updated"}
        client.delete.return_value = {"result": "deleted"}

        data, version = col.get_if_exists("dup", as_obj=False, version=True)
        assert data == {"value": "new"}
        client.get.assert_called_once_with(index=newer, id="dup", routing=routing)
        assert col.get_version_write_target(version) == (newer, "4", "1")
        ok, updated_version = col.update("dup", [(col.UPDATE_SET, "value", "changed")], version=version)
        assert ok and col.save("dup", {"value": "changed"}, version=updated_version)
        deleted = col.delete("dup", version=updated_version)
        assert deleted
        for method, seq_no in ((client.update, "4"), (client.index, "5"), (client.delete, "5")):
            params = method.call_args.kwargs
            assert (params["index"], params["routing"], params["if_seq_no"], params["if_primary_term"]) == (
                newer,
                routing,
                seq_no,
                "1",
            )
        with pytest.raises(VersionConflictException, match="legacy version"):
            col.delete("dup", version="5---1")
        assert client.delete.call_count == 1


class TestILMBulkRouting:
    """Bulk writes remain alias-safe across automatic rollover."""

    def test_new_documents_use_write_alias_after_rollover_without_restart(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            model_class=Action,
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
            model_class=Action,
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

    def test_model_index_hint_resolves_actual_routing_in_one_batch(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            model_class=Action,
        )
        old_index = f"{col.name}-000001"
        mock_datastore.client.indices.get.return_value = {
            old_index: {"aliases": {col.name: {}}},
            f"{col.name}-000002": {"aliases": {col.name: {}}},
            f"{col.name}-000003__reindex": {},
        }
        action = Action.model_validate({"meta": {"index": old_index}, **_action_data()})
        mock_datastore.client.search.return_value = {
            "hits": {
                "hits": [
                    {"_id": "action-1", "_index": old_index, "_routing": "red"},
                    {"_id": "action-2", "_index": old_index, "_routing": "blue"},
                ]
            }
        }

        plan = col.get_bulk_plan()
        plan.add_index_operation("action-1", action)
        plan.add_update_operation("action-2", action, fields=["name"])

        plan.get_plan_data()
        assert json.loads(plan.operations[0][0])["index"] == {"_index": old_index, "_id": "action-1", "routing": "red"}
        assert json.loads(plan.operations[1][0])["update"] == {
            "_index": old_index,
            "_id": "action-2",
            "routing": "blue",
        }
        assert mock_datastore.client.search.call_count == 1
        assert mock_datastore.client.search.call_args.kwargs["index"] == col.name
        mock_datastore.client.indices.get.assert_called_once_with(
            index=f"{col.name}-*",
            expand_wildcards="all",
            ignore_unavailable=True,
            filter_path="*.settings.index.uuid,*.aliases",
        )

    def test_invalid_model_metadata_is_rejected(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            model_class=Action,
        )
        old_index = f"{col.name}-000001"
        mock_datastore.client.indices.get.return_value = {old_index: {}}
        mock_datastore.client.search.return_value = {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [{"_id": "action-1", "_index": old_index}],
            }
        }
        action = Action.model_validate({"meta": {"index": "unrelated-secret-index"}, **_action_data()})

        plan = col.get_bulk_plan()
        with pytest.raises(DataStoreException, match="not a physical member"):
            plan.add_index_operation("action-1", action)
        assert plan.empty
        mock_datastore.client.search.assert_not_called()

    @pytest.mark.parametrize("operation", ["insert", "index", "upsert", "update", "delete"])
    def test_detached_generation_rejects_explicit_bulk_targets(self, mock_datastore, operation):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        detached, member = f"{col.name}-000001", f"{col.name}-000002"
        mock_datastore.client.indices.get.return_value = {
            detached: {"aliases": {"another_alias": {}}},
            member: {"aliases": {col.name: {}}},
        }
        assert col._get_ilm_index_names() == [detached, member]
        assert col._ilm_index_aliases() == {member: {}}
        plan = col.get_bulk_plan()
        args = ("id",) if operation == "delete" else ("id", {"value": "new"})
        with pytest.raises(DataStoreException, match="not a physical member"):
            getattr(plan, f"add_{operation}_operation")(*args, index=detached)
        assert plan.empty
        mock_datastore.client.search.assert_not_called()
        mock_datastore.client.bulk.assert_not_called()

    @pytest.mark.parametrize("operation", ["index", "upsert", "update"])
    def test_detached_model_hint_is_rejected_before_alias_fallback(self, mock_datastore, operation):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(), model_class=Action)
        detached = f"{col.name}-000001"
        mock_datastore.client.indices.get.return_value = {detached: {"aliases": {}}}
        mock_datastore.client.search.return_value = {"hits": {"hits": []}}
        action = Action.model_validate({"meta": {"index": detached}, **_action_data()})
        plan = col.get_bulk_plan()
        with pytest.raises(DataStoreException, match="not a physical member"):
            getattr(plan, f"add_{operation}_operation")("action-1", action)
        assert plan.empty
        mock_datastore.client.search.assert_not_called()
        mock_datastore.client.bulk.assert_not_called()

    def test_implicit_alias_member_and_alias_target_remain_valid(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        member = f"{col.name}-000001"
        mock_datastore.client.indices.get.return_value = {member: {"aliases": {col.name: {}}}}
        mock_datastore.client.search.return_value = {"hits": {"hits": []}}
        plan = col.get_bulk_plan()
        plan.add_insert_operation("insert", {"value": 1}, index=member)
        plan.add_upsert_operation("upsert", {"value": 2}, index=member)
        plan.add_update_operation("alias", {"value": 3}, index=col.name)
        lines = list(map(json.loads, plan.get_plan_data().splitlines()))
        assert lines[0] == {"create": {"_id": "insert", "_index": member}}
        assert lines[2] == {"update": {"_id": "upsert", "_index": member}}
        assert lines[4] == {"update": {"_id": "alias", "_index": col.name}}

    def test_new_upsert_uses_write_alias(self, mock_datastore):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            model_class=Action,
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
            model_class=Action,
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
            size=col.MAX_SEARCH_ROWS,
            _source=False,
            stored_fields=["_routing"],
            allow_partial_search_results=False,
            track_total_hits=True,
        )
        assert json.loads(plan.operations[0][0])["index"]["_index"] == old_index
        assert json.loads(plan.operations[1][0])["update"]["_index"] == new_index

    def test_paged_duplicate_matches_route_update_to_newest_and_delete_all(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        col.MAX_SEARCH_ROWS = 2
        old, middle, new = (f"{col.name}-{n:06}" for n in range(1, 4))
        rows = [
            {"_id": "dup", "_index": index, "_routing": route}
            for index, route in ((middle, "middle"), (old, "legacy"), (new, "blue"))
        ]
        shards = {"successful": 1, "total": 1}
        mock_datastore.client.search.side_effect = [
            {"hits": {"total": {"value": 3, "relation": "eq"}, "hits": rows[:2]}},
            {"_scroll_id": "first", "hits": {"hits": rows[:2]}, "_shards": shards},
        ]
        mock_datastore.client.scroll.side_effect = [
            {"_scroll_id": "second", "hits": {"hits": rows[2:]}, "_shards": shards},
            {"_scroll_id": "last", "hits": {"hits": []}, "_shards": shards},
        ]
        plan = col.get_bulk_plan()
        plan.add_update_operation("dup", {"name": "updated"})
        plan.add_delete_operation("dup")

        batches = [list(map(json.loads, batch.splitlines())) for batch in plan.get_plan_batches(2)]

        assert batches == [
            [
                {"update": {"_id": "dup", "_index": new, "routing": "blue"}},
                {"doc": {"name": "updated"}},
                {"delete": {"_id": "dup", "_index": new, "routing": "blue"}},
            ],
            [
                {"delete": {"_id": "dup", "_index": middle, "routing": "middle"}},
                {"delete": {"_id": "dup", "_index": old, "routing": "legacy"}},
            ],
        ]
        assert all(request.kwargs["size"] == 2 for request in mock_datastore.client.search.call_args_list)
        assert all(
            request.kwargs["stored_fields"] == ["_routing"] for request in mock_datastore.client.search.call_args_list
        )
        mock_datastore.client.clear_scroll.assert_called_once_with(scroll_id=["last"])

    def test_multiple_routes_in_newest_index_abort_before_read_or_bulk_write(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        index = f"{col.name}-000001"
        client = mock_datastore.client
        client.search.return_value = {
            "hits": {"hits": [{"_id": "dup", "_index": index, "_routing": route} for route in ("red", "blue")]}
        }
        with pytest.raises(DataStoreException, match="multiple routes"):
            col.get_if_exists("dup")
        client.get.assert_not_called()
        plan = col.get_bulk_plan()
        plan.add_insert_operation("other", {})
        plan.add_update_operation("dup", {"value": "wrong"})
        with pytest.raises(DataStoreException, match="multiple routes"):
            col.bulk(plan)
        client.bulk.assert_not_called()

    def test_delete_detects_ambiguous_historical_routes_before_deleting_newest(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        older, newer = f"{col.name}-000001", f"{col.name}-000002"
        client = mock_datastore.client
        client.search.return_value = {
            "hits": {
                "hits": [
                    {"_id": "dup", "_index": newer},
                    {"_id": "dup", "_index": older, "_routing": "red"},
                    {"_id": "dup", "_index": older, "_routing": "blue"},
                ]
            }
        }
        with pytest.raises(DataStoreException, match="multiple routes"):
            col.delete("dup")
        plan = col.get_bulk_plan()
        plan.add_delete_operation("dup")
        with pytest.raises(DataStoreException, match="multiple routes"):
            col.bulk(plan)
        client.delete.assert_not_called()
        client.bulk.assert_not_called()

    def test_no_visible_hit_on_scoped_alias_cannot_overwrite_or_delete_hidden_id(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        index = f"{col.name}-000001"
        client = mock_datastore.client
        client.indices.get.return_value = {
            index: {
                "aliases": {
                    col.name: {
                        "filter": {"term": {"tenant": "alpha"}},
                        "index_routing": "legacy",
                    }
                }
            }
        }
        client.search.return_value = {"hits": {"hits": []}}
        plan = col.get_bulk_plan()
        plan.add_insert_operation("insert", {"tenant": "alpha"}, index=index)
        plan.add_upsert_operation("upsert", {"tenant": "alpha"}, index=index)
        lines = list(map(json.loads, plan.get_plan_data().splitlines()))
        for record_id, header, body in (("insert", *lines[:2]), ("upsert", *lines[2:])):
            assert header == {"create": {"_id": record_id, "_index": index, "routing": "legacy"}}
            assert body == {"id": record_id, "tenant": "alpha"}

        plan.add_delete_operation("hidden", index=index)
        with pytest.raises(DataStoreException, match="No visible location"):
            col.bulk(plan)
        client.bulk.assert_not_called()

    def test_legacy_bulk_uses_alias_routing_even_with_hot_index_hint(self, mock_datastore):
        col = _make_collection(mock_datastore)
        plan = col.get_bulk_plan()
        plan.add_insert_operation("new", {"value": 1})
        plan.add_update_operation("old", {"value": 2}, index=col.index_name)
        plan.add_delete_operation("older")
        assert [json.loads(row[0]) for row in plan.operations] == [
            {action: {"_id": key, "_index": col.name}}
            for action, key in (("create", "new"), ("update", "old"), ("delete", "older"))
        ]

    def test_incomplete_duplicate_page_aborts_bulk_before_writes(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        col.MAX_SEARCH_ROWS = 1
        row = {"_id": "dup", "_index": f"{col.name}-000001"}
        mock_datastore.client.search.side_effect = [
            {"hits": {"total": {"value": 2, "relation": "eq"}, "hits": [row]}},
            {"_scroll_id": "first", "hits": {"hits": [row]}, "_shards": {"total": 1, "successful": 1}},
        ]
        mock_datastore.client.scroll.return_value = {
            "_scroll_id": "failed",
            "timed_out": True,
            "hits": {"hits": []},
            "_shards": {"total": 1, "successful": 1},
        }
        plan = col.get_bulk_plan()
        plan.add_delete_operation("dup")
        with pytest.raises(HowlerScanError):
            col.bulk(plan)
        mock_datastore.client.bulk.assert_not_called()
        mock_datastore.client.clear_scroll.assert_called_once_with(scroll_id=["failed"])

    @pytest.mark.parametrize(("operation", "action"), [("update", "update"), ("delete", "delete")])
    def test_missing_update_or_delete_is_not_silently_dropped(self, mock_datastore, operation, action):
        col = _make_collection(
            mock_datastore,
            ilm_config=ILMIndexConfig(warm="30d"),
            model_class=Action,
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
            model_class=Action,
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
        col = _make_collection(mock_datastore, ilm_config=ilm_index, model_class=Action)

        col._create_index_template(ilm_global)

        template = mock_datastore.client.indices.put_index_template.call_args.kwargs["template"]
        assert template == schema.ilm_template_body(
            Action,
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
        mock_datastore.client.cluster.health.assert_called_once_with(
            index=f"{col.name}-000001", timeout="5s", wait_for_status="yellow"
        )

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
            patch.object(col, "_check_fields", side_effect=lambda indexes: calls.append("check")),
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

            mock_datastore.client.indices.update_aliases.assert_called_once_with(
                actions=[
                    {"add": {"index": f"{col.name}-000001", "alias": col.name, "is_write_index": False}},
                    {"add": {"index": f"{col.name}-000002", "alias": col.name, "is_write_index": True}},
                ]
            )

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
        metadata = {"filter": {"term": {"tenant": "alpha"}}, "index_routing": "alpha"}
        mock_datastore.client.indices.get_alias.return_value = {hot_index_name: {"aliases": {col.name: metadata}}}

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
            assert add_action["add"] == {
                "index": f"{col.name}-000001",
                "alias": col.name,
                **metadata,
                "is_write_index": True,
            }
            assert {"remove": {"index": hot_index_name, "alias": col.name}} in alias_actions

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

    def test_legacy_creation_waits_for_shards_before_checking_fields(self, mock_datastore):
        """field_caps fails on RECOVERING shards, so creation waits for yellow before schema checks."""
        col = _make_collection(mock_datastore, ilm_config=None)
        mock_datastore.client.indices.exists.return_value = False
        order = MagicMock()
        mock_datastore.client.indices.create.side_effect = lambda **_: order.create()
        order.health.return_value = {"timed_out": False}
        mock_datastore.client.cluster.health.side_effect = order.health

        with patch.object(col, "_check_fields", side_effect=lambda: order.check_fields()):
            col._ensure_collection()

        assert [name for name, *_ in order.mock_calls] == ["create", "health", "check_fields"]
        assert order.health.call_args.kwargs == {"index": col.index_name, "timeout": "5s", "wait_for_status": "yellow"}

    def test_existing_legacy_collection_does_not_wait_for_status(self, mock_datastore):
        """Existing collections keep their startup path unchanged."""
        col = _make_collection(mock_datastore, ilm_config=None)
        mock_datastore.client.indices.exists.return_value = True

        with patch.object(col, "_check_fields"):
            col._ensure_collection()

        mock_datastore.client.cluster.health.assert_not_called()


KEYWORD_MAPPING = {"type": "keyword", "ignore_above": 8191}


class TestCollectionFieldDiscovery:
    def test_schema_less_collection_keeps_legacy_field_shape(self, mock_datastore):
        col = _make_collection(mock_datastore)
        mock_datastore.client.indices.get.return_value = {
            "howler-testcol_hot": {
                "mappings": {
                    "properties": {
                        "avatar": {"type": "keyword", "copy_to": ["__text__"], "index": False},
                        "id": {"type": "keyword"},
                    }
                }
            }
        }

        assert col.fields() == {
            "avatar": {
                "default": True,
                "indexed": False,
                "list": False,
                "stored": False,
                "deprecated": False,
                "type": "keyword",
                "description": "",
                "regex": None,
                "values": None,
                "deprecated_description": "",
            }
        }

    def test_fields_describe_registered_model_fields(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {
                        "key": {**KEYWORD_MAPPING, "index": True, "doc_values": True},
                        "name": {**KEYWORD_MAPPING, "index": True, "doc_values": True},
                        "tags": {"type": "object"},
                        "id": {"type": "keyword", "store": True, "doc_values": True},
                    }
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {
                "key": {"keyword": {"type": "keyword", "searchable": True, "aggregatable": True}},
                "name": {"keyword": {"type": "keyword", "searchable": True, "aggregatable": True}},
                "id": {"keyword": {"type": "keyword", "searchable": True, "aggregatable": True}},
            }
        }

        fields = col.fields()

        assert "id" not in fields
        assert fields["key"] == {
            "default": False,
            "indexed": True,
            "list": False,
            "stored": True,
            "deprecated": False,
            "type": "keyword",
            "description": None,
            "regex": None,
            "values": None,
            "deprecated_description": None,
        }
        assert fields["name"]["description"] == "A plain, statically typed field."

    def test_fields_summarize_dynamic_mapping_children(self, mock_datastore):
        @register_model(index=True, store=True)
        class MappingDoc(HowlerESModel):
            tags: mapping(
                enum([1, "two"], store=False, description="Enum value"),
                description="A dynamic-key mapping field.",
                deprecated=True,
                deprecated_description="Use codes",
            )
            codes: mapping(validated_keyword("^[a-z]+$"))

        col = _make_collection(mock_datastore, model_class=MappingDoc)
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {
                        "tags": {
                            "properties": {
                                "later_key": {"type": "text"},
                                "first_key": {"type": "keyword", "copy_to": ["__text__"]},
                            }
                        },
                        "codes": {"properties": {"code": KEYWORD_MAPPING}},
                    }
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {"tags.first_key": {"keyword": {"type": "keyword", "searchable": False}}}
        }

        fields = col.fields()

        assert fields["tags"] == {
            "default": True,
            "indexed": False,
            "list": False,
            "stored": True,
            "type": "keyword",
            "description": "A dynamic-key mapping field.",
            "regex": None,
            "values": [1, "two"],
            "deprecated_description": "Use codes",
        }
        assert fields["tags.first_key"] == {**fields["tags"], "deprecated": True, "values": None}
        assert "tags.later_key" not in fields
        assert fields["codes"]["regex"] == "^[a-z]+$"
        assert fields["codes.code"]["regex"] is None

    def test_fields_can_skip_mapping_children(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {
                "mappings": {
                    "properties": {
                        "key": KEYWORD_MAPPING,
                        "name": KEYWORD_MAPPING,
                        "tags": {"properties": {"first_key": {"type": "keyword", "index": True}}},
                    }
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {"fields": {}}

        fields = col.fields(skip_mapping_children=True)

        assert "tags" in fields
        assert "tags.first_key" not in fields

    def test_returned_nested_enum_values_do_not_change_next_description_or_validation(self, mock_datastore):
        class Options(HowlerESModel):
            value: enum([{"tags": ["original"]}])
            labels: mapping(enum([{"tags": ["original"]}]))

        col = _make_collection(mock_datastore, model_class=Options)
        mock_datastore.client.indices.get_mapping.return_value = {
            col.index_name: {
                "mappings": {
                    "properties": {
                        "value": KEYWORD_MAPPING,
                        "labels": {"properties": {"one": KEYWORD_MAPPING}},
                    }
                }
            }
        }
        description = col.fields()
        for key in ("value", "labels"):
            values = description[key]["values"]
            assert values is not None and isinstance(values[0], dict)
            values[0]["tags"].append("changed")
        fresh = col.fields()
        assert fresh["value"]["values"] == fresh["labels"]["values"] == [{"tags": ["original"]}]
        assert fresh["labels.one"]["values"] is None
        data = {"tags": ["original"]}
        assert Options.model_validate({"value": data, "labels": {"one": data}}).labels == {"one": str(data)}

    def test_fields_reject_conflicting_mappings(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol-000001": {"mappings": {"properties": {"key": KEYWORD_MAPPING}}},
            "testcol-000002": {"mappings": {"properties": {"key": {"type": "text", "index": True}}}},
        }
        mock_datastore.client.field_caps.return_value = {"fields": {}}

        with pytest.raises(HowlerRuntimeError, match="conflicting mappings"):
            col.fields()

    def test_fields_reject_multiple_field_types(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {"mappings": {"properties": {"key": KEYWORD_MAPPING}}},
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {
                "key": {
                    "keyword": {"type": "keyword", "searchable": True},
                    "text": {"type": "text", "searchable": True},
                }
            }
        }

        with pytest.raises(HowlerRuntimeError, match="conflicting types"):
            col.fields()


class TestFieldReconciliation:
    @pytest.fixture()
    def generations(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc, ilm_config=ILMIndexConfig())
        older, latest = f"{col.name}-000001", f"{col.name}-000002"
        indices = mock_datastore.client.indices
        indices.get.return_value = {latest: {}, older: {}, f"{latest}__reindex": {}}
        indices.get_alias.return_value = {latest: {"aliases": {col.name: {"is_write_index": True}}}}
        complete = schema.document_mapping(ReconcileDoc)
        incomplete = deepcopy(complete)
        del incomplete["properties"]["key"]
        indices.get_mapping.return_value = {older: {"mappings": incomplete}, latest: {"mappings": complete}}
        return col, older, latest

    def test_repairs_only_missing_generation_and_restores_read_member(self, generations, mock_datastore):
        col, older, latest = generations
        indices = mock_datastore.client.indices
        col._ensure_collection_ilm()

        assert col.index_name == latest
        assert col.index_list_full == [latest, older]
        indices.get_mapping.assert_called_once_with(index=[older, latest], ignore_unavailable=True)
        indices.put_mapping.assert_called_once_with(
            index=older, properties={"key": schema.document_mapping(ReconcileDoc)["properties"]["key"]}
        )
        indices.update_aliases.assert_called_once_with(
            actions=[{"add": {"index": older, "alias": col.name, "is_write_index": False}}]
        )
        indices.put_index_template.assert_called_once()

    @pytest.mark.parametrize(
        "drift",
        [
            "field",
            "extra_field_option",
            "capability",
            "incomplete_caps",
            "template_order",
            "coverage",
            "unsafe_alias",
            "unexpected_member",
            "dynamic",
        ],
    )
    def test_validates_all_generations_and_alias_metadata_before_any_writes(self, generations, mock_datastore, drift):
        col, older, latest = generations
        indices = mock_datastore.client.indices
        mapping = indices.get_mapping.return_value[latest]["mappings"]
        if drift == "field":
            mapping["properties"]["name"]["index"] = False
        elif drift == "extra_field_option":
            mapping["properties"]["name"]["norms"] = True
        elif drift == "capability":
            mock_datastore.client.field_caps.side_effect = [
                {"fields": {}},
                {"fields": {"name": {"keyword": {"type": "keyword", "searchable": False}}}},
            ]
        elif drift == "incomplete_caps":
            mock_datastore.client.field_caps.side_effect = [
                {"indices": [older], "fields": {}},
                {"indices": [], "fields": {}, "failures": [{"indices": [latest]}]},
            ]
        elif drift == "template_order":
            mapping["dynamic_templates"].reverse()
        elif drift == "coverage":
            del indices.get_mapping.return_value[older]
        elif drift == "unsafe_alias":
            indices.get_alias.return_value[latest]["aliases"][col.name]["filter"] = {"term": {"tenant": "alpha"}}
        elif drift == "unexpected_member":
            indices.get_alias.return_value[f"{latest}__reindex"] = {"aliases": {col.name: {"is_write_index": True}}}
        else:
            mapping["dynamic"] = "strict"

        with pytest.raises((HowlerRuntimeError, HowlerValueError)):
            col._ensure_collection_ilm()

        assert {c[0] for c in indices.method_calls} <= {"get", "get_alias", "get_mapping"}
        mock_datastore.client.ilm.put_lifecycle.assert_not_called()

    def test_missing_keyword_and_nondefault_norms_on_another_generation_refused_before_repair(
        self, generations, mock_datastore
    ):
        col, older, latest = generations
        indices = mock_datastore.client.indices
        # A third generation explicitly spells out the default. Neither its presence nor
        # an earlier missing field may hide the conflict on the last generation.
        third = f"{col.name}-000003"
        indices.get.return_value[third] = {}
        maps = indices.get_mapping.return_value
        maps[third] = deepcopy(maps[latest])
        maps[latest]["mappings"]["properties"]["key"]["norms"] = False
        maps[third]["mappings"]["properties"]["key"]["norms"] = True
        assert "key" not in maps[older]["mappings"]["properties"]
        with pytest.raises(HowlerRuntimeError, match="key has conflicting mappings"):
            col._ensure_collection_ilm()
        assert {c[0] for c in indices.method_calls} <= {"get", "get_alias", "get_mapping"}
        mock_datastore.client.ilm.put_lifecycle.assert_not_called()

        del maps[latest]["mappings"]["properties"]["key"]
        # Now the *planned addition* is the only conflict with the live keyword.
        with pytest.raises(HowlerRuntimeError, match="key has conflicting mappings"):
            col._ensure_collection_ilm()
        assert {c[0] for c in indices.method_calls} <= {"get", "get_alias", "get_mapping"}
        mock_datastore.client.ilm.put_lifecycle.assert_not_called()

    @pytest.mark.parametrize(
        "selector,winner",
        [
            ({"match": "*"}, "strings_as_keywords"),
            ({"match_pattern": "regex", "path_match": ".*"}, "strings_as_keywords"),
            ({"match_mapping_type": "string"}, "strings_as_keywords"),
            ({"match_mapping_type": ["long"], "path_match": "tags.*"}, "tags.*_tpl"),
            ({"match_mapping_type": ["long"], "path_match": "tags.secret*"}, "tags.*_tpl"),
            ({"match_mapping_type": "string", "path_match": "tags.secret*"}, "strings_as_keywords"),
        ],
    )
    def test_differently_named_template_cannot_steal_active_rule(self, generations, mock_datastore, selector, winner):
        col, _, latest = generations
        indices = mock_datastore.client.indices
        templates = indices.get_mapping.return_value[latest]["mappings"]["dynamic_templates"]
        templates.insert(0, {"legacy_text": {**selector, "mapping": {"type": "text"}}})
        with pytest.raises(HowlerValueError) as refused:
            col._ensure_collection_ilm()
        assert f"legacy_text shadows {winner} on {latest}" in str(refused.value)
        assert {c[0] for c in indices.method_calls} <= {"get", "get_alias", "get_mapping"}
        mock_datastore.client.ilm.put_lifecycle.assert_not_called()

    def test_partial_namespace_shadow_reports_first_winners_in_helper_order(self, mock_datastore):
        # Deliberately use reverse alphabetical names to check both obsolete and active order.
        expected = [
            {"z_strings": {"match_mapping_type": "string", "mapping": {"type": "keyword"}}},
            {"a_tags": {"path_match": "tags.*", "mapping": {"type": "keyword"}}},
            {"b_labels": {"path_match": "labels.*", "mapping": {"type": "keyword"}}},
        ]
        live = [
            {"z_retired": {"path_match": "tags.secret*", "mapping": {"type": "text"}}},
            {"a_retired": {"path_match": "labels.secret*", "mapping": {"type": "text"}}},
            *expected,
        ]
        pairs = [
            ("z_retired", "z_strings"),
            ("z_retired", "a_tags"),
            ("a_retired", "z_strings"),
            ("a_retired", "b_labels"),
        ]
        assert shadowed_dynamic_templates(expected, live) == pairs

        # The cutover verifier consumes the same helper and must agree with startup.
        from howler.external.elasticsearch_cutover_verify import _template_checks

        blockers, warnings = [], []
        _template_checks("testcol", "testcol-000001", expected, live, blockers, warnings)
        assert blockers[0]["shadowed"] == [{"obsolete": old, "active": active} for old, active in pairs]
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        with pytest.raises(HowlerValueError) as refused:
            col._check_dynamic_templates(expected, {"testcol-000001": live})
        error = str(refused.value)
        offsets = [error.index(f"{old} shadows {active} on testcol-000001") for old, active in pairs]
        assert offsets == sorted(offsets)
        with pytest.raises(HowlerValueError) as refused:
            col._check_dynamic_templates(expected, {"testcol-000002": live, "testcol-000001": live})
        error = str(refused.value)
        messages = [
            f"{old} shadows {active} on {index}"
            for index in ("testcol-000001", "testcol-000002")
            for old, active in pairs
        ]
        offsets = [error.index(message) for message in messages]
        assert offsets == sorted(offsets)

    def test_narrow_shadow_uses_actual_first_match_and_ignores_unrelated_plugin(self, mock_datastore, caplog):
        expected = [
            {"strings": {"match_mapping_type": "string", "mapping": {"type": "keyword"}}},
            {"specific": {"path_match": "tags.secret*", "mapping": {"type": "integer"}}},
            {"tags": {"path_match": "tags.*", "mapping": {"type": "keyword"}}},
        ]
        obsolete = {"legacy": {"path_match": "tags.secret*", "mapping": {"type": "text"}}}
        disabled = {"disabled": {"path_match": "plugin.secret*", "mapping": {"type": "text"}}}
        # Global string rule and narrower specific active rule both precede the obsolete one.
        live = [disabled, *expected[:2], obsolete, expected[2]]
        assert shadowed_dynamic_templates(expected, live) == []
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        with caplog.at_level("WARNING", logger="howler.api.datastore"):
            col._check_dynamic_templates(expected, {"testcol-000001": live})
        assert "disabled" in caplog.text and "legacy" in caplog.text
        from howler.external.elasticsearch_cutover_verify import _template_checks

        blockers, warnings = [], []
        _template_checks("testcol", "testcol-000001", expected, live, blockers, warnings)
        assert blockers == []
        assert warnings[0]["templates"] == ["disabled", "legacy"]

        # Moving the obsolete selector after strings but before the specific rule changes
        # non-string fields only; the expected winner is the earlier specific active rule.
        live = [disabled, expected[0], obsolete, *expected[1:]]
        assert shadowed_dynamic_templates(expected, live) == [("legacy", "specific")]

    def test_global_selector_list_does_not_declare_a_disabled_plugin_namespace(self):
        expected = [
            {"global": {"path_match": ["*", "tags.*"], "mapping": {"type": "keyword"}}},
        ]
        disabled = {"disabled": {"path_match": "plugin.secret*", "mapping": {"type": "text"}}}
        assert shadowed_dynamic_templates(expected, [disabled, *expected]) == []

    def test_planned_addition_preserves_equivalent_explicit_defaults_and_historical_templates(
        self, generations, mock_datastore
    ):
        col, older, latest = generations
        indices = mock_datastore.client.indices
        live = indices.get_mapping.return_value[latest]["mappings"]
        live["properties"]["key"].update(norms=False, store=False, index_options="docs")
        live["dynamic_templates"].insert(
            1, {"disabled_plugin": {"path_match": "disabled_plugin.*", "mapping": {"type": "text"}}}
        )
        # The earlier active global string rule already handles all strings under tags.*.
        live["dynamic_templates"].insert(
            1,
            {
                "unreachable_strings": {
                    "match_mapping_type": "string",
                    "path_match": "tags.*",
                    "mapping": {"type": "text"},
                }
            },
        )
        # A renamed equivalent string matcher, or one placed after the active string rule, is safe.
        live["dynamic_templates"].insert(
            0, {"legacy_strings": deepcopy(live["dynamic_templates"][0]["strings_as_keywords"])}
        )
        live["dynamic_templates"].append({"fallback": {"match": "*", "mapping": {"type": "text"}}})
        col._ensure_collection_ilm()
        indices.put_mapping.assert_called_once_with(
            index=older, properties={"key": schema.document_mapping(ReconcileDoc)["properties"]["key"]}
        )

    def test_refuses_a_missing_dynamic_template(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        mock_datastore.client.indices.get_mapping.return_value = {
            col.index_name: {
                "mappings": {
                    "properties": {"key": KEYWORD_MAPPING, "name": KEYWORD_MAPPING},
                    "dynamic_templates": [],
                }
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {
                "key": {"keyword": {"type": "keyword", "searchable": True}},
                "name": {"keyword": {"type": "keyword", "searchable": True}},
            }
        }
        mock_datastore.client.indices.exists_template.return_value = False

        with pytest.raises(HowlerValueError, match="Refusing to add or change dynamic mapping templates"):
            col._check_fields()
        mock_datastore.client.indices.put_mapping.assert_not_called()
        mock_datastore.client.indices.put_settings.assert_not_called()

    def test_warns_about_unused_dynamic_templates(self, mock_datastore, caplog):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        expected_templates = schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        unused_template = {
            "disabled_plugin.*_tpl": {
                "path_match": "disabled_plugin.*",
                "mapping": {"type": "keyword", "index": True},
            }
        }
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {"mappings": {"dynamic_templates": [*expected_templates, unused_template]}}
        }

        with caplog.at_level("WARNING", logger="howler.api.datastore"):
            col._check_dynamic_templates()

        assert "retains dynamic templates not used by the active schema" in caplog.text

    def test_requires_active_templates_on_every_backing_index(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        expected_templates = schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol-000001": {"mappings": {"dynamic_templates": expected_templates}},
            "testcol-000002": {
                "mappings": {
                    "dynamic_templates": [
                        template for template in expected_templates if next(iter(template)) != "tags.*_tpl"
                    ]
                }
            },
        }

        with pytest.raises(HowlerValueError, match="tags\\.\\*_tpl"):
            col._check_dynamic_templates()

    def test_preserves_active_dynamic_template_order(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        expected_templates = schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol_hot": {"mappings": {"dynamic_templates": list(reversed(expected_templates))}}
        }

        with pytest.raises(HowlerValueError, match="order differs"):
            col._check_dynamic_templates()

    def test_retries_after_expanding_the_field_limit(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        mock_datastore.client.indices.get.return_value = {}
        expected_templates = schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            col.index_name: {
                "mappings": {"properties": {"name": KEYWORD_MAPPING}, "dynamic_templates": expected_templates}
            }
        }
        mock_datastore.client.field_caps.return_value = {
            "fields": {"name": {"keyword": {"type": "keyword", "searchable": True}}}
        }
        mock_datastore.client.indices.exists_template.return_value = False
        api_error = elasticsearch.BadRequestError(
            "boom", MagicMock(), {"error": {"reason": "Limit of total fields [10] has been exceeded"}}
        )
        mock_datastore.client.indices.put_mapping.side_effect = [api_error, None]

        col._check_fields()

        mock_datastore.client.indices.put_settings.assert_called_once_with(
            index=col.index_name, settings={"index.mapping.total_fields.limit": 510}
        )
        assert mock_datastore.client.indices.put_mapping.call_count == 2
        mock_datastore.client.indices.put_index_template.assert_not_called()

    @pytest.mark.parametrize(
        ("live_mapping", "capability", "message"),
        [
            ({"type": "text", "index": True}, {"type": "text", "searchable": True}, "expected store type"),
            (
                {"type": "keyword", "index": False},
                {"type": "keyword", "searchable": False},
                "incompatible indexing",
            ),
            (
                {"type": "keyword", "ignore_above": 128},
                {"type": "keyword", "searchable": True},
                "incompatible ignore_above",
            ),
        ],
    )
    def test_refuses_incompatible_existing_fields(self, mock_datastore, live_mapping, capability, message):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        expected_templates = schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            col.index_name: {
                "mappings": {
                    "properties": {"key": live_mapping, "name": KEYWORD_MAPPING},
                    "dynamic_templates": expected_templates,
                }
            }
        }
        cap_type = "keyword" if capability["type"] == "keyword" else "text"
        mock_datastore.client.field_caps.return_value = {
            "fields": {
                "key": {cap_type: capability},
                "name": {"keyword": {"type": "keyword", "searchable": True}},
            }
        }
        mock_datastore.client.indices.exists_template.return_value = False

        with pytest.raises(HowlerRuntimeError, match=message):
            col._check_fields()

    def test_refuses_conflicting_active_templates_across_indices(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        expected_templates = schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol-000001": {"mappings": {"dynamic_templates": expected_templates}},
            "testcol-000002": {
                "mappings": {
                    "dynamic_templates": [
                        template
                        if next(iter(template)) != "tags.*_tpl"
                        else {"tags.*_tpl": {"path_match": "tags.*", "mapping": {"type": "text", "index": True}}}
                        for template in expected_templates
                    ]
                }
            },
        }

        with pytest.raises(HowlerValueError, match="tags\\.\\*_tpl"):
            col._check_dynamic_templates()
