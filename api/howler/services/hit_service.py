import functools
import json
import re
import typing
from hashlib import sha256
from typing import Any, Literal, Optional, Union, cast, overload

from opentelemetry import trace
from prometheus_client import Counter

import howler.services.comms_service as comms_service
from howler.actions.promote import Escalation
from howler.common.exceptions import (
    HowlerRuntimeError,
    HowlerTypeError,
    HowlerValueError,
    NotFoundException,
    ResourceExists,
)
from howler.common.loader import APP_NAME, datastore
from howler.common.logging import get_logger
from howler.datastore.collection import BulkResult, ESCollection
from howler.datastore.exceptions import VersionConflictException
from howler.datastore.operations import OdmHelper, OdmUpdateOperation
from howler.datastore.types import SearchResult
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
from howler.odm.models.ecs.event import ECSEvent
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import HitOperationType, HitStatusTransition, Log, Status
from howler.odm.models.user import User
from howler.services import (
    action_service,
    analytic_service,
    correlation_service,
    dossier_service,
    overview_service,
    template_service,
)
from howler.utils.dict_utils import extra_keys, flatten
from howler.utils.uid import get_random_id

logger = get_logger(__file__)

tracer = trace.get_tracer(__name__)
odm_helper = OdmHelper(Hit)


@tracer.start_as_current_span(f"{__name__}.get_hit_workflow")
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
                    "source": Status.OPEN,
                    "transition": HitStatusTransition.ASSIGN_TO_ME,
                    "dest": Status.IN_PROGRESS,
                    "actions": [assign_hit],
                }
            ),
            Transition(
                {
                    # assign to other user and starts investigation
                    "source": Status.OPEN,
                    "transition": HitStatusTransition.ASSIGN_TO_OTHER,
                    "dest": Status.OPEN,
                    "actions": [assign_hit],
                }
            ),
            Transition(
                {
                    # assign to other user and starts investigation
                    "source": Status.OPEN,
                    "transition": HitStatusTransition.START,
                    "dest": Status.IN_PROGRESS,
                    "actions": [check_ownership],
                }
            ),
            Transition(
                {
                    # provides vote
                    "source": Status.OPEN,
                    "transition": HitStatusTransition.VOTE,
                    "dest": Status.OPEN,
                    "actions": [vote_hit],
                }
            ),
            Transition(
                {
                    # assign to another user
                    "source": Status.IN_PROGRESS,
                    "transition": HitStatusTransition.ASSIGN_TO_OTHER,
                    "dest": Status.IN_PROGRESS,
                    "actions": [assign_hit],
                }
            ),
            Transition(
                {
                    # removes assignment
                    "source": Status.IN_PROGRESS,
                    "transition": HitStatusTransition.RELEASE,
                    "dest": Status.OPEN,
                    "actions": [unassign_hit],
                }
            ),
            Transition(
                {
                    # user completes investigation
                    "source": [Status.OPEN, Status.IN_PROGRESS],
                    "transition": HitStatusTransition.ASSESS,
                    "dest": Status.RESOLVED,
                    "actions": [assess_hit, assign_hit],
                }
            ),
            Transition(
                {
                    # vote on in_progress hit
                    "source": Status.IN_PROGRESS,
                    "transition": HitStatusTransition.VOTE,
                    "dest": Status.IN_PROGRESS,
                    "actions": [vote_hit],
                }
            ),
            Transition(
                {
                    # removes assignment
                    "source": Status.OPEN,
                    "transition": HitStatusTransition.RELEASE,
                    "dest": Status.OPEN,
                    "actions": [unassign_hit],
                }
            ),
            Transition(
                {
                    # user pauses investigation
                    "source": Status.IN_PROGRESS,
                    "transition": HitStatusTransition.PAUSE,
                    "dest": Status.ON_HOLD,
                    "actions": [check_ownership],
                }
            ),
            Transition(
                {
                    # user restarts investigation after pausing it
                    "source": Status.ON_HOLD,
                    "transition": HitStatusTransition.RESUME,
                    "dest": Status.IN_PROGRESS,
                    "actions": [check_ownership],
                }
            ),
            Transition(
                {
                    # current user starts investigation
                    "transition": HitStatusTransition.ASSIGN_TO_ME,
                    "source": Status.IN_PROGRESS,
                    "dest": Status.IN_PROGRESS,
                    "actions": [assign_hit],
                }
            ),
            Transition(
                {
                    # user restarts investigation after pausing it
                    "source": Status.ON_HOLD,
                    "transition": HitStatusTransition.ASSIGN_TO_OTHER,
                    "dest": Status.IN_PROGRESS,
                    "actions": [assign_hit],
                }
            ),
            Transition(
                {
                    # user restarts investigation after pausing it
                    "transition": HitStatusTransition.VOTE,
                    "source": Status.ON_HOLD,
                    "dest": Status.ON_HOLD,
                    "actions": [vote_hit],
                }
            ),
            Transition(
                {
                    # Reopen a task after resolving it
                    "source": Status.RESOLVED,
                    "transition": HitStatusTransition.RE_EVALUATE,
                    "dest": Status.IN_PROGRESS,
                    "actions": [assess_hit, assign_hit],
                }
            ),
            Transition(
                {
                    # Reopen a task after resolving it
                    "source": Status.RESOLVED,
                    "transition": HitStatusTransition.VOTE,
                    "dest": Status.RESOLVED,
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


@tracer.start_as_current_span(f"{__name__}._modifies_prop")
def _modifies_prop(prop: str, operations: list[OdmUpdateOperation]) -> bool:
    """Check if the list of provided operations modifies the specified property

    Args:
        prop (str): The property to check for changes
        operations (list[OdmUpdateOperation]): The operations that will be performed

    Returns:
        bool: Is the property modified by these operations?
    """
    return any(op for op in operations if op.key == prop)


def convert_hit(  # noqa: C901
    data: dict[str, Any], unique: bool, ignore_extra_values: bool = False
) -> tuple[Hit, list[str]]:
    """Validate and convert a dictionary to a Hit ODM object.

    This function performs comprehensive validation on input data to ensure it can be
    safely converted to a Hit object. It handles hash generation, ID assignment,
    data normalization, and validation warnings. The function also checks for
    deprecated fields and enforces naming conventions for analytics and detections.

    Args:
        data: Dictionary containing hit data to validate and convert
        unique: Whether to enforce uniqueness by checking if the hit ID already exists
        ignore_extra_values: Whether to ignore invalid extra fields (True) or raise an exception (False)
        index: The index to validate against

    Returns:
        Tuple containing:
        - Hit: The validated and converted ODM object
        - list[str]: List of validation warnings (unused fields, deprecated fields, naming issues)

    Raises:
        HowlerValueError: If invalid parameters are provided or naming conventions are violated
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

    if "howler.data" in data:
        parsed_data = []
        for entry in data["howler.data"]:
            if isinstance(entry, str):
                parsed_data.append(entry)
            else:
                parsed_data.append(json.dumps(entry))

        data["howler.data"] = parsed_data

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

    if odm.howler.assessment:
        target_escalation = AssessmentEscalationMap[odm.howler.assessment]
        if odm.howler.escalation != target_escalation:
            warnings.append(
                f"Hits with assessment {odm.howler.assessment} must also have escalation set to {target_escalation}."
            )
            odm.howler.escalation = str(target_escalation)

    if odm.howler.escalation in [Escalation.MISS, Escalation.EVIDENCE] and odm.howler.status != Status.RESOLVED:
        warnings.append("Hits with escalation miss or evidence must also have their status set to resolved.")
        odm.howler.status = Status.RESOLVED.value

    if odm.event:
        odm.event.id = odm.howler.id
        if not odm.event.created:
            odm.event.created = "NOW"
    else:
        odm.event = ECSEvent({"created": "NOW", "id": odm.howler.id})

    if unique and exists(odm.howler.id):
        raise ResourceExists("Resource with id %s already exists" % odm.howler.id)

    return odm, warnings


@tracer.start_as_current_span(f"{__name__}.exists")
def exists(id: str) -> bool:
    """Check if a hit exists in the datastore.

    Args:
        id: The unique identifier of the hit to check

    Returns:
        bool: True if the hit exists, otherwise False
    """
    return datastore().hit.exists(id)


@overload
def get_hit(id: str, as_odm: Literal[True], version: Literal[True]) -> tuple[Hit, str]: ...


@overload
def get_hit(id: str, as_odm: Literal[True], version: Literal[False]) -> Hit: ...


@overload
def get_hit(id: str, as_odm: Literal[True]) -> Hit: ...


@overload
def get_hit(id: str) -> Hit: ...


@overload
def get_hit(id: str, as_odm: Literal[False], version: Literal[True]) -> tuple[dict[str, Any], str]: ...


@overload
def get_hit(id: str, as_odm: Literal[False], version: Literal[False]) -> dict[str, Any]: ...


@overload
def get_hit(id: str, as_odm: Literal[False]) -> dict[str, Any]: ...


@tracer.start_as_current_span(f"{__name__}.get_hit")
def get_hit(id: str, as_odm=False, version=False):
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


@tracer.start_as_current_span(f"{__name__}.create_hit")
def create_hit(
    id: str,
    hit: Hit,
    user: Optional[str] = None,
    skip_exists: bool = False,
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> bool:
    """Create a new hit in the database.

    This function saves a hit to the datastore, optionally adding a creation log entry
    and updating metrics. It will prevent overwriting existing hits unless explicitly allowed.

    Args:
        id: The unique identifier for the hit
        hit: The Hit ODM object to save
        user: Optional username to record in the creation log
        skip_exists: Whether to check for an existing record
        refresh: Optional datastore refresh strategy ("true", "false", "wait_for")

    Returns:
        bool: True if the hit was successfully created

    Raises:
        ResourceExists: If a hit with the same ID already exists and overwrite=False
    """
    if not skip_exists and exists(id):
        raise ResourceExists(f"Hit {id} already exists in datastore")

    if user:
        hit.howler.log = [Log({"timestamp": "NOW", "explanation": "Created hit", "user": user})]

    CREATED_HITS.labels(hit.howler.analytic).inc()
    return datastore().hit.save(id, hit, refresh=refresh)


@tracer.start_as_current_span(f"{__name__}.create_hits")
def create_hits(
    hits: list[Hit], user: Optional[str] = None, overwrite: bool = False, refresh: str | None = None
) -> BulkResult:
    """Bulk create multiple hits in the database.

    Similar to create_hit for batch.
    Will raise and abort the entire batch if any hit already exists and overwrite=False.
    """
    storage = datastore()
    bulk_plan = storage.hit.get_bulk_plan()

    for hit in hits:
        if not overwrite and storage.hit.exists(hit.howler.id):
            raise ResourceExists("Hit %s already exists in datastore" % hit.howler.id)

        if user:
            hit.howler.log = [Log({"timestamp": "NOW", "explanation": "Created hit", "user": user})]

        CREATED_HITS.labels(hit.howler.analytic).inc()
        if overwrite:
            bulk_plan.add_index_operation(hit.howler.id, hit)
        else:
            bulk_plan.add_insert_operation(hit.howler.id, hit)

    ingest_result = storage.hit.bulk(bulk_plan, refresh=refresh)

    failed_ids = {failure.get("id") for failure in ingest_result.failures}
    ids = [hit.howler.id for hit in hits if hit.howler.id not in failed_ids]
    if ids:
        correlation_service.enqueue_for_correlation(ids)

    return ingest_result


@tracer.start_as_current_span(f"{__name__}.update_hit")
def update_hit(
    hit_id: str,
    operations: list[OdmUpdateOperation],
    username: str | None = None,
    version: str | None = None,
    refresh: str | None = None,
):
    """Update one or more properties of a hit in the database.

    This function applies a list of update operations to modify hit properties.
    Note that hit status cannot be modified through this function - use transition_hit instead.

    Args:
        hit_id: The unique identifier of the hit to update
        operations: List of ODM update operations to apply
        username: Optional username to record in the update log
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

    hit = get_hit(hit_id, as_odm=True)
    if not hit:
        raise NotFoundException("Hit does not exist")

    return _update_hits([(hit, operations, version)], username, refresh=refresh)[0]


@tracer.start_as_current_span(f"{__name__}.overwrite_hits")
def overwrite_hits(hits: list[Hit], refresh: str | None = None) -> BulkResult:
    """Bulk save multiple hits to the datastore.

    Similar to save_hit for batch without versioning. Will overwrite existing hits with the same ID.
    """
    storage = datastore()
    bulk_plan = storage.hit.get_bulk_plan()

    for hit in hits:
        bulk_plan.add_index_operation(hit.howler.id, hit)

    return storage.hit.bulk(bulk_plan, refresh=refresh)


@typing.no_type_check
@tracer.start_as_current_span(f"{__name__}.save_hit")
def save_hit(hit: Hit, version: Optional[str] = None, refresh: str | None = None) -> tuple[Hit, str]:
    """Save a hit to the datastore and emit an event notification.

    This function persists a hit object to the database and emits an event
    to notify other systems of the change.

    Args:
        hit: The Hit ODM object to save
        version: Optional version string for optimistic locking
        refresh: Optional refresh parameter for the datastore

    Returns:
        Tuple of (hit_data_dict, version_string)
    """
    datastore().hit.save(hit.howler.id, hit, version=version, refresh=refresh)
    data, _version = datastore().hit.get(hit.howler.id, as_obj=False, version=True)
    comms_service.emit("hits", {"hit": data, "version": _version})

    return data, _version


@tracer.start_as_current_span(f"{__name__}._prepare_hit_update_operations")
def _prepare_hit_update_operations(
    hit: Hit,
    operations: list[OdmUpdateOperation],
    username: str | None = None,
    version: str | None = None,
) -> list[OdmUpdateOperation]:
    """Add worklog entries to a hit's update operations."""
    final_operations = []
    for operation in operations:
        if not operation:
            continue

        try:
            is_list = hit.flat_fields()[operation.key].multivalued
            try:
                previous_value = hit[operation.key]
            except (TypeError, KeyError):
                previous_value = None
        except KeyError:
            key = next(key for key in hit.flat_fields().keys() if key.startswith(operation.key))
            is_list = hit.flat_fields()[key].multivalued
            previous_value = "list"

        if is_list:
            operation_type = (
                HitOperationType.APPENDED
                if operation.operation
                in (
                    ESCollection.UPDATE_APPEND,
                    ESCollection.UPDATE_APPEND_IF_MISSING,
                )
                else HitOperationType.REMOVED
            )
        else:
            operation_type = HitOperationType.SET

        logger.debug("%s - %s - %s -> %s", hit.howler.id, operation.key, previous_value, operation.value)
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
                        "user": username if username else "Unknown",
                    },
                )
            )

    return final_operations


