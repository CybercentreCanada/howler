from typing import Any, Optional

from mergedeep.mergedeep import merge

from howler.common.exceptions import ForbiddenException, HowlerException, InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import SearchException
from howler.odm.models.dossier import Dossier
from howler.odm.models.user import User

logger = get_logger(__file__)

PERMITTED_KEYS = {
    "title",
    "query",
    "leads",
    "pivots",
    "type",
    "owner",
}


def exists(dossier_id: str) -> bool:
    """Returns true if the analytic_id is already in use."""
    return datastore().dossier.exists(dossier_id)


def get_dossier(
    id: str,
    as_odm: bool = False,
    version: bool = False,
) -> Dossier:
    """Return analytic object as either an ODM or Dict"""
    return datastore().dossier.get_if_exists(key=id, as_obj=as_odm, version=version)


def create_dossier(dossier_data: Optional[Any], username: str) -> Dossier:  # noqa: C901
    "Create a dossier"
    if not isinstance(dossier_data, dict):
        raise InvalidDataException("Invalid data format")

    if "title" not in dossier_data:
        raise InvalidDataException("You must specify a title when creating a dossier.")

    if "query" not in dossier_data:
        raise InvalidDataException("You must specify a query when creating a dossier.")

    if "type" not in dossier_data:
        raise InvalidDataException("You must specify a type when creating a dossier.")

    storage = datastore()

    try:
        # Make sure the query is valid
        if query := dossier_data.get("query", None):
            storage.hit.search(query)

        if "owner" not in dossier_data:
            dossier_data["owner"] = username

        dossier = Dossier(dossier_data)

        for pivot in dossier.pivots:
            if len(pivot.mappings) != len(set(mapping.key for mapping in pivot.mappings)):
                raise InvalidDataException("One of your pivots has duplicate keys set.")

        dossier.owner = username

        storage.dossier.save(dossier.dossier_id, dossier)

        storage.dossier.commit()

        return dossier
    except SearchException:
        raise InvalidDataException("You must use a valid query when creating a dossier.")
    except HowlerException as e:
        raise InvalidDataException(str(e))


def update_dossier(dossier_id: str, dossier_data: dict[str, Any], user: User) -> Dossier:  # noqa: C901
    """Update one or more properties of an analytic in the database."""
    if not exists(dossier_id):
        raise NotFoundException(f"Dossier with id '{dossier_id}' does not exist.")

    if set(dossier_data.keys()) - PERMITTED_KEYS:
        raise InvalidDataException(f"Only {', '.join(PERMITTED_KEYS)} can be updated.")

    storage = datastore()

    existing_dossier: Dossier = get_dossier(dossier_id, as_odm=True)
    if existing_dossier.type == "personal" and existing_dossier.owner != user.uname and "admin" not in user.type:
        raise ForbiddenException("You cannot update a personal dossier that is not owned by you.")

    if existing_dossier.type == "global" and existing_dossier.owner != user.uname and "admin" not in user.type:
        raise ForbiddenException("Only the owner of a dossier and administrators can edit a global dossier.")

    if "pivots" in dossier_data:
        for pivot in dossier_data["pivots"]:
            if len(pivot["mappings"]) != len(set(mapping["key"] for mapping in pivot["mappings"])):
                raise InvalidDataException("One of your pivots has duplicate keys set.")

    try:
        if "query" in dossier_data:
            # Make sure the query is valid
            storage.hit.search(dossier_data["query"])

        new_data = Dossier(merge({}, existing_dossier.as_primitives(), dossier_data))

        storage.dossier.save(dossier_id, new_data)

        storage.dossier.commit()

        return new_data
    except SearchException:
        raise InvalidDataException("You must use a valid query when updating a dossier.")
    except (HowlerException, TypeError) as e:
        logger.exception("Error when updating dossier.")
        raise InvalidDataException("We were unable to update the dossier.", cause=e) from e
