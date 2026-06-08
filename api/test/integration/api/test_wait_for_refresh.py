"""Test that the endpoints which should accept a `wait` parameter properly forward it to the datastore call"""

import base64
import importlib
import json
from warnings import warn

import pytest
from werkzeug.test import EnvironBuilder

from howler.app import app
from howler.common import loader
from howler.common.exceptions import HowlerInvalidParameterException
from howler.datastore.collection import ESCollection
from howler.datastore.store import ESStore
from howler.odm import random_data
from howler.odm.models.action import Action
from howler.odm.models.analytic import Analytic
from howler.odm.models.dossier import Dossier
from howler.odm.models.hit import Hit
from howler.odm.models.overview import Overview
from howler.odm.models.template import Template
from howler.odm.models.user import User
from howler.odm.models.view import View
from howler.odm.randomizer import random_model_obj

_TEST_TOKEN = f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}"


def _flatten_test_data(test_data: tuple[tuple[str, tuple[str]]]):
    flattened = []
    for name, keys in test_data:
        flattened.extend((name, key) for key in keys)
    return tuple(flattened)


def _add_entity_name(flattened_test_data: list[tuple[str, str]]):
    return [(endpoint.split("/")[1], endpoint, method) for endpoint, method in flattened_test_data]


def _get_rw_model(model_class):
    model_obj = random_model_obj(model_class)

    # do not create read only objects
    if model_class == Analytic:
        model_obj.rule = "some rule"
        model_obj.rule_type = "lucene"
        model_obj.detections = ["Rule"]

    elif model_class == View:
        model_obj.type = "global"

    if model_obj.get("owner") is not None:
        model_obj.owner = "admin"

    return model_obj


def _get_request_data_obj(endpoint, index, method, entity_obj):
    # overrides for weird endpoints
    if endpoint == "/analytic/{id}/owner":
        return json.dumps({"username": "admin"})

    if method == "POST":
        if index == "analytic":
            return json.dumps(
                {
                    "name": entity_obj["name"],
                    "description": entity_obj["description"],
                    "rule": entity_obj["rule"],
                    "rule_type": entity_obj["rule_type"],
                    "rule_crontab": entity_obj["rule_crontab"],
                }
            )
    elif method in ("PUT", "PATCH"):
        if index == "template":
            return json.dumps(entity_obj["keys"])
        elif index == "dossier":
            return json.dumps(
                {
                    "title": entity_obj["title"],
                    "query": entity_obj["query"],
                }
            )
        elif index == "view":
            return json.dumps({k: v for k, v in entity_obj.as_primitives().items() if k not in ("owner", "view_id")})
        elif index == "user":
            return json.dumps(
                {
                    "is_active": entity_obj["is_active"],
                }
            )

    return entity_obj.json()


REFRESH_SUPPORTING_ENDPOINTS = (
    ("/action/{id}", ("DELETE", "PATCH", "PUT")),
    ("/action", ("POST",)),
    ("/analytic/{id}", ("DELETE", "PUT")),
    ("/analytic/rules", ("POST",)),
    ("/analytic/{id}/owner", ("POST",)),
    ("/dossier/{id}", ("DELETE", "PUT")),
    ("/dossier", ("POST",)),
    ("/overview/{id}", ("DELETE", "PUT")),
    ("/overview", ("POST",)),
    ("/template/{id}", ("DELETE", "PUT")),
    ("/template", ("POST",)),
    ("/user/{id}", ("DELETE", "PUT", "POST")),
    ("/view/{id}", ("DELETE", "PUT")),
    ("/view", ("POST",)),
)

# hit endpoints tested separately because they don't have the same request structure as the other entities
REFRESH_SUPPORTING_HIT_ENDPOINTS_EXPECT_HITS = (("/hit", ("POST",)),)

REFRESH_SUPPORTING_HIT_ENDPOINTS_EXPECT_SINGLE_HIT = (("/hit/{id}/overwrite", ("PUT",)),)

REFRESH_SUPPORTING_HIT_ENDPOINTS_EXPECT_IDS = (
    ("/hit", ("DELETE",)),
    ("/hit/bundle", ("POST",)),
    ("/hit/bundle/{id}", ("DELETE", "PUT")),
)

