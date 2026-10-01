from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Literal, Protocol, cast

from flask import request

from howler.common.exceptions import ForbiddenException, HowlerTypeError, InvalidDataException
from howler.common.loader import datastore
from howler.odm.models.ownership import Ownership
from howler.odm.models.permission_request import PermissionRequest
from howler.odm.models.user import User

if TYPE_CHECKING:
    from howler.datastore.collection import ESCollection


class _VisibilityItem(Protocol):
    @property
    def owner(self) -> str: ...

    @property
    def type(self) -> str: ...

    @property
    def admins(self) -> Sequence[str]: ...

    @property
    def members(self) -> Sequence[str]: ...


def _is_allowed_to_change(level_requested: str, user: User, existing_item: Ownership) -> bool:
    if "admin" in user.type:
        return True

    if user.uname not in existing_item.admins and user.uname != existing_item.owner:
        return False

    return level_requested != "owner" or user.uname == existing_item.owner


def _build_permissions_request() -> list[PermissionRequest]:
    payload = cast(list[dict[str, Any]], request.json)
    if not isinstance(payload, list):
        raise InvalidDataException("Request body must be a JSON array.")
    if not payload:
        raise InvalidDataException("Request body must contain at least one permission.")

    try:
        permission_requests = [PermissionRequest(entry) for entry in payload]
    except (TypeError, ValueError, HowlerTypeError) as e:
        raise InvalidDataException(message=str(e))

    user_ids = [permission_request.user_id for permission_request in permission_requests]
    if any(not user_id for user_id in user_ids):
        raise InvalidDataException("user_id must contain a user.")
    if len(user_ids) != len(set(user_ids)):
        raise InvalidDataException("Each user can only be included once per request.")

    return permission_requests


def give_privileges(
    id: str,
    user: User,
    object_type: type[Ownership],
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """Grant privileges to users on an ownership object."""
    permission_requests = _build_permissions_request()

    storage = datastore()
    index_name = object_type.__name__.lower()
    collection: "ESCollection[Ownership]" = storage[index_name]

    result, version = collection.get(id, as_obj=True, version=True)
    if not result:
        raise InvalidDataException(message=f"{index_name.capitalize()} {id} does not exist")

    owner_requests = [
        permission_request for permission_request in permission_requests if permission_request.privilege == "owner"
    ]
    if len(owner_requests) > 1:
        raise InvalidDataException("Only one owner can be set per request.")

    for permission_request in permission_requests:
        user_id = permission_request.user_id
        if not _is_allowed_to_change(permission_request.privilege, user, result):
            raise ForbiddenException("The user requesting the change is not allowed to make the change.")

        if not storage.user.exists(user_id):
            raise InvalidDataException(message=f"User {user_id} does not exist")

        if permission_request.privilege != "owner" and user_id in result[permission_request.privilege]:
            raise InvalidDataException(message=f"User {user_id} already has permission {permission_request.privilege}")

    # Apply all changes only after the complete request has been validated.
    for permission_request in permission_requests:
        user_id = permission_request.user_id
        if permission_request.privilege == "owner":
            result.owner = user_id

            for privilege in ("admins", "members"):
                current_members = cast(list[str], result[privilege])
                current_members[:] = [member_id for member_id in current_members if member_id != user_id]
        else:
            current_members = cast(list[str], result[permission_request.privilege])
            other_privilege = "members" if permission_request.privilege == "admins" else "admins"
            other_members = cast(list[str], result[other_privilege])

            # Switching between non-owner privileges removes the previous privilege.
            other_members[:] = [member_id for member_id in other_members if member_id != user_id]
            current_members.append(user_id)

    collection.save(id, result, version=version, refresh=refresh)
    return result.as_primitives()


def remove_privileges(  # noqa: C901
    id: str,
    user: User,
    object_type: type[Ownership],
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> dict[str, Any]:
    """Revoke privileges from users on an ownership object."""
    permission_requests = _build_permissions_request()

    storage = datastore()
    index_name = object_type.__name__.lower()
    collection: "ESCollection[Ownership]" = storage[index_name]

    result, version = collection.get(id, as_obj=True, version=True)
    if not result:
        raise InvalidDataException(message=f"{index_name.capitalize()} {id} does not exist")

    for permission_request in permission_requests:
        if not _is_allowed_to_change(permission_request.privilege, user, result):
            raise ForbiddenException("The user requesting the change is not allowed to make the change.")

        if permission_request.privilege == "owner":
            raise InvalidDataException(message="You cannot remove the owner privilege. Only transfer is allowed.")

        user_id = permission_request.user_id
        current_members = result.admins if permission_request.privilege == "admins" else result.members
        if user_id not in current_members:
            raise InvalidDataException(
                message=f"The user '{user_id}' does not have the '{permission_request.privilege}' privilege."
            )

    for permission_request in permission_requests:
        cast(list[str], result[permission_request.privilege]).remove(permission_request.user_id)

    collection.save(id, result, version=version, refresh=refresh)
    return result.as_primitives()
