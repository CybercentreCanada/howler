"""Action execution reads embedded operations from finalized Pydantic models."""

from unittest.mock import MagicMock, patch

from howler.models.action import Action
from howler.models.user import User
from howler.services import action_service


def test_bulk_execute_uses_typed_operation_json():
    action = Action.validate_howler(
        {
            "action_id": "action-1",
            "owner_id": "user-1",
            "name": "Label hits",
            "query": "howler.status:open",
            "triggers": ["create"],
            "operations": [{"operation_id": "add_label", "data_json": '{"label": "triage"}'}],
        }
    )
    user = User.validate_howler({"uname": "user-1", "name": "User", "password": "hash"})
    storage = MagicMock()
    storage.action.search.return_value = {"items": [action]}
    storage.hit.search.return_value = {"total": 1}

    with (
        patch.object(action_service, "datastore", return_value=storage),
        patch.object(action_service, "audit"),
        patch.object(action_service.actions, "execute", return_value=[]) as execute,
    ):
        action_service.bulk_execute_on_query("howler.id:hit-1", user=user)

    execute.assert_called_once_with(
        operation_id="add_label",
        query="(howler.id:hit-1) AND (howler.status:open)",
        user=user,
        label="triage",
    )
