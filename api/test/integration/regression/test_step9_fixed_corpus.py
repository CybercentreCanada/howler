"""Fixed, independent ES 9.5.2 acceptance oracle through the Pydantic datastore.

Run serially, separately from other datastore-mutating suites:
    poetry run pytest -q test/integration/regression/test_step9_fixed_corpus.py -rs

Uses configured ES credentials, but never shared datastore fixtures or collection names.
Only connection unavailability may skip; wrong versions, authentication, schema, indexing,
query and cleanup failures fail. No observed ES8 baseline is claimed: relevance assertions
are an independent ES9 ranking contract, not proof of ES8-vs-ES9 score equivalence.
"""

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from elastic_transport import ConnectionError, ConnectionTimeout

from howler.datastore.collection import DATASTORE_INDEX_PREFIX, ESCollection
from howler.datastore.store import ESStore
from howler.models import HowlerESModel, date, integer, keyword, list_field, optional, register_model, text
from howler.models.schema import document_mapping, index_settings

CORPUS = json.loads((Path(__file__).parent / "fixtures" / "step9_search_corpus.json").read_text())
TARGET_VERSION = "9.5.2"


@register_model(index=True, store=True, id_field="key")
class FixedCorpusDocument(HowlerESModel):
    """Deliberately small real schema exercising analyzed, scalar and multivalue fields."""

    key: keyword()
    message: text(copyto=["__text__"])
    status: keyword()
    owner: optional(keyword())
    severity: integer()
    tags: list_field(keyword())
    observed: date()


def _delete_owned_index(client, physical_index, token):
    """Never use wildcard/alias deletion, and do not delete an index we cannot identify."""
    assert re.fullmatch(r"[a-z0-9][a-z0-9_-]*", physical_index), "Cleanup requires one concrete index name"
    assert physical_index.endswith(f"-step9_corpus_{token}_hot")
    if not client.indices.exists(index=physical_index):
        return
    mapping = client.indices.get_mapping(index=physical_index)
    assert mapping[physical_index]["mappings"].get("_meta", {}).get("step9_owner") == token, (
        f"Refusing to delete index without this run's ownership marker: {physical_index}"
    )
    result = client.indices.delete(index=physical_index)
    assert result["acknowledged"], f"Cleanup not acknowledged for {physical_index}"
    assert not client.indices.exists(index=physical_index), f"Cleanup left {physical_index} behind"


@pytest.fixture(scope="module")
def corpus_collection():
    """Create exactly one disposable index; clean even after setup/seeding failure."""
    assert "PYTEST_XDIST_WORKER" not in os.environ, "Run fixed-corpus datastore tests serially, without xdist"
    store = ESStore(archive_access=False)
    try:
        store.client = store.client.options(request_timeout=5, max_retries=0)
        try:
            info = store.client.info()
        except (ConnectionError, ConnectionTimeout) as exc:
            pytest.skip(f"Elasticsearch {TARGET_VERSION} unavailable: {type(exc).__name__} during cluster info probe")
        assert info["version"]["number"] == TARGET_VERSION, (
            f"Fixed corpus requires Elasticsearch {TARGET_VERSION}; got {info['version']['number']}"
        )

        token = uuid4().hex
        name = f"step9_corpus_{token}"
        alias = f"{DATASTORE_INDEX_PREFIX}-{name}"
        physical_index = f"{alias}_hot"
        # Fail, rather than adopting or deleting anything left by another run.
        assert not store.client.indices.exists(index=alias)
        assert not store.client.indices.exists(index=physical_index)
        mappings = document_mapping(FixedCorpusDocument)
        mappings["_meta"] = {"step9_owner": token}
        try:
            # Pin one shard for term statistics, no replicas, independent of environment defaults.
            created = store.client.indices.create(
                index=physical_index,
                mappings=mappings,
                settings=index_settings(FixedCorpusDocument, shards=1, replicas=0),
                aliases={alias: {}},
            )
            assert created["acknowledged"]
            collection = ESCollection(store, name, model_class=FixedCorpusDocument, max_attempts=1)
            assert collection.index_name == physical_index
            assert collection.ilm_config is None
            # Reverse ingestion order so ID tie-breaking cannot accidentally pass via insertion order.
            for document in reversed(CORPUS["documents"]):
                assert collection.save(document["key"], deepcopy(document))
            refresh = store.client.indices.refresh(index=physical_index)
            assert refresh["_shards"]["failed"] == 0
            assert store.client.count(index=physical_index)["count"] == 8
            yield collection
        finally:
            _delete_owned_index(store.client, physical_index, token)
    finally:
        # ESStore.close only invalidates its client reference; it does not close the transport.
        # This outer finally also runs when ownership-scoped index cleanup raises.
        try:
            store.client.close()
        finally:
            store.close()


