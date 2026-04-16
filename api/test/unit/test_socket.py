from unittest.mock import patch

from howler.utils.socket_utils import check_action


@patch("howler.services.hit_service.update_hit")
@patch("howler.services.hit_service.exists")
@patch("howler.utils.socket_utils.viewer_service")
@patch("howler.services.event_service.emit")
def test_socket(emit, mock_viewer_service, exists, update_hit):
    _id = "test_id"

    exists.return_value = True
    kwargs = {"username": "test_user"}

    actions = [
        ("typing", True),
        ("stop_typing", True),
        ("viewing", False),
        ("stop_viewing", False),
    ]

    for action, broadcast in actions:
        emit.reset_mock()
        exists.reset_mock()
        update_hit.reset_mock()

        outstanding_actions = []

        new_outstanding_actions = check_action(
            _id, action, broadcast, outstanding_actions=outstanding_actions, **kwargs
        )

        if broadcast:
            emit.assert_called_once()
        else:
            emit.assert_not_called()

        if action == "viewing":
            mock_viewer_service.add_viewer.assert_called_once_with(_id, kwargs["username"])
        elif action == "stop_viewing":
            mock_viewer_service.remove_viewer.assert_called_once_with(_id, kwargs["username"])

        if action in ["typing", "viewing"]:
            assert len(new_outstanding_actions) == 1
