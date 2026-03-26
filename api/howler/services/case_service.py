"""Case service module for managing security investigation cases.

This module provides functionality for creating, updating, retrieving, and managing
cases - collections of security alerts and investigation data organized by analysts.
"""

from typing import Any, cast, overload

from prometheus_client import Counter

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.loader import APP_NAME, datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import DataStoreException
from howler.odm.models.case import Case, CaseItem, CaseItemTypes, CaseLog
from howler.odm.models.ecs.related import Related
from howler.odm.models.hit import Hit
from howler.odm.models.observable import Observable
from howler.odm.models.user import User

logger = get_logger(__file__)

CREATED_CASES = Counter(f"{APP_NAME.replace('-', '_')}_created_cases_total", "The number of created cases")


def create_case(_case: dict, user: str = None) -> Case:  # type: ignore
    """Create a new case in the datastore.

    Args:
        case: Case data
        user: Username to record in the creation log

    Returns:
        dict: The created case as a primitives dictionary

    Raises:
        ResourceExists: If a case with the same ID already exists
    """
    if not _case:
        raise InvalidDataException("Case data is required to create a case")

    _case.pop("case_id", None)
    items = _case.pop("items", [])

    case = Case(_case)
    case.log = [CaseLog({"timestamp": "NOW", "explanation": "Case created", "user": user or "system"})]
    datastore().case.save(case.case_id, case)
    CREATED_CASES.inc()

    for item in items:
        append_case_item(case.case_id, item=CaseItem(item))

    if items:
        return cast(Case, datastore().case.get(case.case_id))

    return case


def hide_cases(case_ids: set[str], user: str) -> None:
    """Hide a set of cases by marking them and their references as not visible.

    Sets visible=False on all matching cases, and also sets visible=False on any
    CaseItem in other cases that references one of the hidden cases.

    Args:
        case_ids (set[str]): The IDs of the cases to hide
        user (str): The username performing the hide action
    """
    ds = datastore()

    items_query = f"items.value:({' OR '.join(case_ids)})"
    for case in ds.case.stream_search(items_query, as_obj=False):
        related_case_id = case["case_id"]
        if related_case_id in case_ids:
            continue

        related_case = ds.case.get(related_case_id)
        if related_case:
            hidden_ids: list[str] = []
            for item in related_case.items:
                if item.value in case_ids:
                    item.visible = False
                    hidden_ids.append(item.value)

            if hidden_ids:
                related_case.log.append(
                    CaseLog(
                        {
                            "timestamp": "NOW",
                            "user": user,
                            "explanation": f"Referenced case(s) hidden: {', '.join(hidden_ids)}",
                        }
                    )
                )
                ds.case.save(related_case_id, related_case)

    for case_id in case_ids:
        case = ds.case.get(case_id)
        if case:
            case.visible = False
            case.log.append(
                CaseLog(
                    {
                        "timestamp": "NOW",
                        "user": user,
                        "explanation": "Case set to hidden",
                    }
                )
            )
            ds.case.save(case_id, case)
        else:
            logger.warning(f"Case {case_id} not found when attempting to hide")


def delete_cases(case_ids: set[str]) -> bool:
    """Delete a set of cases from the datastore.

    Also removes any CaseItem references to the deleted cases from other cases.

    Args:
        case_ids (set[str]): The IDs of the cases to delete

    Returns:
        bool: Was the deletion successful?
    """
    ds = datastore()

    items_query = f"items.value:({' OR '.join(case_ids)})"
    for case in ds.case.stream_search(items_query, as_obj=False):
        related_case_id = case["case_id"]
        if related_case_id in case_ids:
            continue

        related_case = ds.case.get(related_case_id)
        if related_case:
            related_case.items = [item for item in related_case.items if item.value not in case_ids]
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

    case = ds.case.get(case_id)
    if case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    immutable_fields = {"case_id", "created", "updated"}
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


@overload
def append_case_item(case_id: str, item: CaseItem) -> Case: ...


@overload
def append_case_item(
    case_id: str, item: None = None, item_type: str = ..., item_value: str = ..., item_path: str = ...
) -> Case: ...


