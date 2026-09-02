import json
from hashlib import sha256
from typing import Any, Literal, Optional, cast, overload

from opentelemetry import trace
from prometheus_client import Counter

from howler.common.exceptions import HowlerTypeError, HowlerValueError, ResourceExists
from howler.common.loader import APP_NAME, datastore
from howler.common.logging import get_logger
from howler.datastore.collection import CREATE_TOKEN
from howler.odm.models.ecs.event import ECSEvent
from howler.odm.models.event import Event
from howler.odm.models.event import Log as EventLog
from howler.odm.models.user import User
from howler.security.utils import is_classification_accessible
from howler.utils.dict_utils import extra_keys, flatten
from howler.utils.uid import get_random_id

logger = get_logger(__file__)
tracer = trace.get_tracer(__name__)


@tracer.start_as_current_span(f"{__name__}.exists")
def exists(id: str) -> bool:
    """Check if an event exists in the datastore.

    Args:
        id: The unique identifier of the event to check

    Returns:
        bool: True if the event exists, otherwise False
    """
    return datastore().event.exists(id)


@overload
def get_event(
    id: str, as_odm: Literal[True], version: Literal[True], user: User | None = None
) -> tuple[Event, str]: ...


@overload
def get_event(id: str, as_odm: Literal[True], version: Literal[False]) -> Event: ...


@overload
def get_event(id: str, as_odm: Literal[True]) -> Event: ...


@overload
def get_event(id: str) -> Event: ...


@overload
def get_event(id: str, as_odm: Literal[False], version: Literal[True]) -> tuple[dict[str, Any], str]: ...


@overload
def get_event(id: str, as_odm: Literal[False], version: Literal[False]) -> dict[str, Any]: ...


@overload
def get_event(id: str, as_odm: Literal[False]) -> dict[str, Any]: ...


@tracer.start_as_current_span(f"{__name__}.get_event")
def get_event(id: str, as_odm=False, version=False, user: User | None = None):
    """Retrieve an event from the datastore.

    Args:
        id: The unique identifier of the event to retrieve
        as_odm: Whether to return the event as an ODM object (True) or dictionary (False)
        version: Whether to include version information in the response

    Returns:
        Event object (if as_odm=True) or dictionary representation of the event.
        Returns None if the event doesn't exist.
    """
    hit_version: str | None = None
    obj: Event | dict[str, Any] | None = None

    hit = datastore().hit.get_if_exists(key=id, as_obj=as_odm, version=version)
    if user is None:
        return hit

    if version:
        obj, hit_version = cast(tuple[dict[str, Any] | Event, str], hit)
    else:
        obj = cast(Event | dict[str, Any], hit)

    classification: str | None = None
    if as_odm and obj:
        classification = cast(Event, obj).classification
    elif obj:
        classification = cast(dict[str, str], obj).get("classification")

    if obj is not None and not is_classification_accessible(user, classification):
        obj = None
        hit_version = CREATE_TOKEN

    if version:
        return obj, hit_version

    return obj


def convert_event(data: dict[str, Any], unique: bool, ignore_extra_values: bool = False) -> tuple[Event, list[str]]:
    """Validate and convert a dictionary to an Event ODM object.

    This function performs validation on input data to ensure it can be safely
    converted to an Event object. It handles hash generation, ID assignment,
    data normalization, and validation warnings.

    Args:
        data: Dictionary containing event data to validate and convert
        unique: Whether to enforce uniqueness by checking if the event ID already exists
        ignore_extra_values: Whether to ignore invalid extra fields (True) or raise an exception (False)

    Returns:
        Tuple containing:
        - Event: The validated and converted ODM object
        - list[str]: List of validation warnings (unused fields, deprecated fields)

    Raises:
        HowlerValueError: If invalid parameters are provided
        HowlerTypeError: If the data cannot be converted to an Event ODM object
        ResourceExists: If unique=True and an event with the generated ID already exists
    """
    data = flatten(data, odm=Event)

    if "howler.hash" not in data:
        hash_contents = {
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

    try:
        odm = Event(data, ignore_extra_values=ignore_extra_values)
    except TypeError as e:
        raise HowlerTypeError(str(e), cause=e) from e

    odm_flatten = odm.flat_fields(show_compound=True)
    unused_keys = extra_keys(Event, data)

    if unused_keys and not ignore_extra_values:
        raise HowlerValueError(f"Event was created with invalid parameters: {', '.join(unused_keys)}")
    deprecated_keys = set(key for key in odm_flatten.keys() & data.keys() if odm_flatten[key].deprecated)

    warnings = [f"{key} is not currently used by howler." for key in unused_keys]
    warnings.extend(
        [f"{key} is deprecated." for key in deprecated_keys],
    )

    if odm.event:
        odm.event.id = odm.howler.id
        if not odm.event.created:
            odm.event.created = "NOW"
    else:
        odm.event = ECSEvent({"created": "NOW", "id": odm.howler.id})

    if unique and exists(odm.howler.id):
        raise ResourceExists("Resource with id %s already exists" % odm.howler.id)

    return odm, warnings


CREATED_EVENTS = Counter(
    f"{APP_NAME.replace('-', '_')}_created_events_total",
    "The number of created events",
)


def create_event(
    id: str,
    event: Event,
    user: Optional[str] = None,
    skip_exists: bool = False,
    refresh: Literal["true", "false", "wait_for"] | None = None,
    **kwargs: Any,
) -> bool:
    """Create a new event in the database.

    This function saves an event to the datastore, optionally adding a creation
    log entry and updating metrics.

    Args:
        id: The unique identifier for the event
        event: The Event ODM object to save
        user: Optional username to record in the creation log
        skip_exists: Whether to skip the existence check

    Returns:
        bool: True if the event was successfully created

    Raises:
        ResourceExists: If an event with the same ID already exists and skip_exists=False
    """
    if not skip_exists and exists(id):
        raise ResourceExists(f"Event {id} already exists in datastore")

    if user:
        event.howler.log = [EventLog({"timestamp": "NOW", "explanation": "Created event", "user": user})]

    CREATED_EVENTS.inc()
    return datastore().event.save(id, event, refresh=refresh)


@tracer.start_as_current_span(f"{__name__}.create_events")
def create_events(
    events: list[Event], user: Optional[str] = None, overwrite: bool = False, refresh: str | None = None
) -> bool:
    """Bulk create multiple events in the database.

    Similar to create_event for batch.
    Will raise and abort the entire batch if any event already exists and overwrite=False.
    """
    storage = datastore()
    bulk_plan = storage.event.get_bulk_plan()

    for event in events:
        if not overwrite and storage.event.exists(event.howler.id):
            raise ResourceExists("Event %s already exists in datastore" % event.howler.id)

        if user:
            event.howler.log = [EventLog({"timestamp": "NOW", "explanation": "Created event", "user": user})]

        CREATED_EVENTS.inc()
        if overwrite:
            bulk_plan.add_index_operation(event.howler.id, event)
        else:
            bulk_plan.add_insert_operation(event.howler.id, event)

    return storage.event.bulk(bulk_plan, refresh=refresh)
