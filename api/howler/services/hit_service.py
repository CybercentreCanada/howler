import functools
import json
import re
import typing
from hashlib import sha256
from typing import Any, Literal, Optional, Union, cast

from prometheus_client import Counter

import howler.services.event_service as event_service
from howler.actions.promote import Escalation
from howler.common.exceptions import HowlerTypeError, HowlerValueError, NotFoundException, ResourceExists
from howler.common.loader import APP_NAME, datastore
from howler.common.logging import get_logger
from howler.datastore.collection import ESCollection
from howler.datastore.operations import OdmHelper, OdmUpdateOperation
from howler.datastore.types import HitSearchResult
from howler.helper.hit import (
    AssessmentEscalationMap,
    assess_hit,
    assign_hit,
    check_ownership,
    demote_hit,
    promote_hit,
    unassign_hit,
    vote_hit,
)
from howler.helper.workflow import Transition, Workflow
from howler.odm.models.ecs.event import Event
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import HitOperationType, HitStatus, HitStatusTransition, Log
from howler.odm.models.user import User
from howler.services import action_service, dossier_service
from howler.utils.dict_utils import extra_keys, flatten
from howler.utils.uid import get_random_id

log = get_logger(__file__)

odm_helper = OdmHelper(Hit)


def get_hit_workflow() -> Workflow:
    """Get the workflow that is used for transitioning between howler statuses

    Returns:
        Workflow: The workflow used to manage hit status transitions
    """
    return Workflow(
        "howler.status",
        [
            Transition(
                {
                    # current user starts investigation
                    "source": HitStatus.OPEN,
                    "transition": HitStatusTransition.ASSIGN_TO_ME,
                    "dest": HitStatus.IN_PROGRESS,
                    "actions": [assign_hit],
                }
            ),
            Transition(
                {
                    # assign to other user and starts investigation
                    "source": HitStatus.OPEN,
                    "transition": HitStatusTransition.ASSIGN_TO_OTHER,
                    "dest": HitStatus.OPEN,
                    "actions": [assign_hit],
                }
            ),
            Transition(
                {
                    # assign to other user and starts investigation
                    "source": HitStatus.OPEN,
                    "transition": HitStatusTransition.START,
                    "dest": HitStatus.IN_PROGRESS,
                    "actions": [check_ownership],
                }
            ),
            Transition(
                {
                    # provides vote
                    "source": HitStatus.OPEN,
                    "transition": HitStatusTransition.VOTE,
                    "dest": HitStatus.OPEN,
                    "actions": [vote_hit],
                }
            ),
            Transition(
                {
                    # assign to another user
                    "source": HitStatus.IN_PROGRESS,
                    "transition": HitStatusTransition.ASSIGN_TO_OTHER,
                    "dest": HitStatus.IN_PROGRESS,
                    "actions": [assign_hit],
                }
            ),
            Transition(
                {
                    # removes assignment
                    "source": HitStatus.IN_PROGRESS,
                    "transition": HitStatusTransition.RELEASE,
                    "dest": HitStatus.OPEN,
                    "actions": [unassign_hit],
                }
            ),
            Transition(
                {
                    # user completes investigation
                    "source": [HitStatus.OPEN, HitStatus.IN_PROGRESS],
                    "transition": HitStatusTransition.ASSESS,
                    "dest": HitStatus.RESOLVED,
                    "actions": [assess_hit, assign_hit],
                }
            ),
            Transition(
                {
                    # vote on in_progress hit
                    "source": HitStatus.IN_PROGRESS,
                    "transition": HitStatusTransition.VOTE,
                    "dest": HitStatus.IN_PROGRESS,
                    "actions": [vote_hit],
                }
            ),
            Transition(
                {
                    # removes assignment
                    "source": HitStatus.OPEN,
                    "transition": HitStatusTransition.RELEASE,
                    "dest": HitStatus.OPEN,
                    "actions": [unassign_hit],
                }
            ),
            Transition(
                {
                    # user pauses investigation
                    "source": HitStatus.IN_PROGRESS,
                    "transition": HitStatusTransition.PAUSE,
                    "dest": HitStatus.ON_HOLD,
                    "actions": [check_ownership],
                }
            ),
            Transition(
                {
                    # user restarts investigation after pausing it
                    "source": HitStatus.ON_HOLD,
                    "transition": HitStatusTransition.RESUME,
                    "dest": HitStatus.IN_PROGRESS,
                    "actions": [check_ownership],
                }
            ),
            Transition(
                {
                    # current user starts investigation
                    "transition": HitStatusTransition.ASSIGN_TO_ME,
                    "source": HitStatus.IN_PROGRESS,
                    "dest": HitStatus.IN_PROGRESS,
                    "actions": [assign_hit],
                }
            ),
            Transition(
                {
                    # user restarts investigation after pausing it
                    "source": HitStatus.ON_HOLD,
                    "transition": HitStatusTransition.ASSIGN_TO_OTHER,
                    "dest": HitStatus.IN_PROGRESS,
                    "actions": [assign_hit],
                }
            ),
            Transition(
                {
                    # user restarts investigation after pausing it
                    "transition": HitStatusTransition.VOTE,
                    "source": HitStatus.ON_HOLD,
                    "dest": HitStatus.ON_HOLD,
                    "actions": [vote_hit],
                }
            ),
            Transition(
                {
                    # Reopen a task after resolving it
                    "source": HitStatus.RESOLVED,
                    "transition": HitStatusTransition.RE_EVALUATE,
                    "dest": HitStatus.IN_PROGRESS,
                    "actions": [assess_hit, assign_hit],
                }
            ),
            Transition(
                {
                    # Reopen a task after resolving it
                    "source": HitStatus.RESOLVED,
                    "transition": HitStatusTransition.VOTE,
                    "dest": HitStatus.RESOLVED,
                    "actions": [vote_hit],
                }
            ),
            Transition(
                {
                    "source": None,
                    "transition": HitStatusTransition.PROMOTE,
                    "dest": None,
                    "actions": [promote_hit],
                }
            ),
            Transition(
                {
                    "source": None,
                    "transition": HitStatusTransition.DEMOTE,
                    "actions": [demote_hit],
                    "dest": None,
                }
            ),
        ],
    )


