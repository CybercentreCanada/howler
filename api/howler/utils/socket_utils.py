from howler.common.logging import get_logger
from howler.datastore.operations import OdmHelper
from howler.odm.models.hit import Hit
from howler.services import event_service, hit_service

logger = get_logger(__file__)

hit_helper = OdmHelper(Hit)


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
        if hit_service.exists(id):
            outstanding_actions.append((id, "stop_viewing", False))
            hit_service.update_hit(
                id,
                [
                    hit_helper.list_add(
                        "howler.viewers",
                        kwargs["username"],
                        silent=True,
                        if_missing=True,
                    )
                ],
                user=kwargs["username"],
            )
    elif action == "stop_viewing":
        if hit_service.exists(id):
            hit_service.update_hit(
                id,
                [hit_helper.list_remove("howler.viewers", kwargs["username"], silent=True)],
                user=kwargs["username"],
            )
        outstanding_actions = [a for a in outstanding_actions if a[1] != "stop_viewing"]

    return outstanding_actions
