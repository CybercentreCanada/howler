from datetime import datetime

from howler import odm
from howler.common.loader import datastore
from howler.datastore.types import SearchResult
from howler.odm.models.hit import Hit
from pyspark.sql.types import StructType

from sync.iceberg.build import build_schema


def get_upserted_hits(
    data_interval_start: datetime | None = None,
    data_interval_end: datetime | None = None,
    deep_paging_id: str | None = None,
    offset: int = 0,
    rows: int | None = None,
    timeout: int | None = None,
) -> SearchResult[Hit]:
    """Get the hits that have been created or updated within the specified time interval."""
    storage = datastore()

    range_query = _range_query_from_interval(data_interval_start, data_interval_end)
    query = f"timestamp:{range_query} OR howler.log.timestamp:{range_query}"

    res = storage.hit.search(
        query=query,
        deep_paging_id=deep_paging_id,
        offset=offset,
        rows=rows,
        timeout=timeout,
        as_obj=True,
    )

    return res


def get_model_struct_schema(model: type[odm.Model]) -> StructType:
    """Get the schema for the odm model structure."""
    schema = build_schema(model)
    return schema


def _range_query_from_interval(data_interval_start: datetime | None, data_interval_end: datetime | None) -> str:
    """Construct a range query string for the specified time interval."""
    query_range_start: str = data_interval_start.strftime(odm.DATEFORMAT) if data_interval_start else "*"
    query_range_end: str = data_interval_end.strftime(odm.DATEFORMAT) if data_interval_end else "*"

    return f"[{query_range_start} TO {query_range_end}]"
