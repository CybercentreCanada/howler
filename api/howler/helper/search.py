from typing import Any, Callable, Optional, Union

from howler.common.loader import datastore
from howler.datastore.collection import ESCollection
from howler.odm.models.user import User

# List of indices where queries are protected with classification access control
ACCESS_CONTROLLED_INDICES: dict[str, ESCollection] = {}

ADMIN_INDEX_MAP: dict[str, Callable[[], ESCollection]] = {}

ADMIN_INDEX_ORDER_MAP: dict[str, str] = {}

ds = datastore()

INDEX_MAP: dict[str, Callable[[], ESCollection]] = {
    "action": lambda: ds.action,
    "analytic": lambda: ds.analytic,
    "dossier": lambda: ds.dossier,
    "hit": lambda: ds.hit,
    "overview": lambda: ds.overview,
    "template": lambda: ds.template,
    "user": lambda: ds.user,
    "view": lambda: ds.view,
}

INDEX_ORDER_MAP: dict[str, str] = {
    "action": "name asc",
    "analytic": "name asc",
    "dossier": "title asc",
    "hit": "event.created desc",
    "overview": "overview_id asc",
    "template": "template_id asc",
    "user": "id asc",
    "view": "title asc",
}


def get_collection(index: str, user: Union[User, dict[str, Any]]) -> Optional[Callable[[], ESCollection]]:
    """Get the ESCollection for a given index

    Args:
        index (str): The name of the ESCollection to retrieve
        user (User): The user retrieving the collection

    Returns:
        ESCollection: The corresponding ESCollection
    """
    return INDEX_MAP.get(index, ADMIN_INDEX_MAP.get(index, None) if "admin" in user["type"] else None)


def get_default_sort(index: str, user: Union[User, dict[str, Any]]) -> Optional[str]:
    """Retrieve the default sorting for a given index

    Args:
        index (str): The index to get the default sort of
        user (Union[User, dict[str, Any]]): The user retrieving the collection

    Returns:
        str: The default sort for the index
    """
    return INDEX_ORDER_MAP.get(
        index,
        ADMIN_INDEX_ORDER_MAP.get(index, None) if "admin" in user["type"] else None,
    )


def has_access_control(index: str) -> bool:
    """Check if the given index has access control enabled

    Args:
        index (str): The index to check

    Returns:
        bool: Does the index have access control
    """
    return index in ACCESS_CONTROLLED_INDICES


def list_all_fields(is_admin: bool = False) -> dict[str, dict]:
    """Generate a list of all fields in each index

    Args:
        is_admin (bool, optional): Should administrator only indexes be included? Defaults to False.

    Returns:
        dict[str, dict]: A list of all fields in each index
    """
    fields_map = {k: INDEX_MAP[k]().fields(skip_mapping_children=True) for k in INDEX_MAP.keys()}

    if is_admin:
        fields_map.update({k: ADMIN_INDEX_MAP[k]().fields(skip_mapping_children=True) for k in ADMIN_INDEX_MAP.keys()})

    return fields_map
