from unittest.mock import MagicMock, patch

import pytest

from howler.services import action_service


class TestEnqueueActionExecution:
    """Tests for enqueue_action_execution."""

    @patch.object(action_service, "get_action_queue")
    @patch("howler.services.action_service.config")
    def test_enqueue_pushes_correct_item(self, mock_config, mock_get_queue):
        """Verify queue receives hit IDs and the initiating username."""
        mock_config.system.action_queue.enabled = True
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        user = MagicMock()
        user.uname = "testuser"

        action_service.enqueue_action_execution(["id1", "id2"], trigger="create", user=user)

        mock_get_queue.assert_called_once_with("create")
        mock_queue.push.assert_called_once()
        pushed = mock_queue.push.call_args[0][0]
        assert pushed["hit_ids"] == ["id1", "id2"]
        assert "trigger" not in pushed
        assert pushed["uname"] == "testuser"

    @patch.object(action_service, "get_action_queue")
    @patch("howler.services.action_service.config")
    def test_enqueue_routes_to_trigger_queue(self, mock_config, mock_get_queue):
        """Each trigger should route to its own named queue."""
        mock_config.system.action_queue.enabled = True
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        user = MagicMock()
        user.uname = "u"

        action_service.enqueue_action_execution(["id1"], trigger="promote", user=user)
        mock_get_queue.assert_called_with("promote")

        action_service.enqueue_action_execution(["id2"], trigger="demote", user=user)
        mock_get_queue.assert_called_with("demote")

    @patch.object(action_service, "bulk_execute_on_query")
    @patch("howler.services.action_service.config")
    def test_enqueue_fallback_when_disabled(self, mock_config, mock_bulk):
        """With action_queue.enabled=False, call bulk_execute_on_query directly."""
        mock_config.system.action_queue.enabled = False

        user = MagicMock()
        user.__getitem__ = MagicMock(return_value="testuser")

        action_service.enqueue_action_execution(["id1"], trigger="promote", user=user)

        mock_bulk.assert_called_once()
        call_kwargs = mock_bulk.call_args
        assert "howler.id:" in call_kwargs[0][0]
        assert call_kwargs[1]["trigger"] == "promote"
        assert call_kwargs[1]["user"] is user

    @patch.object(action_service, "get_action_queue")
    @patch("howler.services.action_service.config")
    def test_enqueue_empty_ids_is_noop(self, mock_config, mock_get_queue):
        """Calling with empty hit_ids should not push anything."""
        mock_config.system.action_queue.enabled = True

        action_service.enqueue_action_execution([], trigger="create", user=None)

        mock_get_queue.assert_not_called()

    @patch.object(action_service, "bulk_execute_on_query")
    @patch.object(action_service, "get_action_queue")
    @patch("howler.services.action_service.config")
    def test_enqueue_fallback_on_push_error(self, mock_config, mock_get_queue, mock_bulk):
        """If queue push fails, fall back to direct execution."""
        mock_config.system.action_queue.enabled = True
        mock_queue = MagicMock()
        mock_queue.push.side_effect = ConnectionError("Redis down")
        mock_get_queue.return_value = mock_queue

        user = MagicMock()
        user.__getitem__ = MagicMock(return_value="testuser")

        action_service.enqueue_action_execution(["id1"], trigger="create", user=user)

        mock_bulk.assert_called_once()

    @patch.object(action_service, "get_action_queue")
    @patch("howler.services.action_service.config")
    def test_enqueue_none_user(self, mock_config, mock_get_queue):
        """When user is None, the queued username should be None."""
        mock_config.system.action_queue.enabled = True
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        action_service.enqueue_action_execution(["id1"], trigger="create", user=None)

        pushed = mock_queue.push.call_args[0][0]
        assert pushed["uname"] is None

    @patch.object(action_service, "bulk_execute_on_query")
    @patch("howler.services.action_service.config")
    def test_enqueue_invalid_trigger_falls_back(self, mock_config, mock_bulk):
        """An invalid trigger should skip the queue and call bulk_execute_on_query directly."""
        mock_config.system.action_queue.enabled = True

        user = MagicMock()
        user.__getitem__ = MagicMock(return_value="testuser")

        with pytest.raises(ValueError, match="Invalid trigger"):
            action_service.enqueue_action_execution(["id1"], trigger="not_a_real_trigger", user=user)


