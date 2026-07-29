from flask import Blueprint, Response

from howler.api import bad_request, ok
from howler.api.v1.utils.params import parse_parameters, parse_refresh
from howler.common.exceptions import InvalidDataException
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
        try:
            result = permission_service.remove_privilege(id, user, odm, refresh=kwargs.get("refresh"))
        except (ValueError, InvalidDataException) as e:
            return bad_request(err=str(e))
        return ok(result)