def _modifies_prop(prop: str, operations: list[OdmUpdateOperation]) -> bool:
    """Check if the list of provided operations modifies the specified property

    Args:
        prop (str): The property to check for changes
        operations (list[OdmUpdateOperation]): The operations that will be performed

    Returns:
        bool: Is the property modified by these operations?
    """
    return any(op for op in operations if op.key == prop)


def does_hit_exist(hit_id: str) -> bool:
    """Checks if the provided ID matches any entries in the database

    Args:
        hit_id (str): The ID to check for in the database

    Returns:
        bool: Does the ID match a document in the database?
    """
    return datastore().hit.exists(hit_id)


def validate_hit_ids(hit_ids: list[str]) -> bool:
    """Checks if all hit_ids are available

    Args:
        hit_ids (list[str]): A list of hit ids to validate

    Returns:
        bool: Whether all of the hit ids are free to use
    """
    return not any(does_hit_exist(hit_id) for hit_id in hit_ids)


def convert_hit(data: dict[str, Any], unique: bool, ignore_extra_values: bool = False) -> tuple[Hit, list[str]]:  # noqa: C901
    """Validate and convert a dictionary to a Hit ODM object.

    This function performs comprehensive validation on input data to ensure it can be
    safely converted to a Hit object. It handles hash generation, ID assignment,
    data normalization, and validation warnings. The function also checks for
    deprecated fields and enforces naming conventions for analytics and detections.

    Args:
        data: Dictionary containing hit data to validate and convert
        unique: Whether to enforce uniqueness by checking if the hit ID already exists
        ignore_extra_values: Whether to ignore invalid extra fields (True) or raise an exception (False)

    Returns:
        Tuple containing:
        - Hit: The validated and converted ODM object
        - list[str]: List of validation warnings (unused fields, deprecated fields, naming issues)

    Raises:
        HowlerValueError: If bundle is specified during creation, invalid parameters are provided,
                         or naming conventions are violated
        HowlerTypeError: If the data cannot be converted to a Hit ODM object
        ResourceExists: If unique=True and a hit with the generated ID already exists

    Note:
        - Automatically generates a hash based on analytic, detection, and raw data
        - Assigns a random ID if not provided
        - Normalizes data fields to ensure consistent storage format
        - Validates analytic and detection names against best practices (letters and spaces only)
    """
    data = flatten(data, odm=Hit)

    if "howler.hash" not in data:
        hash_contents = {
            "analytic": data.get("howler.analytic", "no_analytic"),
            "detection": data.get("howler.detection", "no_detection"),
            "raw_data": data.get("howler.data", {}),
        }

        data["howler.hash"] = sha256(
            json.dumps(hash_contents, sort_keys=True, ensure_ascii=True).encode("utf-8")
        ).hexdigest()

    data["howler.id"] = get_random_id()

    if "howler.bundles" in data and len(data["howler.bundles"]) > 0:
        raise HowlerValueError("You cannot specify a bundle when creating a hit.")

    if "howler.data" in data:
        parsed_data = []
        for entry in data["howler.data"]:
            if isinstance(entry, str):
                parsed_data.append(entry)
            else:
                parsed_data.append(json.dumps(entry))

        data["howler.data"] = parsed_data

    if "bundle_size" not in data and "howler.hits" in data:
        data["howler.bundle_size"] = len(data["howler.hits"])

    # TODO: This is a really strange double-validation check we should look to refactor
    try:
        odm = Hit(data, ignore_extra_values=ignore_extra_values)
    except TypeError as e:
        raise HowlerTypeError(str(e), cause=e) from e

    # Check for deprecated field and unused fields
    odm_flatten = odm.flat_fields(show_compound=True)
    unused_keys = extra_keys(Hit, data)

    if unused_keys and not ignore_extra_values:
        raise HowlerValueError(f"Hit was created with invalid parameters: {', '.join(unused_keys)}")
    deprecated_keys = set(key for key in odm_flatten.keys() & data.keys() if odm_flatten[key].deprecated)

    warnings = [f"{key} is not currently used by howler." for key in unused_keys]
    warnings.extend(
        [f"{key} is deprecated." for key in deprecated_keys],
    )

    if re.search(r"^([A-Za-z ])+$", odm.howler.analytic) is None:
        warnings.append(
            f"The value {odm.howler.analytic} does not match best practices for Howler analytic names. "
            "See howler's documentation for more information."
        )

    if odm.howler.detection and re.search(r"^([A-Za-z ])+$", odm.howler.detection) is None:
        warnings.append(
            f"The value {odm.howler.detection} does not match best practices for Howler detection names. "
            "See howler's documentation for more information."
        )

    if odm.event:
        odm.event.id = odm.howler.id
        if not odm.event.created:
            odm.event.created = "NOW"
    else:
        odm.event = Event({"created": "NOW", "id": odm.howler.id})

    if unique and does_hit_exist(odm.howler.id):
        raise ResourceExists("Resource with id %s already exists" % odm.howler.id)

    return odm, warnings