REFRESH_SUPPORTING_HIT_ENDPOINTS_EXPECT_OPERATIONS = (
    ("/hit/update", ("PUT",)),
    ("/hit/{id}/update", ("PUT",)),
)

REFRESH_SUPPORTING_HIT_TRANSITION_ENDPOINTS = (("/hit/{id}/transition", ("POST",)),)

REFRESH_SUPPORTING_HIT_LABEL_ENDPOINTS = (("/hit/{id}/labels/{label_set}", ("PUT", "DELETE")),)


class MockCollection(ESCollection):
    def __init__(self, datastore: ESStore, name, model_class=None, validate=True, max_attempts=10):
        self.write_call_args_history = []
        super().__init__(datastore, name, model_class, validate, max_attempts)

    def save(self, key, data, version=None, refresh=None):
        self.write_call_args_history.append({"key": key, "data": data, "version": version, "refresh": refresh})
        return super().save(key, data, version, refresh)

    def delete(self, key, refresh=None):
        self.write_call_args_history.append({"key": key, "refresh": refresh})
        return super().delete(key, refresh)

    def update(self, key, operations, version=None, refresh=None):
        self.write_call_args_history.append(
            {"key": key, "operations": operations, "version": version, "refresh": refresh}
        )
        return super().update(key, operations, version, refresh)

    def delete_by_query(self, query: str, sort=None, max_docs=None, refresh=None):
        self.write_call_args_history.append({"query": query, "sort": sort, "max_docs": max_docs, "refresh": refresh})
        return super().delete_by_query(query, sort, max_docs, refresh)

    def delete_by_search_object(self, query: dict, sort=None, max_docs=None, refresh=None):
        self.write_call_args_history.append({"query": query, "sort": sort, "max_docs": max_docs, "refresh": refresh})
        return super().delete_by_search_object(query, sort, max_docs, refresh)

    def update_by_query(self, query, operations, filters=None, access_control=None, max_docs=None, refresh=None):
        self.write_call_args_history.append(
            {
                "query": query,
                "operations": operations,
                "filters": filters,
                "access_control": access_control,
                "max_docs": max_docs,
                "refresh": refresh,
            }
        )
        return super().update_by_query(query, operations, filters, access_control, max_docs, refresh)


@pytest.fixture(scope="module")
def entity_names():
    return (
        ("action", Action),
        ("analytic", Analytic),
        ("dossier", Dossier),
        ("overview", Overview),
        ("template", Template),
        ("view", View),
        ("user", User),
        ("hit", Hit),
    )


@pytest.fixture(scope="function")
def entity_id(request, entity_names, datastore_connection):
    entity_name = request.param
    entity_class = dict(entity_names).get(entity_name)

    if entity_name == "user":
        random_data.wipe_users(datastore_connection)
        random_data.create_users(datastore_connection)
        entity_id = "shawn-h"
    else:
        try:
            c: ESCollection = datastore_connection.get_collection(entity_name)
            model_obj = _get_rw_model(entity_class)
            entity_id = model_obj[f"{entity_name}_id"]
            c.save(entity_id, model_obj)
            c.commit()
        except (AttributeError, KeyError) as e:
            warn(f"Skipping create entity {entity_name}: {e!r}")
            pytest.skip("No test entity created for this endpoint")

    yield entity_id

    try:
        c: ESCollection = datastore_connection.get_collection(entity_name)
        c.delete(entity_id)
        c.commit()
    except Exception as e:
        warn(f"Cleanup: failed to delete test entity {entity_name} with id {entity_id}: {e!r}")


@pytest.fixture(scope="function")
def hit_operations():
    return [
        ("SET", "howler.assignment", "user"),
    ]


@pytest.fixture(scope="function")
def hit_model(datastore_connection):
    lookups = loader.get_lookups()
    users = datastore_connection.user.search("*:*")["items"]
    hit = random_data.generate_useful_hit(lookups=lookups, users=users, prune_hit=False)
    hit.howler.labels = {"generic": ["initial_label"]}
    return hit


