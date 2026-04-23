"""Case service module for managing security investigation cases.

This module provides functionality for creating, updating, retrieving, and managing
cases - collections of security alerts and investigation data organized by analysts.
"""

from typing import Any, overload

from prometheus_client import Counter

from howler.common.exceptions import HowlerValueError, InvalidDataException, NotFoundException
from howler.common.loader import APP_NAME, datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import DataStoreException
from howler.odm.models.case import Case, CaseItem, CaseItemTypes, CaseLog, CaseRule
from howler.odm.models.ecs.related import Related
from howler.odm.models.hit import Hit
from howler.odm.models.observable import Observable
from howler.odm.models.user import User
from howler.services import event_service

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
        updated_case = datastore().case.get(case.case_id)

        if not updated_case:
            raise HowlerValueError("Error occurred when creating case")

        case = updated_case

    event_service.emit("cases", {"case": case.as_primitives()})

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

    # First pass: find other cases that reference any of the cases being hidden
    # and mark those reference items as not visible.
    for related_case in ds.case.stream_search(f"items.value:({' OR '.join(case_ids)})"):
        # Skip cases that are themselves being hidden — they're handled below.
        if related_case.case_id in case_ids:
            continue

        # Walk items and hide any that point to one of the target case IDs.
        hidden_ids: list[str] = []
        for item in related_case.items:
            if item.value in case_ids:
                item.visible = False
                hidden_ids.append(item.value)

        # Only persist the related case if we actually changed something.
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
            ds.case.save(related_case.case_id, related_case)

    # Second pass: mark each target case itself as not visible.
    for case_id in case_ids:
        case = ds.case.get(case_id)
        if case is None:
            logger.warning("Case %s not found, skipping hide", case_id)
            continue

        case.visible = False
        case.log.append(
            CaseLog(
                {
                    "timestamp": "NOW",
                    "user": user,
                    "explanation": "Case hidden",
                }
            )
        )
        ds.case.save(case_id, case)


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

    event_service.emit("cases", {"case": case.as_primitives()})

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

        item = CaseItem({"type": item_type, "value": item_value, "path": item_path})

    if item.path.endswith("/"):
        raise InvalidDataException("item path must not end with a trailing '/'")

    # Verify the case exists and deduplicate paths: if an existing item
    # already occupies the same path, append the new item's unique value in
    # parentheses to avoid a collision.
    _case = datastore().case.get(case_id)
    if _case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    if any(item.path == case_item.path for case_item in _case.items):
        item.path = f"{item.path} ({item.value})"

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

    if hit is None:
        raise NotFoundException(f"Hit {item.value} not found, cannot be added to case")

    _case.items.append(item)

    if not ds.case.save(_case.case_id, _case):
        raise DataStoreException(f"Failed to save {_case.case_id} with new item {item.value}")

    _add_backreference(hit, _case.case_id)

    _sync_case_metadata(_case.case_id)

    updated_case = ds.case.get(_case.case_id)
    if updated_case:
        event_service.emit("cases", {"case": updated_case.as_primitives()})

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

    updated_case = ds.case.get(_case.case_id)
    if updated_case:
        event_service.emit("cases", {"case": updated_case.as_primitives()})

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

    event_service.emit("cases", {"case": _case.as_primitives()})

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

    event_service.emit("cases", {"case": _case.as_primitives()})

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


def remove_case_items(case_id: str, values: list[str]):
    """Remove one or more items from a case in a single atomic operation.

    Validates that every requested value exists within the case before making
    any modifications.  If any value is missing the call raises NotFoundException
    without altering the case.  When all values are confirmed, all matching
    items are removed in memory, the case is persisted once, and back-references
    are cleaned up from any associated hits or observables.

    Args:
        case_id: Unique identifier of the case to remove items from.
        item_values: List of item values (IDs / URLs) to remove.

    Returns:
        The updated Case object.

    Raises:
        NotFoundException: If the case does not exist, or if any requested value
            is not present in the case's items list.
        DataStoreException: If persisting the updated case fails.
    """
    ds = datastore()

    _case = ds.case.get(key=case_id)

    if not _case:
        raise NotFoundException(f"Case {case_id} does not exist")

    # Build a lookup of value → item for all items currently in the case.
    items_by_value = {_item["value"]: _item for _item in _case.items}

    # Pre-validate all requested values before touching anything.
    missing = [v for v in values if v not in items_by_value]
    if missing:
        raise NotFoundException(f"Case item(s) not found in case: {', '.join(missing)}")

    # Resolve items and collect backing objects that need back-reference cleanup.
    items_to_remove = [items_by_value[v] for v in values]
    backing_objs: list[Hit | Observable] = []
    for item in items_to_remove:
        if item.type in [CaseItemTypes.HIT, CaseItemTypes.OBSERVABLE]:
            obj = ds[item.type].get(item.value)
            if obj:
                backing_objs.append(obj)

    # Remove all items in memory, then persist the case once.
    for item in items_to_remove:
        _case.items.remove(item)

    if not ds.case.save(_case.case_id, _case):
        raise DataStoreException("Failed to save case after item removal")

    # Clean up back-references after the case is safely persisted.
    for backing_obj in backing_objs:
        remove_backreference(backing_obj, _case.case_id)

    _sync_case_metadata(case_id)

    updated_case = ds.case.get(_case.case_id)
    if updated_case:
        event_service.emit("cases", {"case": updated_case.as_primitives()})

    return _case


