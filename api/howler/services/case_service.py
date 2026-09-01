"""Case service module for managing security investigation cases.

This module provides functionality for creating, updating, retrieving, and managing
cases - collections of security alerts and investigation data organized by analysts.
"""

from datetime import datetime, timezone
from typing import Any, Callable, Literal, Sequence, cast, overload

from prometheus_client import Counter

from howler.common.exceptions import (
    CaseAccessException,
    HowlerTypeError,
    HowlerValueError,
    InvalidDataException,
    NotFoundException,
    ResourceExists,
)
from howler.common.loader import APP_NAME, datastore
from howler.common.logging import get_logger
from howler.config import CLASSIFICATION
from howler.datastore.collection import CREATE_TOKEN
from howler.datastore.exceptions import DataStoreException
from howler.odm.base import ClassificationObject
from howler.odm.models.case import Case, CaseItem, CaseItemTypes, CaseLog, CaseRule
from howler.odm.models.ecs.related import Related
from howler.odm.models.event import Event
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.security.utils import is_classification_accessible
from howler.services import comms_service

logger = get_logger(__file__)

CREATED_CASES = Counter(f"{APP_NAME.replace('-', '_')}_created_cases_total", "The number of created cases")

ResolvedBacking = tuple[Hit | Event | Case, str | None]
PreparedCaseItem = tuple[CaseItem, ResolvedBacking | None]
CaseState = tuple[list[CaseItem], list[str], list[str], list[str]]


def create_case(
    case_data: dict,
    user: User | None = None,
) -> Case:  # type: ignore
    """Create a new case in the datastore.

    Args:
        case_dict: Case data
        user: Username to record in the creation log

    Returns:
        dict: The created case as a primitives dictionary

    Raises:
        ResourceExists: If a case with the same ID already exists
    """
    if not case_data:
        raise InvalidDataException("Case data is required to create a case")

    case_data.pop("case_id", None)
    items = case_data.pop("items", [])

    case = Case(case_data)
    prepared_items: list[PreparedCaseItem] = []
    if user:
        _check_case_classification(
            case.classification,
            user,
            f"Invalid case classification {case.classification}",
        )

    for raw_item in items:
        case_item = CaseItem(raw_item)
        resolved = _resolve_backing_item(case_item.type, case_item.value, user, case.classification) if user else None
        prepared_items.append((case_item, resolved))

    case.log = [CaseLog({"timestamp": "NOW", "explanation": "Case created", "user": user.uname if user else "system"})]
    case.save(refresh="wait_for", version=CREATE_TOKEN)
    CREATED_CASES.inc()

    try:
        for case_item, resolved in prepared_items:
            append_case_item(case, item=case_item, refresh="wait_for", _resolved=resolved, emit=False)
    except Exception:
        _rollback_created_case(case, prepared_items)
        raise

    if items:
        updated_case = datastore().case.get(case.case_id)

        if not updated_case:
            raise HowlerValueError("Error occurred when creating case")

        case = updated_case

    comms_service.emit("cases", {"case": case.as_primitives()})

    if user:
        filter_case_items_by_classification(case, user.classification)

    return case


def hide_cases(
    case_ids: set[str],
    user: str | User,
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> None:
    """Hide a set of cases by marking them and their references as not visible.

    Sets visible=False on all matching cases, and also sets visible=False on any
    CaseItem in other cases that references one of the hidden cases.

    Args:
        case_ids (set[str]): The IDs of the cases to hide
        user (str): The username performing the hide action
    """
    user_name = user.uname if isinstance(user, User) else user
    accessible_cases = _ensure_cases_accessible(case_ids, user) if isinstance(user, User) else None

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
                        "user": user_name,
                        "explanation": f"Referenced case(s) hidden: {', '.join(hidden_ids)}",
                    }
                )
            )
            related_case.save(refresh=refresh)

    # Second pass: mark each target case itself as not visible.
    for case_id in case_ids:
        case = accessible_cases[case_id] if accessible_cases is not None else ds.case.get(case_id)
        if case is None:
            logger.warning("Case %s not found, skipping hide", case_id)
            continue

        case.visible = False
        case.log.append(
            CaseLog(
                {
                    "timestamp": "NOW",
                    "user": user_name,
                    "explanation": "Case hidden",
                }
            )
        )
        case.save(refresh=refresh)


def delete_cases(
    case_ids: set[str],
    refresh: Literal["true", "false", "wait_for"] | None = None,
    *,
    user: User | None = None,
) -> bool:
    """Delete a set of cases from the datastore.

    Also removes any CaseItem references to the deleted cases from other cases.

    Args:
        case_ids (set[str]): The IDs of the cases to delete

    Returns:
        bool: Was the deletion successful?
    """
    if user is not None:
        _ensure_cases_accessible(case_ids, user)

    ds = datastore()

    for case in ds.case.stream_search(f"items.value:({' OR '.join(case_ids)})"):
        related_case_id = case.case_id
        if related_case_id in case_ids:
            continue

        related_case = ds.case.get(related_case_id)
        if related_case:
            related_case.items = [item for item in related_case.items if item.value not in case_ids]
            related_case.save(refresh=refresh)

    return ds.case.delete_by_query(f"case_id:({' OR '.join(case_ids)})", refresh=refresh)