@tracer.start_as_current_span(f"{__name__}._update_hits")
def _update_hits(
    hit_updates: list[tuple[Hit, list[OdmUpdateOperation], str | None]],
    username: str | None = None,
    refresh: str | None = None,
) -> list[tuple[dict[str, Any] | None, str | None]]:
    """Apply prepared operations to one or more hits in a single bulk request."""
    collection = datastore().hit
    bulk_plan = collection.get_bulk_plan()

    for hit, operations, version in hit_updates:
        if not version and collection.ilm_config:
            _, version = collection.get_if_exists(hit.howler.id, as_obj=False, version=True)

        script = collection.create_scripts_from_operations(
            _prepare_hit_update_operations(hit, operations, username, version)
        )
        bulk_plan.add_scripted_update_operation(hit.howler.id, script, version=version)

    # Format and print the profiling data
    if not bulk_plan.empty and not (bulk_result := collection.bulk(bulk_plan, refresh=refresh)):
        conflicts = [failure for failure in bulk_result.failures if failure.get("status") == 409]
        if conflicts:
            raise VersionConflictException("Unable to update all hits due to a version conflict", failures=conflicts)

        raise HowlerRuntimeError("Unable to update all hits")

    updated_hits = [collection.get(hit.howler.id, as_obj=False, version=True) for hit, _, _ in hit_updates]
    for data, hit_version in updated_hits:
        if data and hit_version:
            comms_service.emit("hits", {"hit": data, "version": hit_version})

    return cast(list[tuple[dict[str, Any] | None, str | None]], updated_hits)


