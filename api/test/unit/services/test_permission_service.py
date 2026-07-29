from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Flask

from howler.common.exceptions import InvalidDataException
from howler.services import permission_service


class DummyOwnership:
    def __init__(self, *, owner="owner", admins=None, members=None):
        self.dummyownership_id = "dummy-id"
        self.owner = owner
        self.admins = admins or []
        self.members = members or []
        self.permissions = {"admins": self.admins, "members": self.members}

    def __getitem__(self, privilege):
        return self.permissions[privilege]

    def as_primitives(self):
        return {
            "dummyownership_id": self.dummyownership_id,
            "owner": self.owner,
            "admins": self.admins,
            "members": self.members,
        }


@pytest.fixture(scope="module")
def app():
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test")

    return app


def make_user(uname="owner", user_types=None):
    return SimpleNamespace(uname=uname, type=user_types or [])


def mock_datastore(monkeypatch, ownership):
    collection = MagicMock()
    collection.get.return_value = ownership

    user_collection = MagicMock()
    user_collection.exists.return_value = True

    storage = MagicMock()
    storage.__getitem__.side_effect = lambda index: collection
    storage.user = user_collection
    monkeypatch.setattr(permission_service, "datastore", lambda: storage)

    return collection, user_collection


def test_is_allowed_to_change_allows_global_admin():
    assert permission_service._is_allowed_to_change("owner", make_user("analyst", ["admin"]), DummyOwnership())


def test_is_allowed_to_change_rejects_user_without_object_privileges():
    assert not permission_service._is_allowed_to_change("members", make_user("analyst"), DummyOwnership())


def test_is_allowed_to_change_rejects_local_admin_owner_transfer():
    ownership = DummyOwnership(admins=["admin"])

    assert not permission_service._is_allowed_to_change("owner", make_user("admin"), ownership)


def test_is_allowed_to_change_allows_owner_and_local_admin_updates():
    ownership = DummyOwnership(admins=["admin"])

    assert permission_service._is_allowed_to_change("owner", make_user(), ownership)
    assert permission_service._is_allowed_to_change("members", make_user("admin"), ownership)


def test_build_permissions_request_returns_valid_payload(app):
    with app.test_request_context(json={"privilege": "members", "user_ids": ["analyst"]}):
        permission_request = permission_service._build_permissions_request()

    assert permission_request.privilege == "members"
    assert permission_request.user_ids == ["analyst"]


def test_build_permissions_request_rejects_non_object_payload(app):
    with app.test_request_context(json=["not", "an", "object"]):
        with pytest.raises(InvalidDataException, match="Request body must be a JSON object"):
            permission_service._build_permissions_request()


def test_build_permissions_request_maps_model_validation_errors(app, monkeypatch):
    def raise_value_error(payload):
        raise ValueError("invalid payload")

    monkeypatch.setattr(permission_service, "PermissionRequest", raise_value_error)

    with app.test_request_context(json={"privilege": "members", "user_ids": ["analyst"]}):
        with pytest.raises(InvalidDataException, match="invalid payload"):
            permission_service._build_permissions_request()


def test_give_privilege_rejects_missing_object(app, monkeypatch):
    collection, _ = mock_datastore(monkeypatch, None)

    with app.test_request_context(json={"privilege": "members", "user_ids": ["analyst"]}):
        with pytest.raises(InvalidDataException, match="Dummyownership dummy-id does not exist"):
            permission_service.give_privilege("dummy-id", make_user(), DummyOwnership)

    collection.save.assert_not_called()


def test_give_privilege_rejects_unauthorized_requester(app, monkeypatch):
    ownership = DummyOwnership()
    collection, _ = mock_datastore(monkeypatch, ownership)

    with app.test_request_context(json={"privilege": "members", "user_ids": ["analyst"]}):
        with pytest.raises(InvalidDataException, match="not allowed"):
            permission_service.give_privilege("dummy-id", make_user("other"), DummyOwnership)

    collection.save.assert_not_called()


def test_give_privilege_requires_one_owner(app, monkeypatch):
    ownership = DummyOwnership()
    collection, _ = mock_datastore(monkeypatch, ownership)

    with app.test_request_context(json={"privilege": "owner", "user_ids": ["one", "two"]}):
        with pytest.raises(InvalidDataException, match="must be a single entry"):
            permission_service.give_privilege("dummy-id", make_user(), DummyOwnership)

    collection.save.assert_not_called()


def test_give_privilege_transfers_owner(app, monkeypatch):
    ownership = DummyOwnership()
    collection, _ = mock_datastore(monkeypatch, ownership)

    with app.test_request_context(json={"privilege": "owner", "user_ids": ["new-owner"]}):
        result = permission_service.give_privilege("dummy-id", make_user(), DummyOwnership, refresh="wait_for")

    assert result["owner"] == "new-owner"
    collection.save.assert_called_once_with("dummy-id", ownership, refresh="wait_for")


