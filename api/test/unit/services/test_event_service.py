"""Unit tests for the event service."""

from unittest.mock import MagicMock, patch

from howler.services import event_service


class TestDispatch:
    """Tests for event_service._dispatch."""

    @patch("howler.services.event_service.logger")
    def test_malformed_message_missing_event_logs_warning(self, mock_logger):
        """A message without __event__ logs a warning and returns early."""
        handler = MagicMock()
        original = event_service.handlers.copy()
        try:
            event_service.handlers["test"] = [handler]

            event_service._dispatch({"__payload__": {"x": 1}})

            mock_logger.warning.assert_called_once()
            handler.assert_not_called()
        finally:
            event_service.handlers.clear()
            event_service.handlers.update(original)

    @patch("howler.services.event_service.logger")
    def test_malformed_message_missing_payload_logs_warning(self, mock_logger):
        """A message without __payload__ logs a warning and returns early."""
        handler = MagicMock()
        original = event_service.handlers.copy()
        try:
            event_service.handlers["test"] = [handler]

            event_service._dispatch({"__event__": "test"})

            mock_logger.warning.assert_called_once()
            handler.assert_not_called()
        finally:
            event_service.handlers.clear()
            event_service.handlers.update(original)