def exists(id: str):
    """Check if a hit exists in the datastore.

    Args:
        id: The unique identifier of the hit to check

    Returns:
        bool: True if the hit exists, False otherwise
    """
    return datastore().hit.exists(id)


def get_hit(
    id: str,
    as_odm: bool = False,
    version: bool = False,
):
    """Retrieve a hit from the datastore.

    Args:
        id: The unique identifier of the hit to retrieve
        as_odm: Whether to return the hit as an ODM object (True) or dictionary (False)
        version: Whether to include version information in the response

    Returns:
        Hit object (if as_odm=True) or dictionary representation of the hit.
        Returns None if the hit doesn't exist.
    """
    return datastore().hit.get_if_exists(key=id, as_obj=as_odm, version=version)


CREATED_HITS = Counter(
    f"{APP_NAME.replace('-', '_')}_created_hits_total",
    "The number of created hits",
    ["analytic"],
)


def create_hit(
    id: str,
    hit: Hit,
    user: Optional[str] = None,
    overwrite: bool = False,
) -> bool:
    """Create a new hit in the database.

    This function saves a hit to the datastore, optionally adding a creation log entry
    and updating metrics. It will prevent overwriting existing hits unless explicitly allowed.

    Args:
        id: The unique identifier for the hit
        hit: The Hit ODM object to save
        user: Optional username to record in the creation log
        overwrite: Whether to allow overwriting an existing hit with the same ID

    Returns:
        bool: True if the hit was successfully created

    Raises:
        ResourceExists: If a hit with the same ID already exists and overwrite=False
    """
    if not overwrite and does_hit_exist(id):
        raise ResourceExists("Hit %s already exists in datastore" % id)

    if user:
        hit.howler.log = [Log({"timestamp": "NOW", "explanation": "Created hit", "user": user})]

    CREATED_HITS.labels(hit.howler.analytic).inc()
    return datastore().hit.save(id, hit)


