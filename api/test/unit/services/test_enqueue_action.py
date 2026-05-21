from unittest.mock import MagicMock, patch

from howler.services import action_service


class TestEnqueueActionExecution:
    """Tests for enqueue_action_execution."""

    @patch.object(action_service, "_get_action_queue")
    @patch("howler.services.action_service.config")
    def test_enqueue_pushes_correct_item(self, mock_config, mock_get_queue):
        """Verify queue receives correctly structured item."""
        mock_config.system.action_queue.enabled = True
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        user = MagicMock()
        user.__getitem__ = MagicMock(return_value="testuser")

        action_service.enqueue_action_execution(["id1", "id2"], trigger="create", user=user)

        mock_queue.push.assert_called_once()
        pushed = mock_queue.push.call_args[0][0]
        assert pushed["hit_ids"] == ["id1", "id2"]
        assert pushed["trigger"] == "create"
        assert pushed["user_uname"] == "testuser"

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

    @patch.object(action_service, "_get_action_queue")
    @patch("howler.services.action_service.config")
    def test_enqueue_empty_ids_is_noop(self, mock_config, mock_get_queue):
        """Calling with empty hit_ids should not push anything."""
        mock_config.system.action_queue.enabled = True

        action_service.enqueue_action_execution([], trigger="create", user=None)

        mock_get_queue.assert_not_called()

    @patch.object(action_service, "bulk_execute_on_query")
    @patch.object(action_service, "_get_action_queue")
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

    @patch.object(action_service, "_get_action_queue")
    @patch("howler.services.action_service.config")
    def test_enqueue_none_user(self, mock_config, mock_get_queue):
        """When user is None, user_uname should be None in the queued item."""
        mock_config.system.action_queue.enabled = True
        mock_queue = MagicMock()
        mock_get_queue.return_value = mock_queue

        action_service.enqueue_action_execution(["id1"], trigger="create", user=None)

        pushed = mock_queue.push.call_args[0][0]
        assert pushed["user_uname"] is None


class TestProcessActionBatch:
    """Tests for process_action_batch."""

    @patch.object(action_service, "bulk_execute_on_query")
    @patch.object(action_service, "datastore")
    def test_process_batch_empty(self, mock_ds, mock_bulk):
        """Empty batch should be a no-op."""
        action_service.process_action_batch([])

        mock_bulk.assert_not_called()
        mock_ds.assert_not_called()

    @patch.object(action_service, "bulk_execute_on_query")
    @patch.object(action_service, "datastore")
    def test_process_batch_groups_by_trigger(self, mock_ds, mock_bulk):
        """Two items with same trigger+user should produce one bulk call."""
        mock_user = MagicMock()
        mock_ds.return_value.user.get.return_value = mock_user

        items = [
            {"hit_ids": ["id1", "id2"], "trigger": "create", "user_uname": "admin"},
            {"hit_ids": ["id3"], "trigger": "create", "user_uname": "admin"},
        ]

        action_service.process_action_batch(items)

        # Should be called once with all 3 IDs combined
        assert mock_bulk.call_count == 1
        query_arg = mock_bulk.call_args[0][0]
        assert "id1" in query_arg
        assert "id2" in query_arg
        assert "id3" in query_arg
        assert mock_bulk.call_args[1]["trigger"] == "create"
        assert mock_bulk.call_args[1]["user"] is mock_user

    @patch.object(action_service, "bulk_execute_on_query")
    @patch.object(action_service, "datastore")
    def test_process_batch_groups_by_user(self, mock_ds, mock_bulk):
        """Same trigger, different users → separate bulk calls."""
        mock_user1 = MagicMock()
        mock_user2 = MagicMock()
        mock_ds.return_value.user.get.side_effect = lambda uname: mock_user1 if uname == "user1" else mock_user2

        items = [
            {"hit_ids": ["id1"], "trigger": "create", "user_uname": "user1"},
            {"hit_ids": ["id2"], "trigger": "create", "user_uname": "user2"},
        ]

        action_service.process_action_batch(items)

        assert mock_bulk.call_count == 2

    @patch.object(action_service, "bulk_execute_on_query")
    @patch.object(action_service, "datastore")
    def test_process_batch_unknown_user_skipped(self, mock_ds, mock_bulk):
        """When user not found in datastore, the group should be skipped."""
        mock_ds.return_value.user.get.return_value = None

        items = [
            {"hit_ids": ["id1"], "trigger": "create", "user_uname": "nonexistent"},
        ]

        action_service.process_action_batch(items)

        mock_bulk.assert_not_called()

    @patch.object(action_service, "bulk_execute_on_query")
    @patch.object(action_service, "datastore")
    def test_process_batch_deduplicates_ids(self, mock_ds, mock_bulk):
        """Duplicate IDs within a batch group should be deduplicated."""
        mock_user = MagicMock()
        mock_ds.return_value.user.get.return_value = mock_user

        items = [
            {"hit_ids": ["id1", "id2"], "trigger": "create", "user_uname": "admin"},
            {"hit_ids": ["id2", "id3"], "trigger": "create", "user_uname": "admin"},
        ]

        action_service.process_action_batch(items)

        query_arg = mock_bulk.call_args[0][0]
        # id2 should appear only once
        assert query_arg.count("id2") == 1
        assert "id1" in query_arg
        assert "id3" in query_arg

    @patch.object(action_service, "bulk_execute_on_query")
    @patch.object(action_service, "datastore")
    def test_process_batch_multiple_triggers(self, mock_ds, mock_bulk):
        """Items with different triggers should produce separate calls."""
        mock_user = MagicMock()
        mock_ds.return_value.user.get.return_value = mock_user

        items = [
            {"hit_ids": ["id1"], "trigger": "create", "user_uname": "admin"},
            {"hit_ids": ["id2"], "trigger": "promote", "user_uname": "admin"},
        ]

        action_service.process_action_batch(items)

        assert mock_bulk.call_count == 2
        triggers = {c[1]["trigger"] for c in mock_bulk.call_args_list}
        assert triggers == {"create", "promote"}

    @patch.object(action_service, "bulk_execute_on_query")
    @patch.object(action_service, "datastore")
    def test_process_batch_bulk_error_does_not_crash(self, mock_ds, mock_bulk):
        """If bulk_execute_on_query raises, the error is logged but not propagated."""
        mock_user = MagicMock()
        mock_ds.return_value.user.get.return_value = mock_user
        mock_bulk.side_effect = Exception("ES is down")

        items = [
            {"hit_ids": ["id1"], "trigger": "create", "user_uname": "admin"},
        ]

        # Should not raise
        action_service.process_action_batch(items)
