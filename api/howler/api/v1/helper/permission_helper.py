from typing import Any, Literal

from howler.common.exceptions import InvalidDataException
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
    # Allow global admin to make changes to any object
    if "admin" in user.type:
        return True

    # User is not a local admin or owner of the object, they cannot make changes to the permissions
    if user.uname not in existing_item.admins and user.uname != existing_item.owner:
        return False

    if level_requested == "owner" and user.uname != existing_item.owner:
        return False

    return True


# I applied the save into these function for simplicity. We could make batch save insted if we plan these
# to be use on large amount of people. From the use they have at the moment it shouldn't be more then a few people.


def _grant_privilege(
    requested_level: str,
    user_to_modify: str,
    existing_item: Ownership,
    user_requesting_change: User,
    refresh: Literal["true", "false", "wait_for"] | None,
    object_type_name: str,
) -> bool:
    """Set privilege for a user on a ownership object.

    Variables:
        requested_level => The privilege level requested base on the string ["admins", "members", "owner"]
        user_to_modify => The user to add or remove from the privilege level
        existing_item => The ownership object to modify
        user_requesting_change => The user requesting the change


    return : Boolean if the change and save was successful
    """
    # does the user to change exist
    storage = datastore()
    user = storage.get_collection("user").get_if_exists(user_to_modify)

    if not user:
        raise InvalidDataException("The user to modify does not exist")

    # is the requesting user allowed to update permission
    if not _is_allowed_to_change(requested_level, user_requesting_change, existing_item):
        raise InvalidDataException("The user requesting the change is not allowed to make the change.")

    # Does the permission exist
    if requested_level not in existing_item:
        raise InvalidDataException(f"{requested_level} is not a valid privilege level for this object")

    # Permission update
    if requested_level == "owner":
        if existing_item["owner"] == user_to_modify:
            return False
        existing_item["owner"] = user_to_modify
        return True

    current_members = existing_item[requested_level]
    if user_to_modify in current_members:
        return False
    existing_item[requested_level] = [*current_members, user_to_modify]

    storage[object_type_name].save(getattr(existing_item, f"{object_type_name}_id"), existing_item, refresh=refresh)

    return True


def _revoke_privilege(
    requested_level: str,
    user_to_modify: str,
    existing_item: Ownership,
    user_requesting_change: User,
    refresh: Literal["true", "false", "wait_for"] | None,
    object_type_name: str,
) -> bool:
    """Remove privilege for a user on a ownership object.

    Variables:
        requested_level => The privilege level requested base on the string ["admins", "members", "owner"]
        user_to_modify => The user to add or remove from the privilege level
        existing_item => The ownership object to modify
        user_requesting_change => The user requesting the change


    return : boolean if the change was made and save
    """
    # does the user to change exist
    storage = datastore()
    user = storage.get_collection("user").get_if_exists(user_to_modify)
    if not user:
        raise InvalidDataException("The user to modify does not exist")

    # is the requesting user allowed to update permission
    if not _is_allowed_to_change(requested_level, user_requesting_change, existing_item):
        raise InvalidDataException("The user requesting the change is not allowed to make the change.")

    # Does the permission exist
    if requested_level not in existing_item:
        raise InvalidDataException(f"{requested_level} is not a valid privilege level for this object")

    # Permission update
    if requested_level == "owner":
        if existing_item["owner"] == user_to_modify:
            return False

        existing_item["owner"] = user_to_modify
        return True

    current_members = existing_item[requested_level]
    if user_to_modify not in current_members:
        return False
    existing_item[requested_level] = [m for m in current_members if m != user_to_modify]

    storage[object_type_name].save(getattr(existing_item, f"{object_type_name}_id"), existing_item, refresh=refresh)

    return True


# TODO: give privilege seem to have a tendancy to not work or send the wrong information back. lets look into that
# " members: Add partial. Added [], missing [shawn-h] " I'll do that tomorrow
def give_privilege(
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
        "user_ids": ["user1", "user2"],
    }
    """
    if not isinstance(j_request, dict):
        raise InvalidDataException("Request body must be a JSON object.")

    # Kept in a variable for type safety during verification
    user_idss = j_request.get("user_ids")

    if not isinstance(user_idss, list) or len(user_idss) == 0:
        raise InvalidDataException("The key 'user_ids' must be a non-empty list.")

    if not isinstance(j_request.get("privilege"), str) or not j_request.get("privilege"):
        raise InvalidDataException("The key 'privilege' must be a string.")

    if any(not isinstance(user_ids, str) or not user_ids.strip() for user_ids in user_idss):
        raise InvalidDataException("Each value in 'user_ids' must be a non-empty string.")

    storage = datastore()
    result = storage[object_type.__name__.lower()].get_if_exists(str(id), as_obj=True)

    if not result:
        raise InvalidDataException(message=f"This {object_type.__name__.lower()} does not exist")

    errors: list[tuple[str, str]] = []

    for user_ids in user_idss:
        try:
            _grant_privilege(
                str(j_request.get("privilege")), user_ids.strip(), result, user, refresh, object_type.__name__.lower()
            )
        except InvalidDataException as e:
            errors.append((user_ids, e.message))
            continue  # Chosen so we can have partial success. Failure will be clearly sent to the user

    if errors:
        error_details = "; ".join([f"{user_ids}: {msg}" for user_ids, msg in errors])
        raise InvalidDataException(message=f"Failed to revoke privileges for some users: {error_details}")

    return result.as_primitives()


def remove_privilege(
    id: str,
    user: User,
    object_type: type[Ownership],
    j_request: dict,
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """Revoke permission from multiple users.

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
            "user_ids": ["user to remove permission from","Other user"],
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

    for user_ids in permission_request.user_ids:
        if user_ids not in (result.admins if permission_request.privilege == "admins" else result.members):
            raise InvalidDataException(
                message=(f"The user '{user_ids}' does not have the '{permission_request.privilege}' privilege.")
            )

    if permission_request.privilege == "owner":
        raise InvalidDataException(
            message="You cannot remove the owner privilege. Only transfer is allowed. (Use the give_privilege endpoint)"
        )

    errors: list[tuple[str, str]] = []

    for user_name in permission_request.user_ids:
        try:
            _revoke_privilege(
                permission_request.privilege, user_name, result, user, refresh, object_type.__name__.lower()
            )
        # Save could not be done
        except InvalidDataException as err:
            errors.append((user_name, err.message))
            continue  # Chosen so we can have partial success. Failure will be clearly sent to the user

    if errors:
        error_details = "; ".join([f"{user_ids}: {msg}" for user_ids, msg in errors])
        raise InvalidDataException(message=f"Failed to revoke privileges for some users: {error_details}")

    return result.as_primitives()
