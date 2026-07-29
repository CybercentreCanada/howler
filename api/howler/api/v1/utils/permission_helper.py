from flask import Blueprint, Response

from howler.api import bad_request, ok
from howler.api.v1.utils.params import parse_parameters, parse_refresh
from howler.common.exceptions import InvalidDataException
from howler.common.swagger import generate_swagger_docs
from howler.odm.models.ownership import Ownership
from howler.odm.models.user import User
from howler.security import api_login
from howler.services import permission_service


def add_access_control_endpoints(api: Blueprint, odm: type[Ownership]):
    """Add access control routes for managing user permissions.

    Args:
        api: The Flask Blueprint to add routes to.
        odm: The Ownership ODM model class.
    """

    @generate_swagger_docs()
    @api.route("/<id>/permission", methods=["PUT"])
    @api_login(required_priv=["R", "W"])
    @parse_parameters(refresh=parse_refresh)
    def give_privilege(id: str, user: User, **kwargs) -> Response:
        """Give permission from one user to another.

        The json object need to send "privilege", "user_id" as a key.
        privilege : The value need to be one of ["admins", "members", "owner"]
        user_id : the value need to be the user to add or remove from the permission
        is_adding: The value neeed to be a boolean representing if we add or remove a user.

        Variables:
        dossier_id => The id of the dossier to give administrative privilege of

        Optional Arguments:
            None

        Data Block:
        {
            "privilege": "privilege to give"  # [members, admins, owner]
            "user_id": ["user to give permission to", "other_user_to_give_permission"]
        }

        Result Example:
        {
            "success": True     # If the operation succeeded
        }
        """
        try:
            result = permission_service.give_privilege(id, user, odm, refresh=kwargs.get("refresh"))
        except (ValueError, InvalidDataException) as e:
            return bad_request(err=str(e))
        return ok(result)

    @generate_swagger_docs()
    @api.route("/<id>/permission", methods=["DELETE"])
    @api_login(required_priv=["R", "W"])
    @parse_parameters(refresh=parse_refresh)
    def remove_privilege(id: str, user: User, **kwargs) -> Response:
        """Revoke permission from one user to another.

        Variables:
            dossier_id => The id of the dossier to revoke administrative privilege of

        Arguments:
            refresh =>  ('true' | 'false' | 'wait_for') Whether to refresh the datastore before returning.
                'wait_for' will wait for the change to be visible in search.

        Optional Arguments:
            None

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
            result = permission_service.remove_privilege(id, user, odm, refresh=kwargs.get("refresh"))
        except (ValueError, InvalidDataException) as e:
            return bad_request(err=str(e))
        return ok(result)
