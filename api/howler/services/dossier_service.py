"""Dossier service module for managing security investigation dossiers.

This module provides functionality for creating, updating, retrieving, and managing
dossiers - collections of security alerts and investigation data organized by analysts.
Dossiers can be personal (private to the creator) or global (shared with the team).
"""

from typing import Any, Optional, cast

from mergedeep.mergedeep import merge

from howler.common.exceptions import ForbiddenException, HowlerException, InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import SearchException
from howler.odm.models.dossier import Dossier
from howler.odm.models.user import User
from howler.services import lucene_service

logger = get_logger(__file__)

# Define which fields are allowed to be updated in a dossier, preventing unauthorized modification of sensitive fields
PERMITTED_KEYS = {
    "title",
    "query",
    "leads",
    "pivots",
    "type",
    "owner",
}


def exists(dossier_id: str) -> bool:
    """Check if a dossier exists in the datastore.

    Args:
        dossier_id: Unique identifier for the dossier

    Returns:
        True if the dossier exists, False otherwise
    """
    return datastore().dossier.exists(dossier_id)


def get_dossier(
    id: str,
    as_odm: bool = False,
    version: bool = False,
) -> Dossier:
    """Retrieve a dossier from the datastore.

    Args:
        id: Unique identifier for the dossier
        as_odm: Whether to return as ODM object (True) or dictionary (False)
        version: Whether to include version information in the response

    Returns:
        Dossier object or dictionary containing dossier data

    Raises:
        NotFoundException: If the dossier doesn't exist
    """
    return datastore().dossier.get_if_exists(key=id, as_obj=as_odm, version=version)


def create_dossier(dossier_data: Optional[Any], username: str) -> Dossier:  # noqa: C901
    """Create a new dossier in the datastore.

    This function validates the input data, ensures the query is valid by testing it
    against the hit collection, and creates a new dossier with the specified parameters.

    Args:
        dossier_data: Dictionary containing dossier configuration data
        username: Username of the user creating the dossier

    Returns:
        Newly created Dossier object

    Raises:
        InvalidDataException: If data format is invalid, required fields are missing,
                            or the query is invalid
        HowlerException: If there's an error during dossier creation
    """
    # Validate input data format
    if not isinstance(dossier_data, dict):
        raise InvalidDataException("Invalid data format")

    # Validate required fields for dossier creation
    if "title" not in dossier_data:
        raise InvalidDataException("You must specify a title when creating a dossier.")

    if "query" not in dossier_data:
        raise InvalidDataException("You must specify a query when creating a dossier.")

    if "type" not in dossier_data:
        raise InvalidDataException("You must specify a type when creating a dossier.")

    storage = datastore()

    try:
        # Validate the Lucene query by attempting to search with it
        # This ensures the query syntax is correct before saving the dossier
        if query := dossier_data.get("query", None):
            storage.hit.search(query)

        if "owner" not in dossier_data:
            dossier_data["owner"] = username

        dossier = Dossier(dossier_data)

        # Validate pivot configurations to ensure no duplicate mapping keys
        for pivot in dossier.pivots:
            if len(pivot.mappings) != len(set(mapping.key for mapping in pivot.mappings)):
                raise InvalidDataException("One of your pivots has duplicate keys set.")

        # Ensure the owner is set to the current user (security measure)
        dossier.owner = username

        # Save the dossier to the datastore
        storage.dossier.save(dossier.dossier_id, dossier)

        # Commit the transaction to persist changes
        storage.dossier.commit()

        return dossier
    except SearchException:
        # Handle invalid Lucene query syntax
        raise InvalidDataException("You must use a valid query when creating a dossier.")
    except HowlerException as e:
        # Handle other application-specific errors
        raise InvalidDataException(str(e))