@tracer.start_as_current_span(f"{__name__}.get_transitions")
def get_transitions(status: Status) -> list[str]:
    """Get a list of the valid transitions beginning from the specified status

    Args:
        status (HitStatus): The status we want to transition from

    Returns:
        list[str]: A list of valid transitions to execute
    """
    return get_hit_workflow().get_transitions(status)


def transition_hits(
    hits: Hit | list[Hit] | None,
    transition: HitStatusTransition,
    user: User,
    version: Optional[str] = None,
    refresh: str | None = None,
    **kwargs,
) -> list[tuple[dict[str, Any] | None, str | None]]:
    """Transition one or more hits in a single bulk transaction.

    For certain transitions (PROMOTE, DEMOTE, ASSESS, RE_EVALUATE), it also executes bulk actions and emits events.

    Args:
        hits: A hit ID, list of hit IDs, hit dictionary, or list of hit dictionaries to transition
        transition: The transition to execute (e.g., ASSIGN_TO_ME, ASSESS, PROMOTE)
        user: The user running the transition
        version: Optional version to validate against when transitioning a single hit ID
        **kwargs: Additional arguments including an assessment value

    Returns:
        A tuple containing the updated hit and the optimistic-lock version token after the transition.

    Raises:
        NotFoundException: If one or more hits do not exist
    """
    if hits is None:
        raise NotFoundException("Hit does not exist")

    if not isinstance(hits, list):
        hits = [hits]

    workflow: Workflow = get_hit_workflow()
    hit_updates: list[tuple[Hit, list[OdmUpdateOperation], str | None]] = []
    transitioned_ids: list[str] = []

    for hit in hits:
        hit_status = hit["howler"]["status"]
        hit_id = hit["howler"]["id"]

        logger.debug("Transitioning (%s)", hit)

        updates = workflow.transition(hit_status, transition, user=user, hit=hit, **kwargs)
        hit_updates.append((hit, updates, version))
        transitioned_ids.append(hit_id)

    updated_hits = _update_hits(hit_updates, user.uname, refresh=refresh)

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
            new_escalation = AssessmentEscalationMap[kwargs["assessment"]]  # pyright: ignore[reportInvalidTypeArguments]
            trigger = "promote" if new_escalation == Escalation.EVIDENCE else "demote"
        elif transition == HitStatusTransition.RE_EVALUATE:
            # Re-evaluation always promotes the hit
            trigger = "promote"
        else:
            # For direct PROMOTE/DEMOTE transitions, use the transition name
            trigger = cast(Union[Literal["promote"], Literal["demote"]], transition)

        datastore().hit.commit()
        # Enqueue action execution for all hits in a single request.
        action_service.enqueue_action_execution(transitioned_ids, trigger=trigger, user=user)

    return updated_hits