@pytest.fixture(scope="function")
def hit_id(hit_model: Hit, datastore_connection):
    datastore_connection.hit.save(hit_model.howler.id, hit_model)
    datastore_connection.hit.commit()
    yield hit_model.howler.id
    try:
        datastore_connection.hit.delete(hit_model.howler.id)
        datastore_connection.hit.commit()
    except Exception as e:
        warn(f"Cleanup: failed to delete test hit with id {hit_model.howler.id}: {e!r}")


@pytest.fixture(scope="function")
def hit_list(datastore_connection):
    hits = []
    for _ in range(5):
        lookups = loader.get_lookups()
        users = datastore_connection.user.search("*:*")["items"]
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
def namespaces_for_patch(entity_names):
    return [f"howler.api.v1.{entity_name}" for entity_name, _ in entity_names] + [
        "howler.services.dossier_service",
        "howler.services.user_service",
        "howler.services.hit_service",
    ]


@pytest.fixture(scope="function")
def mock_ds(monkeypatch, datastore_connection, entity_names, namespaces_for_patch):
    collections = {
        entity_name: MockCollection(datastore_connection.ds, entity_name, model_class=entity_class)
        for entity_name, entity_class in entity_names
    }
    original_collections = datastore_connection.ds._collections
    datastore_connection.ds._collections = collections
    for namespace in namespaces_for_patch:
        module = importlib.import_module(namespace)
        monkeypatch.setattr(module, "datastore", lambda: datastore_connection)
    yield datastore_connection
    datastore_connection.ds._collections = original_collections


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


@pytest.mark.parametrize(
    "entity_id,endpoint,method",
    _add_entity_name(_flatten_test_data(REFRESH_SUPPORTING_ENDPOINTS)),
    indirect=["entity_id"],
)
def test_wait_param_forwarded_to_es(
    test_client, endpoint: str, method: str, datastore_connection, entity_id, entity_names
):
    entity_name_dict = dict(entity_names)
    index = endpoint.split("/")[1]

    entity_class = entity_name_dict.get(index)

    if index not in entity_name_dict:
        pytest.skip(f"Unimplemented mock collection for index {index}")

    entity_obj = _get_rw_model(entity_class)

    templated_endpoint = endpoint
    if "{id}" in endpoint:
        if not entity_id:
            pytest.skip("No test entity created for this endpoint")

        if index == "user" and method == "POST":
            # new user to test creation
            entity_id = "new-test-user"

        templated_endpoint = endpoint.format(id=entity_id)
        entity_obj["uname" if index == "user" else f"{index}_id"] = entity_id

    request = EnvironBuilder(
        path=f"/api/v1{templated_endpoint}",
        method=method,
        query_string={"refresh": "wait_for"},
        content_type="application/json",
        data=_get_request_data_obj(endpoint, index, method, entity_obj),
        headers={"Authorization": _TEST_TOKEN},
    )

    response = test_client.open(request)

    assert response.status_code in (200, 201, 204)
    assert datastore_connection.get_collection(index).write_call_args_history[-1]["refresh"] == "wait_for"


@pytest.mark.parametrize(
    "endpoint,method",
    _flatten_test_data(REFRESH_SUPPORTING_HIT_ENDPOINTS_EXPECT_HITS),
)
def test_wait_param_forwarded_to_es_hits_expect_hits(
    endpoint: str, method: str, test_client, datastore_connection, hit_list
):
    request = EnvironBuilder(
        path=f"/api/v1{endpoint}",
        method=method,
        query_string={"refresh": "wait_for"},
        content_type="application/json",
        data=json.dumps([hit.as_primitives() for hit in hit_list]),
        headers={"Authorization": _TEST_TOKEN},
    )

    response = test_client.open(request)

    assert response.status_code in (200, 201, 204)
    assert datastore_connection.hit.write_call_args_history[-1]["refresh"] == "wait_for"


@pytest.mark.parametrize(
    "endpoint,method",
    _flatten_test_data(REFRESH_SUPPORTING_HIT_ENDPOINTS_EXPECT_SINGLE_HIT),
)
def test_wait_param_forwarded_to_es_hits_expect_single_hit(
    endpoint: str, method: str, test_client, datastore_connection, hit_id, hit_model
):
    request = EnvironBuilder(
        path=f"/api/v1{endpoint.format(id=hit_id) if '{id}' in endpoint else endpoint}",
        method=method,
        query_string={"refresh": "wait_for"},
        content_type="application/json",
        data=hit_model.json(),
        headers={"Authorization": _TEST_TOKEN},
    )

    response = test_client.open(request)

    assert response.status_code in (200, 201, 204)
    assert datastore_connection.hit.write_call_args_history[-1]["refresh"] == "wait_for"


