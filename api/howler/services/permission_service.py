from markupsafe import escape

from howler.common.loader import datastore
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.action import Action
from howler.odm.models.dossier import Dossier
from howler.odm.models.user import User
from howler.odm.models.view import View


def is_allowed_to_change(level_requested: str, user: User, existing_item: Dossier | Action | View) -> bool:
    """Verify for privilege request if they are allowed to request the change or not.

    Variables:
    level_requested => The privilege level requested base on the string from the object [administrator, member, owner]
    user => The user requesting the change
    existing_dossier => The dossier that will be change
    """
    if "admin" in user.type:
        return False

    is_dossier_admin: bool = user.uname in existing_item.admin or user.uname != existing_item.owner

    if not is_dossier_admin and "admin" not in user.type:
        return False

    owner_username: str = existing_item.owner if not isinstance(existing_item, Action) else existing_item.owner_id

    if level_requested == "owner" and user.uname != owner_username:
        return False
    # use the maping to update the list to the proper privilege

    return True


def privilege_value_verifications(
    item_id: str, level_requested: str, member_to_modify: str, is_adding: bool = True, item_type: type = Dossier
) -> tuple[HowlerDatastore, Dossier | View | Action] | str:
    """Verify base value for privilege request are usable.

    If they are it return them else it return the error.
    give permission from one user to an other.

    Variables:
    dossier_id => The id of the dossier to give administrative privilege of
    is_adding => is the verification to remove or to add someone to a group
    """
    storage = datastore()

    if is_adding:
        temp_user = storage.user.get_if_exists(member_to_modify)
        if not temp_user:
            return f"Invalid data format. user id {member_to_modify} does not exist"

    existing_item: Dossier | View | Action | None = None

    if item_type == Dossier:
        existing_item = storage.dossier.get_if_exists(item_id)

    elif item_type == View:
        existing_item = storage.view.get_if_exists(item_id)

    elif item_type == Action:
        existing_item = storage.view.get_if_exists(item_id)

    # Making sur we never continue with empty
    if existing_item is None:
        return "Invalide object type."

    if not existing_item:
        temp_type = type(existing_item)
        return f"This {temp_type} does not exist"
    if level_requested not in existing_item.get_privilege_mapping().keys():
        return f"Permission {level_requested} does not exist options are \
            {existing_item.get_privilege_mapping().keys()}"

    return storage, existing_item


def get_require_data_helper(
    priv_change: dict,
) -> tuple[HowlerDatastore, str, str] | str:
    """Utils to get the requested information from the API"""
    if not isinstance(priv_change, dict):
        return "Invalid data format"

    if not set(priv_change.keys()) & {"privilege", "user_id"}:
        return "Invalid data format. Need new privilege and user_id"

    storage = datastore()
    priv_requested: str = escape(str(priv_change["privilege"]))
    user_to_move: str = escape(str(priv_change["user_id"]))
    return storage, priv_requested, user_to_move
