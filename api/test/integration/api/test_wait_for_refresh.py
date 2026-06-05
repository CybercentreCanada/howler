"""Test that the endpoints which should accept a `wait` parameter properly forward it to the datastore call"""

import base64
import importlib
import json
from warnings import warn

import pytest
from werkzeug.test import EnvironBuilder

from howler.app import app
from howler.common.exceptions import HowlerInvalidParameterException
from howler.datastore.collection import ESCollection
from howler.datastore.store import ESStore
from howler.odm import random_data
from howler.odm.models.action import Action
from howler.odm.models.analytic import Analytic
from howler.odm.models.dossier import Dossier
from howler.odm.models.overview import Overview
from howler.odm.models.template import Template
from howler.odm.models.user import User
from howler.odm.models.view import View
from howler.odm.randomizer import random_model_obj


def _flatten_test_data(test_data: tuple[tuple[str, tuple[str]]]):
    flattened = []
    for name, keys in test_data:
        flattened.extend((name, key, name.split("/")[1]) for key in keys)
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


def _get_request_data_obj(index, method, entity_obj):
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
    ("/dossier/{id}", ("DELETE", "PUT")),
    ("/dossier", ("POST",)),
    ("/hit", ("POST", "DELETE")),
    ("/hit/update", ("PUT",)),
    ("/hit/bundle", ("POST",)),
    ("/hit/bundle/{id}", ("DELETE", "PUT")),
    ("/hit/{id}/overwrite", ("PUT",)),
    ("/hit/{id}/transition", ("PUT",)),
    ("/hit/{id}/update", ("PUT",)),
    ("/hit/{id}/labels/{label_set}", ("PUT", "DELETE")),
    ("/overview/{id}", ("DELETE", "PUT")),
    ("/overview", ("POST",)),
    ("/template/{id}", ("DELETE", "PUT")),
    ("/template", ("POST",)),
    ("/tool/{id}/hits", ("POST", "PUT")),
    ("/user/{id}", ("DELETE", "PUT", "POST")),
    ("/view/{id}", ("DELETE", "PUT")),
    ("/view", ("POST",)),
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

    def update(self, key, operations, version=None, refresh=None):
        self.write_call_args_history.append(
            {"key": key, "operations": operations, "version": version, "refresh": refresh}
        )
        return super().update(key, operations, version, refresh)


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
def namespaces_for_patch(entity_names):
    return [f"howler.api.v1.{entity_name}" for entity_name, _ in entity_names] + [
        "howler.services.dossier_service",
        "howler.services.user_service",
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
    "endpoint,method,entity_id", _flatten_test_data(REFRESH_SUPPORTING_ENDPOINTS), indirect=["entity_id"]
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

    if "{id}" in endpoint:
        if not entity_id:
            pytest.skip("No test entity created for this endpoint")

        endpoint = endpoint.format(id=entity_id)
        entity_obj["uname" if index == "user" else f"{index}_id"] = entity_id

    request = EnvironBuilder(
        path=f"/api/v1{endpoint}",
        method=method,
        query_string={"refresh": "wait_for"},
        content_type="application/json",
        data=_get_request_data_obj(index, method, entity_obj),
        headers={"Authorization": f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}"},
    )

    response = test_client.open(request)

    assert response.status_code in (200, 201, 204)
    assert datastore_connection.get_collection(index).write_call_args_history[-1]["refresh"] == "wait_for"


@pytest.mark.parametrize(
    "endpoint,method,entity_id", _flatten_test_data(REFRESH_SUPPORTING_ENDPOINTS), indirect=["entity_id"]
)
def test_no_wait_no_refresh_arg(test_client, endpoint: str, method: str, datastore_connection, entity_id):
    index = endpoint.split("/")[1]

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
