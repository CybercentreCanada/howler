"""Test that the endpoints which should accept a `wait` parameter properly forward it to the datastore call"""

import base64
import importlib
import json
import random
import secrets
from typing import Any
from warnings import warn

import pytest
from werkzeug.test import EnvironBuilder

from howler.app import app
from howler.common import loader
from howler.common.exceptions import HowlerInvalidParameterException
from howler.datastore.collection import ESCollection
from howler.odm import random_data
from howler.odm.models.analytic import Analytic
from howler.odm.models.hit import Hit
from howler.odm.randomizer import random_model_obj

_TEST_TOKEN = f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}"
random.seed(1783007511)  # Ensure deterministic test data for reproducibility


def _get_rw_model(model_class):
    model_obj = random_model_obj(model_class)

    # do not create read only objects
    if model_class == Analytic:
        model_obj.rule = "some rule"
        model_obj.rule_type = "lucene"
        model_obj.detections = ["Rule"]

    if model_obj.get("owner") is not None:
        model_obj.owner = "admin"

    return model_obj


def _build_request(test_client, endpoint: str, method: str, data: str):
    request = EnvironBuilder(
        path=f"/api/v1{endpoint}",
        method=method,
        query_string={"refresh": "wait_for"},
        content_type="application/json",
        data=data,
        headers={"Authorization": _TEST_TOKEN},
    )
    return test_client.open(request)


SPY_INDEXES = ("action", "analytic", "dossier", "overview", "template", "view", "user", "hit")


class SpyCollection:
    def __init__(self, index_name: str, wrapped_collection: ESCollection):
        self.index_name = index_name
        self.wrapped_collection = wrapped_collection
        self.write_call_args_history: list[dict[str, Any]] = []

    def __getattr__(self, name: str):
        return getattr(self.wrapped_collection, name)

    def _record_write(self, operation: str, refresh: str | None):
        self.write_call_args_history.append({"index": self.index_name, "operation": operation, "refresh": refresh})

    def save(self, key, data, version=None, refresh=None):
        self._record_write("save", refresh)
        return self.wrapped_collection.save(key, data, version, refresh)

    def delete(self, key, refresh=None):
        self._record_write("delete", refresh)
        return self.wrapped_collection.delete(key, refresh)

    def update(self, key, operations, version=None, refresh=None):
        self._record_write("update", refresh)
        return self.wrapped_collection.update(key, operations, version, refresh)

    def bulk(self, operations, refresh=None):
        self._record_write("bulk", refresh)
        return self.wrapped_collection.bulk(operations, refresh)

    def delete_by_query(self, query: str, sort=None, max_docs=None, refresh=None):
        self._record_write("delete_by_query", refresh)
        return self.wrapped_collection.delete_by_query(query, sort, max_docs, refresh)

    def delete_by_search_object(self, query: dict, sort=None, max_docs=None, refresh=None):
        self._record_write("delete_by_search_object", refresh)
        return self.wrapped_collection.delete_by_search_object(query, sort, max_docs, refresh)

    def update_by_query(self, query, operations, filters=None, access_control=None, max_docs=None, refresh=None):
        self._record_write("update_by_query", refresh)
        return self.wrapped_collection.update_by_query(query, operations, filters, access_control, max_docs, refresh)


@pytest.fixture(scope="function")
def hit_list(datastore_connection):
    random_data.wipe_analytics(datastore_connection)
    random_data.create_analytics(datastore_connection)
    hits = []
    lookups = loader.get_lookups()
    users = datastore_connection.user.search("*:*")["items"]
    for _ in range(5):
        hit = random_data.generate_useful_hit(lookups=lookups, users=users, prune_hit=False)
        hits.append(hit)
    return hits


@pytest.fixture(scope="function")
def hit_ids(hit_list: list[Hit], datastore_connection):
    for hit in hit_list:
        datastore_connection.hit.save(hit.howler.id, hit)
    datastore_connection.hit.commit()
    yield [hit.howler.id for hit in hit_list]
    for hit in hit_list:
        try:
            datastore_connection.hit.delete(hit.howler.id)
        except Exception as e:
            warn(f"Cleanup: failed to delete test hit with id {hit.howler.id}: {e!r}")
    datastore_connection.hit.commit()


