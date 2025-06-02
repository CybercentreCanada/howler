import json
import sys
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Literal, Optional, Union

from howler_client.common.dict_utils import flatten
from howler_client.common.utils import ClientError, api_path
from howler_client.logger import get_logger
from howler_client.module.comment import Comment
from howler_client.utils.json_encoders import BytesDatetimeEncoder, DatetimeEncoder

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

if TYPE_CHECKING:
    from howler_client import Connection
    from howler_client.module.search import Search

logger = get_logger("hit")

UPDATE_SET = "SET"
UPDATE_INC = "INC"
UPDATE_DEC = "DEC"
UPDATE_MAX = "MAX"
UPDATE_MIN = "MIN"
UPDATE_APPEND = "APPEND"
UPDATE_APPEND_IF_MISSING = "APPEND_IF_MISSING"
UPDATE_REMOVE = "REMOVE"
UPDATE_DELETE = "DELETE"

UPDATE_OPERATIONS = [
    UPDATE_APPEND,
    UPDATE_APPEND_IF_MISSING,
    UPDATE_DEC,
    UPDATE_INC,
    UPDATE_MAX,
    UPDATE_MIN,
    UPDATE_REMOVE,
    UPDATE_SET,
    UPDATE_DELETE,
]


class Hit(object):
    "Operations pertaining to ingesting and interacting with Howler hits."

    def __init__(self: Self, connection: "Connection", search: "Search"):
        self._connection: "Connection" = connection
        self._search: "Search" = search
        self.comment: "Comment" = Comment(connection)

    def __call__(self: Self, hit_id: str) -> dict[str, Any]:
        """Return the hit for a given ID

        Args:
            hit_id (str): ID of the hit

        Returns:
            dict[str, Any]: The corresponding hit data
        """
        return self._connection.get(api_path("hit", hit_id))

    def create_from_map(
        self: Self,
        tool_name: str,
        map: dict[str, list[str]],
        documents: list[dict[str, Any]],
        ignore_extra_values: bool = False,
    ) -> dict[str, Union[Optional[str], list[str]]]:
        """Create hits for a given tool using the raw documents and a map of the document fields to howler's fields.

        Args:
            tool_name (str): Name of the tool the hits will be created for
            map (dict[str, list[str]]): Dictionary where the keys are the flattened path of the tool's raw document and
                    the values are a list of flattened path for Howler's fields where the data will be copied into
            documents (list[dict[str, Any]]): The data to ingest into howler, in the tool's raw document format
            ignore_extra_values (bool, optional): Whether to allow extra fields, or raise an error. Defaults to False.

        Returns:
            dict[str, Union[Optional[str], list[str]]]: A list of IDs/Errors in the same order as the original documents
        """
        data = {"map": map, "hits": documents}

        try:
            result = self._connection.post(
                api_path("tools", tool_name, "hits", ignore_extra_values=ignore_extra_values),
                json=data,
            )
        except ClientError as e:
            if e.api_response and isinstance(e.api_response, list):
                for res in e.api_response:
                    if "warn" in res and res["warn"]:
                        logger.warning(res["warn"])

                    if "error" in res and res["error"]:
                        logger.error(res["error"])  # noqa: TRY400
            raise

        for res in result:
            if "warn" in res and res["warn"]:
                warn = res["warn"]
                if isinstance(warn, list):
                    for w in warn:
                        logger.warn(w)
                else:
                    logger.warn(warn)

        return result

    def generate_hash(self: Self, hit: dict[str, Any]) -> str:
        """Generate hash value for hit using the analytic, detection, and raw_data values from the hit data.

        Args:
            hit (str): hit data

        Returns:
            str: A hash value for the hit
        """
        howler_data = hit.get("howler.data", [])

        if not isinstance(howler_data, list):
            howler_data = [howler_data]

        hash_contents = {
            "analytic": hit["howler.analytic"],
            "detection": hit.get("howler.detection", "no_detection"),
            "raw_data": sorted(
                json.dumps(entry, sort_keys=True, ensure_ascii=True, cls=BytesDatetimeEncoder) for entry in howler_data
            ),
        }

        return sha256(json.dumps(hash_contents, sort_keys=True, ensure_ascii=True).encode("utf-8")).hexdigest()

    def create(  # noqa: C901
        self: Self,
        data: Union[dict[str, Any], list[dict[str, Any]]],
        ignore_extra_values: bool = False,
    ):
        """Create one or many hits using the howler schema.

        Args:
            data (Union[dict[str, Any], list[dict[str, Any]]]): The hit or list of hits to create
            ignore_extra_values (bool, optional): Whtether to ignore extra values, or throw an exception.
                Defaults to False.

        Returns:
            dict[str, list[dict[str, Any]]]: A list of valid and invalid hits
        """
        if not isinstance(data, list):
            data = [data]

        final_hit_list = []
        for hit in data:
            hit = flatten(hit, fields=["howler"])

            existing_hash = hit.get("howler.hash", None)
            if existing_hash is None:
                existing_hash = self.generate_hash(hit)

            hit["howler.hash"] = existing_hash

            if "howler.data" in hit:
                howler_data = hit["howler.data"]
                if not isinstance(howler_data, list):
                    howler_data = [howler_data]

                hit["howler.data"] = [
                    json.dumps(
                        entry,
                        sort_keys=True,
                        ensure_ascii=True,
                        cls=BytesDatetimeEncoder,
                    )
                    for entry in howler_data
                ]

            final_hit_list.append(hit)

        search_result = self._search.grouped.hit(
            "howler.hash",
            limit=1,
            filters=[f"howler.hash:{' '.join(list_hit['howler.hash'] for list_hit in final_hit_list)}"],
        )["items"]

        for hit in final_hit_list:
            for match in search_result:
                if hit["howler.hash"] == match["value"]:
                    matched_hit = match["items"][0]

                    logger.warning(
                        f"Hit with hash {hit['howler.hash']} already exists in the DB at "
                        f"id {matched_hit['howler']['id']}, reusing"
                    )
                    final_hit_list.remove(hit)

        if len(final_hit_list) < 1:
            logger.info("No hits to submit.")
            return None

        result = self._connection.post(
            api_path("hit", ignore_extra_values=ignore_extra_values),
            data=json.dumps(final_hit_list, cls=DatetimeEncoder),
            headers={"Content-Type": "application/json"},
        )

        if not result:
            logger.warning("No result was returned.")
            return result

        for invalid_hit in result["invalid"]:
            logger.error(invalid_hit["error"])

        for entry in search_result:
            result["valid"].append(entry["items"][0])

        return result

    def overwrite(self: Self, hit_id: str, new_hit_data: dict[str, Any]):
        """Overwrite a hit.

        This is different from updating a hit, as you simply provide a partial hit object

        Args:
            hit_id (str): Id of the hit you would like to overwrite
            new_hit_data (dict[str, Any]): A partial hit data object to overwrite the specified hit with

        Raises:
            ClientError: Updates provided were invalid
        """
        if not isinstance(new_hit_data, dict):
            raise TypeError("New hit data must be of type dict.")

        return self._connection.put(api_path(f"hit/{hit_id}/overwrite"), json=new_hit_data)

    def update(self: Self, hit_id: str, updates: list[tuple[str, str, Any]]):
        """Update a hit.

        Args:
            hit_id (str): Id of the hit you would like to update
            updates (list[tuple[str, str, Any]]): A list of updates to run. The first entry in the tuple must be a valid
                update operation (see UPDATE_OPERATIONS), the second a key for a howler hit, and the third the value
                to use in the operation.

        Raises:
            ClientError: Updates provided were invalid
        """
        if not isinstance(updates, list):
            raise TypeError("Updates must be of type list.")

        for update in updates:
            if not isinstance(update, tuple):
                raise TypeError("Entries in updates must be of type tuple.")

            if update[0] not in UPDATE_OPERATIONS:
                raise ClientError(
                    f"Invalid update - operation must be one of {','.join(UPDATE_OPERATIONS)}!",
                    400,
                )

        return self._connection.put(api_path(f"hit/{hit_id}/update"), json=updates)

    def update_by_query(self: Self, query: str, updates: list[tuple[str, str, Any]]):
        """Update a set of hits by query.

        Args:
            query (str): Query representing the hits you would like to update
            updates (list[tuple[str, str, Any]]): A list of updates to run. The first entry in the tuple must be a valid
                update operation (see UPDATE_OPERATIONS), the second a key for a howler hit, and the third the value
                to use in the operation.

        Raises:
            ClientError: Updates provided were invalid
        """
        if not isinstance(updates, list):
            raise TypeError("Updates must be of type list.")

        for update in updates:
            if not isinstance(update, tuple):
                raise TypeError("Entries in updates must be of type tuple.")
            if update[0] not in UPDATE_OPERATIONS:
                raise ClientError(
                    f"Invalid update - operation must be one of {','.join(UPDATE_OPERATIONS)}!",
                    400,
                )

        return self._connection.put(api_path("hit/update"), json={"query": query, "operations": updates})

    def delete(self: Self, hit_ids: list[str]) -> dict[Literal["success"], bool]:
        """Delete a list of hits by id

        Returns:
            dict[Literal["success"], bool]: Whether the delete operation was successful
        """
        if not isinstance(hit_ids, list):
            hit_ids = [hit_ids]

        return self._connection.delete(api_path("hit"), json=hit_ids)