DELETED_HITS = Counter(f"{APP_NAME.replace('-', '_')}_deleted_hits_total", "The number of deleted hits")


@tracer.start_as_current_span(f"{__name__}.delete_hits")
def delete_hits(hit_ids: set[str], refresh: str | None = None) -> bool:
    """Delete a set of hits from the database

    Args:
        hit_ids (set[str]): The IDs of the hits to delete
        refresh (str | None): Whether to refresh the datastore before returning.

    Returns:
        bool: Was the deletion successful?
    """
    ds = datastore()

    success = True
    operations: list[OdmUpdateOperation] = []

    for hit_id in hit_ids:
        success = success and ds.hit.delete(hit_id)
        operations.append(odm_helper.list_remove("howler.related", hit_id, silent=True))

    ds.hit.update_by_query(f"howler.related:({' OR '.join(hit_ids)})", operations, refresh=refresh)

    return success


@overload
def search(
    query: str,
    as_obj: Literal[True],
    offset: int = 0,
    rows: Optional[int] = None,
    sort: Optional[Any] = None,
    fl: str | None = None,
    timeout: int | None = None,
    deep_paging_id: str | None = None,
    track_total_hits: bool = False,
) -> SearchResult[Hit]: ...


@overload
def search(
    query: str,
    as_obj: Literal[False],
    offset: int = 0,
    rows: Optional[int] = None,
    sort: Optional[Any] = None,
    fl: str | None = None,
    timeout: int | None = None,
    deep_paging_id: str | None = None,
    track_total_hits: bool = False,
) -> SearchResult[dict[str, Any]]: ...


