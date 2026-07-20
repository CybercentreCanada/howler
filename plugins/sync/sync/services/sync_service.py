from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
from typing import cast

from howler.common.loader import datastore
from howler.odm.models.hit import Hit
from howler.odm.randomizer import Model, random_model_obj
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType

LUCENE_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


def get_upserted_hits(
    data_interval_start: datetime | None = None,
    data_interval_end: datetime | None = None,
    deep_paging_id: str | None = None,
    offset: int = 0,
    rows: int | None = None,
    timeout: int | None = None,
):
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
        as_obj=False,
    )

    return res


def get_hit_struct_schema() -> StructType:
    """Get the schema for the hit structure."""
    dummy_hit: Hit = random_model_obj(cast(Model, Hit))

    with _get_local_spark_session() as spark:
        df = spark.read.option("inferSchema", True).json(spark.sparkContext.parallelize([dummy_hit.json()]))

    return df.schema


def _range_query_from_interval(data_interval_start: datetime | None, data_interval_end: datetime | None) -> str:
    """Construct a range query string for the specified time interval."""
    query_range_start: str = data_interval_start.strftime(LUCENE_DATE_FORMAT) if data_interval_start else "*"
    query_range_end: str = data_interval_end.strftime(LUCENE_DATE_FORMAT) if data_interval_end else "*"

    return f"[{query_range_start} TO {query_range_end}]"


@contextmanager
def _get_local_spark_session() -> Generator[SparkSession, None, None]:
    """Get a local Spark session"""
    spark = SparkSession.builder.master("local").appName("howler-sync-service").getOrCreate()  # type: ignore
    yield spark
    spark.stop()
