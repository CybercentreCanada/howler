"""Unit tests for ILM methods on ESCollection.

These tests mock the Elasticsearch client to verify the correct ILM policy,
index template, and _ensure_collection_ilm logic without requiring a running ES.
"""

import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Annotated
from unittest.mock import MagicMock, call, patch

import elasticsearch
import pytest
from elastic_transport import ApiResponseMeta, ObjectApiResponse

from howler.common.exceptions import HowlerRuntimeError, HowlerValueError
from howler.config_models import ILMConfig, ILMIndexConfig
from howler.datastore.collection import ESCollection
from howler.datastore.exceptions import DataStoreException, SearchException
from howler.models import (
    HowlerESModel,
    HowlerModelValidationError,
    Keyword,
    mapping,
    metadata,
    register_model,
    schema,
)
from howler.models.action import Action
from howler.models.analytic import Analytic
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

    key: Keyword
    name: Annotated[Keyword, metadata(description="A plain, statically typed field.")]
    tags: mapping(Keyword, default={}, description="A dynamic-key mapping field.")


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

    @pytest.mark.parametrize("wrapped", [False, True])
    def test_get_task_results_polls_until_completed(self, mock_datastore, monkeypatch, wrapped):
        col = _make_collection(mock_datastore)
        completed = {"completed": True, "response": self._query_result()}
        if wrapped:
            meta = ApiResponseMeta(status=200, http_version="1.1", headers={}, duration=0.0, node=None)
            completed = ObjectApiResponse(meta=meta, body=completed)
        mock_datastore.client.tasks.get.side_effect = [
            {"completed": False},
            completed,
        ]
        monkeypatch.setattr("howler.datastore.collection.time.sleep", lambda _: None)

        assert col._get_task_results({"task": "node:1"}) == self._query_result()

        assert mock_datastore.client.tasks.get.call_count == 2
        assert mock_datastore.client.tasks.get.call_args.kwargs == {
            "task_id": "node:1",
            "wait_for_completion": False,
        }

    @pytest.mark.parametrize(
        "response,match",
        [
            ({"completed": True, "response": {"timed_out": True, "failures": []}}, None),
            ({"completed": True, "response": {"timed_out": False, "failures": [{"reason": "failed"}]}}, None),
            ({"completed": True, "error": {"reason": "failed"}}, "task node:1 failed"),
        ],
    )
    def test_get_task_results_rejects_strict_query_failures(self, mock_datastore, response, match):
        col = _make_collection(mock_datastore)
        mock_datastore.client.tasks.get.return_value = response

        with pytest.raises(DataStoreException, match=match):
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

    def test_projected_search_object_validates_only_selected_fields(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Action)
        action = col._format_output(
            {"_id": "document-id", "_index": "howler-action_hot", "_score": 1.5, "_source": {"name": "Projected"}},
            ["name", "id"],
            as_obj=True,
        )
        assert action.name == "Projected"
        assert "action_id" not in action.__dict__
        assert action.meta.id == "document-id"
        assert action.meta.score == 1.5
        assert action.as_primitives() == {"name": "Projected"}

    def test_save_rejects_invalid_full_model(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Action)

        with pytest.raises(HowlerModelValidationError):
            col.save("document-id", {"name": "Incomplete"})
        with pytest.raises(HowlerModelValidationError):
            col.save("document-id", {**_action_data(), "unknown": True})

    def test_projected_model_cannot_be_saved_as_full_replacement(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Action)
        projected = col._format_output({"_id": "document-id", "_source": {"name": "Projected"}}, ["name"], as_obj=True)
        with pytest.raises(HowlerModelValidationError):
            col.save("document-id", projected)

        mock_datastore.client.index.assert_not_called()

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

    def test_implicit_stored_field_object_projection_is_partial(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=User)

        user = col._format_output({"_id": "user-1", "_source": {"uname": "user-1", "name": "Test User"}}, as_obj=True)
        assert user.uname == "user-1"
        assert user.name == "Test User"
        assert "password" not in user.__dict__

    def test_nested_declared_ids_survive_partial_object_projection(self, mock_datastore):
        col = _make_collection(mock_datastore, model_class=Hit)

        hit = col._format_output({"_id": "hit-1", "_source": {"howler": {"id": "hit-1"}}}, ["howler.id"], as_obj=True)
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

    def test_multiget_duplicate_id_uses_newest_generation_regardless_of_other_ids(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"), model_class=Action)
        old_index = f"{col.name}-000001"
        new_index = f"{col.name}-000002"
        hits = [
            {"_id": "old-only", "_index": old_index},
            {"_id": "duplicate", "_index": old_index},
            {"_id": "duplicate", "_index": new_index},
        ]
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 3, "relation": "eq"}, "hits": hits}}

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
        hits = [{"_id": "document-id", "_index": index} for index in (old_index, new_index)]
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 2, "relation": "eq"}, "hits": hits}}
        mock_datastore.client.delete.return_value = {"result": "deleted"}

        result = col.delete("document-id", refresh="wait_for")
        assert result is True

        assert mock_datastore.client.delete.call_args_list == [
            call(id="document-id", index=new_index, refresh="wait_for"),
            call(id="document-id", index=old_index, refresh="wait_for"),
        ]

    def test_delete_missing_ilm_document_returns_false_without_alias_delete(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

        result = col.delete("missing")
        assert result is False
        mock_datastore.client.delete.assert_not_called()


class TestILMVersionedOperations:
    """Tests for alias-safe ILM reads followed by optimistic-concurrency writes."""

    @pytest.fixture()
    def ilm_document(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        concrete_index = f"{col.name}-000001"
        client = mock_datastore.client
        client.search.return_value = {
            "hits": {
                "total": {"value": 1, "relation": "eq"},
                "hits": [{"_id": "document-id", "_index": concrete_index}],
            }
        }
        client.get.return_value = {
            "_id": "document-id",
            "_index": concrete_index,
            "_seq_no": 5,
            "_primary_term": 2,
            "_source": {"id": "document-id", "value": "original"},
        }
        return col, client, concrete_index

    @pytest.mark.parametrize("found", [True, False])
    def test_versioned_get(self, ilm_document, found):
        col, client, index = ilm_document
        if not found:
            client.search.return_value = {"hits": {"hits": []}}
        data, version = col.get_if_exists("document-id", as_obj=False, version=True)
        assert (data, version) == (({"value": "original"}, f"{index}---5---2") if found else (None, "create"))
        if found:
            client.search.assert_called_once_with(
                index=col.name,
                query={"ids": {"values": ["document-id"]}},
                size=col.MAX_SEARCH_ROWS,
                _source=False,
            )
            client.get.assert_called_once_with(index=index, id="document-id")

    @pytest.mark.parametrize("mode", ["existing", "missing", "versioned", "delete"])
    def test_ilm_writes(self, ilm_document, mode):
        col, client, index = ilm_document
        version = f"{index}---5---2"
        if mode == "missing":
            client.search.return_value = {"hits": {"hits": []}}
            col.save("document-id", {"value": "new"})
            assert client.index.call_args.kwargs["index"] == col.name
            assert client.index.call_args.kwargs["op_type"] == "create"
            return
        if mode == "delete":
            client.delete.return_value = {"result": "not_found"}
            assert col.delete("document-id", version=version) is False
            kwargs = client.delete.call_args.kwargs
        else:
            col.save("document-id", {"value": "updated"}, version=version if mode == "versioned" else None)
            kwargs = client.index.call_args.kwargs
            if mode == "versioned":
                client.update.return_value = {"result": "updated", "_index": index, "_seq_no": 6, "_primary_term": 2}
                assert col.update("document-id", [(col.UPDATE_SET, "value", "updated")], version=version) == (
                    True,
                    f"{index}---6---2",
                )
                assert client.update.call_args.kwargs["index"] == index
        assert (kwargs["index"], kwargs["if_seq_no"], kwargs["if_primary_term"]) == (index, "5", "2")

    def test_unversioned_update_returns_false_for_missing_ilm_document(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"), model_class=Action)
        mock_datastore.client.search.return_value = {"hits": {"hits": []}}

        assert col.update("missing-document", [(col.UPDATE_SET, "name", "updated")]) is False
        mock_datastore.client.update.assert_not_called()

    def test_read_update_save_and_atomic_delete_target_the_newest_generation(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        older, newer = f"{col.name}-000001", f"{col.name}-000002"
        client = mock_datastore.client
        client.search.return_value = {
            "hits": {"hits": [{"_id": "dup", "_index": older}, {"_id": "dup", "_index": newer}]}
        }
        client.get.return_value = {"_index": newer, "_seq_no": 4, "_primary_term": 1, "_source": {"value": "new"}}
        client.update.return_value = {"_index": newer, "_seq_no": 5, "_primary_term": 1, "result": "updated"}
        client.delete.return_value = {"result": "deleted"}

        data, version = col.get_if_exists("dup", as_obj=False, version=True)
        assert data == {"value": "new"}
        client.get.assert_called_once_with(index=newer, id="dup")
        ok, updated_version = col.update("dup", [(col.UPDATE_SET, "value", "changed")], version=version)
        assert ok and col.save("dup", {"value": "changed"}, version=updated_version)
        assert col.delete("dup", version=updated_version)
        for method, seq_no in ((client.update, "4"), (client.index, "5"), (client.delete, "5")):
            params = method.call_args.kwargs
            assert (params["index"], params["if_seq_no"], params["if_primary_term"]) == (newer, seq_no, "1")


class TestILMBulkRouting:
    """Bulk writes remain alias-safe across automatic rollover."""

    def test_new_documents_use_write_alias_after_rollover_without_restart(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"), model_class=Action)
        col.index_name = f"{col.name}-000001"

        plan = col.get_bulk_plan()
        plan.add_insert_operation("action-1", _action_data())

        assert json.loads(plan.operations[0][0]) == {"create": {"_index": col.name, "_id": "action-1"}}

    def test_existing_documents_resolve_in_one_search(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"), model_class=Action)
        old_index = f"{col.name}-000001"
        mock_datastore.client.search.return_value = {
            "hits": {"hits": [{"_id": f"action-{i}", "_index": old_index} for i in (1, 2)]}
        }

        plan = col.get_bulk_plan()
        plan.add_index_operation("action-1", _action_data())
        plan.add_update_operation("action-2", {"name": "updated"}, fields=["name"])
        plan.get_plan_data()

        for operation, action, key in zip(plan.operations, ("index", "update"), ("action-1", "action-2")):
            assert json.loads(operation[0])[action] == {"_index": old_index, "_id": key}
        assert mock_datastore.client.search.call_count == 1
        assert mock_datastore.client.search.call_args.kwargs["index"] == col.name

    def test_explicit_index_is_used_without_lookup(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        member = f"{col.name}-000001"
        plan = col.get_bulk_plan()
        plan.add_insert_operation("insert", {"value": 1}, index=member)
        plan.add_update_operation("update", {"value": 2}, index=member)
        lines = list(map(json.loads, plan.get_plan_data().splitlines()))
        assert lines[0] == {"create": {"_id": "insert", "_index": member}}
        assert lines[2] == {"update": {"_id": "update", "_index": member}}
        mock_datastore.client.search.assert_not_called()

    def test_duplicate_matches_route_update_to_newest_and_delete_all(self, mock_datastore):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig())
        old, middle, new = (f"{col.name}-{n:06}" for n in range(1, 4))
        mock_datastore.client.search.return_value = {
            "hits": {"hits": [{"_id": "dup", "_index": index} for index in (middle, old, new)]}
        }
        plan = col.get_bulk_plan()
        plan.add_update_operation("dup", {"name": "updated"})
        plan.add_delete_operation("dup")

        lines = list(map(json.loads, plan.get_plan_data().splitlines()))
        assert lines == [
            {"update": {"_id": "dup", "_index": new}},
            {"doc": {"name": "updated"}},
            *({"delete": {"_id": "dup", "_index": index}} for index in (new, middle, old)),
        ]

    @pytest.mark.parametrize("operation", ["update", "upsert", "delete"])
    def test_missing_document_falls_back_to_write_alias(self, mock_datastore, operation):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"), model_class=Action)
        mock_datastore.client.search.return_value = {"hits": {"total": {"value": 0, "relation": "eq"}, "hits": []}}

        plan = col.get_bulk_plan()
        if operation == "update":
            plan.add_update_operation("missing", {"name": "Updated"}, fields=["name"])
        elif operation == "upsert":
            plan.add_upsert_operation("missing", _action_data())
        else:
            plan.add_delete_operation("missing")
        plan.get_plan_data()

        action = "delete" if operation == "delete" else "update"
        assert len(plan.operations) == 1
        assert json.loads(plan.operations[0][0]) == {action: {"_index": col.name, "_id": "missing"}}


class TestCreateILMPolicy:
    hot = {"hot": {"min_age": "0ms", "actions": {"rollover": {"max_age": "7d", "max_primary_shard_size": "25gb"}}}}
    cold = {"cold": {"min_age": "90d", "actions": {}}}
    warm = {"warm": {"min_age": "30d", "actions": {"forcemerge": {"max_num_segments": 3}}}}

    @pytest.mark.parametrize(
        ("config", "expected"),
        [
            ({}, hot),
            ({"warm": "30d", "cold": "90d"}, {**hot, **warm, **cold}),
            (
                {"warm": "30d", "cold": "90d", "warm_forcemerge_segments": 5},
                {**hot, "warm": {"min_age": "30d", "actions": {"forcemerge": {"max_num_segments": 5}}}, **cold},
            ),
            (
                {"warm": "30d", "cold": "90d", "warm_forcemerge_segments": None},
                {**hot, "warm": {"min_age": "30d", "actions": {}}, **cold},
            ),
            ({"warm": "14d"}, {**hot, "warm": {"min_age": "14d", "actions": {"forcemerge": {"max_num_segments": 3}}}}),
            ({"cold": "60d"}, {**hot, "cold": {"min_age": "60d", "actions": {}}}),
        ],
    )
    def test_policy_phases(self, mock_datastore, config, expected):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(**config))
        col._create_ilm_policy(ILMConfig(enabled=True, rollover_max_age="7d", rollover_max_size="25gb"))
        mock_datastore.client.ilm.put_lifecycle.assert_called_once_with(
            name=f"{col.name}_policy", policy={"phases": expected}
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

    @pytest.mark.parametrize("state", ["existing", "missing", "legacy", "reentry"])
    def test_existing_ilm_alias_reconciliation(self, mock_datastore, state):
        col = _make_collection(mock_datastore, ilm_config=ILMIndexConfig(warm="30d"))
        indices = mock_datastore.client.indices
        older, newer, hot = f"{col.name}-000001", f"{col.name}-000002", f"{col.name}_hot"
        generations = [older, newer] if state in ("existing", "missing") else [older]
        latest = generations[-1]
        indices.get.return_value = dict.fromkeys(generations, {})
        indices.exists_alias.return_value = state != "missing"
        if state in ("legacy", "reentry"):
            indices.get_alias.return_value = {
                hot: {"aliases": {col.name: {"is_write_index": True} if state == "legacy" else {}}}
            }
        if state == "reentry":
            col.index_name = latest
            indices.get_alias.return_value[latest] = {"aliases": {col.name: {"is_write_index": True}}}

        with (
            patch.object(col, "_create_ilm_policy"),
            patch.object(col, "_create_index_template"),
            patch.object(col, "_check_fields"),
        ):
            col._ensure_collection_ilm()

        expected = []
        if state in ("legacy", "reentry"):
            expected.append({"remove": {"index": hot, "alias": col.name}})
        if state != "reentry":
            expected.extend(
                {"add": {"index": index, "alias": col.name, "is_write_index": index == latest}} for index in generations
            )
        indices.update_aliases.assert_called_once_with(actions=expected)
        indices.create.assert_not_called()
        indices.clone.assert_not_called()
        assert col.index_name == latest

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
        mock_datastore.client.indices.get_alias.return_value = {hot_index_name: {"aliases": {col.name: {}}}}

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
            assert add_action["add"] == {"index": f"{col.name}-000001", "alias": col.name, "is_write_index": True}
            assert {"remove": {"index": hot_index_name, "alias": col.name}} in alias_actions

        assert col.index_name == f"{col.name}-000001"


class TestEnsureCollectionILMDispatch:
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
        create = mock_datastore.client.indices.create.call_args.kwargs
        assert create["index"] == col.index_name and create["aliases"] == {col.name: {}}
        mock_datastore.client.indices.put_alias.assert_not_called()


KEYWORD_MAPPING = {"type": "keyword", "ignore_above": 8191}


class TestCollectionFieldDiscovery:
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
        live = indices.get_mapping.return_value[latest]["mappings"]
        live["properties"]["key"].update(norms=False, store=False, index_options="docs")
        templates = live["dynamic_templates"]
        templates.insert(1, {"disabled_plugin": {"path_match": "disabled_plugin.*", "mapping": {"type": "text"}}})
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
            "dynamic",
        ],
    )
    def test_validates_all_generations_before_any_writes(self, generations, mock_datastore, drift):
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

    @pytest.mark.parametrize("drift", ["missing", "changed", "order"])
    def test_rejects_dynamic_template_drift_on_any_backing_index(self, mock_datastore, drift):
        col = _make_collection(mock_datastore, model_class=ReconcileDoc)
        expected_templates = schema.document_mapping(ReconcileDoc)["dynamic_templates"]
        live = deepcopy(expected_templates)
        if drift == "missing":
            live = [template for template in live if "tags.*_tpl" not in template]
        elif drift == "changed":
            next(template["tags.*_tpl"] for template in live if "tags.*_tpl" in template)["mapping"]["type"] = "text"
        else:
            live.reverse()
        mock_datastore.client.indices.get_mapping.return_value = {
            "testcol-000001": {"mappings": {"dynamic_templates": expected_templates}},
            "testcol-000002": {"mappings": {"dynamic_templates": live}},
        }
        with pytest.raises(HowlerValueError, match="order differs" if drift == "order" else r"tags\.\*_tpl"):
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
