import json
from hashlib import sha256
from typing import Any, Optional

from prometheus_client import Counter

from howler.common.exceptions import HowlerTypeError, HowlerValueError, ResourceExists
from howler.common.loader import APP_NAME, datastore
from howler.common.logging import get_logger
from howler.odm.models.ecs.event import Event
from howler.odm.models.observable import Log as ObservableLog
from howler.odm.models.observable import Observable
from howler.services.hit_service import exists
from howler.utils.dict_utils import extra_keys, flatten
from howler.utils.uid import get_random_id

logger = get_logger(__file__)


def convert_observable(
    data: dict[str, Any], unique: bool, ignore_extra_values: bool = False
) -> tuple[Observable, list[str]]:
    """Validate and convert a dictionary to an Observable ODM object.

    This function performs validation on input data to ensure it can be safely
    converted to an Observable object. It handles hash generation, ID assignment,
    data normalization, and validation warnings.

    Args:
        data: Dictionary containing observable data to validate and convert
        unique: Whether to enforce uniqueness by checking if the observable ID already exists
        ignore_extra_values: Whether to ignore invalid extra fields (True) or raise an exception (False)

    Returns:
        Tuple containing:
        - Observable: The validated and converted ODM object
        - list[str]: List of validation warnings (unused fields, deprecated fields)

    Raises:
        HowlerValueError: If invalid parameters are provided
        HowlerTypeError: If the data cannot be converted to an Observable ODM object
        ResourceExists: If unique=True and an observable with the generated ID already exists
    """
    data = flatten(data, odm=Observable)

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
        odm = Observable(data, ignore_extra_values=ignore_extra_values)
    except TypeError as e:
        raise HowlerTypeError(str(e), cause=e) from e

    odm_flatten = odm.flat_fields(show_compound=True)
    unused_keys = extra_keys(Observable, data)

    if unused_keys and not ignore_extra_values:
        raise HowlerValueError(f"Observable was created with invalid parameters: {', '.join(unused_keys)}")
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
        odm.event = Event({"created": "NOW", "id": odm.howler.id})

    if unique and exists(odm.howler.id, indexes=["observable"]):
        raise ResourceExists("Resource with id %s already exists" % odm.howler.id)

    return odm, warnings


CREATED_OBSERVABLES = Counter(
    f"{APP_NAME.replace('-', '_')}_created_observables_total",
    "The number of created observables",
)


def create_observable(id: str, observable: Observable, user: Optional[str] = None, skip_exists: bool = False) -> bool:
    """Create a new observable in the database.

    This function saves an observable to the datastore, optionally adding a creation
    log entry and updating metrics.

    Args:
        id: The unique identifier for the observable
        observable: The Observable ODM object to save
        user: Optional username to record in the creation log
        skip_exists: Whether to skip the existence check

    Returns:
        bool: True if the observable was successfully created

    Raises:
        ResourceExists: If an observable with the same ID already exists and skip_exists=False
    """
    if not skip_exists and exists(id, indexes=["observable"]):
        raise ResourceExists(f"Observable {id} already exists in datastore")

    if user:
        observable.howler.log = [ObservableLog({"timestamp": "NOW", "explanation": "Created observable", "user": user})]

    CREATED_OBSERVABLES.inc()
    return datastore().observable.save(id, observable)
