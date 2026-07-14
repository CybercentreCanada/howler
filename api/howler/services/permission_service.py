from markupsafe import escape

from howler.common.exceptions import (
    HowlerAttributeError,
    HowlerInvalidPermissionException,
    InvalidDataException,
)
from howler.common.loader import datastore
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.dossier import Dossier
from howler.odm.models.ownership_object import OwnershipObject
from howler.odm.models.user import User


def is_allowed_to_change(level_requested: str, user: User, existing_item: OwnershipObject) -> bool:
    """Verify for privilege request if they are allowed to request the change or not.

    Variables:
    level_requested => The privilege level requested base on the string from the object [administrator, member, owner]
    user => The user requesting the change
    existing_dossier => The dossier that will be change
    """
    if "admin" in user.type:
        return True

    is_admin: bool = user.uname in existing_item.admins or user.uname == existing_item.owner

    if not is_admin:
        return False

    in_owner = user.uname == existing_item.owner
    if level_requested == "owner" and not in_owner:
        return False
    return True


def verify_privilege_values(
    item_id: str, level_requested: str, member_to_modify: str, is_adding: bool = True, item_type: type = Dossier
) -> OwnershipObject:
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
    field_requested = level_requested
    if level_requested == "administrator":
        field_requested = "admins"
    elif level_requested == "member":
        field_requested = "members"

    if field_requested not in existing_item.__dict__.keys():
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


def set_privilege(
    requested_level: str, user_to_modify: str, existing_item: OwnershipObject, user_requesting_change: User
) -> tuple[bool, OwnershipObject]:
    """Set privilege for a user on a ownership object.

    Variables:
        requested_level => The privilege level requested base on the string ["administrator", "member", "owner"]
        user_to_modify => The user to add or remove from the privilege level
        existing_item => The ownership object to modify
        user_requesting_change => The user requesting the change


    return : Boolean of the change and the original object
    """
    # does the user to change exist
    storage = datastore()
    user = storage.get_collection("user").get_if_exists(user_to_modify)
    if not user:
        raise InvalidDataException("The user to modify does not exist")

    # is the requesting user allowed to update permission
    if not is_allowed_to_change(requested_level, user_requesting_change, existing_item):
        raise HowlerInvalidPermissionException("The user requesting the change is not allowed to make the change.")

    # Does the permission exist
    field_requested = (
        "admins"
        if requested_level == "administrator"
        else "members"
        if requested_level == "member"
        else requested_level
    )

    if field_requested not in existing_item.__dict__.keys():
        raise HowlerInvalidPermissionException(f"{requested_level} is not a valid privilege level for this object")

    # Permission update
    if field_requested == "owner":
        if existing_item.owner == user_to_modify:
            return False, existing_item
        existing_item.owner = user_to_modify
        return True, existing_item

    current_members = getattr(existing_item, field_requested)
    if user_to_modify in current_members:
        return False, existing_item
    current_members.append(user_to_modify)

    return True, existing_item


def remove_privilege(
    requested_level: str, user_to_modify: str, existing_item: OwnershipObject, user_requesting_change: User
) -> tuple[bool, OwnershipObject]:
    """Remove privilege for a user on a ownership object.

    Variables:
        requested_level => The privilege level requested base on the string ["administrator", "member", "owner"]
        user_to_modify => The user to add or remove from the privilege level
        existing_item => The ownership object to modify
        user_requesting_change => The user requesting the change


    return : boolean representing change and the original object
    """
    # does the user to change exist
    storage = datastore()
    user = storage.get_collection("user").get_if_exists(user_to_modify)
    if not user:
        raise InvalidDataException("The user to modify does not exist")

    # is the requesting user allowed to update permission
    if not is_allowed_to_change(requested_level, user_requesting_change, existing_item):
        raise HowlerInvalidPermissionException("The user requesting the change is not allowed to make the change.")

    # Does the permission exist
    field_requested = (
        "admins"
        if requested_level == "administrator"
        else "members"
        if requested_level == "member"
        else requested_level
    )

    if field_requested not in existing_item.__dict__.keys():
        raise HowlerInvalidPermissionException(f"{requested_level} is not a valid privilege level for this object")

    # Permission update
    if field_requested == "owner":
        if existing_item.owner == user_to_modify:
            return False, existing_item
        # transfer ownership to None or empty string
        existing_item.owner = user_to_modify
        return True, existing_item

    current_members = getattr(existing_item, field_requested)
    if user_to_modify not in current_members:
        return False, existing_item
    current_members.remove(user_to_modify)

    return True, existing_item  # if we are here, nothing happened
