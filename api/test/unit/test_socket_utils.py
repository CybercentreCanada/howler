from unittest.mock import patch

from howler.utils.socket_utils import check_action

_ID = "test_id"
_USER = "test_user"
_KWARGS = {"username": _USER}


class TestCheckActionBroadcast:
    """Tests for broadcasting behavior in check_action."""

    @patch("howler.services.viewer_service.remove_viewer")
    @patch("howler.services.viewer_service.add_viewer")
    @patch("howler.services.event_service.emit")
    def test_broadcast_emits_event(self, emit, add_viewer, remove_viewer):
        """When broadcast=True, a broadcast event is emitted."""
        check_action(_ID, "typing", True, outstanding_actions=[], **_KWARGS)

        emit.assert_called_once_with(
            "broadcast",
            {"id": _ID, "action": "typing", "username": _USER},
        )

    @patch("howler.services.viewer_service.remove_viewer")
    @patch("howler.services.viewer_service.add_viewer")
    @patch("howler.services.event_service.emit")
    def test_no_broadcast_does_not_emit(self, emit, add_viewer, remove_viewer):
        """When broadcast=False, no broadcast event is emitted."""
        check_action(_ID, "typing", False, outstanding_actions=[], **_KWARGS)

        emit.assert_not_called()


class TestCheckActionTyping:
    """Tests for typing/stop_typing actions."""

    @patch("howler.services.viewer_service.remove_viewer")
    @patch("howler.services.viewer_service.add_viewer")
    @patch("howler.services.event_service.emit")
    def test_typing_appends_stop_typing(self, emit, add_viewer, remove_viewer):
        """typing action adds a stop_typing outstanding action."""
        result = check_action(_ID, "typing", False, outstanding_actions=[], **_KWARGS)

        assert len(result) == 1
        assert result[0] == (_ID, "stop_typing", True)

    @patch("howler.services.viewer_service.remove_viewer")
    @patch("howler.services.viewer_service.add_viewer")
    @patch("howler.services.event_service.emit")
    def test_stop_typing_removes_outstanding(self, emit, add_viewer, remove_viewer):
        """stop_typing action removes stop_typing from outstanding actions."""
        outstanding = [(_ID, "stop_typing", True)]
        result = check_action(_ID, "stop_typing", False, outstanding_actions=outstanding, **_KWARGS)

        assert len(result) == 0


class TestCheckActionViewing:
    """Tests for viewing/stop_viewing actions."""

    @patch("howler.services.viewer_service.remove_viewer")
    @patch("howler.services.viewer_service.add_viewer")
    @patch("howler.services.event_service.emit")
    def test_viewing_adds_viewer(self, emit, add_viewer, remove_viewer):
        """viewing action calls viewer_service.add_viewer."""
        check_action(_ID, "viewing", False, outstanding_actions=[], **_KWARGS)

        add_viewer.assert_called_once_with(_ID, _USER)

    @patch("howler.services.viewer_service.remove_viewer")
    @patch("howler.services.viewer_service.add_viewer")
    @patch("howler.services.event_service.emit")
    def test_viewing_appends_stop_viewing(self, emit, add_viewer, remove_viewer):
        """viewing action adds a stop_viewing outstanding action."""
        result = check_action(_ID, "viewing", False, outstanding_actions=[], **_KWARGS)

        assert len(result) == 1
        assert result[0] == (_ID, "stop_viewing", False)

    @patch("howler.services.viewer_service.remove_viewer")
    @patch("howler.services.viewer_service.add_viewer")
    @patch("howler.services.event_service.emit")
    def test_stop_viewing_removes_viewer(self, emit, add_viewer, remove_viewer):
        """stop_viewing action calls viewer_service.remove_viewer."""
        check_action(_ID, "stop_viewing", False, outstanding_actions=[], **_KWARGS)

        remove_viewer.assert_called_once_with(_ID, _USER)

    @patch("howler.services.viewer_service.remove_viewer")
    @patch("howler.services.viewer_service.add_viewer")
    @patch("howler.services.event_service.emit")
    def test_stop_viewing_removes_outstanding(self, emit, add_viewer, remove_viewer):
        """stop_viewing action removes stop_viewing from outstanding actions."""
        outstanding = [(_ID, "stop_viewing", False)]
        result = check_action(_ID, "stop_viewing", False, outstanding_actions=outstanding, **_KWARGS)

        assert len(result) == 0

    @patch("howler.services.viewer_service.remove_viewer")
    @patch("howler.services.viewer_service.add_viewer")
    @patch("howler.services.event_service.emit")
    def test_viewing_does_not_emit_broadcast(self, emit, add_viewer, remove_viewer):
        """viewing with broadcast=False does not emit a broadcast event directly."""
        check_action(_ID, "viewing", False, outstanding_actions=[], **_KWARGS)

        emit.assert_not_called()