def test_fixed_corpus_is_valid_without_cluster():
    """Validate the fixture and schema offline, without deriving its expected search results."""
    assert CORPUS["target_version"] == TARGET_VERSION
    assert [doc["key"] for doc in CORPUS["documents"]] == ["a", "b", "c", "d", "e", "f", "g", "h"]
    for document in CORPUS["documents"]:
        assert FixedCorpusDocument.model_validate(document).key == document["key"]
    for case in CORPUS["searches"]:
        assert case["total"] == len(case["ids"]) == len(set(case["ids"]))
        assert set(case["ids"]) <= {"a", "b", "c", "d", "e", "f", "g", "h"}


@pytest.mark.parametrize("marker", [None, "another-run"])
def test_cleanup_refuses_unowned_index(marker):
    client = MagicMock()
    index = "howler-step9_corpus_thisrun_hot"
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {index: {"mappings": {"_meta": {"step9_owner": marker}}}}
    with pytest.raises(AssertionError, match="ownership marker"):
        _delete_owned_index(client, index, "thisrun")
    client.indices.delete.assert_not_called()


def test_cleanup_deletes_only_owned_concrete_index():
    client = MagicMock()
    index = "howler-step9_corpus_thisrun_hot"
    client.indices.exists.side_effect = [True, False]
    client.indices.get_mapping.return_value = {index: {"mappings": {"_meta": {"step9_owner": "thisrun"}}}}
    client.indices.delete.return_value = {"acknowledged": True}
    _delete_owned_index(client, index, "thisrun")
    client.indices.delete.assert_called_once_with(index=index)


@pytest.mark.parametrize("index", ["*-step9_corpus_thisrun_hot", "howler-hit_hot", "howler-step9_corpus_thisrun"])
def test_cleanup_rejects_wildcard_shared_index_and_alias(index):
    client = MagicMock()
    with pytest.raises(AssertionError):
        _delete_owned_index(client, index, "thisrun")
    assert not client.mock_calls


def test_cleanup_does_not_hide_delete_failure():
    client = MagicMock()
    index = "howler-step9_corpus_thisrun_hot"
    client.indices.exists.return_value = True
    client.indices.get_mapping.return_value = {index: {"mappings": {"_meta": {"step9_owner": "thisrun"}}}}
    client.indices.delete.side_effect = RuntimeError("delete failed")
    with pytest.raises(RuntimeError, match="delete failed"):
        _delete_owned_index(client, index, "thisrun")


def test_fixture_closes_transport_on_wrong_version(monkeypatch):
    store = MagicMock()
    client = store.client
    client.options.return_value = client
    client.info.return_value = {"version": {"number": "8.19.0"}}
    monkeypatch.setattr(f"{__name__}.ESStore", lambda **kwargs: store)
    fixture = corpus_collection.__wrapped__()
    with pytest.raises(AssertionError, match="requires Elasticsearch 9.5.2"):
        next(fixture)
    client.indices.create.assert_not_called()
    client.close.assert_called_once_with()
    store.close.assert_called_once_with()


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_fixture_closes_transport_after_index_cleanup(monkeypatch, cleanup_fails):
    store = MagicMock()
    client = store.client
    client.options.return_value = client
    client.info.return_value = {"version": {"number": TARGET_VERSION}}
    client.indices.exists.return_value = False
    client.indices.create.return_value = {"acknowledged": True}
    client.indices.refresh.return_value = {"_shards": {"failed": 0}}
    client.count.return_value = {"count": 8}
    monkeypatch.setattr(f"{__name__}.ESStore", lambda **kwargs: store)

    def make_collection(_store, name, **kwargs):
        return MagicMock(index_name=f"{DATASTORE_INDEX_PREFIX}-{name}_hot", ilm_config=None)

    monkeypatch.setattr(f"{__name__}.ESCollection", make_collection)
    events = []

    def cleanup(_client, index, token):
        assert index == f"{DATASTORE_INDEX_PREFIX}-step9_corpus_{token}_hot"
        events.append("delete")
        if cleanup_fails:
            raise RuntimeError("cleanup failed")

    monkeypatch.setattr(f"{__name__}._delete_owned_index", cleanup)
    client.close.side_effect = lambda: events.append("transport-close")
    store.close.side_effect = lambda: events.append("store-close")
    fixture = corpus_collection.__wrapped__()
    next(fixture)
    if cleanup_fails:
        with pytest.raises(RuntimeError, match="cleanup failed"):
            fixture.close()
    else:
        fixture.close()
    assert events == ["delete", "transport-close", "store-close"]
    client.close.assert_called_once_with()
    store.close.assert_called_once_with()