def update_hit(
    hit_id: str,
    operations: list[OdmUpdateOperation],
    user: Optional[str] = None,
    version: Optional[str] = None,
):
    """Update one or more properties of a hit in the database.

    This function applies a list of update operations to modify hit properties.
    Note that hit status cannot be modified through this function - use transition_hit instead.

    Args:
        hit_id: The unique identifier of the hit to update
        operations: List of ODM update operations to apply
        user: Optional username to record in the update log
        version: Optional version string for optimistic locking

    Returns:
        Tuple of (updated_hit_data, new_version)

    Raises:
        HowlerValueError: If attempting to modify hit status through this function
    """
    # Status of a hit should only be updated through the transition function
    if _modifies_prop("howler.status", operations):
        raise HowlerValueError(
            "Status of a Hit cannot be modified like other properties. Please use a transition to do so."
        )

    return _update_hit(hit_id, operations, user, version=version)


@typing.no_type_check
def save_hit(hit: Hit, version: Optional[str] = None) -> tuple[Hit, str]:
    """Save a hit to the datastore and emit an event notification.

    This function persists a hit object to the database and emits an event
    to notify other systems of the change.

    Args:
        hit: The Hit ODM object to save
        version: Optional version string for optimistic locking

    Returns:
        Tuple of (hit_data_dict, version_string)
    """
    datastore().hit.save(hit.howler.id, hit, version=version)
    data, _version = datastore().hit.get(hit.howler.id, as_obj=False, version=True)
    event_service.emit("hits", {"hit": data, "version": _version})

    return data, version


