from unittest.mock import patch

from howler.services import viewer_service


class TestAddViewer:
    """Tests for viewer_service.add_viewer."""

    @patch.object(viewer_service, "event_service")
    @patch.object(viewer_service, "redis")
    def test_add_viewer_calls_sadd_and_expire(self, mock_redis, mock_event):
        """add_viewer writes the username to a Redis set and refreshes the TTL."""
        mock_redis.smembers.return_value = {b"alice"}

        viewer_service.add_viewer("entity-1", "alice")

        mock_redis.sadd.assert_called_once_with("viewers:entity-1", "alice")
        mock_redis.expire.assert_called_once_with("viewers:entity-1", viewer_service.VIEWER_TTL)

    @patch.object(viewer_service, "event_service")
    @patch.object(viewer_service, "redis")
    def test_add_viewer_emits_viewers_update(self, mock_redis, mock_event):
        """add_viewer emits a viewers_update event with the current viewer list."""
        mock_redis.smembers.return_value = {b"alice", b"bob"}

        viewer_service.add_viewer("entity-1", "alice")

        mock_event.emit.assert_called_once_with(
            "viewers_update",
            {"id": "entity-1", "viewers": ["alice", "bob"]},
        )


class TestRemoveViewer:
    """Tests for viewer_service.remove_viewer."""

    @patch.object(viewer_service, "event_service")
    @patch.object(viewer_service, "redis")
    def test_remove_viewer_calls_srem(self, mock_redis, mock_event):
        """remove_viewer removes the username from the Redis set."""
        mock_redis.smembers.return_value = set()

        viewer_service.remove_viewer("entity-1", "alice")

        mock_redis.srem.assert_called_once_with("viewers:entity-1", "alice")

    @patch.object(viewer_service, "event_service")
    @patch.object(viewer_service, "redis")
    def test_remove_viewer_emits_viewers_update(self, mock_redis, mock_event):
        """remove_viewer emits a viewers_update event after removal."""
        mock_redis.smembers.return_value = {b"bob"}

        viewer_service.remove_viewer("entity-1", "alice")

        mock_event.emit.assert_called_once_with(
            "viewers_update",
            {"id": "entity-1", "viewers": ["bob"]},
        )


class TestGetViewers:
    """Tests for viewer_service.get_viewers."""

    @patch.object(viewer_service, "redis")
    def test_get_viewers_returns_sorted_list(self, mock_redis):
        """get_viewers decodes bytes and returns a sorted list of usernames."""
        mock_redis.smembers.return_value = {b"charlie", b"alice", b"bob"}

        result = viewer_service.get_viewers("entity-1")

        assert result == ["alice", "bob", "charlie"]

    @patch.object(viewer_service, "redis")
    def test_get_viewers_handles_string_members(self, mock_redis):
        """get_viewers handles members that are already strings."""
        mock_redis.smembers.return_value = {"charlie", "alice"}

        result = viewer_service.get_viewers("entity-1")

        assert result == ["alice", "charlie"]

    @patch.object(viewer_service, "redis")
    def test_get_viewers_returns_empty_for_missing_key(self, mock_redis):
        """get_viewers returns an empty list when the Redis set does not exist."""
        mock_redis.smembers.return_value = set()

        result = viewer_service.get_viewers("nonexistent")

        assert result == []