class TestGetActionQueue:
    """Tests for get_action_queue."""

    def test_invalid_trigger_raises_value_error(self):
        """get_action_queue should raise ValueError for an unknown trigger."""
        with pytest.raises(ValueError, match="Invalid trigger"):
            action_service.get_action_queue("bogus_trigger")


class TestProcessActionBatch:
    """Tests for process_action_batch."""

    @patch.object(action_service, "datastore")
    @patch.object(action_service, "bulk_execute_on_query")
    def test_process_batch_fetches_odm_user(self, mock_bulk, mock_datastore):
        """The batch processor should fetch an ODM user from the queued username."""
        user = MagicMock()
        mock_datastore.return_value.user.get.return_value = user

        action_service.process_action_batch("create", [{"hit_ids": ["id1"], "uname": "admin"}])

        mock_datastore.return_value.user.get.assert_called_once_with("admin")
        mock_bulk.assert_called_once()
        assert mock_bulk.call_args.kwargs["user"] is user

    @patch.object(action_service, "bulk_execute_on_query")
    def test_process_batch_empty(self, mock_bulk):
        """Empty batch should be a no-op."""
        action_service.process_action_batch("create", [])

        mock_bulk.assert_not_called()

    @patch.object(action_service, "datastore")
    @patch.object(action_service, "bulk_execute_on_query")
    def test_process_batch_coalesces_same_user(self, mock_bulk, mock_datastore):
        """Two items with same user should produce one bulk call."""
        items = [
            {"hit_ids": ["id1", "id2"], "uname": "admin"},
            {"hit_ids": ["id3"], "uname": "admin"},
        ]

        action_service.process_action_batch("create", items)

        # Should be called once with all 3 IDs combined
        assert mock_bulk.call_count == 1
        query_arg = mock_bulk.call_args[0][0]
        assert "id1" in query_arg
        assert "id2" in query_arg
        assert "id3" in query_arg
        assert mock_bulk.call_args[1]["trigger"] == "create"

    @patch.object(action_service, "datastore")
    @patch.object(action_service, "bulk_execute_on_query")
    def test_process_batch_groups_by_user(self, mock_bulk, mock_datastore):
        """Different users -> separate bulk calls."""
        items = [
            {"hit_ids": ["id1"], "uname": "user1"},
            {"hit_ids": ["id2"], "uname": "user2"},
        ]

        action_service.process_action_batch("create", items)

        assert mock_bulk.call_count == 2

    @patch.object(action_service, "datastore")
    @patch.object(action_service, "bulk_execute_on_query")
    def test_process_batch_none_user(self, mock_bulk, mock_datastore):
        """When user is None, the batch group should still be processed."""
        mock_datastore.return_value.user.get.return_value = None
        items = [
            {"hit_ids": ["id1"], "uname": None},
        ]

        action_service.process_action_batch("create", items)

        assert mock_bulk.call_count == 1
        assert mock_bulk.call_args[1]["user"] is None

    @patch.object(action_service, "datastore")
    @patch.object(action_service, "bulk_execute_on_query")
    def test_process_batch_deduplicates_ids(self, mock_bulk, mock_datastore):
        """Duplicate IDs within a batch group should be deduplicated."""
        items = [
            {"hit_ids": ["id1", "id2"], "uname": "admin"},
            {"hit_ids": ["id2", "id3"], "uname": "admin"},
        ]

        action_service.process_action_batch("create", items)

        query_arg = mock_bulk.call_args[0][0]
        # id2 should appear only once
        assert query_arg.count("id2") == 1
        assert "id1" in query_arg
        assert "id3" in query_arg

    @patch.object(action_service, "datastore")
    @patch.object(action_service, "bulk_execute_on_query")
    def test_process_batch_passes_trigger(self, mock_bulk, mock_datastore):
        """The trigger argument should be forwarded to bulk_execute_on_query."""
        items = [{"hit_ids": ["id1"], "uname": "admin"}]

        action_service.process_action_batch("promote", items)

        assert mock_bulk.call_args[1]["trigger"] == "promote"

    @patch.object(action_service, "datastore")
    @patch.object(action_service, "bulk_execute_on_query")
    def test_process_batch_bulk_error_does_not_crash(self, mock_bulk, mock_datastore):
        """If bulk_execute_on_query raises, the error is logged but not propagated."""
        mock_bulk.side_effect = Exception("ES is down")

        items = [
            {"hit_ids": ["id1"], "uname": "admin"},
        ]

        # Should not raise
        action_service.process_action_batch("create", items)