@pytest.fixture(scope="function")
def hit_bundle(hit_ids, datastore_connection):
    lookups = loader.get_lookups()
    users = datastore_connection.user.search("*:*")["items"]
    bundle = random_data.generate_useful_hit(lookups=lookups, users=users, prune_hit=False)
    bundle.howler.is_bundle = True
    bundle.howler.hits = hit_ids
    bundle.howler.bundle_size = len(hit_ids)
    return bundle


@pytest.fixture(scope="function")
def hit_bundle_id(hit_bundle: Hit, datastore_connection):
    datastore_connection.hit.save(hit_bundle.howler.id, hit_bundle)
    datastore_connection.hit.commit()
    yield hit_bundle.howler.id
    try:
        datastore_connection.hit.delete(hit_bundle.howler.id)
        datastore_connection.hit.commit()
    except Exception as e:
        warn(f"Cleanup: failed to delete test hit bundle with id {hit_bundle.howler.id}: {e!r}")


@pytest.fixture(scope="function")
def tool_hit_field_map():
    return {
        "analytic": ["howler.analytic"],
        "file.sha256": ["file.hash.sha256", "howler.hash"],
        "file.name": ["file.name"],
        "src_ip": ["source.ip", "related.ip"],
        "dest_ip": ["destination.ip", "related.ip"],
        "time.created": ["event.start"],
        "time.completed": ["event.end"],
        "raw": ["howler.data"],
        "zone": ["cloud.availability_zone"],
    }


@pytest.fixture(scope="function")
def tool_hit_raw_hit(datastore_connection):
    raw_hit = {
        "analytic": "tool-refresh-forwarding",
        "src_ip": "10.10.10.10",
        "dest_ip": "10.10.10.11",
        "file": {
            "name": "refresh-test.exe",
            "sha256": secrets.token_hex(32),
        },
        "time": {
            "created": "2026-01-01T00:00:00.000Z",
            "completed": "2026-01-01T00:05:00.000Z",
        },
        "zone": "integration-test",
    }
    raw_hit["raw"] = {**raw_hit}

    yield raw_hit

    datastore_connection.hit.delete_by_query("howler.analytic:tool-refresh-forwarding", refresh="true")
    datastore_connection.analytic.delete_by_query("name:tool-refresh-forwarding", refresh="true")


@pytest.fixture(scope="function")
def namespaces_for_patch():
    return [
        "howler.api.v1.analytic",
        "howler.api.v1.hit",
        "howler.api.v1.tool",
        "howler.services.analytic_service",
        "howler.services.hit_service",
        "howler.services.user_service",
    ]


@pytest.fixture(scope="function")
def mock_ds(monkeypatch, datastore_connection, namespaces_for_patch):
    original_collections = dict(datastore_connection.ds._collections)
    wrapped_collections = {}

    # Build and cache wrappers so writes are recorded while preserving datastore behavior.
    for index_name in SPY_INDEXES:
        real_collection = datastore_connection.get_collection(index_name)
        wrapped_collections[index_name] = SpyCollection(index_name=index_name, wrapped_collection=real_collection)

    datastore_connection.ds._collections = wrapped_collections

    for namespace in namespaces_for_patch:
        module = importlib.import_module(namespace)
        monkeypatch.setattr(module, "datastore", lambda: datastore_connection)

    yield datastore_connection

    datastore_connection.ds._collections = original_collections


def _clear_spy_history(datastore_connection):
    for collection in datastore_connection.ds._collections.values():
        if hasattr(collection, "write_call_args_history"):
            collection.write_call_args_history.clear()


def _get_spy_history(datastore_connection):
    history: list[dict[str, Any]] = []
    for collection in datastore_connection.ds._collections.values():
        if hasattr(collection, "write_call_args_history"):
            history.extend(collection.write_call_args_history)
    return history


def _assert_refresh_for_all_writes(
    datastore_connection,
    expected_refresh: str,
    expected_indexes: set[str],
    min_writes: int,
):
    history = _get_spy_history(datastore_connection)
    assert len(history) >= min_writes, f"Expected at least {min_writes} writes, got {len(history)}"

    indexes_written = {call["index"] for call in history}
    assert indexes_written == expected_indexes

    calls_without_expected_refresh = [call for call in history if call["refresh"] != expected_refresh]
    assert not calls_without_expected_refresh