def _update_hit(
    hit_id: str,
    operations: list[OdmUpdateOperation],
    user: Optional[str] = None,
    version: Optional[str] = None,
) -> tuple[Hit, str]:
    """Internal function to update a hit with proper logging and event emission.

    This function applies update operations to a hit, automatically adding worklog entries
    for non-silent operations and emitting events to notify other systems of changes.

    Args:
        hit_id: The unique identifier of the hit to update
        operations: List of ODM update operations to apply
        user: Optional username to record in operation logs
        version: Optional version string for optimistic locking

    Returns:
        Tuple of (updated_hit_data, new_version)

    Raises:
        HowlerValueError: If user parameter is provided but not a string
    """
    final_operations = []

    if user and not isinstance(user, str):
        raise HowlerValueError("User must be of type string")

    current_hit = get_hit(hit_id, as_odm=True)

    for operation in operations:
        if not operation:
            continue

        try:
            is_list = current_hit.flat_fields()[operation.key].multivalued
            try:
                previous_value = current_hit[operation.key]
            except (TypeError, KeyError):
                previous_value = None
        except KeyError:
            key = next(key for key in current_hit.flat_fields().keys() if key.startswith(operation.key))
            is_list = current_hit.flat_fields()[key].multivalued
            previous_value = "list"

        operation_type = ""
        if is_list:
            if operation.operation in (
                ESCollection.UPDATE_APPEND,
                ESCollection.UPDATE_APPEND_IF_MISSING,
            ):
                operation_type = HitOperationType.APPENDED
            else:
                operation_type = HitOperationType.REMOVED
        else:
            operation_type = HitOperationType.SET

        log.debug("%s - %s - %s -> %s", hit_id, operation.key, previous_value, operation.value)
        final_operations.append(operation)

        if not operation.silent:
            final_operations.append(
                OdmUpdateOperation(
                    ESCollection.UPDATE_APPEND,
                    "howler.log",
                    {
                        "timestamp": "NOW",
                        "previous_version": version,
                        "key": operation.key,
                        "explanation": operation.explanation,
                        "new_value": operation.value or "None",
                        "previous_value": previous_value or "None",
                        "type": operation_type,
                        "user": user if user else "Unknown",
                    },
                )
            )

    datastore().hit.update(hit_id, final_operations, version)
    # Need to fetch the new data of the hit for the event_service
    data, _version = datastore().hit.get(hit_id, as_obj=False, version=True)
    event_service.emit("hits", {"hit": data, "version": _version})

    return data, _version


def get_transitions(status: HitStatus) -> list[str]:
    """Get a list of the valid transitions beginning from the specified status

    Args:
        status (HitStatus): The status we want to transition from

    Returns:
        list[str]: A list of valid transitions to execute
    """
    return get_hit_workflow().get_transitions(status)


def get_all_children(hit: Hit):
    """Get a list of all child hits for a given hit, including nested children.

    This function recursively traverses bundle structures to find all child hits.
    If a child hit is itself a bundle, it will recursively get its children too.

    Args:
        hit: The parent hit to get children for

    Returns:
        List of all child hits (may include None values for missing hits)
    """
    # Get immediate child hits from the hit's bundle
    child_hits = [get_hit(hit_id) for hit_id in hit["howler"].get("hits", [])]

    # Recursively process child hits that are themselves bundles
    for entry in child_hits:
        if not entry:
            continue

        # If this child is a bundle, get its children too
        if entry["howler"]["is_bundle"]:
            child_hits.extend(get_all_children(entry))

    return child_hits


