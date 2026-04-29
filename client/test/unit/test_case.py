"""Unit tests for the v2 Case client module."""

from unittest.mock import MagicMock

from howler_client.module.v2.case import Case


def _make_case_module() -> tuple[Case, MagicMock]:
    conn = MagicMock()
    return Case(conn), conn


class TestCaseCall:
    def test_get_case_by_id(self):
        case, conn = _make_case_module()
        conn.get.return_value = {"case_id": "case-001", "title": "Test"}

        result = case("case-001")

        assert result["case_id"] == "case-001"
        conn.get.assert_called_once()
        assert "case/case-001" in conn.get.call_args[0][0]
        assert "v2" in conn.get.call_args[0][0]


class TestCaseCreate:
    def test_create_posts_to_case_endpoint(self):
        case, conn = _make_case_module()
        conn.post.return_value = {"case_id": "case-new", "title": "New"}

        result = case.create({"title": "New", "summary": "S"})

        assert result["case_id"] == "case-new"
        conn.post.assert_called_once()
        assert "v2" in conn.post.call_args[0][0]
        assert conn.post.call_args[1]["json"] == {"title": "New", "summary": "S"}


class TestCaseUpdate:
    def test_update_puts_to_case_id(self):
        case, conn = _make_case_module()
        conn.put.return_value = {"case_id": "case-001", "title": "Updated"}

        result = case.update("case-001", {"title": "Updated"})

        assert result["title"] == "Updated"
        conn.put.assert_called_once()
        assert "case/case-001" in conn.put.call_args[0][0]
        assert conn.put.call_args[1]["json"] == {"title": "Updated"}


class TestCaseDelete:
    def test_delete_sends_ids_as_json(self):
        case, conn = _make_case_module()
        conn.delete.return_value = None

        case.delete(["case-001", "case-002"])

        conn.delete.assert_called_once()
        assert conn.delete.call_args[1]["json"] == ["case-001", "case-002"]


class TestCaseHide:
    def test_hide_posts_ids(self):
        case, conn = _make_case_module()
        conn.post.return_value = {"success": True}

        result = case.hide(["case-001"])

        assert result["success"] is True
        conn.post.assert_called_once()
        assert "hide" in conn.post.call_args[0][0]
        assert conn.post.call_args[1]["json"] == ["case-001"]


class TestCaseAppendItem:
    def test_append_item_posts_to_items_endpoint(self):
        case, conn = _make_case_module()
        conn.post.return_value = {"case_id": "case-001"}

        case.append_item("case-001", "hit", "hit-abc", "alerts/test")

        conn.post.assert_called_once()
        path = conn.post.call_args[0][0]
        assert "case/case-001/items" in path
        assert conn.post.call_args[1]["json"] == {
            "type": "hit",
            "value": "hit-abc",
            "path": "alerts/test",
        }


class TestCaseDeleteItems:
    def test_delete_items_sends_values(self):
        case, conn = _make_case_module()
        conn.delete.return_value = {"case_id": "case-001"}

        case.delete_items("case-001", ["hit-abc"])

        conn.delete.assert_called_once()
        assert "case/case-001/items" in conn.delete.call_args[0][0]
        assert conn.delete.call_args[1]["json"] == {"values": ["hit-abc"]}


class TestCaseRenameItem:
    def test_rename_item_puts_value_and_path(self):
        case, conn = _make_case_module()
        conn.put.return_value = {"case_id": "case-001"}

        case.rename_item("case-001", "hit-abc", "new/path")

        conn.put.assert_called_once()
        assert "case/case-001/items" in conn.put.call_args[0][0]
        assert conn.put.call_args[1]["json"] == {"value": "hit-abc", "new_path": "new/path"}


class TestCaseAddRule:
    def test_add_rule_posts_rule_data(self):
        case, conn = _make_case_module()
        conn.post.return_value = {"case_id": "case-001"}
        rule = {"query": "*:*", "destination": "alerts", "author": "user"}

        case.add_rule("case-001", rule)

        conn.post.assert_called_once()
        assert "case/case-001/rules" in conn.post.call_args[0][0]
        assert conn.post.call_args[1]["json"] == rule


class TestCaseDeleteRule:
    def test_delete_rule_calls_correct_path(self):
        case, conn = _make_case_module()
        conn.delete.return_value = {"case_id": "case-001"}

        case.delete_rule("case-001", "rule-abc")

        conn.delete.assert_called_once()
        assert "case/case-001/rules/rule-abc" in conn.delete.call_args[0][0]


class TestCaseUpdateRule:
    def test_update_rule_puts_rule_data(self):
        case, conn = _make_case_module()
        conn.put.return_value = {"case_id": "case-001"}
        updates = {"enabled": False}

        case.update_rule("case-001", "rule-abc", updates)

        conn.put.assert_called_once()
        assert "case/case-001/rules/rule-abc" in conn.put.call_args[0][0]
        assert conn.put.call_args[1]["json"] == {"enabled": False}
