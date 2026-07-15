from datetime import datetime

from howler.common.loader import datastore

LUCENE_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def get_upserted_hits(data_interval_start: datetime | None = None, data_interval_end: datetime | None = None):
    """Get the hits that have been created or updated within the specified time interval."""
    storage = datastore()

    range_query = _range_query_from_interval(data_interval_start, data_interval_end)
    query = f"timestamp:{range_query} OR howler.log.timestamp:{range_query}"

    res = storage.hit.search(query=query)

    return res["items"] if res else []


def _range_query_from_interval(data_interval_start: datetime | None, data_interval_end: datetime | None) -> str:
    """Construct a range query string for the specified time interval."""
    query_range_start: str = data_interval_start.strftime(LUCENE_DATE_FORMAT) if data_interval_start else "*"
    query_range_end: str = data_interval_end.strftime(LUCENE_DATE_FORMAT) if data_interval_end else "*"

    return f"[{query_range_start} TO {query_range_end}]"
