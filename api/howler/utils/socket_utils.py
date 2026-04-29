from howler.common.logging import get_logger
from howler.services import event_service, viewer_service

logger = get_logger(__file__)


def check_action(
    id: str, action: str, broadcast: bool, outstanding_actions: list[tuple[str, str, bool]] = [], **kwargs
) -> list[tuple[str, str, bool]]:
    """Emit an event based on the specified action for use by websocket clients

    Args:
        id (str): The id of the item the action is being run on
        action (str): The action we are running
        broadcast (bool): Whether to advertise this action to other users
        outstanding_actions (list[tuple[str, str, bool]], optional): A list of actions that must be run after the
        user is disconnected. Defaults to [].

    Returns:
        list[tuple[str, str, bool]]: The new list of outstanding actions
    """
    if broadcast:
        event_service.emit(
            "broadcast",
            {"id": id, "action": action, "username": kwargs["username"]},
        )

    if action == "typing":
        outstanding_actions.append((id, "stop_typing", True))
    elif action == "stop_typing":
        outstanding_actions = [a for a in outstanding_actions if a[1] != "stop_typing"]

    elif action == "viewing":
        outstanding_actions.append((id, "stop_viewing", False))
        viewer_service.add_viewer(id, kwargs["username"])
    elif action == "stop_viewing":
        viewer_service.remove_viewer(id, kwargs["username"])
        outstanding_actions = [a for a in outstanding_actions if a[1] != "stop_viewing"]

    return outstanding_actions