def append_case_item(  # noqa: C901
    case_id: str,
    item: CaseItem | None = None,
    item_type: str | None = None,
    item_value: str | None = None,
    item_path: str = "related",
) -> Case:
    """Append an item to a case, dispatching to the appropriate handler based on item type.

    Can be called either with a pre-built CaseItem object or with individual
    item_type, item_value, and item_path parameters to construct one.

    Args:
        case_id: Unique identifier of the case to append the item to.
        item: A pre-built CaseItem object. If provided, item_type, item_value,
            and item_path are ignored.
        item_type: The type of item to append (e.g. "hit", "observable", "case",
            "table", "lead", "reference"). Required if item is not provided.
        item_value: The value/identifier of the item to append. Required if item
            is not provided.
        item_path: Path for organizing the item within the case. Must not end
            with a trailing "/".

    Raises:
        InvalidDataException: If item is not provided and item_type or item_value
            are missing, or if item_type is not a valid CaseItemTypes value, or
            if the resolved item path ends with a trailing "/".
    """
    if item is None:
        if not all([item_type, item_value]):
            raise InvalidDataException("item_type, item_value, and item_path are required if item is not provided")

        if item_type not in CaseItemTypes:
            raise InvalidDataException(f"Invalid item type: {item_type}, valid types are: {', '.join(CaseItemTypes)}")

        if not item_path:
            item_path = "related"

        item = CaseItem({"type": item_type, "value": item_value, "path": item_path})

    if item.path.endswith("/"):
        raise InvalidDataException("item path must not end with a trailing '/'")

    match item.type:
        case CaseItemTypes.HIT:
            return append_hit(case_id, item)
        case CaseItemTypes.OBSERVABLE:
            return append_observable(case_id, item)
        case CaseItemTypes.CASE:
            return append_case(case_id, item)
        case CaseItemTypes.TABLE:
            return append_table(case_id, item)
        case CaseItemTypes.LEAD:
            return append_lead(case_id, item)
        case CaseItemTypes.REFERENCE:
            return append_reference(case_id, item)
        case _:
            raise InvalidDataException(f"Unsupported item type: {item_type}")


def append_hit(case_id: str, item: CaseItem) -> Case:
    """Append a hit item to a case and create a back-reference on the hit.

    Validates that the case and hit both exist and that the hit is not already
    present in the case. Sets the item's path to include the hit's analytic
    and ID, then persists the updated case and adds a back-reference from the
    hit to the case.

    Args:
        case_id: Unique identifier of the case to append the hit to.
        item: A CaseItem whose ``value`` is the ID of an existing hit.

    Raises:
        NotFoundException: If the case or hit does not exist.
        InvalidDataException: If the hit is already present in the case.
        DataStoreException: If saving the updated case fails.
    """
    ds = datastore()

    _case = ds.case.get(case_id)

    if _case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    if any(item.value == case_item["value"] for case_item in _case.items):
        raise InvalidDataException(f"Hit {item.value} already exists in case {case_id}")

    hit = ds.hit.get(item.value)

    _case.items.append(item)

    if not ds.case.save(_case.case_id, _case):
        raise DataStoreException(f"Failed to save {_case.case_id} with new item {item.value}")

    _add_backreference(hit, _case.case_id)

    _sync_case_metadata(_case.case_id)

    return _case


def append_observable(case_id: str, item: CaseItem) -> Case:
    """Append an observable item to a case and create a back-reference on the observable.

    Validates that the case and observable both exist and that the observable is
    not already present in the case. It then persists the updated case and adds a back-reference
    from the observable to the case.

    Args:
        case_id: Unique identifier of the case to append the observable to.
        item: A CaseItem whose ``value`` is the ID of an existing observable.

    Raises:
        NotFoundException: If the case or observable does not exist.
        InvalidDataException: If the observable is already present in the case.
        DataStoreException: If saving the updated case fails.
    """
    ds = datastore()

    _case = ds.case.get(key=case_id)

    if _case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    if any(item.value == case_item["value"] for case_item in _case.items):
        raise InvalidDataException(f"Observable {item.value} already exists in case {case_id}")

    observable = ds.observable.get(key=item.value)

    if observable is None:
        raise NotFoundException(f"Observable {item.value} not found, cannot be added to case")

    _case.items.append(item)

    if not ds.case.save(_case.case_id, _case):
        raise DataStoreException(f"Failed to save {_case.case_id} with new item {item.value}")

    _add_backreference(observable, _case.case_id)
    _sync_case_metadata(case_id)

    return _case


