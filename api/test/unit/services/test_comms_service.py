"""Unit tests for the comms service."""

from unittest.mock import MagicMock, patch

from howler.services import comms_service


class TestDispatch:
    """Tests for comms_service._dispatch."""

    @patch("howler.services.comms_service.logger")
    def test_malformed_message_missing_event_logs_warning(self, mock_logger):
        """A message without __event__ logs a warning and returns early."""
        handler = MagicMock()
        original = comms_service.handlers.copy()
        try:
            comms_service.handlers["test"] = [handler]

            comms_service._dispatch({"__payload__": {"x": 1}})

            mock_logger.warning.assert_called_once()
            handler.assert_not_called()
        finally:
            comms_service.handlers.clear()
            comms_service.handlers.update(original)

    @patch("howler.services.comms_service.logger")
    def test_malformed_message_missing_payload_logs_warning(self, mock_logger):
        """A message without __payload__ logs a warning and returns early."""
        handler = MagicMock()
        original = comms_service.handlers.copy()
        try:
            comms_service.handlers["test"] = [handler]

            comms_service._dispatch({"__event__": "test"})

            mock_logger.warning.assert_called_once()
            handler.assert_not_called()
        finally:
            comms_service.handlers.clear()
            comms_service.handlers.update(original)

    @patch("howler.services.comms_service.logger")
    def test_handler_exception_is_caught_and_logged(self, mock_logger):
        """If a handler raises, the exception is logged and dispatch continues."""
        bad_handler = MagicMock(side_effect=RuntimeError("boom"))
        good_handler = MagicMock()
        original = comms_service.handlers.copy()
        try:
            comms_service.handlers["test"] = [bad_handler, good_handler]

            comms_service._dispatch({"__event__": "test", "__payload__": {"x": 1}})

            mock_logger.exception.assert_called_once()
            good_handler.assert_called_once_with({"x": 1})
        finally:
            comms_service.handlers.clear()
            comms_service.handlers.update(original)


class TestOff:
    """Tests for comms_service.off."""

    def test_off_unknown_event_is_noop(self):
        """Calling off() for an unregistered event does not raise."""
        handler = MagicMock()
        original = comms_service.handlers.copy()
        try:
            # Ensure "nonexistent" is not in handlers
            comms_service.handlers.pop("nonexistent", None)
            comms_service.off("nonexistent", handler)
            handler.assert_not_called()
        finally:
            comms_service.handlers.clear()
            comms_service.handlers.update(original)

    def test_off_unregistered_handler_is_noop(self):
        """Calling off() for a handler that was never registered does not raise."""
        registered_handler = MagicMock()
        unregistered_handler = MagicMock()
        original = comms_service.handlers.copy()
        try:
            comms_service.handlers["test"] = [registered_handler]
            comms_service.off("test", unregistered_handler)
            assert registered_handler in comms_service.handlers["test"]
        finally:
            comms_service.handlers.clear()
            comms_service.handlers.update(original)

    def test_off_removes_registered_handler(self):
        """Calling off() for a registered handler removes it from the list."""
        handler = MagicMock()
        original = comms_service.handlers.copy()
        try:
            comms_service.on("test_off", handler)
            assert handler in comms_service.handlers["test_off"]
            comms_service.off("test_off", handler)
            assert handler not in comms_service.handlers.get("test_off", [])
        finally:
            comms_service.handlers.clear()
            comms_service.handlers.update(original)


class TestEmitDebugInProcess:
    """Tests for comms_service.emit in DEBUG in-process mode."""

    @patch("howler.services.comms_service._get_sender")
    @patch("howler.services.comms_service.DEBUG", True)
    @patch("howler.services.comms_service._watcher_started", False)
    def test_emit_calls_handlers_directly_when_debug_and_no_watcher(self, mock_get_sender):
        """In DEBUG mode without a watcher, handlers are called in-process."""
        mock_sender = MagicMock()
        mock_get_sender.return_value = mock_sender
        handler = MagicMock()
        original = comms_service.handlers.copy()
        try:
            comms_service.handlers["test_event"] = [handler]
            comms_service.emit("test_event", {"key": "value"})
            handler.assert_called_once_with({"key": "value"})
        finally:
            comms_service.handlers.clear()
            comms_service.handlers.update(original)