def rename_case_item(case_id: str, item_value: str, new_path: str) -> Case:
    """Rename (re-path) a single item within a case.

    Validates that the target item exists in the case, that the new path is not
    already used by another item, then updates the item's path in memory and
    persists the case once.

    Args:
        case_id: Unique identifier of the case to modify.
        item_value: The value/identifier of the item to rename.
        new_path: The new path for the item (must not end with '/').

    Returns:
        The updated Case object.

    Raises:
        NotFoundException: If the case does not exist or the item is not found.
        InvalidDataException: If new_path ends with '/' or is already taken by
            another item in the case.
        DataStoreException: If persisting the updated case fails.
    """
    if not new_path or new_path.endswith("/"):
        raise InvalidDataException("new_path must be a non-empty string and must not end with '/'")

    ds = datastore()

    _case = ds.case.get(key=case_id)

    if not _case:
        raise NotFoundException(f"Case {case_id} does not exist")

    item = next((_item for _item in _case.items if _item["value"] == item_value), None)
    if not item:
        raise NotFoundException(f"Case item {item_value} does not exist in case {case_id}")

    if any(_item["path"] == new_path for _item in _case.items if _item["value"] != item_value):
        raise InvalidDataException(f"An item already exists at path '{new_path}' in case {case_id}")

    item.path = new_path

    if not ds.case.save(_case.case_id, _case):
        raise DataStoreException("Failed to save case after item rename")

    event_service.emit("cases", {"case": _case.as_primitives()})

    return _case


def add_case_rule(case_id: str, rule_data: dict, user: User) -> Case:
    """Add a correlation rule to a case.

    Injects a unique id and the author from the current user, then appends
    the rule to the case's rules list.

    Args:
        case_id: Unique identifier of the case.
        rule_data: Dictionary with ``query``, ``destination``, and optionally ``timeframe``.
        user: The user creating the rule.

    Returns:
        The updated Case object.

    Raises:
        NotFoundException: If the case does not exist.
        InvalidDataException: If required rule fields are missing.
    """
    ds = datastore()

    _case = ds.case.get(case_id)
    if _case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    if not rule_data.get("query"):
        raise InvalidDataException("Rule 'query' is required")

    if not rule_data.get("destination"):
        raise InvalidDataException("Rule 'destination' is required")

    rule_data.pop("rule_id", None)
    rule_data["author"] = user.uname
    rule_data.setdefault("enabled", True)

    rule = CaseRule(rule_data)
    _case.rules.append(rule)

    _case.log.append(
        CaseLog(
            {
                "timestamp": "NOW",
                "user": user.uname,
                "explanation": f"Added correlation rule targeting '{rule.destination}'",
            }
        )
    )

    _case.updated = "NOW"
    ds.case.save(case_id, _case)
    event_service.emit("cases", {"case": _case.as_primitives()})
    return _case


def remove_case_rule(case_id: str, rule_id: str, user: User) -> Case:
    """Remove a correlation rule from a case.

    Args:
        case_id: Unique identifier of the case.
        rule_id: UUID of the rule to remove.
        user: The user performing the deletion.

    Returns:
        The updated Case object.

    Raises:
        NotFoundException: If the case or rule does not exist.
    """
    ds = datastore()

    _case = ds.case.get(case_id)
    if _case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    original_len = len(_case.rules)
    _case.rules = [r for r in _case.rules if r.rule_id != rule_id]

    if len(_case.rules) == original_len:
        raise NotFoundException(f"Rule {rule_id} not found in case {case_id}")

    _case.log.append(
        CaseLog(
            {
                "timestamp": "NOW",
                "user": user.uname,
                "explanation": f"Removed correlation rule {rule_id}",
            }
        )
    )

    _case.updated = "NOW"
    ds.case.save(case_id, _case)
    event_service.emit("cases", {"case": _case.as_primitives()})
    return _case


def update_case_rule(case_id: str, rule_id: str, update_data: dict, user: User) -> Case:
    """Update fields on an existing correlation rule.

    Allowed fields: ``enabled``, ``query``, ``destination``, ``timeframe``.

    Args:
        case_id: Unique identifier of the case.
        rule_id: UUID of the rule to update.
        update_data: Dictionary of fields to patch.
        user: The user performing the update.

    Returns:
        The updated Case object.

    Raises:
        NotFoundException: If the case or rule does not exist.
        InvalidDataException: If no valid fields are provided.
    """
    ds = datastore()

    _case = ds.case.get(case_id)
    if _case is None:
        raise NotFoundException(f"Case {case_id} does not exist")

    allowed_fields = {"enabled", "query", "destination", "timeframe"}
    patch = {k: v for k, v in update_data.items() if k in allowed_fields}
    if not patch:
        raise InvalidDataException(
            f"No valid fields provided for update. Allowed fields: {', '.join(sorted(allowed_fields))}"
        )

    rule = next((r for r in _case.rules if r.rule_id == rule_id), None)
    if rule is None:
        raise NotFoundException(f"Rule {rule_id} not found in case {case_id}")

    changes: list[str] = []
    for key, value in patch.items():
        old_value = getattr(rule, key, None)
        setattr(rule, key, value)
        changes.append(f"{key}: '{old_value}' → '{value}'")

    _case.log.append(
        CaseLog(
            {
                "timestamp": "NOW",
                "user": user.uname,
                "explanation": f"Updated correlation rule {rule_id}: {'; '.join(changes)}",
            }
        )
    )

    _case.updated = "NOW"
    ds.case.save(case_id, _case)
    event_service.emit("cases", {"case": _case.as_primitives()})
    return _case
