"""Unit tests for the v2 Ingest client module."""

import json
from unittest.mock import MagicMock

import pytest

from howler_client.common.utils import ClientError
from howler_client.module.ingest import Ingest


def _make_ingest_module() -> tuple[Ingest, MagicMock]:
    conn = MagicMock()
    return Ingest(conn), conn


class TestIngestCreate:
    def test_create_single_record_wraps_in_list(self):
        ingest, conn = _make_ingest_module()
        conn.post.return_value = {"valid": [{"howler": {"id": "h1"}}], "invalid": []}

        ingest.create("hit", {"howler": {"analytic": "A"}})

        conn.post.assert_called_once()
        path = conn.post.call_args[0][0]
        assert "v2" in path
        assert "ingest/hit" in path
        sent_data = json.loads(conn.post.call_args[1]["data"])
        assert isinstance(sent_data, list)
        assert len(sent_data) == 1

    def test_create_list_of_records(self):
        ingest, conn = _make_ingest_module()
        conn.post.return_value = {"valid": [], "invalid": []}

        records = [{"howler": {"analytic": "A"}}, {"howler": {"analytic": "B"}}]
        ingest.create("observable", records)

        sent_data = json.loads(conn.post.call_args[1]["data"])
        assert len(sent_data) == 2


class TestIngestDelete:
    def test_delete_sends_ids_as_json(self):
        ingest, conn = _make_ingest_module()
        conn.delete.return_value = {"success": True}

        ingest.delete("hit,observable", ["id-1", "id-2"])

        conn.delete.assert_called_once()
        assert "ingest/hit,observable" in conn.delete.call_args[0][0]
        assert conn.delete.call_args[1]["json"] == ["id-1", "id-2"]


class TestIngestValidate:
    def test_validate_single_record_wraps_in_list(self):
        ingest, conn = _make_ingest_module()
        conn.post.return_value = {"valid": [{}], "invalid": []}

        ingest.validate("hit", {"howler": {"analytic": "A"}})

        sent_data = json.loads(conn.post.call_args[1]["data"])
        assert isinstance(sent_data, list)
        assert "ingest/hit/validate" in conn.post.call_args[0][0]


class TestIngestOverwrite:
    def test_overwrite_uses_patch(self):
        ingest, conn = _make_ingest_module()
        conn.request.return_value = {"howler": {"id": "h1"}}

        ingest.overwrite("hit", "h1", {"howler": {"analytic": "B"}})

        conn.request.assert_called_once()
        # First arg is the session.patch method
        assert conn.request.call_args[0][0] == conn.session.patch
        path = conn.request.call_args[0][1]
        assert "ingest/hit/h1/overwrite" in path

    def test_overwrite_raises_on_non_dict(self):
        ingest, _ = _make_ingest_module()

        with pytest.raises(TypeError, match="dict"):
            ingest.overwrite("hit", "h1", ["not", "a", "dict"])

    def test_overwrite_with_replace_flag(self):
        ingest, conn = _make_ingest_module()
        conn.request.return_value = {"howler": {"id": "h1"}}

        ingest.overwrite("hit", "h1", {"howler": {"analytic": "B"}}, replace=True)

        path = conn.request.call_args[0][1]
        assert "replace=True" in path


class TestIngestUpdateByQuery:
    def test_update_by_query_sends_query_and_operations(self):
        ingest, conn = _make_ingest_module()
        conn.put.return_value = {"success": True}

        ops = [("SET", "howler.assignment", "user")]
        ingest.update_by_query("hit", "howler.id:*", ops)

        conn.put.assert_called_once()
        assert "ingest/hit/update" in conn.put.call_args[0][0]
        body = conn.put.call_args[1]["json"]
        assert body["query"] == "howler.id:*"
        assert body["operations"] == ops

    def test_update_by_query_raises_on_non_list(self):
        ingest, _ = _make_ingest_module()

        with pytest.raises(TypeError, match="list"):
            ingest.update_by_query("hit", "*:*", "not a list")

    def test_update_by_query_raises_on_non_tuple_entry(self):
        ingest, _ = _make_ingest_module()

        with pytest.raises(TypeError, match="tuple"):
            ingest.update_by_query("hit", "*:*", [["SET", "key", "val"]])

    def test_update_by_query_raises_on_invalid_operation(self):
        ingest, _ = _make_ingest_module()

        with pytest.raises(ClientError):
            ingest.update_by_query("hit", "*:*", [("INVALID", "key", "val")])
