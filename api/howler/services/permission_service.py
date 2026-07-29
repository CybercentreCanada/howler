from typing import Any, Literal, cast

from flask import request

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


def _build_permissions_request():
    payload = cast(dict[str, str], request.json)
    if not isinstance(payload, dict):
        raise InvalidDataException("Request body must be a JSON object.")

    try:
        return PermissionRequest(payload)
    except ValueError as e:
        raise InvalidDataException(message=str(e))


def give_privilege(
    id: str,
    user: User,
    object_type: type[Ownership],
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """Grant a privilege to one or more users on an ownership object.

    Args:
        id: Identifier of the ownership object to update.
        user: Authenticated user requesting the privilege change.
        object_type: Ownership model class that determines the datastore collection.
        refresh: Elasticsearch refresh behavior for the saved object.

    Request JSON:
        privilege: Privilege to grant: ``"members"``, ``"admins"``, or ``"owner"``.
        user_ids: Usernames to receive the privilege. ``"owner"`` requires exactly one username.

    Returns:
        The updated ownership object as primitive values.

    Raises:
        InvalidDataException: If the object does not exist, the requester is unauthorized,
            the request is invalid, or a target user does not exist or already has the privilege.
    """
    permission_request = _build_permissions_request()

    storage = datastore()
    index_name = object_type.__name__.lower()
    collection = storage[index_name]

    result = cast(Ownership, collection.get(id))
    if not result:
        raise InvalidDataException(message=f"{index_name.capitalize()} {id} does not exist")

    # is the requesting user allowed to update permission
    if not _is_allowed_to_change(permission_request.privilege, user, result):
        raise InvalidDataException("The user requesting the change is not allowed to make the change.")

    if permission_request.privilege == "owner" and len(permission_request.user_ids) != 1:
        raise InvalidDataException("When setting the owner, user_ids must be a single entry long.")

    # Ownership is a scalar transfer; member and admin privileges are additive.
    if permission_request.privilege == "owner":
        result.owner = permission_request.user_ids[0]

        collection.save(id, result, refresh=refresh)

        return result.as_primitives()

    errors: list[tuple[str, str]] = []
    for user_id in permission_request.user_ids:
        if not storage.user.exists(user_id):
            errors.append((user_id, f"User {user_id} does not exist"))
            continue

        if user_id in result[permission_request.privilege]:
            errors.append((user_id, f"User {user_id} already has permission {permission_request.privilege}"))
            continue

        cast(list[str], result[permission_request.privilege]).append(user_id)

    # Do not persist partial batch updates when any requested grant is invalid.
    if errors:
        error_details = "; ".join([f"{user_ids}: {msg}" for user_ids, msg in errors])
        raise InvalidDataException(message=f"Failed to revoke privileges for some users: {error_details}")

    collection.save(id, result, refresh=refresh)
    return result.as_primitives()


def remove_privilege(
    id: str,
    user: User,
    object_type: type[Ownership],
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """Revoke a privilege from one or more users on an ownership object.

    Args:
        id: Identifier of the ownership object to update.
        user: Authenticated user requesting the privilege change.
        object_type: Ownership model class that determines the datastore collection.
        refresh: Elasticsearch refresh behavior for the saved object.

    Request JSON:
        privilege: Privilege to revoke: ``"members"`` or ``"admins"``. Ownership
            cannot be revoked and must be transferred with ``give_privilege``.
        user_ids: Usernames from which to revoke the privilege.

    Returns:
        The updated ownership object as primitive values.

    Raises:
        InvalidDataException: If the object does not exist, the requester is unauthorized,
            ownership is requested, or a target user does not exist or lacks the privilege.
    """
    permission_request = _build_permissions_request()

    storage = datastore()
    index_name = object_type.__name__.lower()
    collection = storage[index_name]

    result = cast(Ownership, collection.get(id))
    if not result:
        raise InvalidDataException(message=f"{index_name.capitalize()} {id} does not exist")

    if not _is_allowed_to_change(permission_request.privilege, user, result):
        raise InvalidDataException("The user requesting the change is not allowed to make the change.")

    # Ownership must always belong to one user, so it can only be transferred.
    if permission_request.privilege == "owner":
        raise InvalidDataException(message="You cannot remove the owner privilege. Only transfer is allowed.")

    for user_ids in permission_request.user_ids:
        if user_ids not in (result.admins if permission_request.privilege == "admins" else result.members):
            raise InvalidDataException(
                message=(f"The user '{user_ids}' does not have the '{permission_request.privilege}' privilege.")
            )

    errors: list[tuple[str, str]] = []
    for user_id in permission_request.user_ids:
        if not storage.user.exists(user_id):
            errors.append((user_id, f"User {user_id} does not exist"))
            continue

        if user_id not in result[permission_request.privilege]:
            errors.append((user_id, f"User {user_id} does not have permission {permission_request.privilege}"))
            continue

        cast(list[str], result[permission_request.privilege]).remove(user_id)

    # Do not persist partial batch updates when any requested revocation is invalid.
    if errors:
        error_details = "; ".join([f"{user_ids}: {msg}" for user_ids, msg in errors])
        raise InvalidDataException(message=f"Failed to revoke privileges for some users: {error_details}")

    collection.save(id, result, refresh=refresh)
    return result.as_primitives()