@pytest.mark.parametrize(
    ("existing_members", "user_exists", "expected_message"),
    [
        ([], False, "User analyst does not exist"),
        (["analyst"], True, "User analyst already has permission members"),
    ],
)
def test_give_privilege_rejects_invalid_batch_entries(
    app, monkeypatch, existing_members, user_exists, expected_message
):
    ownership = DummyOwnership(members=existing_members)
    collection, user_collection = mock_datastore(monkeypatch, ownership)
    user_collection.exists.return_value = user_exists

    with app.test_request_context(json={"privilege": "members", "user_ids": ["analyst"]}):
        with pytest.raises(InvalidDataException, match=expected_message):
            permission_service.give_privilege("dummy-id", make_user(), DummyOwnership)

    collection.save.assert_not_called()


def test_give_privilege_adds_multiple_users_after_validating_batch(app, monkeypatch):
    ownership = DummyOwnership()
    collection, _ = mock_datastore(monkeypatch, ownership)

    with app.test_request_context(json={"privilege": "members", "user_ids": ["one", "two"]}):
        result = permission_service.give_privilege("dummy-id", make_user(), DummyOwnership, refresh="true")

    assert result["members"] == ["one", "two"]
    collection.save.assert_called_once_with("dummy-id", ownership, refresh="true")


def test_remove_privilege_rejects_missing_object(app, monkeypatch):
    collection, _ = mock_datastore(monkeypatch, None)

    with app.test_request_context(json={"privilege": "members", "user_ids": ["analyst"]}):
        with pytest.raises(InvalidDataException, match="Dummyownership dummy-id does not exist"):
            permission_service.remove_privilege("dummy-id", make_user(), DummyOwnership)

    collection.save.assert_not_called()


def test_remove_privilege_rejects_unauthorized_requester(app, monkeypatch):
    ownership = DummyOwnership(members=["analyst"])
    collection, _ = mock_datastore(monkeypatch, ownership)

    with app.test_request_context(json={"privilege": "members", "user_ids": ["analyst"]}):
        with pytest.raises(InvalidDataException, match="not allowed"):
            permission_service.remove_privilege("dummy-id", make_user("other"), DummyOwnership)

    collection.save.assert_not_called()


def test_remove_privilege_rejects_owner_removal(app, monkeypatch):
    ownership = DummyOwnership()
    collection, _ = mock_datastore(monkeypatch, ownership)

    with app.test_request_context(json={"privilege": "owner", "user_ids": ["owner"]}):
        with pytest.raises(InvalidDataException, match="Only transfer is allowed"):
            permission_service.remove_privilege("dummy-id", make_user(), DummyOwnership)

    collection.save.assert_not_called()


@pytest.mark.parametrize(
    ("privilege", "ownership"),
    [
        ("admins", DummyOwnership(admins=[])),
        ("members", DummyOwnership(members=[])),
    ],
)
def test_remove_privilege_requires_existing_privilege(app, monkeypatch, privilege, ownership):
    collection, _ = mock_datastore(monkeypatch, ownership)

    with app.test_request_context(json={"privilege": privilege, "user_ids": ["analyst"]}):
        with pytest.raises(InvalidDataException, match=f"does not have the '{privilege}' privilege"):
            permission_service.remove_privilege("dummy-id", make_user(), DummyOwnership)

    collection.save.assert_not_called()


def test_remove_privilege_rejects_missing_target_user_without_saving(app, monkeypatch):
    ownership = DummyOwnership(members=["analyst"])
    collection, user_collection = mock_datastore(monkeypatch, ownership)
    user_collection.exists.return_value = False

    with app.test_request_context(json={"privilege": "members", "user_ids": ["analyst"]}):
        with pytest.raises(InvalidDataException, match="User analyst does not exist"):
            permission_service.remove_privilege("dummy-id", make_user(), DummyOwnership)

    collection.save.assert_not_called()


def test_remove_privilege_rejects_inconsistent_privilege_lookup(app, monkeypatch):
    ownership = DummyOwnership(members=["analyst"])
    ownership.permissions["members"] = []
    collection, _ = mock_datastore(monkeypatch, ownership)

    with app.test_request_context(json={"privilege": "members", "user_ids": ["analyst"]}):
        with pytest.raises(InvalidDataException, match="User analyst does not have permission members"):
            permission_service.remove_privilege("dummy-id", make_user(), DummyOwnership)

    collection.save.assert_not_called()


@pytest.mark.parametrize("privilege", ["admins", "members"])
def test_remove_privilege_removes_users_and_saves(app, monkeypatch, privilege):
    ownership = DummyOwnership(
        admins=["analyst"] if privilege == "admins" else [],
        members=["analyst"] if privilege == "members" else [],
    )
    collection, _ = mock_datastore(monkeypatch, ownership)

    with app.test_request_context(json={"privilege": privilege, "user_ids": ["analyst"]}):
        result = permission_service.remove_privilege("dummy-id", make_user(), DummyOwnership, refresh="wait_for")

    assert result[privilege] == []
    collection.save.assert_called_once_with("dummy-id", ownership, refresh="wait_for")
