from typing import Any, Literal, cast

from flask import request

from howler.common.exceptions import InvalidDataException
from howler.common.loader import datastore
from howler.odm.models.ownership import Ownership
from howler.odm.models.permission_request import PermissionRequest
from howler.odm.models.user import User


def _is_allowed_to_change(level_requested: str, user: User, existing_item: Ownership) -> bool:
    if "admin" in user.type:
        return True

    if user.uname not in existing_item.admins and user.uname != existing_item.owner:
        return False

    return level_requested != "owner" or user.uname == existing_item.owner


def _build_permissions_request() -> PermissionRequest:
    payload = cast(dict[str, Any], request.json)
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
    """Grant a privilege to one or more users on an ownership object."""
    permission_request = _build_permissions_request()

    storage = datastore()
    index_name = object_type.__name__.lower()
    collection = storage[index_name]

    result = cast(Ownership, collection.get(id))
    if not result:
        raise InvalidDataException(message=f"{index_name.capitalize()} {id} does not exist")

    if not _is_allowed_to_change(permission_request.privilege, user, result):
        raise InvalidDataException("The user requesting the change is not allowed to make the change.")

    if permission_request.privilege == "owner" and len(permission_request.user_ids) != 1:
        raise InvalidDataException("When setting the owner, user_ids must be a single entry long.")

    errors: list[tuple[str, str]] = []
    for user_id in permission_request.user_ids:
        if not storage.user.exists(user_id):
            errors.append((user_id, f"User {user_id} does not exist"))
            continue

        if permission_request.privilege != "owner" and user_id in result[permission_request.privilege]:
            errors.append((user_id, f"User {user_id} already has permission {permission_request.privilege}"))

    if errors:
        error_details = "; ".join([f"{user_id}: {message}" for user_id, message in errors])
        raise InvalidDataException(message=f"Failed to grant privileges for some users: {error_details}")

    if permission_request.privilege == "owner":
        result.owner = permission_request.user_ids[0]
    else:
        for user_id in permission_request.user_ids:
            cast(list[str], result[permission_request.privilege]).append(user_id)

    collection.save(id, result, refresh=refresh)
    return result.as_primitives()


def remove_privilege(
    id: str,
    user: User,
    object_type: type[Ownership],
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """Revoke a privilege from one or more users on an ownership object."""
    permission_request = _build_permissions_request()

    storage = datastore()
    index_name = object_type.__name__.lower()
    collection = storage[index_name]

    result = cast(Ownership, collection.get(id))
    if not result:
        raise InvalidDataException(message=f"{index_name.capitalize()} {id} does not exist")

    if not _is_allowed_to_change(permission_request.privilege, user, result):
        raise InvalidDataException("The user requesting the change is not allowed to make the change.")

    if permission_request.privilege == "owner":
        raise InvalidDataException(message="You cannot remove the owner privilege. Only transfer is allowed.")

    errors: list[tuple[str, str]] = []
    for user_id in permission_request.user_ids:
        if not storage.user.exists(user_id):
            errors.append((user_id, f"User {user_id} does not exist"))
            continue

        if user_id not in result[permission_request.privilege]:
            errors.append((user_id, f"User {user_id} does not have permission {permission_request.privilege}"))

    if errors:
        error_details = "; ".join([f"{user_id}: {message}" for user_id, message in errors])
        raise InvalidDataException(message=f"Failed to revoke privileges for some users: {error_details}")

    for user_id in permission_request.user_ids:
        cast(list[str], result[permission_request.privilege]).remove(user_id)

    collection.save(id, result, refresh=refresh)
    return result.as_primitives()