def _assert_refresh_by_index(
    datastore_connection,
    expected_refresh_by_index: dict[str, str],
    expected_indexes: set[str],
    min_writes: int,
):
    history = _get_spy_history(datastore_connection)
    assert len(history) >= min_writes, f"Expected at least {min_writes} writes, got {len(history)}"

    indexes_written = {call["index"] for call in history}
    assert indexes_written == expected_indexes

    invalid_calls = [
        call
        for call in history
        if call["index"] in expected_refresh_by_index and call["refresh"] != expected_refresh_by_index[call["index"]]
    ]
    assert not invalid_calls


@pytest.fixture(scope="function")
def test_client(mock_ds):
    app.config.update({"TESTING": True})
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="function")
def refresh_param(request):
    mock_request = EnvironBuilder(
        method="GET", query_string={"refresh": request.param} if request.param is not None else {}
    )

    yield mock_request


@pytest.mark.parametrize(
    "refresh_param,expected",
    [
        ("true", "true"),
        ("TRUE", "true"),
        ("false", "false"),
        ("FALSE", "false"),
        ("wait_for", "wait_for"),
        ("WAIT_FOR", "wait_for"),
        (None, None),
    ],
    indirect=["refresh_param"],
)
def test_parse_wait_flag(test_client, refresh_param, expected):
    from howler.api.v1.utils.params import parse_refresh

    with test_client.application.request_context(refresh_param.get_environ()):
        from flask import request

        assert parse_refresh(request.args.get("refresh")) == expected


def test_parse_wait_flag_invalid(test_client):
    from howler.api.v1.utils.params import parse_refresh

    mock_request = EnvironBuilder(method="GET", query_string={"refresh": "invalid"})

    with test_client.application.request_context(mock_request.get_environ()):
        from flask import request

        with pytest.raises(HowlerInvalidParameterException):
            parse_refresh(request.args.get("refresh"))


def test_rule_refresh_forwards_all_writes(test_client, datastore_connection):
    endpoint = "/analytic/rules"
    method = "POST"
    entity_obj = _get_rw_model(Analytic)

    _clear_spy_history(datastore_connection)

    response = _build_request(
        test_client,
        endpoint=endpoint,
        method=method,
        data=json.dumps(
            {
                "name": entity_obj["name"],
                "description": entity_obj["description"],
                "rule": entity_obj["rule"],
                "rule_type": entity_obj["rule_type"],
                "rule_crontab": entity_obj["rule_crontab"],
            }
        ),
    )

    assert response.status_code == 200, response.data.decode("utf-8")
    _assert_refresh_for_all_writes(
        datastore_connection,
        expected_refresh="wait_for",
        expected_indexes={"analytic", "template"},
        min_writes=2,
    )


def test_bundle_put_refresh_forwards_all_writes(test_client, datastore_connection, hit_bundle_id):
    endpoint = "/hit/bundle/{id}"
    method = "PUT"

    _clear_spy_history(datastore_connection)

    response = _build_request(
        test_client,
        endpoint=endpoint.format(id=hit_bundle_id),
        method=method,
        data=json.dumps([]),
    )

    assert response.status_code == 200, response.data.decode("utf-8")
    _assert_refresh_for_all_writes(
        datastore_connection,
        expected_refresh="wait_for",
        expected_indexes={"hit"},
        min_writes=1,
    )


def test_hit_post_refresh_forwards_all_writes(test_client, datastore_connection, hit_list, monkeypatch):
    endpoint = "/hit"
    method = "POST"

    hit_module = importlib.import_module("howler.api.v1.hit")
    monkeypatch.setattr(hit_module, "DEBUG_FORCE_REFRESH", False)

    _clear_spy_history(datastore_connection)

    response = _build_request(
        test_client,
        endpoint=endpoint,
        method=method,
        data=json.dumps([hit.as_primitives() for hit in hit_list]),
    )

    assert response.status_code == 201, response.data.decode("utf-8")
    _assert_refresh_for_all_writes(
        datastore_connection,
        expected_refresh="wait_for",
        expected_indexes={"hit", "analytic"},
        min_writes=2,
    )