def transition_hit(
    id: str,
    transition: HitStatusTransition,
    user: User,
    version: Optional[str] = None,
    **kwargs,
):
    """Transition a hit from one status to another while updating related properties.

    This function handles status transitions for both individual hits and bundles,
    applying the same transition to all child hits in a bundle. For certain transitions
    (PROMOTE, DEMOTE, ASSESS, RE_EVALUATE), it also executes bulk actions and emits events.

    Args:
        id: The id of the hit to transition
        transition: The transition to execute (e.g., ASSIGN_TO_ME, ASSESS, PROMOTE)
        user: The user running the transition
        version: Optional version to validate against. The transition will not run if the version doesn't match.
        **kwargs: Additional arguments including potential 'hit' object and 'assessment' value

    Raises:
        NotFoundException: If the hit does not exist
    """
    # Get the primary hit (either provided in kwargs or fetch from database)
    primary_hit: Hit = kwargs.pop("hit", None) or get_hit(id, as_odm=False)

    if not primary_hit:
        raise NotFoundException("Hit does not exist")

    workflow: Workflow = get_hit_workflow()

    # Get all child hits that need to be processed along with the primary hit
    child_hits = get_all_children(primary_hit)
    primary_hit_status = primary_hit["howler"]["status"]

    # Log all hits that will be transitioned
    all_hit_ids = [h["howler"]["id"] for h in ([primary_hit] + [ch for ch in child_hits if ch])]
    log.debug("Transitioning (%s)", ", ".join(all_hit_ids))

    # Process each hit (primary + children) with the workflow transition
    for current_hit in [primary_hit] + [ch for ch in child_hits if ch]:
        current_hit_status = current_hit["howler"]["status"]
        current_hit_id = current_hit["howler"]["id"]

        # Skip hits that don't match the primary hit's status
        # This ensures consistent state transitions across bundles
        if current_hit_status != primary_hit_status:
            log.debug("Skipping %s (status mismatch)", current_hit_id)
            continue

        # Apply the workflow transition to get required updates
        updates = workflow.transition(current_hit_status, transition, user=user, hit=current_hit, **kwargs)

        # Apply updates if any were generated by the workflow
        if updates:
            # Only apply version validation to the primary hit
            hit_version = version if (current_hit_id == primary_hit["howler"]["id"] and version) else None
            _update_hit(current_hit_id, updates, user["uname"], version=hit_version)

    # Execute bulk actions for transitions that require them
    # These transitions need additional processing beyond the workflow
    transitions_requiring_bulk_actions = [
        HitStatusTransition.PROMOTE,
        HitStatusTransition.DEMOTE,
        HitStatusTransition.ASSESS,
        HitStatusTransition.RE_EVALUATE,
    ]

    if transition in transitions_requiring_bulk_actions:
        # Determine the trigger action (promote/demote) based on transition type
        trigger: Union[Literal["promote"], Literal["demote"]]

        if transition == HitStatusTransition.ASSESS:
            # For assessments, determine promotion/demotion based on escalation level
            new_escalation = AssessmentEscalationMap[kwargs["assessment"]]
            trigger = "promote" if new_escalation == Escalation.EVIDENCE else "demote"
        elif transition == HitStatusTransition.RE_EVALUATE:
            # Re-evaluation always promotes the hit
            trigger = "promote"
        else:
            # For direct PROMOTE/DEMOTE transitions, use the transition name
            trigger = cast(Union[Literal["promote"], Literal["demote"]], transition)

        # Commit database changes before executing bulk actions
        datastore().hit.commit()

        # Build query for all processed hits (primary + children)
        all_processed_hits = [primary_hit] + child_hits
        hit_query = f"howler.id:({' OR '.join(h['howler']['id'] for h in all_processed_hits)})"

        # Execute bulk actions on all hits
        action_service.bulk_execute_on_query(hit_query, trigger=trigger, user=user)

        # Emit events for all processed hits to notify other systems
        for processed_hit in all_processed_hits:
            data, hit_version = datastore().hit.get(processed_hit["howler"]["id"], as_obj=False, version=True)
            event_service.emit("hits", {"hit": data, "version": hit_version})


DELETED_HITS = Counter(f"{APP_NAME.replace('-', '_')}_deleted_hits_total", "The number of deleted hits")


def delete_hits(hit_ids: list[str]) -> bool:
    """Delete a set of hits from the database

    Args:
        hit_ids (list[str]): The IDs of the hits to delete

    Returns:
        bool: Was the deletion successful?
    """
    ds = datastore()

    operations = []
    result = True

    for hit_id in hit_ids:
        operations.append(odm_helper.list_remove("howler.hits", hit_id, silent=True))

        result = result and ds.hit.delete(hit_id)
        DELETED_HITS.inc()

    ds.hit.update_by_query("howler.is_bundle:true", operations)

    ds.hit.commit()

    return result


