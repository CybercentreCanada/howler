import sys
from typing import TYPE_CHECKING, Any, Optional, Union

from howler_client.common.utils import api_path
from howler_client.logger import get_logger
from howler_client.module.hit import Hit

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from howler_client import Connection

logger = get_logger("bundle")


class Bundle(object):
    """Methods related to hit bundles"""

    def __init__(self: Self, connection: "Connection", hit: Hit):
        self._connection: Connection = connection
        self._hit: Hit = hit

    def __call__(self: Self, hit_id: str) -> dict[str, Any]:
        """Return the bundle for a given ID.

        Args:
            hit_id (str): ID of the bundle

        Raises:
            ClientError: The hit does not exist
            AttributeError: The hit is not a bundle

        Returns:
            Hit: The bundle in question
        """
        result = self._hit(hit_id)

        if result["howler"]["is_bundle"]:
            return result
        else:
            raise AttributeError("This hit is not a bundle! Use client.hit(...) instead.")

    def create_from_map(
        self: Self,
        tool_name: str,
        bundle_hit: dict[str, Any],
        map: dict[str, list[str]],
        documents: list[dict[str, Any]],
        ignore_extra_values: bool = False,
    ) -> dict[str, Union[str, list[str], None]]:
        """Create a bundle using a format similar to the hit.create_from_map function

        Args:
            tool_name (str): Name of the tool the hits will be created for.
            bundle_hit (Hit): The bundle hit
            map (dict[str, list[str]]): Dictionary where the keys are the flattened path of the tool's raw document and
                    the values are a list of flattened path for Howler's fields where the data will be copied into.
            documents (list[Hit]): A list of hits to create as children of the bundle hit provided
            ignore_extra_values (bool, optional): Ignore invalid values and return a warning, or throw an error.
                    Defaults to False.

        Returns:
            list[dict[str, Optional[str]]]: The list of IDs of the created hits
        """
        map = {**map, "bundle": ["howler.is_bundle"]}
        bundle_hit = {**bundle_hit, "bundle": True}
        hit = [bundle_hit] + documents

        return self._hit.create_from_map(tool_name, map, hit, ignore_extra_values=ignore_extra_values)

    def create(
        self: Self,
        bundle_hit: dict[str, Any],
        data: Optional[Union[dict[str, Any], list[dict[str, Any]]]] = [],
        ignore_extra_values: bool = False,
    ) -> dict[str, Any]:
        """Create a bundle using a format similar to the hit.create function

        Args:
            bundle_hit (dict[str, Any]): The bundle hit to create
            data (Union[dict[str, Any], list[dict[str, Any]]], optional): A Hit or list of Hits to create as
                    children of the bundle hit
            ignore_extra_values (bool, optional): Ignore invalid values and return a warning, or throw an error.
                    Defaults to False.

        Returns:
            Hit: The created bundle hit
        """
        if not data:
            data = []

        if not isinstance(data, list):
            data = [data]

        if len(data) > 0:
            result = self._hit.create(data, ignore_extra_values=ignore_extra_values)

            if not result or len(result["invalid"]) > 0:
                return result

            hit_ids = [h["howler"]["id"] for h in result["valid"]]
        else:
            hit_ids = []

        return self._connection.post(api_path("hit/bundle"), json={"bundle": bundle_hit, "hits": hit_ids})

    def add(self: Self, bundle_id: str, hit_ids: Union[str, list[str]]):
        """Add a list of hits to a bundle by their IDs

        Args:
            bundle_id (str): The ID of the bundle we want to add the hits to
            hit_ids (Union[str, list[str]]): The list of hit IDs to add to the bundle
        """
        if not isinstance(hit_ids, list):
            hit_ids = [hit_ids]

        return self._connection.put(api_path("hit/bundle", bundle_id), json=hit_ids)

    def remove(self: Self, bundle_id: str, hit_ids: Union[str, list[str]]):
        """Remove a list of hits from a bundle by their IDs

        Args:
            bundle_id (str): The bundle ID from which to remove the hits
            hit_ids (Union[str, list[str]]): A list of hit IDs to remove from the bundle
        """
        if not isinstance(hit_ids, list):
            hit_ids = [hit_ids]

        return self._connection.delete(api_path("hit/bundle", bundle_id), json=hit_ids)
