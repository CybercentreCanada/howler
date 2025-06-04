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
from howler.odm.base import BANNED_FIELDS
from howler.odm.models.ecs.event import Event
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import HitOperationType, HitStatus, HitStatusTransition, Log
from howler.odm.models.user import User
from howler.services import action_service
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
    """Validate if the provided dict is a valid hit.

    Args:
        data (dict[str, Any]): The dict to validate and convert to an ODM
        unique (bool): Whether to check if the hit ID already exists in the database
        ignore_extra_values (bool, optional): Whether to throw an exception for any invalid extra values, or simply
            emit a warning. Defaults to False.

    Raises:
        HowlerValueError: Raised if a bundle is included when creating the hit.
        ResourceExists: unique is True, and there already exists a hit with this hit ID in the database.

    Returns:
        Hit: The validated and converted ODM.
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

    try:
        odm = Hit(data, ignore_extra_values=ignore_extra_values)
    except TypeError as e:
        raise HowlerTypeError(str(e), cause=e) from e

    # Check for deprecated field and unused fields
    odm_flatten = odm.flat_fields(show_compound=True)
    unused_keys = extra_keys(data, set(odm_flatten.keys()) - BANNED_FIELDS)

    if unused_keys and not ignore_extra_values:
        raise HowlerValueError(f"Hit was created with invalid parameters: {', '.join(unused_keys)}")
    deprecated_keys = set(key for key in odm_flatten.keys() & data.keys() if odm_flatten[key].deprecated)

    warnings = [f"{key} is not currently used by howler." for key in unused_keys]
    warnings.extend(
        [f"{key} is deprecated." for key in deprecated_keys],
    )

    if re.search(r"^([A-Za-z ])+$", odm.howler.analytic) is None:
        warnings.append(
            (
                f"The value {odm.howler.analytic} does not match best practices for Howler analytic names. "
                "See howler's documentation for more information."
            )
        )

    if odm.howler.detection and re.search(r"^([A-Za-z ])+$", odm.howler.detection) is None:
        warnings.append(
            (
                f"The value {odm.howler.detection} does not match best practices for Howler detection names. "
                "See howler's documentation for more information."
            )
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
    "Check if a hit exists"
    return datastore().hit.exists(id)


def get_hit(
    id: str,
    as_odm: bool = False,
    version: bool = False,
):
    """Return hit object as either an ODM or Dict"""
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
    """Create a hit in the database"""
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
    """Update one or more properties of a hit in the database."""
    # Status of a hit should only be updated through the transition function
    if _modifies_prop("status", operations):
        raise HowlerValueError(
            "Status of a Hit cannot be modified like other properties. Please use a transition to do so."
        )

    return _update_hit(hit_id, operations, user, version=version)


@typing.no_type_check
def save_hit(hit: Hit, version: Optional[str] = None) -> tuple[Hit, str]:
    "Save a hit to the datastore"
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
    """Add the worklog operations to the operation list"""
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
    "Get a list of all the children for a given hit"
    child_hits = [get_hit(hit_id) for hit_id in hit["howler"].get("hits", [])]

    for entry in child_hits:
        if not entry:
            continue

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
    """Transition a hit from one status to another while updating related properties

    Args:
        id (str): The id of the hit to transition
        transition (HitStatusTransition): The transition to execute
        user (dict[str, Any]): The user running the transition
        version (str): A version to validate against. The transition will not run if the version doesn't match.
    """
    hit: Hit = get_hit(id, as_odm=False) if not kwargs.get("hit", None) else kwargs.pop("hit")

    workflow: Workflow = get_hit_workflow()

    if not hit:
        raise NotFoundException("Hit does not exist")

    child_hits = get_all_children(hit)

    log.debug(
        "Transitioning (%s)",
        ", ".join([h["howler"]["id"] for h in ([hit] + [ch for ch in child_hits if ch])]),
    )

    for _hit in [hit] + [ch for ch in child_hits if ch]:
        hit_status = _hit["howler"]["status"]
        hit_id = _hit["howler"]["id"]

        if hit_status != hit["howler"]["status"]:
            log.debug("Skipping %s", hit_id)
            continue

        updates = workflow.transition(hit_status, transition, user=user, hit=_hit, **kwargs)

        if updates:
            _update_hit(
                hit_id,
                updates,
                user["uname"],
                version=(version if (hit_id == hit["howler"]["id"] and version) else None),
            )

    if transition in [
        HitStatusTransition.PROMOTE,
        HitStatusTransition.DEMOTE,
        HitStatusTransition.ASSESS,
        HitStatusTransition.RE_EVALUATE,
    ]:
        trigger: Union[Literal["promote"], Literal["demote"]]

        if transition == HitStatusTransition.ASSESS:
            new_assessment = AssessmentEscalationMap[kwargs["assessment"]]

            if new_assessment == Escalation.EVIDENCE:
                trigger = "promote"
            else:
                trigger = "demote"
        elif transition == HitStatusTransition.RE_EVALUATE:
            trigger = "promote"
        else:
            trigger = cast(Union[Literal["promote"], Literal["demote"]], transition)

        datastore().hit.commit()
        action_service.bulk_execute_on_query(
            f"howler.id:({' OR '.join(h['howler']['id'] for h in ([hit] + child_hits))})",
            trigger=trigger,
            user=user,
        )

        for _hit in [hit] + child_hits:
            data, _version = datastore().hit.get(_hit["howler"]["id"], as_obj=False, version=True)
            event_service.emit("hits", {"hit": data, "version": _version})


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
    """Search for a list of hits

    Args:
        query (str): The query to execute
        offset (int, optional): The offset (how many entries to skip). Defaults to 0.
        rows (int, optional): How many rows to return. Defaults to None.
        sort (any, optional): How to sorty the results. Defaults to None.
        fl (any, optional): Defaults to None.
        timeout (any, optional): Defaults to None.
        deep_paging_id (any, optional): Defaults to None.
        track_total_hits (any, optional): Defaults to None.
        as_obj (bool, optional): Defaults to True.

    Returns:
        HitSearchResult: A list of matching hits
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