@tracer.start_as_current_span(f"{__name__}.search")
def search(
    query,
    as_obj=True,
    offset=0,
    rows=None,
    sort=None,
    fl=None,
    timeout=None,
    deep_paging_id=None,
    track_total_hits=False,
):
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


TYPE_PRIORITY = {"personal": 2, "readonly": 1, "global": 0, None: 0}


def __compare_metadata(object_a: dict[str, Any], object_b: dict[str, Any]) -> int:
    # Sort priority:
    # 1. personal > readonly > global
    # 2. detection > !detection

    if object_a.get("type", None) != object_b.get("type", None):
        return TYPE_PRIORITY[object_b.get("type", None)] - TYPE_PRIORITY[object_a.get("type", None)]

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


def augment_metadata(data: list[dict[str, Any]] | dict[str, Any] | None, metadata: list[str], user: User):  # noqa: C901
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
    if isinstance(data, list):
        hits = data
    elif data is not None:
        hits = [data]
    else:
        hits = []

    hits = [hit for hit in hits if hit.get("__index", "hit") == "hit"]

    if len(hits) < 1:
        return

    logger.debug("Augmenting %s hits with %s", len(hits), ",".join(metadata))

    if "template" in metadata:
        template_candidates = template_service.get_matching_templates(hits, as_odm=False, uname=user.uname)

        logger.debug("\tRetrieved %s matching templates", len(template_candidates))

        for hit in hits:
            hit["__template"] = __match_metadata(cast(list[dict[str, Any]], template_candidates), hit)

    if "overview" in metadata:
        overview_candidates = overview_service.get_matching_overviews(hits, as_odm=False)

        logger.debug("\tRetrieved %s matching overviews", len(overview_candidates))

        for hit in hits:
            hit["__overview"] = __match_metadata(cast(list[dict[str, Any]], overview_candidates), hit)

    if "analytic" in metadata:
        matched_analytics = analytic_service.get_matching_analytics(hits)
        logger.debug("\tRetrieved %s matching analytics", len(matched_analytics))

        for hit in hits:
            matched_analytic = next(
                (
                    analytic
                    for analytic in matched_analytics
                    if analytic.name.lower() == hit["howler"]["analytic"].lower()
                ),
                None,
            )

            hit["__analytic"] = matched_analytic.as_primitives() if matched_analytic else None

    if "dossiers" in metadata:
        dossiers: list[dict[str, Any]] = datastore().dossier.search(
            f"type:global OR owner:{user.uname}",
            as_obj=False,
            # TODO: Eventually implement caching here
            rows=1000,
        )["items"]

        for hit in hits:
            hit["__dossiers"] = dossier_service.get_matching_dossiers(hit, dossiers, username=user.uname)
