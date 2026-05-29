"""Test that the endpoints which should accept a `wait` parameter properly forward it to the datastore call"""

import base64
import importlib
from warnings import warn

import pytest
from werkzeug.test import EnvironBuilder

from howler.app import app
from howler.datastore.collection import ESCollection
from howler.datastore.store import ESStore
from howler.odm.models.action import Action
from howler.odm.models.analytic import Analytic
from howler.odm.models.dossier import Dossier
from howler.odm.models.overview import Overview
from howler.odm.models.template import Template
from howler.odm.models.view import View
from howler.odm.randomizer import random_model_obj


def _flatten_test_data(test_data: tuple[tuple[str, tuple[str]]]):
    flattened = []
    for name, keys in test_data:
        flattened.extend((name, key) for key in keys)
    return tuple(flattened)


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


WAIT_SUPPORTING_ENDPOINTS = (
    ("/action/{id}", ("DELETE",)),
    ("/analytic/{id}", ("DELETE",)),
    ("/dossier/{id}", ("DELETE",)),
    ("/overview/{id}", ("DELETE",)),
    ("/template/{id}", ("DELETE",)),
    ("/view/{id}", ("DELETE",)),
)


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


@pytest.fixture(scope="module")
def entity_names():
    return (
        ("action", Action),
        ("analytic", Analytic),
        ("dossier", Dossier),
        ("overview", Overview),
        ("template", Template),
        ("view", View),
    )


@pytest.fixture(scope="function")
def entity_ids(entity_names, datastore_connection):
    ids = {}

    for entity_name, entity_class in entity_names:
        try:
            c: ESCollection = datastore_connection.get_collection(entity_name)
            model_obj = _get_rw_model(entity_class)
            entity_id = model_obj[f"{entity_name}_id"]
            c.save(entity_id, model_obj)
            c.commit()
            ids[entity_name] = entity_id
        except AttributeError as e:
            warn(f"Skipping create entity {entity_name}: {e!r}")
            continue

    yield ids

    for entity_name, entity_id in ids.items():
        try:
            c: ESCollection = datastore_connection.get_collection(entity_name)
            c.delete(entity_id)
            c.commit()
        except Exception as e:
            warn(f"Cleanup: failed to delete test entity {entity_name} with id {entity_id}: {e!r}")


@pytest.fixture(scope="function")
def mock_ds(monkeypatch, datastore_connection, entity_names):
    collections = {
        entity_name: MockCollection(datastore_connection.ds, entity_name, model_class=entity_class)
        for entity_name, entity_class in entity_names
    }
    original_collections = datastore_connection.ds._collections
    datastore_connection.ds._collections = collections
    for entity_name, _ in entity_names:
        module = importlib.import_module(f"howler.api.v1.{entity_name}")
        monkeypatch.setattr(module, "datastore", lambda: datastore_connection)
    yield datastore_connection
    datastore_connection.ds._collections = original_collections


@pytest.fixture(scope="function")
def test_client(mock_ds):
    app.config.update({"TESTING": True})
    with app.test_client() as client:
        yield client


@pytest.fixture(scope="function")
def wait_flag(request):
    mock_request = EnvironBuilder(
        method="GET", query_string={"wait": request.param} if request.param is not None else {}
    )

    yield mock_request


@pytest.mark.parametrize(
    "wait_flag,expected",
    [
        ("true", "wait_for"),
        ("TRUE", "wait_for"),
        ("tRue", "wait_for"),
        ("false", None),
        ("invalid", None),
        (None, None),
    ],
    indirect=["wait_flag"],
)
def test_parse_wait_flag(test_client, wait_flag, expected):
    from howler.api.v1.utils.string_utils import parse_wait_flag

    with test_client.application.request_context(wait_flag.get_environ()):
        assert parse_wait_flag() == expected


@pytest.mark.parametrize("endpoint,method", _flatten_test_data(WAIT_SUPPORTING_ENDPOINTS))
def test_wait_param_forwarded_to_es(test_client, endpoint: str, method: str, datastore_connection, entity_ids):
    index = endpoint.split("/")[1]
    entity_id = entity_ids.get(index)

    if "{id}" in endpoint:
        if not entity_id:
            pytest.skip("No test entity created for this endpoint")

        endpoint = endpoint.format(id=entity_id)

    request = EnvironBuilder(
        path=f"/api/v1{endpoint}",
        method=method,
        query_string={"wait": "true"},
        headers={"Authorization": f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}"},
    )

    response = test_client.open(request)

    assert response.status_code == 204
    assert datastore_connection.get_collection(index).write_call_args_history[-1]["refresh"] == "wait_for"


@pytest.mark.parametrize("endpoint,method", _flatten_test_data(WAIT_SUPPORTING_ENDPOINTS))
def test_no_wait_no_refresh_arg(test_client, endpoint: str, method: str, datastore_connection, entity_ids):
    index = endpoint.split("/")[1]
    entity_id = entity_ids.get(index)

    if "{id}" in endpoint:
        if not entity_id:
            pytest.skip("No test entity created for this endpoint")

        endpoint = endpoint.format(id=entity_id)

    request = EnvironBuilder(
        path=f"/api/v1{endpoint}",
        method=method,
        headers={"Authorization": f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}"},
    )

    response = test_client.open(request)

    assert response.status_code == 204
    assert datastore_connection.get_collection(index).write_call_args_history[-1]["refresh"] is None
