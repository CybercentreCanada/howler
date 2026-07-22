from typing import Any, Literal

from howler.common.exceptions import (
    HowlerInvalidPermissionException,
    InvalidDataException,
)
from howler.common.loader import datastore
from howler.odm.models.ownership import Ownership
from howler.odm.models.permission_request import PermissionRequest
from howler.odm.models.user import User


def _is_allowed_to_change(level_requested: str, user: User, existing_item: Ownership) -> bool:
    """Verify for privilege request if they are allowed to request the change or not.

    Variables:
    level_requested => The privilege level requested base on the string from the object [admins, members, owner]
    user => The user requesting the change
    existing_item => The ownership object that will be changed
    """
    if "admin" in user.type:
        return True

    if user.uname not in existing_item.admins and user.uname != existing_item.owner:
        return False

    if level_requested == "owner" and user.uname != existing_item.owner:
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
    if not _is_allowed_to_change(requested_level, user_requesting_change, existing_item):
        raise HowlerInvalidPermissionException("The user requesting the change is not allowed to make the change.")

    # Does the permission exist
    if requested_level not in existing_item:
        raise HowlerInvalidPermissionException(f"{requested_level} is not a valid privilege level for this object")

    # Permission update
    if requested_level == "owner":
        if existing_item["owner"] == user_to_modify:
            return False, existing_item
        existing_item["owner"] = user_to_modify
        return True, existing_item

    current_members = existing_item[requested_level]
    if user_to_modify in current_members:
        return False, existing_item
    existing_item[requested_level] = [*current_members, user_to_modify]

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
    if not _is_allowed_to_change(requested_level, user_requesting_change, existing_item):
        raise HowlerInvalidPermissionException("The user requesting the change is not allowed to make the change.")

    # Does the permission exist
    if requested_level not in existing_item:
        raise HowlerInvalidPermissionException(f"{requested_level} is not a valid privilege level for this object")

    # Permission update
    if requested_level == "owner":
        if existing_item["owner"] == user_to_modify:
            return False, existing_item
        # transfer ownership to None or empty string
        existing_item["owner"] = user_to_modify
        return True, existing_item

    current_members = existing_item[requested_level]
    if user_to_modify not in current_members:
        return False, existing_item
    existing_item[requested_level] = [m for m in current_members if m != user_to_modify]

    return True, existing_item


