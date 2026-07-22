import re

from howler.common.loader import APP_NAME, DATASTORE_INDEX_PREFIX
from howler.datastore.exceptions import SearchException


def normalize_indexes(indexes: str | list[str]) -> str:
    """Normalizes Elasticsearch index names into a comma-separated string.

    Parses the input indexes and applies naming conventions. Special patterns like
    wildcards, exclusions, and explicitly formatted indexes are preserved as-is.
    Regular indexes are formatted with the datastore index prefix and '_hot' suffix.

    Args:
        indexes: A comma-separated string or list of index names to normalize.

    Returns:
        A comma-separated string of normalized index names ready for Elasticsearch queries.

    Raises:
        SearchException: If no valid indexes are provided after parsing and stripping whitespace.

    Examples:
        >>> normalize_indexes("logs,metrics")
        "howler-logs_hot,howler-metrics_hot"

        >>> normalize_indexes(["*", "custom-index"])
        "*,custom-index"

        >>> normalize_indexes("alerts, events")
        "howler-alerts_hot,howler-events_hot"
    """
    if isinstance(indexes, str):
        parsed_indexes = [item.strip() for item in indexes.split(",") if item.strip()]
    else:
        parsed_indexes = [item.strip() for item in indexes if item.strip()]

    if not parsed_indexes:
        raise SearchException("No indexes were provided.")

    normalized_indexes: list[str] = []
    for index in parsed_indexes:
        if index in {"*", "_all"} or "-" in index or "*" in index:
            normalized_indexes.append(index)
        else:
            normalized_indexes.append(f"{DATASTORE_INDEX_PREFIX}-{index}")

    return ",".join(normalized_indexes)


def get_logical_index_name(raw_index: str) -> str:
    """Strip the physical datastore prefix and hot-index suffix from an index name."""
    for index_prefix in sorted({DATASTORE_INDEX_PREFIX, APP_NAME}, key=len, reverse=True):
        if raw_index.startswith(f"{index_prefix}-"):
            raw_index = raw_index.removeprefix(f"{index_prefix}-")
            break

    return re.sub(r"-\d+$", "", raw_index).removesuffix("_hot")
