from unittest.mock import patch

from howler.utils.socket_utils import check_action


@patch("howler.services.hit_service.update_hit")
@patch("howler.services.hit_service.exists")
@patch("howler.services.event_service.emit")
def test_socket(emit, exists, update_hit):
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

        if action.endswith("viewing"):
            exists.assert_called_once()
            update_hit.assert_called_once()

        if action in ["typing", "viewing"]:
            assert len(new_outstanding_actions) == 1