@pytest.mark.parametrize(
    "endpoint,method",
    _flatten_test_data(REFRESH_SUPPORTING_HIT_ENDPOINTS_EXPECT_IDS),
)
def test_wait_param_forwarded_to_es_hits_expect_ids(
    endpoint: str, method: str, test_client, datastore_connection, hit_ids, hit_bundle_id, hit_model
):

    if "bundle" in endpoint:
        if "{id}" in endpoint:
            endpoint = endpoint.format(id=hit_bundle_id)
            request_data = []

        else:
            request_data = {
                "bundle": hit_model.as_primitives(),
                "hits": hit_ids,
            }
    else:
        request_data = hit_ids

    request = EnvironBuilder(
        path=f"/api/v1{endpoint}",
        method=method,
        query_string={"refresh": "wait_for"},
        content_type="application/json",
        data=json.dumps(request_data),
        headers={"Authorization": _TEST_TOKEN},
    )

    response = test_client.open(request)

    assert response.status_code in (200, 201, 204)
    assert datastore_connection.hit.write_call_args_history[-1]["refresh"] == "wait_for"


@pytest.mark.parametrize(
    "endpoint,method",
    _flatten_test_data(REFRESH_SUPPORTING_HIT_ENDPOINTS_EXPECT_OPERATIONS),
)
def test_wait_param_forwarded_to_es_hits_expect_operations(
    endpoint: str, method: str, test_client, datastore_connection, hit_id, hit_operations
):
    if "{id}" in endpoint:
        endpoint = endpoint.format(id=hit_id)
        request_data = hit_operations
    else:
        request_data = {"query": {"ids": hit_id}, "operations": hit_operations}

    request = EnvironBuilder(
        path=f"/api/v1{endpoint}",
        method=method,
        query_string={"refresh": "wait_for"},
        content_type="application/json",
        data=json.dumps(request_data),
        headers={"Authorization": _TEST_TOKEN},
    )

    response = test_client.open(request)

    assert response.status_code in (200, 201, 204)
    assert datastore_connection.hit.write_call_args_history[-1]["refresh"] == "wait_for"


@pytest.mark.parametrize(
    "endpoint,method",
    _flatten_test_data(REFRESH_SUPPORTING_HIT_TRANSITION_ENDPOINTS),
)
def test_wait_param_forwarded_to_es_hits_transition(
    endpoint: str, method: str, test_client, datastore_connection, hit_id
):
    request_data = {"transition": "assign_to_me", "data": {}}

    request = EnvironBuilder(
        path=f"/api/v1{endpoint.format(id=hit_id)}",
        method=method,
        query_string={"refresh": "wait_for"},
        content_type="application/json",
        data=json.dumps(request_data),
        headers={"Authorization": _TEST_TOKEN},
    )

    response = test_client.open(request)

    assert response.status_code in (200, 201, 204)
    assert datastore_connection.hit.write_call_args_history[-1]["refresh"] == "wait_for"


@pytest.mark.parametrize(
    "endpoint,method",
    _flatten_test_data(REFRESH_SUPPORTING_HIT_LABEL_ENDPOINTS),
)
def test_wait_param_forwarded_to_es_hits_labels(endpoint: str, method: str, test_client, datastore_connection, hit_id):

    request = EnvironBuilder(
        path=f"/api/v1{endpoint.format(id=hit_id, label_set='generic')}",
        method=method,
        query_string={"refresh": "wait_for"},
        content_type="application/json",
        data=json.dumps({"value": ["initial_label" if method == "DELETE" else "test_label"]}),
        headers={"Authorization": _TEST_TOKEN},
    )

    response = test_client.open(request)

    assert response.status_code in (200, 201, 204)
    assert datastore_connection.hit.write_call_args_history[-1]["refresh"] == "wait_for"