def append_case(case_id: str, item: CaseItem) -> Case:
    """Append a case reference item to a case.

    Validates that both the parent case and the referenced case exist, and that
    the referenced case is not already present in the parent case. It then persists the updated
    parent case.

    Args:
        case_id: Unique identifier of the parent case to append the reference to.
        item: A CaseItem whose ``value`` is the ID of an existing case to reference.

    Raises:
        NotFoundException: If the parent case or referenced case does not exist.
        InvalidDataException: If the referenced case is already present in the parent case.
        DataStoreException: If saving the updated case fails.
    """
    ds = datastore()

    _case = ds.case.get(case_id)

    if _case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    if any(item.value == case_item["value"] for case_item in _case.items):
        raise InvalidDataException(f"Observable {item.value} already exists in case {case_id}")

    referenced_case = ds.case.get(item.value)

    if referenced_case is None:
        raise NotFoundException(f"Referenced case {item.value} not found, cannot be added to case")

    _case.items.append(item)

    if not datastore().case.save(_case.case_id, _case):
        raise DataStoreException(f"Failed to save {_case.case_id} with new item {item.value}")

    return _case


def append_table(case_id: str, item: CaseItem) -> Case:
    """Append a table item to a case.

    Not yet implemented.

    Args:
        case_id: Unique identifier of the case to append the table to.
        item: A CaseItem representing the table to append.

    Raises:
        NotImplementedError: Always raised; this feature is not yet implemented.
    """
    raise NotImplementedError


def append_lead(case_id: str, item: CaseItem) -> Case:
    """Append a lead item to a case.

    Not yet implemented.

    Args:
        case_id: Unique identifier of the case to append the lead to.
        item: A CaseItem representing the lead to append.

    Raises:
        NotImplementedError: Always raised; this feature is not yet implemented.
    """
    raise NotImplementedError


def append_reference(case_id: str, item: CaseItem) -> Case:
    """Append an external reference item to a case.

    Validates that the case exists and that the reference URL is not already
    present in the case. It then persists the updated case.

    Args:
        case_id: Unique identifier of the case to append the reference to.
        item: A CaseItem whose ``value`` is the external URL to reference.

    Raises:
        NotFoundException: If the case does not exist.
        InvalidDataException: If the reference URL is already present in the case.
        DataStoreException: If saving the updated case fails.
    """
    ds = datastore()

    _case = ds.case.get_if_exists(key=case_id, as_obj=True)

    if _case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    if any(item.value == case_item["value"] for case_item in _case.items):
        raise InvalidDataException(f"Reference {item.value} already exists in case {case_id}")

    _case.items.append(item)

    if not datastore().case.save(_case.case_id, _case):
        raise DataStoreException(f"Failed to save {_case.case_id} with new item {item.value}")

    return _case


def _collect_indicators_from_related(related: Related | None) -> set[str]:
    """Extract all indicator values from a Related ECS compound object."""
    if related is None:
        return set()

    indicators: set[str] = set()
    for key in related.fields().keys():
        value = related[key]
        if value:
            indicators.update(str(v) for v in value if v)

    return indicators


