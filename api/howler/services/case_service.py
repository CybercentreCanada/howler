"""Case service module for managing security investigation cases.

This module provides functionality for creating, updating, retrieving, and managing
cases - collections of security alerts and investigation data organized by analysts.
"""

from typing import Any, Literal, overload

from prometheus_client import Counter

from howler.common.exceptions import InvalidDataException, NotFoundException, ResourceExists
from howler.common.loader import APP_NAME, datastore
from howler.common.logging import get_logger
from howler.odm.models.case import Case, CaseLog
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


CREATED_CASES = Counter(f"{APP_NAME.replace('-', '_')}_created_cases_total", "The number of created cases")


def create_case(case_id: str, case: Case, user: str, skip_exists: bool = False, index: str = "case") -> bool:
    """Create a new case in the datastore.

    This function validates the input data, ensures the query is valid by testing it
    against the hit collection, and creates a new case with the specified parameters.

    Args:
        case_id: Unique identifier for the case
        case: Case ODM object to save
        user: Optional username to record in the creation log
        skip_exists: Whether to skip the existence check

    Returns:
        bool: True if the case was successfully created

    Raises:
        ResourceExists: If a case with the same ID already exists
    """
    if not skip_exists and exists(case_id):
        raise ResourceExists(f"Hit {case_id} already exists in datastore")

    if user:
        case.log = [CaseLog({"timestamp": "NOW", "explanation": "Created case", "user": user})]

    CREATED_CASES.inc()
    return datastore()[index].save(case_id, case)


def delete_cases(case_ids: set[str], index: str = "case") -> bool:
    """Delete a set of cases from the datastore.

    Also removes any CaseItem references to the deleted cases from other cases.

    Args:
        case_ids (set[str]): The IDs of the cases to delete

    Returns:
        bool: Was the deletion successful?
    """
    ds = datastore()

    items_query = f"items.id:({' OR '.join(case_ids)})"
    for case in ds.case.stream_search(items_query, as_obj=False):
        related_case_id = case["case_id"]
        if related_case_id in case_ids:
            continue

        related_case = ds.case.get_if_exists(related_case_id, as_obj=True)
        if related_case:
            related_case.items = [item for item in related_case.items if item.id not in case_ids]
            ds.case.save(related_case_id, related_case)

    return ds.case.delete_by_query(f"case_id:({' OR '.join(case_ids)})")


def update_case(case_id: str, case_data: dict[str, Any], user: User) -> Case:
    """Update one or more properties of a case in the database.

    This function validates the provided fields, applies changes to the case object,
    appends a CaseLog entry for each changed property.

    Args:
        case_id: Unique identifier of the case to update
        case_data: Dictionary containing fields to update
        user: User object representing the requesting user

    Returns:
        Updated Case object

    Raises:
        NotFoundException: If the case doesn't exist
        InvalidDataException: If invalid or immutable fields are provided
    """
    ds = datastore()

    case = ds.case.get_if_exists(case_id, as_obj=True)
    if case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    immutable_fields = {"case_id", "created", "updated", "items"}
    compound_fields = {"items", "enrichments", "rules", "tasks"}

    immutable_violations = set(case_data.keys()) & immutable_fields
    if immutable_violations:
        raise InvalidDataException(f"Cannot modify immutable field(s): {', '.join(immutable_violations)}")

    updatable = {k: v for k, v in case_data.items() if k not in immutable_fields}
    if not updatable:
        raise InvalidDataException("No valid fields provided for update")

    for key, new_value in updatable.items():
        previous_value = getattr(case, key, None)

        if key in compound_fields:
            explanation = f"Updated {key}"
            prev_str = None
            new_str = None
        elif isinstance(previous_value, list) and isinstance(new_value, list):
            prev_set = set(str(v) for v in previous_value)
            new_set = set(str(v) for v in new_value)
            added = sorted(new_set - prev_set)
            removed = sorted(prev_set - new_set)

            parts: list[str] = []
            if added:
                parts.append(f"added [{', '.join(added)}]")
            if removed:
                parts.append(f"removed [{', '.join(removed)}]")

            explanation = f"Updated {key}: {'; '.join(parts)}" if parts else f"Updated {key} (no changes)"
            prev_str = ", ".join(str(v) for v in previous_value) or None
            new_str = ", ".join(str(v) for v in new_value) or None
        else:
            explanation = f"Updated {key} from '{previous_value}' to '{new_value}'"
            prev_str = str(previous_value) if previous_value is not None else None
            new_str = str(new_value) if new_value is not None else None

        case.log.append(
            CaseLog(
                {
                    "timestamp": "NOW",
                    "key": key,
                    "previous_value": prev_str,
                    "new_value": new_str,
                    "user": user.uname,
                    "explanation": explanation,
                }
            )
        )
        setattr(case, key, new_value)

    case.updated = "NOW"
    ds.case.save(case_id, case)

    return case
