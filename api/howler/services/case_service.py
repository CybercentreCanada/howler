"""Case service module for managing security investigation cases.

This module provides functionality for creating, updating, retrieving, and managing
cases - collections of security alerts and investigation data organized by analysts.
"""

from typing import Any, Literal, Optional, overload

from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.odm.models.case import Case
from howler.odm.models.user import User

logger = get_logger(__file__)


def exists(case_id: str) -> bool:
    """Check if a case exists in the datastore.

    Args:
        case_id: Unique identifier for the case

    Returns:
        True if the case exists, False otherwise
    """
    return datastore().case.exists(case_id)


@overload
def get_case(id: str, as_odm: Literal[True], version: Literal[True]) -> tuple[Case, str]: ...


@overload
def get_case(id: str, as_odm: Literal[True], version: Literal[False]) -> Case: ...


@overload
def get_case(id: str, as_odm: Literal[True]) -> Case: ...


@overload
def get_case(id: str) -> Case: ...


@overload
def get_case(id: str, as_odm: Literal[False], version: Literal[True]) -> tuple[dict[str, Any], str]: ...


@overload
def get_case(id: str, as_odm: Literal[False], version: Literal[False]) -> dict[str, Any]: ...


@overload
def get_case(id: str, as_odm: Literal[False]) -> dict[str, Any]: ...


def get_case(
    id: str,
    as_odm=False,
    version=False,
):
    """Retrieve a case from the datastore.

    Args:
        id: Unique identifier for the case
        as_odm: Whether to return as ODM object (True) or dictionary (False)
        version: Whether to include version information in the response

    Returns:
        case object or dictionary containing case data

    Raises:
        NotFoundException: If the case doesn't exist
    """
    return datastore().case.get_if_exists(key=id, as_obj=as_odm, version=version)


def create_case(case_data: Optional[Any], username: str) -> Case:  # noqa: C901
    """Create a new case in the datastore.

    This function validates the input data, ensures the query is valid by testing it
    against the hit collection, and creates a new case with the specified parameters.

    Args:
        case_data: Dictionary containing case configuration data
        username: Username of the user creating the case

    Returns:
        Newly created Case object

    Raises:
        InvalidDataException: If data format is invalid, required fields are missing,
                            or the query is invalid
        HowlerException: If there's an error during case creation
    """
    raise NotImplementedError()


def update_case(case_id: str, case_data: dict[str, Any], user: User) -> Case:  # noqa: C901
    """Update one or more properties of a case in the database.

    This function enforces access control rules and validates data before updating.

    Args:
        case_id: Unique identifier of the case to update
        case_data: Dictionary containing fields to update
        user: User object representing the requesting user

    Returns:
        Updated case object

    Raises:
        NotFoundException: If the case doesn't exist
        InvalidDataException: If invalid fields are provided or data is malformed
        ForbiddenException: If user lacks permission to update the case
    """
    raise NotImplementedError()