@pytest.mark.parametrize("case", CORPUS["searches"], ids=lambda case: case["name"])
@pytest.mark.parametrize("as_obj", [False, True], ids=["dict", "pydantic"])
def test_exact_result_sets_and_order(corpus_collection, case, as_obj):
    result = corpus_collection.search(
        case["query"],
        filters=deepcopy(case.get("filters", [])),
        access_control=case.get("access_control"),
        sort=case["sort"],
        rows=20,
        track_total_hits=True,
        as_obj=as_obj,
    )
    actual = [item.key if as_obj else item["key"] for item in result["items"]]
    assert result["total"] == case["total"]
    assert len(actual) == len(set(actual)), "Duplicate documents in result"
    assert set(actual) == set(case["ids"]), "Result-set drift"
    assert actual == case["ids"], "Ordering drift (do not sort/normalize before comparison)"


def test_pagination_across_equal_sort_values(corpus_collection):
    case = CORPUS["pagination"]
    seen = []
    for page_number, expected in enumerate(case["pages"]):
        offset = page_number * case["rows"]
        result = corpus_collection.search(
            case["query"], sort=case["sort"], rows=case["rows"], offset=offset, track_total_hits=True, as_obj=False
        )
        actual = [item["key"] for item in result["items"]]
        assert result["offset"] == offset
        assert result["rows"] == case["rows"]
        assert result["total"] == case["total"]
        assert actual == expected
        seen.extend(actual)
    assert seen == ["a", "b", "c", "g", "d", "h", "e", "f"]
    assert len(set(seen)) == case["total"]


@pytest.mark.parametrize("case", CORPUS["aggregations"], ids=lambda case: case["name"])
def test_exact_aggregations(corpus_collection, case):
    result = corpus_collection.search(
        case["query"],
        filters=deepcopy(case.get("filters", [])),
        aggregations=list(deepcopy(CORPUS["aggregation_request"]).items()),
        sort="key asc",
        rows=0,
        track_total_hits=True,
        as_obj=False,
    )
    assert result["items"] == []
    assert result["total"] == case["total"]
    # Compare the complete response, including bucket order, zero buckets and error counts.
    assert result["aggregations"] == case["expected"]


def test_relevance_scores_are_not_normalized(corpus_collection):
    """Verify positive BM25 frequency ordering and the deliberate tie, not ES8 equivalence."""
    response = corpus_collection.datastore.client.search(
        index=corpus_collection.index_name,
        query={"query_string": {"query": "message:phishing"}},
        sort=[{"_score": "desc"}, {"key": "asc"}],
        track_scores=True,
        track_total_hits=True,
        size=20,
    )
    assert response["timed_out"] is False
    assert response["_shards"]["failed"] == 0
    assert response["hits"]["total"] == {"value": 4, "relation": "eq"}
    hits = response["hits"]["hits"]
    assert [hit["_id"] for hit in hits] == ["a", "b", "c", "g"]
    assert hits[0]["_score"] > hits[1]["_score"] > hits[2]["_score"] > 0
    assert hits[2]["_score"] == hits[3]["_score"]