def test_hit_post_force_refresh_mixed_by_index(test_client, datastore_connection, hit_list, monkeypatch):
    endpoint = "/hit"
    method = "POST"

    hit_module = importlib.import_module("howler.api.v1.hit")
    monkeypatch.setattr(hit_module, "DEBUG_FORCE_REFRESH", True)

    _clear_spy_history(datastore_connection)

    response = _build_request(
        test_client,
        endpoint=endpoint,
        method=method,
        data=json.dumps([hit.as_primitives() for hit in hit_list]),
    )

    assert response.status_code == 201, response.data.decode("utf-8")
    _assert_refresh_by_index(
        datastore_connection,
        expected_refresh_by_index={"hit": "true", "analytic": "wait_for"},
        expected_indexes={"hit", "analytic"},
        min_writes=2,
    )


def test_bundle_post_refresh_forwards_all_writes(test_client, datastore_connection, hit_bundle, hit_ids):
    endpoint = "/hit/bundle"
    method = "POST"

    hit_bundle.howler.analytic = f"refresh-multi-bundle-{secrets.token_hex(6)}"

    _clear_spy_history(datastore_connection)

    response = _build_request(
        test_client,
        endpoint=endpoint,
        method=method,
        data=json.dumps({"bundle": hit_bundle.as_primitives(), "hits": hit_ids}),
    )

    assert response.status_code == 201, response.data.decode("utf-8")
    _assert_refresh_for_all_writes(
        datastore_connection,
        expected_refresh="wait_for",
        expected_indexes={"hit", "analytic"},
        min_writes=3,
    )


def test_bundle_delete_refresh_forwards_all_writes(test_client, datastore_connection, hit_bundle_id):
    endpoint = "/hit/bundle/{id}"
    method = "DELETE"

    _clear_spy_history(datastore_connection)

    response = _build_request(
        test_client,
        endpoint=endpoint.format(id=hit_bundle_id),
        method=method,
        data=json.dumps(["*"]),
    )

    assert response.status_code == 200, response.data.decode("utf-8")
    _assert_refresh_for_all_writes(
        datastore_connection,
        expected_refresh="wait_for",
        expected_indexes={"hit"},
        min_writes=1,
    )


def test_tool_hits_post_refresh_forwards_all_writes(
    test_client, datastore_connection, monkeypatch, tool_hit_field_map, tool_hit_raw_hit
):
    endpoint = "/tools/{tool_name}/hits"
    method = "POST"

    tool_module = importlib.import_module("howler.api.v1.tool")
    monkeypatch.setattr(tool_module, "DEBUG_FORCE_REFRESH", False)

    _clear_spy_history(datastore_connection)

    response = _build_request(
        test_client,
        endpoint=endpoint.format(tool_name="refresh-test-tool"),
        method=method,
        data=json.dumps({"map": tool_hit_field_map, "hits": [tool_hit_raw_hit]}),
    )

    assert response.status_code == 201, response.data.decode("utf-8")
    _assert_refresh_for_all_writes(
        datastore_connection,
        expected_refresh="wait_for",
        expected_indexes={"hit", "analytic"},
        min_writes=2,
    )


def test_tool_hits_post_force_refresh_mixed_by_index(
    test_client, datastore_connection, monkeypatch, tool_hit_field_map, tool_hit_raw_hit
):
    endpoint = "/tools/{tool_name}/hits"
    method = "POST"

    tool_module = importlib.import_module("howler.api.v1.tool")
    monkeypatch.setattr(tool_module, "DEBUG_FORCE_REFRESH", True)

    _clear_spy_history(datastore_connection)

    response = _build_request(
        test_client,
        endpoint=endpoint.format(tool_name="refresh-test-tool"),
        method=method,
        data=json.dumps({"map": tool_hit_field_map, "hits": [tool_hit_raw_hit]}),
    )

    assert response.status_code == 201, response.data.decode("utf-8")
    _assert_refresh_by_index(
        datastore_connection,
        expected_refresh_by_index={"hit": "true", "analytic": "wait_for"},
        expected_indexes={"hit", "analytic"},
        min_writes=2,
    )


def test_invalid_refresh_param(test_client):
    endpoint = "/analytic/rules"
    method = "POST"

    request = EnvironBuilder(
        path=f"/api/v1{endpoint}",
        method=method,
        query_string={"refresh": "invalid"},
        content_type="application/json",
        data=json.dumps({}),
        headers={"Authorization": _TEST_TOKEN},
    )
    response = test_client.open(request)

    assert response.status_code == 400
    assert b"Invalid refresh option" in response.data
