from collections.abc import Sequence
from typing import Any, Literal, Protocol, cast

from flask import request

from howler.common.exceptions import ForbiddenException, InvalidDataException
from howler.common.loader import datastore
from howler.odm.models.ownership import Ownership
from howler.odm.models.permission_request import PermissionRequest
from howler.odm.models.user import User


class _VisibilityItem(Protocol):
    @property
    def owner(self) -> str: ...

    @property
    def type(self) -> str: ...

    @property
    def admins(self) -> Sequence[str]: ...

    @property
    def members(self) -> Sequence[str]: ...


def can_change_visibility(existing_item: _VisibilityItem, requested_type: str) -> bool:
    """Return whether a shared record can change its visibility."""
    shared_users = set(existing_item.admins).union(existing_item.members)
    shared_users.discard(existing_item.owner)

    return requested_type == existing_item.type or not shared_users


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
        permission_request = PermissionRequest(payload)
    except ValueError as e:
        raise InvalidDataException(message=str(e))

    if not permission_request.user_ids:
        raise InvalidDataException("user_ids must contain at least one user.")

    return permission_request


def give_privilege(
    id: str,
    user: User,
    object_type: type[Ownership],
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """Grant a privilege to one or more users on an ownership object."""
    permission_request = _build_permissions_request()
    user_ids = list(dict.fromkeys(permission_request.user_ids))

    storage = datastore()
    index_name = object_type.__name__.lower()
    collection = storage[index_name]

    result = cast(Ownership, collection.get(id))
    if not result:
        raise InvalidDataException(message=f"{index_name.capitalize()} {id} does not exist")

    if not _is_allowed_to_change(permission_request.privilege, user, result):
        raise ForbiddenException("The user requesting the change is not allowed to make the change.")

    if permission_request.privilege == "owner" and len(user_ids) != 1:
        raise InvalidDataException("When setting the owner, user_ids must be a single entry long.")

    errors: list[tuple[str, str]] = []
    for user_id in user_ids:
        if not storage.user.exists(user_id):
            errors.append((user_id, f"User {user_id} does not exist"))
            continue

        if permission_request.privilege != "owner" and user_id in result[permission_request.privilege]:
            errors.append((user_id, f"User {user_id} already has permission {permission_request.privilege}"))

    if errors:
        error_details = "; ".join([f"{user_id}: {message}" for user_id, message in errors])
        raise InvalidDataException(message=f"Failed to grant privileges for some users: {error_details}")

    if permission_request.privilege == "owner":
        result.owner = user_ids[0]
    else:
        for user_id in user_ids:
            cast(list[str], result[permission_request.privilege]).append(user_id)

    collection.save(id, result, refresh=refresh)
    return result.as_primitives()


def remove_privilege(  # noqa: C901
    id: str,
    user: User,
    object_type: type[Ownership],
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """Revoke a privilege from one or more users on an ownership object."""
    permission_request = _build_permissions_request()
    user_ids = list(dict.fromkeys(permission_request.user_ids))

    storage = datastore()
    index_name = object_type.__name__.lower()
    collection = storage[index_name]

    result = cast(Ownership, collection.get(id))
    if not result:
        raise InvalidDataException(message=f"{index_name.capitalize()} {id} does not exist")

    if not _is_allowed_to_change(permission_request.privilege, user, result):
        raise ForbiddenException("The user requesting the change is not allowed to make the change.")

    if permission_request.privilege == "owner":
        raise InvalidDataException(message="You cannot remove the owner privilege. Only transfer is allowed.")

    current_members = result.admins if permission_request.privilege == "admins" else result.members
    for user_id in user_ids:
        if user_id not in current_members:
            raise InvalidDataException(
                message=f"The user '{user_id}' does not have the '{permission_request.privilege}' privilege."
            )

    errors: list[tuple[str, str]] = []
    for user_id in user_ids:
        if not storage.user.exists(user_id):
            errors.append((user_id, f"User {user_id} does not exist"))
            continue

        if user_id not in result[permission_request.privilege]:
            errors.append((user_id, f"User {user_id} does not have permission {permission_request.privilege}"))

    if errors:
        error_details = "; ".join([f"{user_id}: {message}" for user_id, message in errors])
        raise InvalidDataException(message=f"Failed to revoke privileges for some users: {error_details}")

    for user_id in user_ids:
        cast(list[str], result[permission_request.privilege]).remove(user_id)

    collection.save(id, result, refresh=refresh)
    return result.as_primitives()