def filter_case_items_by_classification(case_data: dict | Case, user_classification: str):
    """Remove items from a case dict that exceed the user's classification.

    Items without a ``classification`` value are always included. Items with a
    classification are only included when ``CLASSIFICATION.is_accessible``
    confirms the requesting user can see them.

    Note: unlike ``is_classification_accessible``, this filter does not bypass
    for admin-type users — it operates on the user's clearance string alone, so
    admins also have over-classified case items filtered from responses.

    Args:
        case_data: Raw case data (as returned by ``as_obj=False`` datastore calls).
        user_classification: The requesting user's maximum classification string.
    """
    if isinstance(case_data, dict):
        if "items" not in case_data:
            return

        case_data["items"] = [
            item
            for item in case_data["items"]
            if item.get("classification") is None
            or CLASSIFICATION.is_accessible(user_classification, item["classification"])
        ]
    elif isinstance(case_data, Case):
        if not case_data.items:
            return

        case_data.items = [
            item
            for item in case_data.items
            if item.classification is None or CLASSIFICATION.is_accessible(user_classification, item.classification)
        ]
    else:
        raise HowlerTypeError("Invalid case type.")


def _check_case_classification(classification: str | None, user: User, message: str) -> None:
    """Reject case classifications that exceed the requesting user's clearance."""
    if not is_classification_accessible(user, classification):
        raise InvalidDataException(message)


def _load_case(case: str | Case | None, user: User | None = None) -> Case:
    """Load a case and optionally enforce the user's access to it."""
    case_id = case if isinstance(case, str) else None
    if isinstance(case, str):
        case = datastore().case.get(case)

    if case is None:
        raise NotFoundException(f"Case {case_id} does not exist" if case_id else "Case does not exist")

    if isinstance(user, User) and not is_classification_accessible(user, case.classification):
        raise CaseAccessException(f"Case {case.case_id} does not exist")

    return case


def _ensure_cases_accessible(case_ids: set[str], user: User) -> dict[str, Case]:
    """Ensure every case ID exists and is accessible to the requesting user."""
    accessible_cases: dict[str, Case] = {}
    inaccessible_ids: list[str] = []
    for case_id in case_ids:
        try:
            accessible_cases[case_id] = _load_case(case_id, user)
        except NotFoundException:
            inaccessible_ids.append(case_id)

    if inaccessible_ids:
        raise NotFoundException(f"Case id(s) {', '.join(inaccessible_ids)} do not exist.")

    return accessible_cases


def get_case(case_id: str, user: User) -> Case:
    """Return a case after enforcing classification access."""
    return _load_case(case_id, user)


def _check_item_classification(
    parent_classification: str | ClassificationObject | None,
    item_type: str,
    item_value: str,
    item_classification: str | ClassificationObject | None,
) -> None:
    """Ensure a backing object can be attached to the parent case classification."""
    valid_classifications = (str, ClassificationObject)
    if (
        isinstance(parent_classification, valid_classifications)
        and isinstance(item_classification, valid_classifications)
        and not CLASSIFICATION.is_accessible(parent_classification, item_classification)
    ):
        raise InvalidDataException(f"Cannot add {item_type} {item_value} to a lower-classified case")


def _capture_case_state(case: Case) -> CaseState:
    """Capture mutable case fields needed for compensating persistence."""
    return list(case.items), list(case.targets), list(case.threats), list(case.indicators)


def _restore_case_state(case: Case, state: CaseState) -> None:
    """Restore mutable case fields after a failed persistence operation."""
    case.items, case.targets, case.threats, case.indicators = state


def _save_case_or_rollback(
    case: Case,
    state: CaseState,
    refresh: Literal["true", "false", "wait_for"] | None,
    error_message: str,
) -> None:
    """Save a case change and restore its in-memory state when saving fails."""
    try:
        saved = case.save(refresh=refresh)
    except Exception:
        _restore_case_state(case, state)
        raise

    if not saved:
        _restore_case_state(case, state)
        raise DataStoreException(error_message)


def _restore_backreferences(backing_objs: Sequence[tuple[Hit | Event, str | None, list[str]]]) -> None:
    """Best-effort restore of backing objects' related-case lists after a failed persistence step."""
    for backing_obj, version, original_related in backing_objs:
        backing_obj.howler.related = original_related
        try:
            backing_obj.save(version=version)
        except Exception:
            logger.exception("Failed to restore backing-object reference")


def _rollback_case(
    case: Case,
    state: CaseState,
    refresh: Literal["true", "false", "wait_for"] | None,
    context: str,
) -> None:
    """Restore in-memory case state and best-effort persist it after a failed operation."""
    _restore_case_state(case, state)
    try:
        case.save(refresh=refresh)
    except Exception:
        logger.exception("Failed to restore case %s after %s failure", case.case_id, context)


