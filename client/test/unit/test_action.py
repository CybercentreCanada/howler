"""Unit tests for the action client module."""

from unittest.mock import MagicMock

from howler_client.module.action import Action


def _make_action_module() -> tuple[Action, MagicMock]:
    conn = MagicMock()
    return Action(conn), conn


class TestActionCall:
    def test_get_action_by_id(self):
        action, conn = _make_action_module()
        conn.get.return_value = {"action_id": "action-001", "name": "Test"}

        result = action("action-001")

        assert result["action_id"] == "action-001"
        conn.get.assert_called_once_with("api/v1/action/action-001")


class TestActionList:
    def test_list_gets_actions_endpoint(self):
        action, conn = _make_action_module()
        conn.get.return_value = [{"action_id": "action-001"}]

        result = action.list()

        assert result == [{"action_id": "action-001"}]
        conn.get.assert_called_once_with("api/v1/action/")


class TestActionCreate:
    def test_create_posts_action_data_with_refresh(self):
        action, conn = _make_action_module()
        data = {"name": "Label alerts", "query": "howler.id:*", "operations": []}
        conn.post.return_value = {"action_id": "action-001", **data}

        result = action.create(data, refresh="wait_for")

        assert result["action_id"] == "action-001"
        conn.post.assert_called_once_with("api/v1/action/?refresh=wait_for", json=data)


class TestActionExecute:
    def test_execute_posts_request_id_and_query(self):
        action, conn = _make_action_module()
        conn.post.return_value = {"add_label": []}

        result = action.execute("action-001", "request-001", "howler.id:alert-001")

        assert result == {"add_label": []}
        conn.post.assert_called_once_with(
            "api/v1/action/action-001/execute",
            json={"request_id": "request-001", "query": "howler.id:alert-001"},
        )

    def test_execute_uses_configured_query_when_not_overridden(self):
        action, conn = _make_action_module()
        conn.post.return_value = {"add_label": []}

        action.execute("action-001", "request-001")

        conn.post.assert_called_once_with(
            "api/v1/action/action-001/execute",
            json={"request_id": "request-001"},
        )
