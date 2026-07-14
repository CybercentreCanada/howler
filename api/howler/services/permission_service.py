from markupsafe import escape

from howler.common.exceptions import HowlerAttributeError, InvalidDataException
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
        return True
    conversion: dict = existing_item.get_privilege_mapping()

    is_admin: bool = user.uname in conversion.get("administrator", []) or (
        user.uname in conversion["owner"]
        if isinstance(conversion.get("owner"), list)
        else user.uname == conversion.get("owner", "")
    )

    if not is_admin:
        return False

    owner_val = conversion.get("owner", "")
    in_owner = user.uname in owner_val if isinstance(owner_val, list) else user.uname == owner_val
    if level_requested == "owner" and not in_owner:
        return False
    return True


def verify_privilege_values(
    item_id: str, level_requested: str, member_to_modify: str, is_adding: bool = True, item_type: type = Dossier
) -> Dossier | View | Action:
    """Verify base value for privilege request are usable.

    If they are it return them else it return the error.
    give permission from one user to an other.

    Variables:
    dossier_id => The id of the dossier to give administrative privilege of
    is_adding => is the verification to remove or to add someone to a group
    """
    storage = datastore()

    try:
        existing_item = storage.get_collection(item_type.__name__.lower()).get_if_exists(item_id)
    except HowlerAttributeError as e:
        raise InvalidDataException("Invalid item type") from e

    # Making sur we never continue with empty
    if existing_item is None:
        raise InvalidDataException(f"This {item_type.__name__} does not exist")

    if not existing_item:
        temp_type = type(existing_item)
        raise InvalidDataException(f"This {temp_type.__name__} does not exist")
    if level_requested not in existing_item.get_privilege_mapping().keys():
        raise InvalidDataException(f"{level_requested} is not a valid privilege level for this {item_type.__name__}")

    return existing_item


# TODO : AG : Make a new ODM object insted and return an instantiated object
def get_require_data_helper(
    priv_change: dict,
) -> tuple[HowlerDatastore, str, str] | str:
    """Utils to get the requested information from the API"""
    if not isinstance(priv_change, dict):
        return "Invalid data format"

    if not {"privilege", "user_id"}.issubset(priv_change.keys()):
        return "Invalid data format. Need new privilege and user_id"

    storage = datastore()
    priv_requested: str = escape(str(priv_change["privilege"]))
    user_to_move: str = escape(str(priv_change["user_id"]))
    return storage, priv_requested, user_to_move


def _get_edit_auth_error(existing_item: Dossier | Action | View, user: User) -> str | None:
    """Helper function to validate if a user can edit an item. Returns the error string or None."""
    if existing_item.type == "readonly":
        return "You cannot edit a built-in view."

    if existing_item.type == "personal" and user.uname != existing_item.owner:
        return "You cannot update a personal view that is not owned by you."

    if existing_item.type == "global" and "admin" not in user.type:
        mapping = existing_item.get_privilege_mapping()
        allowed_users = {u for val in mapping.values() for u in ([val] if isinstance(val, str) else val)}
        if user.uname not in allowed_users:
            return "Only the members of a view and global administrators can edit a global view."

    return None