def _sync_case_metadata(case_id: str) -> None:  # noqa: C901
    """Re-compute and persist threat/target/indicator lists from all case items.

    Iterates over hit and observable items in the case and re-derives the
    ``targets``, ``threats``, and ``indicators`` lists from the backing
    objects' ECS ``related.*`` fields and, for hits, the outline fields.
    """
    ds = datastore()
    _case = ds.case.get(case_id)
    if _case is None:
        return

    targets: set[str] = set()
    threats: set[str] = set()
    indicators: set[str] = set()

    for item in _case.items:
        if item.type == CaseItemTypes.HIT and item.value:
            hit = ds.hit.get(item.value)
            if hit is None:
                continue

            indicators.update(_collect_indicators_from_related(hit.related))

            if hit.howler.outline:
                outline = hit.howler.outline
                if outline.threat:
                    threats.add(outline.threat)
                if outline.target:
                    targets.add(outline.target)
                if outline.indicators:
                    indicators.update(str(v) for v in outline.indicators if v)

        elif item.type == CaseItemTypes.OBSERVABLE and item.value:
            observable = ds.observable.get(item.value)
            if observable is None:
                continue

            indicators.update(_collect_indicators_from_related(observable.related))

    _case.targets = sorted(targets)
    _case.threats = sorted(threats)
    _case.indicators = sorted(indicators)
    ds.case.save(case_id, _case)


def _add_backreference(backing_obj: Hit | Observable | None, case_id: str):
    """Add a back-reference from a hit or observable to a case.

    Records the case ID in the backing object's ``howler.related_ids`` set so
    that the relationship can be traversed from the hit/observable side. If the
    back-reference already exists, the call is a no-op.

    Args:
        backing_obj: The Hit or Observable object to add the back-reference to.
        case_id: Unique identifier of the case to reference.

    Raises:
        InvalidDataException: If backing_obj is None or case_id is empty/falsy.
    """
    if backing_obj is None:
        raise InvalidDataException("Cannot add back reference on a nonexistent object")

    if not case_id:
        raise InvalidDataException("Missing back reference case_id")

    if any(case_id == related_id for related_id in backing_obj.howler.related):
        return

    backing_obj.howler.related.append(case_id)
    datastore()[backing_obj.__class__.__name__.lower()].save(backing_obj.howler.id, backing_obj)


def remove_backreference(backing_obj: Hit | Observable | None, case_id: str):
    """Remove a back-reference from a hit or observable to a case.

    Removes the case ID from the backing object's ``howler.related`` list
    and persists the change. If the case ID is not present in the list,
    the call is a no-op.

    Args:
        backing_obj: The Hit or Observable object to remove the back-reference from.
        case_id: Unique identifier of the case reference to remove.

    Raises:
        InvalidDataException: If backing_obj is None or case_id is empty/falsy.
    """
    if backing_obj is None:
        raise InvalidDataException("Cannot remove back reference on a nonexisting object")

    if not case_id:
        raise InvalidDataException("Missing back reference case_id")

    if case_id in backing_obj.howler.related:
        backing_obj.howler.related.remove(case_id)
        datastore()[backing_obj.__class__.__name__.lower()].save(backing_obj.howler.id, backing_obj)


def remove_case_item(case_id: str, item_value: str):
    """Remove an item from a case and clean up any associated back-references.

    Locates the item within the case by its value, removes it from the case's
    items list, persists the updated case, and removes the back-reference from
    the backing hit or observable if applicable.

    Args:
        case_id: Unique identifier of the case to remove the item from.
        item_value: The value/identifier of the item to remove.

    Raises:
        NotFoundException: If the case does not exist.
        DataStoreException: If saving the updated case fails.
    """
    ds = datastore()

    _case = ds.case.get(key=case_id)

    if not _case:
        raise NotFoundException(f"Case {case_id} does not exist")

    item = next((_item for _item in _case.items if _item["value"] == item_value), None)
    if not item:
        raise NotFoundException(f"Case item {item_value} does not exist")

    backing_obj: Hit | Observable | None = None
    if item.type in [CaseItemTypes.HIT, CaseItemTypes.OBSERVABLE]:
        backing_obj = ds[item.type].get(item.value)

    _case.items.remove(item)

    if not ds.case.save(_case.case_id, _case):
        raise DataStoreException("Failed to save case after item removal")

    if backing_obj:
        remove_backreference(backing_obj, _case.case_id)

    _sync_case_metadata(case_id)

    return _case