def update_dossier(dossier_id: str, dossier_data: dict[str, Any], user: User) -> Dossier:  # noqa: C901
    """Update one or more properties of a dossier in the database.

    This function enforces access control rules and validates data before updating.
    Personal dossiers can only be updated by their owners or admins.
    Global dossiers can only be updated by their owners or admins.

    Args:
        dossier_id: Unique identifier of the dossier to update
        dossier_data: Dictionary containing fields to update
        user: User object representing the requesting user

    Returns:
        Updated Dossier object

    Raises:
        NotFoundException: If the dossier doesn't exist
        InvalidDataException: If invalid fields are provided or data is malformed
        ForbiddenException: If user lacks permission to update the dossier
    """
    # Verify the dossier exists before attempting to update
    if not exists(dossier_id):
        raise NotFoundException(f"Dossier with id '{dossier_id}' does not exist.")

    # Validate that only permitted fields are being updated
    # This prevents unauthorized modification of sensitive fields
    if set(dossier_data.keys()) - PERMITTED_KEYS:
        raise InvalidDataException(f"Only {', '.join(PERMITTED_KEYS)} can be updated.")

    storage = datastore()

    # Retrieve the existing dossier for access control checks
    existing_dossier: Dossier = get_dossier(dossier_id, as_odm=True)

    # Enforce access control for personal dossiers
    # Only the owner or admin users can modify personal dossiers
    if existing_dossier.type == "personal" and existing_dossier.owner != user.uname and "admin" not in user.type:
        raise ForbiddenException("You cannot update a personal dossier that is not owned by you.")

    # Enforce access control for global dossiers
    # Only the owner or admin users can modify global dossiers
    if existing_dossier.type == "global" and existing_dossier.owner != user.uname and "admin" not in user.type:
        raise ForbiddenException("Only the owner of a dossier and administrators can edit a global dossier.")

    # Validate pivot configurations if they're being updated
    # Ensure no duplicate mapping keys exist within any pivot
    if "pivots" in dossier_data:
        for pivot in dossier_data["pivots"]:
            if len(pivot["mappings"]) != len(set(mapping["key"] for mapping in pivot["mappings"])):
                raise InvalidDataException("One of your pivots has duplicate keys set.")

    try:
        # Validate the Lucene query if it's being updated
        if "query" in dossier_data:
            # Test the query against the hit index to ensure it's valid
            storage.hit.search(dossier_data["query"])

        # Merge the new data with existing dossier data
        new_data = Dossier(merge({}, existing_dossier.as_primitives(), dossier_data))

        storage.dossier.save(dossier_id, new_data)

        # Commit the transaction to persist changes
        storage.dossier.commit()

        return new_data
    except SearchException:
        # Handle invalid Lucene query syntax
        raise InvalidDataException("You must use a valid query when updating a dossier.")
    except (HowlerException, TypeError) as e:
        # Log the error for debugging purposes
        logger.exception("Error when updating dossier.")
        # Provide a user-friendly error message while preserving the original exception
        raise InvalidDataException("We were unable to update the dossier.", cause=e) from e


def get_matching_dossiers(hit: dict[str, Any], dossiers: Optional[list[dict[str, Any]]] = None):
    """Get a list of dossiers that match a specific security alert/hit.

    This function evaluates each dossier's query against the provided hit data
    to determine which dossiers are relevant to the security event.

    Args:
        hit: Dictionary containing security alert/hit data to match against
        dossiers: Optional list of dossiers to check. If None, all dossiers
                 will be retrieved from the datastore

    Returns:
        List of dossier dictionaries that match the provided hit

    Note:
        This function uses Lucene query matching to determine relevance.
        Dossiers with no query are assumed to match all hits.
    """
    # Retrieve all dossiers if none provided
    if dossiers is None:
        dossiers: list[dict[str, Any]] = datastore().dossier.search(
            "dossier_id:*",
            as_obj=False,
            # TODO: Eventually implement caching here
            rows=1000,
        )["items"]

    matching_dossiers: list[dict[str, Any]] = []

    # Evaluate each dossier against the hit data
    for dossier in cast(list[dict[str, Any]], dossiers):
        # Dossiers without queries match all hits by default
        # This allows for catch-all dossiers that collect all security events
        if "query" not in dossier or dossier["query"] is None:
            matching_dossiers.append(dossier)
            continue

        # Use Lucene service to check if the hit matches the dossier's query
        # This determines if the security event is relevant to this investigation
        if lucene_service.match(dossier["query"], hit):
            matching_dossiers.append(dossier)

    return matching_dossiers
