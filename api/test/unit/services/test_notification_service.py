"""Unit tests for the notification service."""

from unittest.mock import MagicMock, patch

import pytest

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.datastore.exceptions import SearchException
from howler.services import notification_service


class TestGetUserNotifications:
    """Tests for retrieving a user's notifications."""

    @patch("howler.services.notification_service.datastore")
    def test_queries_recipient_newest_first(self, mock_datastore):
        notification = {"notification_id": "n-1", "recipient": "alice", "message": "hello"}
        mock_datastore.return_value.notification.search.return_value = {
            "items": [notification],
            "offset": 5,
            "rows": 10,
            "total": 6,
        }
        mock_datastore.return_value.notification.count.return_value = {"count": 2}

        result = notification_service.get_user_notifications("alice", offset=5, rows=10)

        assert result == {"items": [notification], "offset": 5, "rows": 10, "total": 6, "unread": 2}
        mock_datastore.return_value.notification.count.assert_called_once_with(
            'recipient:"alice"', filters="read:false"
        )
        mock_datastore.return_value.notification.search.assert_called_once_with(
            'recipient:"alice"',
            as_obj=False,
            offset=5,
            rows=10,
            sort="created desc",
            track_total_hits=True,
        )

    @patch("howler.services.notification_service.datastore")
    def test_sanitizes_username_in_query(self, mock_datastore):
        mock_datastore.return_value.notification.search.return_value = {
            "items": [],
            "offset": 0,
            "rows": 25,
            "total": 0,
        }
        mock_datastore.return_value.notification.count.return_value = {"count": 0}

        notification_service.get_user_notifications('al"ice OR recipient:*')

        query = mock_datastore.return_value.notification.search.call_args.args[0]
        assert query == 'recipient:"al\\"ice OR recipient\\:\\*"'

    @patch("howler.services.notification_service.datastore")
    def test_search_failure_raises_invalid_data(self, mock_datastore):
        mock_datastore.return_value.notification.search.side_effect = SearchException("bad search")

        with pytest.raises(InvalidDataException):
            notification_service.get_user_notifications("alice")

    @patch("howler.services.notification_service.datastore")
    def test_count_failure_raises_invalid_data(self, mock_datastore):
        mock_datastore.return_value.notification.search.return_value = {
            "items": [],
            "offset": 0,
            "rows": 25,
            "total": 0,
        }
        mock_datastore.return_value.notification.count.side_effect = SearchException("bad count")

        with pytest.raises(InvalidDataException):
            notification_service.get_user_notifications("alice")


class TestMarkNotificationRead:
    """Tests for marking a notification as read."""

    @patch("howler.services.notification_service.datastore")
    def test_marks_unread_notification_read(self, mock_datastore):
        collection = mock_datastore.return_value.notification
        collection.get_if_exists.return_value = {"notification_id": "n-1", "recipient": "alice", "read": False}
        collection.update.return_value = (True, "1---1")

        result = notification_service.mark_notification_read("n-1", "alice")

        assert result["read"] is True
        collection.update.assert_called_once_with("n-1", [(collection.UPDATE_SET, "read", True)])

    @patch("howler.services.notification_service.datastore")
    def test_already_read_notification_is_not_updated(self, mock_datastore):
        collection = mock_datastore.return_value.notification
        collection.get_if_exists.return_value = {"notification_id": "n-1", "recipient": "alice", "read": True}

        assert notification_service.mark_notification_read("n-1", "alice")["read"] is True
        collection.update.assert_not_called()

    @pytest.mark.parametrize("stored", [None, {"notification_id": "n-1", "recipient": "bob", "read": False}])
    @patch("howler.services.notification_service.datastore")
    def test_missing_or_foreign_notification_raises_not_found(self, mock_datastore, stored):
        collection = mock_datastore.return_value.notification
        collection.get_if_exists.return_value = stored

        with pytest.raises(NotFoundException):
            notification_service.mark_notification_read("n-1", "alice")
        collection.update.assert_not_called()

    @patch("howler.services.notification_service.datastore")
    def test_failed_update_raises_invalid_data(self, mock_datastore):
        collection = mock_datastore.return_value.notification
        collection.get_if_exists.return_value = {"notification_id": "n-1", "recipient": "alice", "read": False}
        collection.update.return_value = False

        with pytest.raises(InvalidDataException):
            notification_service.mark_notification_read("n-1", "alice")


class TestDeleteNotification:
    """Tests for deleting a notification."""

    @patch("howler.services.notification_service.datastore")
    def test_deletes_own_notification(self, mock_datastore):
        collection = mock_datastore.return_value.notification
        collection.get_if_exists.return_value = {"notification_id": "n-1", "recipient": "alice"}
        collection.delete.return_value = True

        notification_service.delete_notification("n-1", "alice")

        collection.delete.assert_called_once_with("n-1")

    @pytest.mark.parametrize("stored", [None, {"notification_id": "n-1", "recipient": "bob"}])
    @patch("howler.services.notification_service.datastore")
    def test_missing_or_foreign_notification_raises_not_found(self, mock_datastore, stored):
        collection = mock_datastore.return_value.notification
        collection.get_if_exists.return_value = stored

        with pytest.raises(NotFoundException):
            notification_service.delete_notification("n-1", "alice")
        collection.delete.assert_not_called()

    @patch("howler.services.notification_service.datastore")
    def test_failed_delete_raises_not_found(self, mock_datastore):
        collection = mock_datastore.return_value.notification
        collection.get_if_exists.return_value = {"notification_id": "n-1", "recipient": "alice"}
        collection.delete.return_value = False

        with pytest.raises(NotFoundException):
            notification_service.delete_notification("n-1", "alice")


class TestCreateAnalyticCommentNotification:
    """Tests for creating analytic comment notifications."""

    @staticmethod
    def _analytic(owner: str = "owner") -> dict:
        return {
            "analytic_id": "a7c2f1f0-2f43-4d2b-9b4c-2c7e9f6d1e11",
            "name": "Suspicious Login",
            "owner": owner,
        }

    @patch("howler.services.notification_service.comms_service")
    @patch("howler.services.notification_service.datastore")
    def test_skips_self_comment(self, mock_datastore, mock_comms):
        mock_datastore.return_value.analytic.search.return_value = {"items": [self._analytic("owner")]}

        assert notification_service.create_analytic_comment_notification("id", "owner") is None
        mock_datastore.return_value.notification.save.assert_not_called()
        mock_comms.emit.assert_not_called()

    @patch("howler.services.notification_service.comms_service")
    @patch("howler.services.notification_service.datastore")
    def test_saves_and_emits_for_owner(self, mock_datastore, mock_comms):
        datastore_instance: MagicMock = mock_datastore.return_value
        datastore_instance.analytic.search.return_value = {"items": [self._analytic("owner")]}

        notification = notification_service.create_analytic_comment_notification("id", "analyst")

        assert notification is not None
        assert notification.recipient == "owner"
        assert notification.sender == "analyst"
        assert notification.read is False
        datastore_instance.notification.save.assert_called_once_with(notification.notification_id, notification)
        mock_comms.emit.assert_called_once_with("notification", notification.as_primitives())