def _resolve_backing_item(
    item_type: str | None,
    item_value: str | None,
    user: User,
    parent_classification: str | ClassificationObject | None = None,
) -> ResolvedBacking | None:
    """Load, authorize, and classify a referenced item in one datastore read."""
    if item_type not in ("hit", "event", "case") or not item_value:
        return None

    ds = datastore()
    if item_type == "case":
        backing_obj = ds.case.get(item_value)
        version = None
    else:
        backing_obj, version = ds[item_type].get(item_value, as_obj=True, version=True)

    if backing_obj is None or not is_classification_accessible(user, backing_obj.classification):
        raise NotFoundException(f"{item_type} {item_value} does not exist")

    _check_item_classification(parent_classification, item_type, item_value, backing_obj.classification)
    return backing_obj, version


def _rollback_created_case(case: Case, prepared_items: list[PreparedCaseItem]) -> None:
    """Remove persisted relationships and the parent case after creation fails."""
    for _case_item, resolved in prepared_items:
        if resolved is None or not isinstance(resolved[0], (Hit, Event)):
            continue

        backing_obj, version = cast(tuple[Hit | Event, str | None], resolved)
        remove_backreference(backing_obj, case.case_id)
        try:
            backing_obj.save(version=version)
        except Exception:
            logger.exception("Failed to restore %s after case creation failed", type(backing_obj).__name__.lower())

    try:
        if not datastore().case.delete(case.case_id, refresh="wait_for"):
            logger.warning("Failed to delete partially created case %s", case.case_id)
    except Exception:
        logger.exception("Failed to delete partially created case %s", case.case_id)


def get_last_resolved_time(case: Case) -> datetime | None:
    """Return the timestamp of the most recent resolution of a case.

    Scans the case log newest-to-oldest for an entry where ``key='status'``
    and ``new_value='resolved'``. In the case of multiple resolve/unresolve
    cycles, returns the **final** resolved timestamp.

    Args:
        case: The Case object whose log to scan.

    Returns:
        A timezone-aware datetime if the case was ever resolved, else None.
    """
    for entry in reversed(case.log):
        if entry.key == "status" and entry.new_value == "resolved":
            ts = entry.timestamp
            if isinstance(ts, datetime):
                if ts.tzinfo is None:
                    return ts.replace(tzinfo=timezone.utc)
                return ts
            try:
                dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
                return dt
            except (ValueError, TypeError):
                continue
    return None


def _describe_field_change(
    key: str, previous: Any, new: Any, compound_fields: set[str]
) -> tuple[str, str | None, str | None]:
    """Build a human-readable explanation and string snapshots for a field change.

    Returns:
        A tuple of (explanation, previous_value_str, new_value_str).
    """
    # Compound fields (items, rules, …) are too complex to diff meaningfully.
    if key in compound_fields:
        return f"Updated {key}", None, None

    # List fields: show which entries were added / removed.
    if isinstance(previous, list) and isinstance(new, list):
        prev_set = {str(v) for v in previous}
        new_set = {str(v) for v in new}
        added = sorted(new_set - prev_set)
        removed = sorted(prev_set - new_set)

        parts: list[str] = []
        if added:
            parts.append(f"added [{', '.join(added)}]")
        if removed:
            parts.append(f"removed [{', '.join(removed)}]")

        explanation = f"Updated {key}: {'; '.join(parts)}" if parts else f"Updated {key} (no changes)"
        return (
            explanation,
            ", ".join(str(v) for v in previous) or None,
            ", ".join(str(v) for v in new) or None,
        )

    # Scalar fields: simple before/after.
    return (
        f"Updated {key} from '{previous}' to '{new}'",
        str(previous) if previous is not None else None,
        str(new) if new is not None else None,
    )


def _validate_rule_values(timeframe: Any, expire_after_resolved: Any) -> None:
    """Validate the coupled timeframe and expiry settings before mutation."""
    if timeframe is not None and (isinstance(timeframe, bool) or not isinstance(timeframe, int) or timeframe <= 0):
        raise HowlerValueError("Rule timeframe must be a positive integer or None")
    if timeframe is None and expire_after_resolved:
        raise InvalidDataException("Rule cannot expire after resolved when no timeframe is set")


