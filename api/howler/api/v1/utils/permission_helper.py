from flask import Blueprint, Response

from howler.api import bad_request, forbidden, ok
from howler.api.v1.utils.params import parse_parameters, parse_refresh
from howler.common.exceptions import ForbiddenException, InvalidDataException
from howler.common.swagger import generate_swagger_docs
from howler.odm.models.ownership import Ownership
from howler.odm.models.user import User
from howler.security.login import api_login
from howler.services import permission_service


def add_access_control_endpoints(api: Blueprint, odm: type[Ownership]):
    """Add access control routes for managing user permissions."""

    @generate_swagger_docs()
    @api.route("/<id>/permission", methods=["PUT"])
    @api_login(required_priv=["R", "W"])
    @parse_parameters(refresh=parse_refresh)
    def give_privilege(id: str, user: User, **kwargs) -> Response:
        """Grant a permission on an action, dossier, or view.

        Variables:
        id => The identifier of the object whose permissions should be updated.

        Arguments:
        None

        Optional Arguments:
        refresh => ('true' | 'false' | 'wait_for') Whether to refresh the datastore before returning.

        Data Block:
        {
            "privilege": "members",       # The permission level: 'owner', 'admins', or 'members'
            "user_ids": ["username"]       # The users receiving the permission
        }

        Result Example:
        {
            ...object   # The updated action, dossier, or view
        }
        """
        try:
            result = permission_service.give_privilege(id, user, odm, refresh=kwargs.get("refresh"))
        except ForbiddenException as e:
            return forbidden(err=e.message)
        except (ValueError, InvalidDataException) as e:
            return bad_request(err=str(e))
        return ok(result)

    @generate_swagger_docs()
    @api.route("/<id>/permission", methods=["DELETE"])
    @api_login(required_priv=["R", "W"])
    @parse_parameters(refresh=parse_refresh)
    def remove_privilege(id: str, user: User, **kwargs) -> Response:
        """Revoke a permission on an action, dossier, or view.

        Variables:
        id => The identifier of the object whose permissions should be updated.

        Arguments:
        None

        Optional Arguments:
        refresh => ('true' | 'false' | 'wait_for') Whether to refresh the datastore before returning.

        Result Example:
        {
            ...object   # The updated action, dossier, or view
        }
        """
        try:
            result = permission_service.remove_privilege(id, user, odm, refresh=kwargs.get("refresh"))
        except ForbiddenException as e:
            return forbidden(err=e.message)
        except (ValueError, InvalidDataException) as e:
            return bad_request(err=str(e))
        return ok(result)
