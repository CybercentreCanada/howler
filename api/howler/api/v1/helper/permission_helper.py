from howler.api import bad_request, forbidden, not_found, ok
from howler.common.exceptions import (
    HowlerInvalidPermissionException,
    InvalidDataException,
)
from howler.common.loader import datastore
from howler.odm.models.ownership import Ownership
from howler.odm.models.permission_request import PermissionRequest
from howler.odm.models.user import User
from howler.services import permission_service


def give_privilege(id: str, user: User, object_type: type[Ownership], j_request: dict, refresh: str | None = None):
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
        return bad_request(err=str(e))

    storage = datastore()
    result = storage[object_type.__name__.lower()].get_if_exists(str(id), as_obj=True)

    if not result:
        return not_found(err=f"This {object_type.__name__.lower()} does not exist")

    if not isinstance(result, object_type):
        return bad_request(
            err=f"Wrong request type. Object of type {type(result)} was requested insted of {object_type.__name__}"
        )

    try:
        success, result = permission_service.set_privilege(
            permission_request.privilege, permission_request.user_id, result, user
        )
    except HowlerInvalidPermissionException as e:
        return forbidden(err=e.message)
    except InvalidDataException as e:
        return bad_request(err=e.message)

    if success:
        storage[object_type.__name__.lower()].save(
            getattr(result, f"{object_type.__name__.lower()}_id"),
            result,
            refresh=refresh,
        )

    return ok(result.as_primitives())


def revoke_privilege(id: str, user: User, object_type: type[Ownership], j_request: dict, refresh: str | None = None):
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
        return bad_request(err=str(e))

    storage = datastore()
    result = storage[object_type.__name__.lower()].get_if_exists(str(id), as_obj=True)

    if not result:
        return not_found(err=f"This {object_type.__name__.lower()} does not exist")

    if not isinstance(result, object_type):
        return bad_request(
            err=f"Wrong request type. Object of type {type(result)} was requested insted of {object_type.__name__}"
        )

    if permission_request.user_id not in (
        result.admins if permission_request.privilege == "admins" else result.members
    ):
        return bad_request(
            err=f"{permission_request.user_id} is not in the {permission_request.privilege} permission group"
        )

    if permission_request.privilege == "owner":
        return bad_request(
            err="You cannot remove the owner privilege. Only transfer is allowed. (Use the give_privilege endpoint)"
        )

    try:
        success, result = permission_service.remove_privilege(
            permission_request.privilege, permission_request.user_id, result, user
        )
    except HowlerInvalidPermissionException as e:
        return forbidden(err=e.message)
    except InvalidDataException as e:
        return bad_request(err=e.message)

    if success:
        storage[object_type.__name__.lower()].save(
            getattr(result, f"{object_type.__name__.lower()}_id"),
            result,
            refresh=refresh,
        )

    return ok(result.as_primitives())