def update_case(
    case_id: str,
    case_data: dict[str, Any],
    user: User,
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> Case:
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
    case = _load_case(case_id, user)

    if "classification" in case_data:
        _check_case_classification(
            case_data["classification"],
            user,
            f"Cannot set classification to {case_data['classification']}",
        )

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

        explanation, prev_str, new_str = _describe_field_change(key, previous_value, new_value, compound_fields)

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
    case.save(refresh=refresh)

    comms_service.emit("cases", {"case": case.as_primitives()})

    return case


def get_parent_from_path(
    case: str | Case | None,
    path: str | None,
    create_if_missing: bool = False,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    persist: bool = True,
) -> CaseItem | None:
    """Given a path, return the lowest parent of the path in the case.

    If ensure is set to true, create folders in the case until the path exists.

    Args:
        case: The case to search for.
        path: The path to return the lowest parent for.
        create_if_missing: Whether to create the path if it's missing or return None.
        persist: Whether to save the case immediately when a folder is created. Callers that
            are accumulating multiple in-memory changes before a single bulk save should pass
            False.

    Raises:
        InvalidDataException: If the path is invalid.
    """
    if isinstance(case, str):
        logger.debug("Attempting to fetch case %s", case)
        case = datastore().case.get(case)

    if case is None:
        raise NotFoundException("Case does not exist")

    case = _load_case(case)

    if not path or path == "/":
        return None

    # Normalize path: remove leading/trailing slashes and split
    path_parts = [p for p in path.strip("/").split("/") if p]

    if not path_parts:
        return None

    current_parent: str | None = None

    for part in path_parts:
        # Find folder matching this part with current parent
        folder = next(
            (
                item
                for item in case.items
                if item.type == CaseItemTypes.FOLDER and item.name == part and item.parent == current_parent
            ),
            None,
        )

        if folder is None:
            if not create_if_missing:
                return None
            # Create the folder
            folder_item = CaseItem({"type": CaseItemTypes.FOLDER, "name": part, "parent": current_parent, "value": ""})
            case.items.append(folder_item)
            current_parent = folder_item.id
        else:
            current_parent = folder.id

    if persist:
        case.save(refresh)

    # Find the final parent folder
    if current_parent is None:  # pragma: no cover
        return None  # pragma: no cover

    return next((item for item in case.items if item.id == current_parent), None)


@overload
def append_case_item(
    case: str | Case | None,
    item: CaseItem,
    item_type: str | None = None,
    item_value: str | None = None,
    item_parent: str | None = None,
    item_name: str | None = None,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    *,
    user: User | None = None,
    path: str | None = None,
    _resolved: ResolvedBacking | None = None,
    emit: bool = True,
) -> Case: ...


@overload
def append_case_item(
    case: str | Case | None,
    item: None = None,
    item_type: str = ...,
    item_value: str = ...,
    item_parent: str | None = ...,
    item_name: str | None = ...,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    *,
    user: User | None = None,
    path: str | None = None,
    _resolved: ResolvedBacking | None = None,
    emit: bool = True,
) -> Case: ...


def append_case_item(  # noqa: C901
    case: str | Case | None,
    item: CaseItem | None = None,
    item_type: str | None = None,
    item_value: str | None = None,
    item_parent: str | None = None,
    item_name: str | None = None,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    *,
    user: User | None = None,
    path: str | None = None,
    _resolved: ResolvedBacking | None = None,
    emit: bool = True,
) -> Case:
    """Append an item to a case, dispatching to the appropriate handler based on item type.

    Can be called either with a pre-built CaseItem object or with individual
    item_type, item_value, item_parent, and item_name parameters to construct one.

    Args:
        case_id: Unique identifier of the case to append the item to.
        item: A pre-built CaseItem object. If provided, other params are ignored.
        item_type: The type of item to append. Required if item is not provided.
        item_value: The value/identifier of the item to append. Required if item
            is not provided.
        item_parent: Parent folder ID, or None for root placement.
        item_name: Optional display name for the item.

    Raises:
        InvalidDataException: If item is not provided and item_type or item_value
            are missing, or if item_type is not a valid CaseItemTypes value.
    """
    case = _load_case(case, user)

    if item is None:
        if not all([item_type, item_value]):
            raise InvalidDataException("item_type and item_value are required if item is not provided")

        if item_type not in CaseItemTypes:
            raise InvalidDataException(f"Invalid item type: {item_type}, valid types are: {', '.join(CaseItemTypes)}")

        data: dict = {"type": item_type, "value": item_value, "parent": item_parent}
        if item_name is not None:
            data["name"] = item_name
        item = CaseItem(data)

    if item.name is None:
        item.name = item.value

    if path:
        parent = get_parent_from_path(case, path, create_if_missing=True, persist=False)
        item.parent = parent.id if parent else None

    # If a parent is specified, ensure it references an existing folder item.
    if item.parent is not None:
        _ensure_parent_exists(case, item.parent)

    conflict = check_conflicts(case, item)
    resolved = _resolved
    if resolved is None and user is not None:
        resolved = _resolve_backing_item(item.type, item.value, user, case.classification)

    match item.type:
        case CaseItemTypes.HIT | CaseItemTypes.EVENT | CaseItemTypes.CASE:
            if conflict:
                item.name = f"{item.name} ({item.value})" if item.name else item.value

            resolved_obj, resolved_version = resolved if resolved is not None else (None, None)
            if item.type == CaseItemTypes.HIT:
                return append_hit(
                    case,
                    item,
                    refresh,
                    backing_obj=cast("Hit | None", resolved_obj),
                    version=resolved_version,
                    emit=emit,
                )
            if item.type == CaseItemTypes.EVENT:
                return append_event(
                    case,
                    item,
                    refresh,
                    backing_obj=cast("Event | None", resolved_obj),
                    version=resolved_version,
                    emit=emit,
                )
            return append_case(case, item, refresh, backing_obj=cast("Case | None", resolved_obj), emit=emit)
        case CaseItemTypes.REFERENCE | CaseItemTypes.MARKDOWN | CaseItemTypes.FOLDER:
            if conflict:
                raise ResourceExists("An item with the same name already exists in this location.")

            case.items.append(item)

            if not case.save(refresh):  # pragma: no cover
                raise DataStoreException(f"Failed to save {case.case_id} with new {item.type} {item.name}")

            if emit:
                comms_service.emit("cases", {"case": case.as_primitives()})

            return case
        case _:
            raise InvalidDataException(f"Unsupported item type: {item.type}")


def check_conflicts(case: Case, item: CaseItem) -> bool:
    """Validate that two items are not created with the same name and parent.

    Args:
        case: The case whose items to search.
        item: The case item to check for conflicts with

    Raises:
        InvalidDataException: If there is a conflict between the existing case items and the new item
    """
    if item.type in {CaseItemTypes.HIT, CaseItemTypes.EVENT} and any(
        existing.type == item.type and existing.value == item.value for existing in case.items
    ):
        raise InvalidDataException(f"Item {item.value} already exists in case {case.case_id}")

    # Unnamed items (name=None) are identified by their value, not their name; skip name-based
    # conflict detection for them so that multiple unnamed hits can coexist in the same parent.
    name = item.name
    if item.name is None:
        name = item.value

    # Check for duplicate folder under same parent
    return any(ci.name == name and ci.parent == item.parent for ci in case.items)


def _ensure_parent_exists(case: Case, parent_id: str) -> None:
    """Validate that a parent ID references an existing folder item in the case.

    Args:
        case: The case whose items to search.
        parent_id: The ID that must correspond to a folder-type item.

    Raises:
        InvalidDataException: If the parent ID does not match any folder item.
    """
    parent = next((item for item in case.items if item.id == parent_id), None)
    if parent is None:
        raise InvalidDataException(f"Parent item '{parent_id}' does not exist in the case")
    if parent.type != CaseItemTypes.FOLDER:
        raise InvalidDataException(f"Parent item '{parent_id}' is not a folder (type: {parent.type})")


def move_case_item(
    case: str | Case | None,
    item_id: str,
    new_parent: str | None,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    *,
    user: User | None = None,
) -> Case:
    """Move an item to a different parent folder (or to root).

    Args:
        case: Case object or unique identifier of the case.
        item_id: The UUID of the item to move.
        new_parent: The UUID of the target folder, or None for root.

    Returns:
        The updated Case object.

    Raises:
        NotFoundException: If the case or item does not exist.
        InvalidDataException: If the target parent is invalid or would create a cycle.
        DataStoreException: If saving the case fails.
    """
    case = _load_case(case, user)

    item = next((i for i in case.items if i.id == item_id), None)
    if item is None:
        raise NotFoundException(f"Item {item_id} does not exist in case {case.case_id}")

    # Case items must remain root-level
    if item.type == CaseItemTypes.CASE and new_parent is not None:
        raise InvalidDataException("Case items must be root-level (parent must be null)")

    # Validate new parent
    if new_parent is not None:
        _ensure_parent_exists(case, new_parent)

        # Prevent cycles: the new parent must not be a descendant of the item being moved
        if item.type == CaseItemTypes.FOLDER:
            if _is_descendant(case.items, new_parent, item_id):
                raise InvalidDataException(f"Cannot move folder '{item_id}' under its own descendant '{new_parent}'")

    if any(ci.name == item.name and ci.parent == new_parent and ci.id != item_id for ci in case.items):
        raise InvalidDataException(f"An item with name '{item.name}' already exists in destination.")

    item.parent = new_parent

    if not case.save(refresh=refresh):  # pragma: no cover
        raise DataStoreException("Failed to save case after item move")

    comms_service.emit("cases", {"case": case.as_primitives()})

    return case


def _is_descendant(items: list[CaseItem], candidate_id: str, ancestor_id: str) -> bool:
    """Check if candidate_id is a descendant of ancestor_id in the item tree.

    Walks up from candidate_id via parent pointers. Returns True if ancestor_id
    is encountered, indicating a cycle would be created.
    """
    items_by_id = {item.id: item for item in items}
    current: str | None = candidate_id
    visited: set[str] = set()
    while current is not None:
        if current == ancestor_id:
            return True
        if current in visited:
            break
        visited.add(current)
        item = items_by_id.get(current)
        if item is None:
            break
        current = item.parent
    return False


def remove_case_items(  # noqa: C901
    case: str | Case | None,
    item_ids: list[str],
    force: bool = False,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    *,
    user: User | None = None,
) -> Case:  # noqa: C901
    """Remove items from a case by their IDs.

    Args:
        case: Case object or unique identifier of the case.
        item_ids: List of item UUIDs to remove.
        force: If True, also remove children of folder items. If False,
            reject removal of non-empty folders.

    Returns:
        The updated Case object.

    Raises:
        NotFoundException: If the case or any item does not exist.
        InvalidDataException: If a non-empty folder is being removed without force=True.
        DataStoreException: If saving the case fails.
    """
    case = _load_case(case, user)
    ds = datastore()

    items_by_id = {item.id: item for item in case.items}
    missing = [iid for iid in item_ids if iid not in items_by_id]
    if missing:
        raise NotFoundException(f"Item(s) not found in case: {', '.join(missing)}")

    # Collect all IDs to remove (including children if force=True)
    ids_to_remove: set[str] = set()
    for iid in item_ids:
        item = items_by_id[iid]
        if item.type == CaseItemTypes.FOLDER:
            children = [ci for ci in case.items if ci.parent == iid]
            if children and not force:
                raise InvalidDataException(
                    f"Folder '{iid}' is not empty. Use force=True to remove it and its children."
                )
            if force:
                # Recursively collect all descendants
                ids_to_remove.update(_collect_descendant_ids(case.items, iid))
        ids_to_remove.add(iid)

    # Resolve backing objects for back-reference cleanup
    items_to_remove = [items_by_id[iid] for iid in ids_to_remove if iid in items_by_id]
    backing_objs: list[tuple[Hit | Event, str, list[str]]] = []
    for item in items_to_remove:
        if item.type in [CaseItemTypes.HIT, CaseItemTypes.EVENT]:
            obj, version = ds[item.type].get(item.value, as_obj=True, version=True)
            if obj:
                backing_objs.append((obj, version, list(obj.howler.related)))

    case_state = _capture_case_state(case)
    case.items = [item for item in case.items if item.id not in ids_to_remove]
    recompute_case_metadata(case)
    _save_case_or_rollback(case, case_state, refresh, "Failed to save case after item removal")

    failure: Exception | None = None
    for backing_obj, version, _original_related in backing_objs:
        try:
            remove_backreference(backing_obj, case.case_id)
            if not backing_obj.save(version=version):
                failure = DataStoreException(
                    f"Failed to save removed {type(backing_obj).__name__.lower()} backreference"
                )
                break
        except Exception as exc:
            failure = exc
            break

    if failure is not None:
        _restore_backreferences(backing_objs)
        _rollback_case(case, case_state, refresh, "item removal")
        raise failure

    comms_service.emit("cases", {"case": case.as_primitives()})

    return case


def _collect_descendant_ids(items: list[CaseItem], parent_id: str) -> set[str]:
    """Recursively collect all descendant item IDs of a given parent."""
    result: set[str] = set()
    for item in items:
        if item.parent == parent_id:
            result.add(item.id)
            result.update(_collect_descendant_ids(items, item.id))
    return result


def _append_backing_item(
    case: Case,
    item: CaseItem,
    backing_obj: Hit | Event,
    version: str | None,
    refresh: Literal["true", "false", "wait_for"] | None,
    item_type: str,
    emit: bool,
) -> Case:
    """Persist a case item and its backing-object relationship with compensation."""
    case_state = _capture_case_state(case)
    original_item_classification = item.classification
    item.classification = backing_obj.classification
    case.items.append(item)
    recompute_case_metadata(case)

    try:
        _save_case_or_rollback(
            case,
            case_state,
            refresh,
            f"Failed to save {case.case_id} with new item {item.value}",
        )
    except Exception:
        item.classification = original_item_classification
        raise

    original_related = list(backing_obj.howler.related)
    failure: Exception | None = None
    try:
        added = add_backreference(backing_obj, case.case_id)
        saved = not added or backing_obj.save(version=version)
        if not saved:
            failure = DataStoreException(f"Failed to save {item_type} {item.value} backreference")
    except Exception as exc:
        failure = exc

    if failure is not None:
        _restore_backreferences([(backing_obj, version, original_related)])
        item.classification = original_item_classification
        _rollback_case(case, case_state, refresh, f"{item_type} append")
        raise failure

    if emit:
        comms_service.emit("cases", {"case": case.as_primitives()})
    return case


def _append_hit_or_event(
    case: Case,
    item: CaseItem,
    refresh: Literal["true", "false", "wait_for"] | None,
    item_type: str,
    fetch: Callable[[], tuple[Hit | Event | None, str | None]],
    backing_obj: Hit | Event | None,
    version: str | None,
    emit: bool,
) -> Case:
    """Resolve (or reuse an already-resolved) hit/event, then append it to the case."""
    pre_resolved = backing_obj is not None
    if backing_obj is None:
        backing_obj, version = fetch()

    if backing_obj is None:
        raise NotFoundException(f"{item_type.capitalize()} {item.value} not found, cannot be added to case")

    if not pre_resolved:
        _check_item_classification(case.classification, item_type, item.value, backing_obj.classification)

    return _append_backing_item(case, item, backing_obj, version, refresh, item_type, emit)


def append_hit(
    case: Case,
    item: CaseItem,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    *,
    backing_obj: Hit | None = None,
    version: str | None = None,
    emit: bool = True,
) -> Case:
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
    return _append_hit_or_event(
        case,
        item,
        refresh,
        "hit",
        lambda: ds.hit.get(item.value, as_obj=True, version=True),
        backing_obj,
        version,
        emit,
    )


def append_event(
    case: Case,
    item: CaseItem,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    *,
    backing_obj: Event | None = None,
    version: str | None = None,
    emit: bool = True,
) -> Case:
    """Append an event item to a case and create a back-reference on the event.

    Validates that the case and event both exist and that the event is
    not already present in the case. It then persists the updated case and adds a back-reference
    from the event to the case.

    Args:
        case_id: Unique identifier of the case to append the event to.
        item: A CaseItem whose ``value`` is the ID of an existing event.

    Raises:
        NotFoundException: If the case or event does not exist.
        InvalidDataException: If the event is already present in the case.
        DataStoreException: If saving the updated case fails.
    """
    ds = datastore()
    return _append_hit_or_event(
        case,
        item,
        refresh,
        "event",
        lambda: ds.event.get(key=item.value, as_obj=True, version=True),
        backing_obj,
        version,
        emit,
    )


def append_case(
    case: Case,
    item: CaseItem,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    *,
    backing_obj: Case | None = None,
    emit: bool = True,
) -> Case:
    """Append a case reference item to a case.

    Validates that both the parent case and the referenced case exist, and that
    the referenced case is not already present in the parent case. It then persists the updated
    parent case.

    Case items must always be root-level; the ``CaseItem.__init__`` guard rejects
    construction with a non-null ``parent`` for ``type == "case"``.

    Args:
        case_id: Unique identifier of the parent case to append the reference to.
        item: A CaseItem whose ``value`` is the ID of an existing case to reference.

    Raises:
        NotFoundException: If the parent case or referenced case does not exist.
        InvalidDataException: If the referenced case is already present in the parent case.
        DataStoreException: If saving the updated case fails.
    """
    if any(item.value == case_item["value"] for case_item in case.items):
        raise InvalidDataException(f"Item {item.value} already exists in case {case.case_id}")

    if backing_obj is None:
        ds = datastore()
        referenced_case = ds.case.get(item.value)
    else:
        referenced_case = backing_obj

    if referenced_case is None:
        raise NotFoundException(f"Referenced case {item.name} not found, cannot be added to case")

    if backing_obj is None:
        _check_item_classification(case.classification, "case", item.value, referenced_case.classification)
    case_state = _capture_case_state(case)
    item.classification = referenced_case.classification
    case.items.append(item)

    _save_case_or_rollback(
        case,
        case_state,
        refresh,
        f"Failed to save {case.case_id} with new item {item.name}",
    )

    if emit:
        comms_service.emit("cases", {"case": case.as_primitives()})

    return case


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


def recompute_case_metadata(case: Case) -> None:  # noqa: C901
    """Re-compute (in memory only) threat/target/indicator lists from all case items.

    Iterates over hit and event items in the case and re-derives the
    ``targets``, ``threats``, and ``indicators`` lists from the backing
    objects' ECS ``related.*`` fields and, for hits, the outline fields. Does
    not persist the case; callers are responsible for saving it.
    """
    ds = datastore()

    targets: set[str] = set()
    threats: set[str] = set()
    indicators: set[str] = set()

    for item in case.items:
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

        elif item.type == CaseItemTypes.EVENT and item.value:
            event = ds.event.get(item.value)
            if event is None:
                continue

            indicators.update(_collect_indicators_from_related(event.related))

    case.targets = sorted(targets)
    case.threats = sorted(threats)
    case.indicators = sorted(indicators)


def add_backreference(backing_obj: Hit | Event | None, case_id: str) -> bool:
    """Add a back-reference from a hit or event to a case, in memory only.

    Records the case ID in the backing object's ``howler.related`` list so
    that the relationship can be traversed from the hit/event side. Does not
    persist the change; callers are responsible for saving the object.

    Args:
        backing_obj: The Hit or Event object to add the back-reference to.
        case_id: Unique identifier of the case to reference.

    Returns:
        True if a new back-reference was added, False if it already existed.

    Raises:
        InvalidDataException: If backing_obj is None or case_id is empty/falsy.
    """
    if backing_obj is None:
        raise InvalidDataException("Cannot add back reference on a nonexistent object")

    if not case_id:
        raise InvalidDataException("Missing back reference case_id")

    if any(case_id == related_id for related_id in backing_obj.howler.related):
        return False

    backing_obj.howler.related.append(case_id)
    return True


def remove_backreference(
    backing_obj: Hit | Event | None,
    case_id: str,
):
    """Remove a back-reference from a hit or event to a case, in memory only.

    Removes the case ID from the backing object's ``howler.related`` list.
    Does not persist the change; callers are responsible for saving the
    object. If the case ID is not present in the list, the call is a no-op.

    Args:
        backing_obj: The Hit or Event object to remove the back-reference from.
        case_id: Unique identifier of the case reference to remove.

    Raises:
        InvalidDataException: If backing_obj is None or case_id is empty/falsy.
    """
    if backing_obj is None:
        raise InvalidDataException("Cannot remove back reference on a nonexisting object")

    if not case_id:  # pragma: no cover
        raise InvalidDataException("Missing back reference case_id")

    if case_id in backing_obj.howler.related:
        backing_obj.howler.related.remove(case_id)


def rename_case_item(
    case_id: str,
    item_id: str,
    new_name: str,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    *,
    user: User | None = None,
) -> Case:
    """Rename a single item within a case by updating its display name.

    Args:
        case_id: Unique identifier of the case.
        item_id: The UUID of the item to rename.
        new_name: The new display name for the item.

    Returns:
        The updated Case object.

    Raises:
        NotFoundException: If the case or item does not exist.
        InvalidDataException: If new_name is empty.
        DataStoreException: If persisting the updated case fails.
    """
    if not new_name or not new_name.strip():
        raise InvalidDataException("new_name must be a non-empty string")

    case = _load_case(case_id, user)

    item = next((i for i in case.items if i.id == item_id), None)
    if item is None:
        raise NotFoundException(f"Item {item_id} does not exist in case {case_id}")

    # Guard: reject if the target name is already used by a sibling (item with the same parent).
    if any(i.name == new_name.strip() and i.id != item_id and i.parent == item.parent for i in case.items):
        raise InvalidDataException(f"Name '{new_name.strip()}' is already used by a sibling item in this case")

    item.name = new_name.strip()

    if item.type == CaseItemTypes.FOLDER:
        item.value = item.name

    if not case.save(refresh=refresh):  # pragma: no cover
        raise DataStoreException("Failed to save case after item rename")

    comms_service.emit("cases", {"case": case.as_primitives()})

    return case


def add_case_rule(
    case_id: str, rule_data: dict, user: User, refresh: Literal["true", "false", "wait_for"] | None = None
) -> Case:
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
    case = _load_case(case_id, user)

    if not rule_data.get("query"):
        raise InvalidDataException("Rule 'query' is required")

    if not rule_data.get("destination"):
        raise InvalidDataException("Rule 'destination' is required")

    rule_data.pop("rule_id", None)
    rule_data.pop("created_at", None)
    rule_data["author"] = user.uname
    rule_data.setdefault("enabled", True)
    rule_data.setdefault("expire_after_resolved", False)

    try:
        _validate_rule_values(rule_data.get("timeframe"), rule_data["expire_after_resolved"])
        rule = CaseRule(rule_data)
    except HowlerValueError as ex:
        raise InvalidDataException(str(ex)) from ex

    case.rules.append(rule)

    case.log.append(
        CaseLog(
            {
                "timestamp": "NOW",
                "user": user.uname,
                "explanation": f"Added correlation rule targeting '{rule.destination}'",
            }
        )
    )

    case.updated = "NOW"
    case.save(refresh=refresh)
    comms_service.emit("cases", {"case": case.as_primitives()})
    return case


def remove_case_rule(
    case_id: str, rule_id: str, user: User, refresh: Literal["true", "false", "wait_for"] | None = None
) -> Case:
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
    case = _load_case(case_id, user)

    original_len = len(case.rules)
    case.rules = [r for r in case.rules if r.rule_id != rule_id]

    if len(case.rules) == original_len:
        raise NotFoundException(f"Rule {rule_id} not found in case {case_id}")

    case.log.append(
        CaseLog(
            {
                "timestamp": "NOW",
                "user": user.uname,
                "explanation": f"Removed correlation rule {rule_id}",
            }
        )
    )

    case.updated = "NOW"
    case.save(refresh)
    comms_service.emit("cases", {"case": case.as_primitives()})
    return case


def update_case_rule(
    case_id: str,
    rule_id: str,
    update_data: dict,
    user: User,
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> Case:
    """Update fields on an existing correlation rule.

    Allowed fields: ``enabled``, ``query``, ``destination``, ``timeframe``,
    ``expire_after_resolved``.

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
    case = _load_case(case_id, user)

    allowed_fields = {"enabled", "query", "destination", "timeframe", "expire_after_resolved"}
    patch = {k: v for k, v in update_data.items() if k in allowed_fields}
    if not patch:
        raise InvalidDataException(
            f"No valid fields provided for update. Allowed fields: {', '.join(sorted(allowed_fields))}"
        )

    rule = next((r for r in case.rules if r.rule_id == rule_id), None)
    if rule is None:
        raise NotFoundException(f"Rule {rule_id} not found in case {case_id}")

    changes: list[str] = []
    _validate_rule_values(
        patch.get("timeframe", rule.timeframe),
        patch.get("expire_after_resolved", rule.expire_after_resolved),
    )

    for key, value in patch.items():
        old_value = getattr(rule, key, None)
        setattr(rule, key, value)
        changes.append(f"{key}: '{old_value}' → '{value}'")

    case.log.append(
        CaseLog(
            {
                "timestamp": "NOW",
                "user": user.uname,
                "explanation": f"Updated correlation rule {rule_id}: {'; '.join(changes)}",
            }
        )
    )

    case.updated = "NOW"
    case.save(refresh=refresh)
    comms_service.emit("cases", {"case": case.as_primitives()})
    return case