def give_privilege(
    id: str,
    user: User,
    object_type: type[Ownership],
    j_request: dict,
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """give permission from one user to an other.

        The json object need to send "privilege", "user_id" as a key.
        privilege : The value need to be one of ["admins", "members", "owner"]
        user_id : the value need to be the user to add or remove from the permission
    Variables:
    action_id => The id of the action to give administrative privilege of

    Arguments:
        id : The id of the action to give administrative privilege of
        user : the user requesting the privilege change (injected by the api_login decorator)
        j_request : the json request body containing the privilege and user_id

    Optional Arguments:
    refresh =>  ('true' | 'false' | 'wait_for') Whether to refresh the datastore before returning.
        'wait_for' will wait for the change to be visible in search.

    Data Block:
    {
        "privilege": "privilege to give"  # [members, admins, owner]
        "user_id": "user to give permission to"
    }

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    try:
        permission_request = PermissionRequest(j_request)
    except ValueError as e:
        raise InvalidDataException(message=str(e))

    storage = datastore()
    result = storage[object_type.__name__.lower()].get_if_exists(str(id), as_obj=True)

    if not result:
        raise InvalidDataException(message=f"This {object_type.__name__.lower()} does not exist")

    try:
        success, result = set_privilege(permission_request.privilege, permission_request.user_id, result, user)
    except HowlerInvalidPermissionException as e:
        raise HowlerInvalidPermissionException(message=e.message)
    except InvalidDataException as e:
        raise InvalidDataException(message=e.message)

    if success:
        storage[object_type.__name__.lower()].save(
            getattr(result, f"{object_type.__name__.lower()}_id"),
            result,
            refresh=refresh,
        )

    return result.as_primitives()


def give_multi_privilege(
    id: str,
    user: User,
    object_type: type[Ownership],
    j_request: dict,
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """Give the same privilege to multiple users in a single request.

    Data Block:
    {
        "privilege": "privilege to give",  # [members, admins, owner]
        "user_id": ["user1", "user2"],
    }
    """
    if not isinstance(j_request, dict):
        raise InvalidDataException("Request body must be a JSON object.")

    user_ids = j_request.get("user_id")

    if not isinstance(user_ids, list) or len(user_ids) == 0:
        raise InvalidDataException("The key 'user_id' must be a non-empty list.")

    if not isinstance(j_request.get("privilege"), str) or not j_request.get("privilege"):
        raise InvalidDataException("The key 'privilege' must be a string.")

    if any(not isinstance(user_id, str) or not user_id.strip() for user_id in user_ids):
        raise InvalidDataException("Each value in 'user_id' must be a non-empty string.")

    storage = datastore()
    result = storage[object_type.__name__.lower()].get_if_exists(str(id), as_obj=True)

    if not result:
        raise InvalidDataException(message=f"This {object_type.__name__.lower()} does not exist")

    any_success = False
    for user_id in user_ids:
        try:
            success, result = set_privilege(str(j_request.get("privilege")), user_id.strip(), result, user)
        except HowlerInvalidPermissionException as e:
            raise HowlerInvalidPermissionException(message=e.message)
        except InvalidDataException as e:
            raise InvalidDataException(message=e.message)

        any_success = any_success or success

    if any_success:
        storage[object_type.__name__.lower()].save(
            getattr(result, f"{object_type.__name__.lower()}_id"),
            result,
            refresh=refresh,
        )

    return result.as_primitives()


def revoke_privilege(
    id: str,
    user: User,
    object_type: type[Ownership],
    j_request: dict,
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """Revoke permission from one user.

    Variables:
        id => The unique ID of the action embedded in the URL path

    Arguments:
        id: The id of the action to modify permissions for
        user: The user making the request (injected by the api_login decorator)

    Optional Arguments:
    refresh =>  ('true' | 'false' | 'wait_for') Whether to refresh the datastore before returning.
        'wait_for' will wait for the change to be visible in search.
        Defaults to 'true'.

    Data Block:
        {
            "privilege": "privilege to revoke",  # [members, admins, owner]
            "user_id": "user to remove permission from",
        }

    Result Example:
        {
            "success": True
        }
    """
    try:
        permission_request = PermissionRequest(j_request)
    except ValueError as e:
        raise InvalidDataException(message=str(e))

    storage = datastore()
    result = storage[object_type.__name__.lower()].get_if_exists(str(id), as_obj=True)

    if not result:
        raise InvalidDataException(message=f"This {object_type.__name__.lower()} does not exist")

    if permission_request.user_id not in (
        result.admins if permission_request.privilege == "admins" else result.members
    ):
        raise HowlerInvalidPermissionException(
            message=(
                f"The user '{permission_request.user_id}' does not have the '{permission_request.privilege}' privilege."
            )
        )

    if permission_request.privilege == "owner":
        raise HowlerInvalidPermissionException(
            message="You cannot remove the owner privilege. Only transfer is allowed. (Use the give_privilege endpoint)"
        )

    try:
        success, result = remove_privilege(permission_request.privilege, permission_request.user_id, result, user)
    except HowlerInvalidPermissionException as e:
        raise HowlerInvalidPermissionException(message=e.message)
    except InvalidDataException as e:
        raise InvalidDataException(message=e.message)

    if success:
        storage[object_type.__name__.lower()].save(
            getattr(result, f"{object_type.__name__.lower()}_id"),
            result,
            refresh=refresh,
        )

    return result.as_primitives()
