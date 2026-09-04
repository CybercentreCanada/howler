from howler.common.logging import get_logger
from howler.odm.models.user import User
from howler.services import comms_service, viewer_service

logger = get_logger(__file__)


def check_action(
    id: str,
    action: str,
    broadcast: bool,
    outstanding_actions: list[tuple[str, str, bool]] | None = None,
    user: User | None = None,
    **kwargs,
) -> list[tuple[str, str, bool]]:
    """Emit an event based on the specified action for use by websocket clients

    Args:
        id (str): The id of the item the action is being run on
        action (str): The action we are running
        broadcast (bool): Whether to advertise this action to other users
        outstanding_actions (list[tuple[str, str, bool]], optional): A list of actions that must be run after the
        user is disconnected. Defaults to None.

    Returns:
        list[tuple[str, str, bool]]: The new list of outstanding actions
    """
    if outstanding_actions is None:
        outstanding_actions = []
    else:
        outstanding_actions = outstanding_actions.copy()

    if broadcast and user:
        comms_service.emit(
            "broadcast",
            {"id": id, "action": action, "username": user.uname},
        )

    if action == "typing":
        outstanding_actions.append((id, "stop_typing", True))
    elif action == "stop_typing":
        outstanding_actions = [a for a in outstanding_actions if a[1] != "stop_typing"]

    elif action == "viewing":
        outstanding_actions.append((id, "stop_viewing", False))
        if user:
            viewer_service.add_viewer(id, user.uname)

    elif action == "stop_viewing":
        if user:
            viewer_service.remove_viewer(id, user.uname)
        outstanding_actions = [a for a in outstanding_actions if a[1] != "stop_viewing"]

    return outstanding_actions