def search(
    query: str,
    offset: int = 0,
    rows: Optional[int] = None,
    sort: Optional[Any] = None,
    fl: Optional[Any] = None,
    timeout: Optional[Any] = None,
    deep_paging_id: Optional[Any] = None,
    track_total_hits: Optional[Any] = None,
    as_obj: bool = True,
) -> HitSearchResult:
    """Search for hits in the datastore using a query.

    This function provides a flexible search interface for finding hits based on
    various criteria. It supports pagination, sorting, field limiting, and other
    advanced search features.

    Args:
        query: The search query string (supports Lucene syntax)
        offset: Number of results to skip (for pagination)
        rows: Maximum number of results to return
        sort: Sort criteria for the results
        fl: Field list - which fields to include in results
        timeout: Query timeout duration
        deep_paging_id: Identifier for deep pagination
        track_total_hits: Whether to track the total hit count
        as_obj: Whether to return results as ODM objects (True) or dictionaries (False)

    Returns:
        HitSearchResult containing the matching hits and metadata
    """
    return datastore().hit.search(
        query=query,
        offset=offset,
        rows=rows,
        sort=sort,
        fl=fl,
        timeout=timeout,
        deep_paging_id=deep_paging_id,
        track_total_hits=track_total_hits,
        as_obj=as_obj,
    )


TYPE_PRIORITY = {"personal": 2, "readonly": 1, "global": 0}


def __compare_metadata(object_a: dict[str, Any], object_b: dict[str, Any]) -> int:
    # Sort priority:
    # 1. personal > readonly > global
    # 2. detection > !detection

    if object_a["type"] != object_b["type"]:
        return TYPE_PRIORITY[object_b["type"]] - TYPE_PRIORITY[object_a["type"]]

    if object_a.get("detection", None) and not object_b.get("detection", None):
        return -1

    if not object_a.get("detection", None) and object_b.get("detection", None):
        return 1

    return 0


def __match_metadata(candidates: list[dict[str, Any]], hit: dict[str, Any]) -> Optional[dict[str, Any]]:
    matching_candidates: list[dict[str, Any]] = []

    for candidate in candidates:
        if candidate["analytic"].lower() != hit["howler"]["analytic"].lower():
            continue

        if not candidate.get("detection", None):
            matching_candidates.append(candidate)
            continue

        if not hit["howler"].get("detection", None):
            continue

        if hit["howler"]["detection"].lower() != candidate["detection"].lower():
            continue

        matching_candidates.append(candidate)

    if len(matching_candidates) < 1:
        return None

    return sorted(matching_candidates, key=functools.cmp_to_key(__compare_metadata))[0]


def augment_metadata(data: list[dict[str, Any]] | dict[str, Any], metadata: list[str], user: dict[str, Any]):
    """Augment hit search results with additional metadata.

    This function enriches hit data by adding related information such as templates,
    overviews, and matching dossiers. The metadata is added as special fields prefixed
    with double underscores (e.g., __template, __overview, __dossiers).

    Args:
        data: Hit data - either a single hit dictionary or list of hit dictionaries
        metadata: List of metadata types to include ('template', 'overview', 'dossiers')
        user: User context for determining accessible templates and other user-specific data

    Note:
        This function modifies the input data in-place, adding metadata fields.
        Templates are filtered based on user permissions (global or owned by user).
    """
    hits = data if isinstance(data, list) else [data]

    analytics: set[str] = set()
    for hit in hits:
        analytics.add(f'"{hit["howler"]["analytic"]}"')

    if len(analytics) > 0:
        if "template" in metadata:
            template_candidates = datastore().template.search(
                f"analytic:({' OR '.join(analytics)}) AND (type:global OR owner:{user['uname']})",
                as_obj=False,
            )["items"]

            for hit in hits:
                hit["__template"] = __match_metadata(template_candidates, hit)

        if "overview" in metadata:
            overview_candidates = datastore().overview.search(
                f"analytic:({' OR '.join(analytics)})",
                as_obj=False,
            )["items"]

            for hit in hits:
                hit["__overview"] = __match_metadata(overview_candidates, hit)

    if "dossiers" in metadata:
        dossiers: list[dict[str, Any]] = datastore().dossier.search(
            "dossier_id:*",
            as_obj=False,
            # TODO: Eventually implement caching here
            rows=1000,
        )["items"]

        for hit in hits:
            hit["__dossiers"] = dossier_service.get_matching_dossiers(hit, dossiers)
