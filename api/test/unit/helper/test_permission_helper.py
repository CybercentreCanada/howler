from unittest.mock import MagicMock

import pytest
from flask import Flask

from howler.api.v1.helper import permission_helper
from howler.common.exceptions import InvalidDataException


class DummyOwnership:
    def __init__(self):
        self.dummyownership_id = "dummy-id"

    def as_primitives(self):
        return {"dummyownership_id": self.dummyownership_id}


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test")

    return app


def test_give_multi_privilege_success(request_context, monkeypatch):
    user = MagicMock()
    obj = DummyOwnership()
    collection = MagicMock()
    collection.get_if_exists.return_value = obj

    set_privilege = MagicMock(side_effect=[(True, obj), (True, obj)])

    monkeypatch.setattr(permission_helper, "datastore", lambda: {"dummyownership": collection})
    monkeypatch.setattr(permission_helper.permission_service, "set_privilege", set_privilege)

    with request_context.test_request_context():
        response = permission_helper.give_multi_privilege(
            "dummy-id",
            user,
            DummyOwnership,
            {"privilege": "members", "user_id": ["user1", " user2 "]},
            refresh="wait_for",
        )

    assert response.status_code == 200
    assert set_privilege.call_count == 2
    assert set_privilege.call_args_list[0].args == ("members", "user1", obj, user)
    assert set_privilege.call_args_list[1].args == ("members", "user2", obj, user)
    collection.save.assert_called_once_with("dummy-id", obj, refresh="wait_for")


def test_give_multi_privilege_requires_user_id_list(request_context):
    with request_context.test_request_context():
        response = permission_helper.give_multi_privilege(
            "dummy-id",
            MagicMock(),
            DummyOwnership,
            {"privilege": "members", "user_id": "user1"},
            refresh="true",
        )

    assert response.status_code == 400
    assert response.json["api_error_message"] == "The key 'user_id' must be a non-empty list."


def test_give_multi_privilege_returns_not_found(request_context, monkeypatch):
    collection = MagicMock()
    collection.get_if_exists.return_value = None

    monkeypatch.setattr(permission_helper, "datastore", lambda: {"dummyownership": collection})

    with request_context.test_request_context():
        response = permission_helper.give_multi_privilege(
            "missing-id", MagicMock(), DummyOwnership, {"privilege": "members", "user_id": ["user1"]}, "true"
        )

    assert response.status_code == 404


def test_give_multi_privilege_maps_invalid_data_exception(request_context, monkeypatch):
    obj = DummyOwnership()
    collection = MagicMock()
    collection.get_if_exists.return_value = obj

    def _raise_invalid_data(*args, **kwargs):
        raise InvalidDataException("bad payload")

    monkeypatch.setattr(permission_helper, "datastore", lambda: {"dummyownership": collection})
    monkeypatch.setattr(permission_helper.permission_service, "set_privilege", _raise_invalid_data)

    with request_context.test_request_context():
        response = permission_helper.give_multi_privilege(
            "dummy-id", MagicMock(), DummyOwnership, {"privilege": "members", "user_id": ["user1"]}, "true"
        )

    assert response.status_code == 400
    assert response.json["api_error_message"] == "bad payload"
