from howler.common.exceptions import (
    HowlerInvalidPermissionException,
    InvalidDataException,
)
from howler.common.loader import datastore
from howler.odm.models.ownership import Ownership
from howler.odm.models.user import User


def __is_allowed_to_change(level_requested: str, user: User, existing_item: Ownership) -> bool:
    """Verify for privilege request if they are allowed to request the change or not.

    Variables:
    level_requested => The privilege level requested base on the string from the object [admins, members, owner]
    user => The user requesting the change
    existing_item => The ownership object that will be changed
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


def set_privilege(
    requested_level: str, user_to_modify: str, existing_item: Ownership, user_requesting_change: User
) -> tuple[bool, Ownership]:
    """Set privilege for a user on a ownership object.

    Variables:
        requested_level => The privilege level requested base on the string ["admins", "members", "owner"]
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
    if not __is_allowed_to_change(requested_level, user_requesting_change, existing_item):
        raise HowlerInvalidPermissionException("The user requesting the change is not allowed to make the change.")

    # Does the permission exist
    # NOTE: ODM models may not materialize optional/default fields in __dict__ until touched,
    # so validating against __dict__ can incorrectly reject valid ownership fields.
    if not hasattr(existing_item, requested_level):
        raise HowlerInvalidPermissionException(f"{requested_level} is not a valid privilege level for this object")

    # Permission update
    if requested_level == "owner":
        if existing_item.owner == user_to_modify:
            return False, existing_item
        existing_item.owner = user_to_modify
        return True, existing_item

    current_members = getattr(existing_item, requested_level)
    if user_to_modify in current_members:
        return False, existing_item
    current_members.append(user_to_modify)

    return True, existing_item


def remove_privilege(
    requested_level: str, user_to_modify: str, existing_item: Ownership, user_requesting_change: User
) -> tuple[bool, Ownership]:
    """Remove privilege for a user on a ownership object.

    Variables:
        requested_level => The privilege level requested base on the string ["admins", "members", "owner"]
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
    if not __is_allowed_to_change(requested_level, user_requesting_change, existing_item):
        raise HowlerInvalidPermissionException("The user requesting the change is not allowed to make the change.")

    # Does the permission exist
    # NOTE: ODM models may not materialize optional/default fields in __dict__ until touched,
    # so validating against __dict__ can incorrectly reject valid ownership fields.
    if not hasattr(existing_item, requested_level):
        raise HowlerInvalidPermissionException(f"{requested_level} is not a valid privilege level for this object")

    # Permission update
    if requested_level == "owner":
        if existing_item.owner == user_to_modify:
            return False, existing_item
        # transfer ownership to None or empty string
        existing_item.owner = user_to_modify
        return True, existing_item

    current_members = getattr(existing_item, requested_level)
    if user_to_modify not in current_members:
        return False, existing_item
    current_members.remove(user_to_modify)

    return True, existing_item  # if we are here, nothing happened
