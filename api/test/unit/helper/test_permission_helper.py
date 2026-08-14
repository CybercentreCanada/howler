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

    user_collection = MagicMock()
    user_collection.get_if_exists.return_value = MagicMock()

    def mock_datastore():
        store = {"dummyownership": collection, "user": user_collection}
        return store

    set_privilege_mock = MagicMock(side_effect=[(True, obj), (True, obj)])

    monkeypatch.setattr(permission_helper, "datastore", mock_datastore)
    monkeypatch.setattr(permission_helper, "set_privilege", set_privilege_mock)

    with request_context.test_request_context():
        result = permission_helper.give_multi_privilege(
            "dummy-id",
            user,
            DummyOwnership,
            {"privilege": "members", "user_id": ["user1", " user2 "]},
            refresh="wait_for",
        )

    assert result == {"dummyownership_id": "dummy-id"}
    assert set_privilege_mock.call_count == 2
    assert set_privilege_mock.call_args_list[0].args == ("members", "user1", obj, user)
    assert set_privilege_mock.call_args_list[1].args == ("members", "user2", obj, user)
    collection.save.assert_called_once_with("dummy-id", obj, refresh="wait_for")


def test_give_multi_privilege_requires_user_id_list(request_context):
    with request_context.test_request_context():
        with pytest.raises(InvalidDataException, match="The key 'user_id' must be a non-empty list."):
            permission_helper.give_multi_privilege(
                "dummy-id",
                MagicMock(),
                DummyOwnership,
                {"privilege": "members", "user_id": "user1"},
                refresh="true",
            )


def test_give_multi_privilege_returns_not_found(request_context, monkeypatch):
    collection = MagicMock()
    collection.get_if_exists.return_value = None

    monkeypatch.setattr(permission_helper, "datastore", lambda: {"dummyownership": collection})

    with request_context.test_request_context():
        with pytest.raises(InvalidDataException, match="does not exist"):
            permission_helper.give_multi_privilege(
                "missing-id", MagicMock(), DummyOwnership, {"privilege": "members", "user_id": ["user1"]}, "true"
            )


def test_give_multi_privilege_maps_invalid_data_exception(request_context, monkeypatch):
    obj = DummyOwnership()
    collection = MagicMock()
    collection.get_if_exists.return_value = obj

    user_collection = MagicMock()
    user_collection.get_if_exists.return_value = MagicMock()

    def mock_datastore():
        store = {"dummyownership": collection, "user": user_collection}
        return store

    def _raise_invalid_data(*args, **kwargs):
        raise InvalidDataException("bad payload")

    monkeypatch.setattr(permission_helper, "datastore", mock_datastore)
    monkeypatch.setattr(permission_helper, "set_privilege", _raise_invalid_data)

    with request_context.test_request_context():
        with pytest.raises(InvalidDataException, match="bad payload"):
            permission_helper.give_multi_privilege(
                "dummy-id", MagicMock(), DummyOwnership, {"privilege": "members", "user_id": ["user1"]}, "true"
            )
