"""The single post-write hook for hit and event changes.

Every write that creates or changes a hit or event with a known record ID calls
:func:`record_written` once per changed record, after the datastore write
returns. That covers full saves, partial update operations, bulk ingestion, the
v2 ingest overwrite, and the ``Hit.save``/``Event.save`` mixin writes used for
case back-references and correlation.

Writes not covered:

- Query-driven bulk writes (``update_by_query``) don't call the hook, because
  the changed record IDs aren't known. A reconciliation job is expected to
  cover these.
- Deletes don't call the hook.

For bulk writes, the hook is called once for each record the datastore reports as
created or changed, including records from earlier requests when a later request
in the same plan fails. Records whose items failed, or that were left unchanged,
don't reach the hook.
"""

from typing import TYPE_CHECKING, Iterable, Literal, TypedDict, cast

if TYPE_CHECKING:
    from howler.datastore.bulk import ElasticBulkPlan
    from howler.datastore.collection import ESCollection

RecordType = Literal["hit", "event"]

RECORD_TYPES: tuple[RecordType, ...] = ("hit", "event")


class WrittenRecord(TypedDict):
    """A reference to a hit or event that was just written."""

    type: RecordType
    id: str


def record_written(record: WrittenRecord) -> None:
    """Handle a write to a single hit or event.

    Does nothing yet; this is the seam that post-write processing plugs into.

    Args:
        record: The type and ID of the record that was written.
    """


def records_written(record_type: RecordType, record_ids: Iterable[str]) -> None:
    """Call :func:`record_written` once for each written record of the given type.

    Args:
        record_type: The type of every record that was written.
        record_ids: The IDs of the written records.
    """
    for record_id in record_ids:
        record_written({"type": record_type, "id": record_id})


def record_saved(index: str, record_id: str) -> None:
    """Call :func:`record_written` if a record saved to the given index is a hit or event.

    Args:
        index: The index the record was saved to.
        record_id: The ID of the saved record.
    """
    if index in RECORD_TYPES:
        record_written({"type": cast(RecordType, index), "id": record_id})


def bulk_write(
    record_type: RecordType,
    collection: "ESCollection",
    plan: "ElasticBulkPlan",
    refresh: str | None = None,
) -> bool:
    """Run a bulk plan, then call :func:`record_written` for each record it created or changed.

    The hook fires even if the bulk call raises partway through, for the records written
    before the failure, and the exception is then re-raised.

    Args:
        record_type: The type of every record in the plan.
        collection: The hit or event collection to write to.
        plan: The bulk plan to run.
        refresh: Optional datastore refresh strategy.

    Returns:
        bool: True if every item in the plan succeeded.
    """
    try:
        return collection.bulk(plan) if refresh is None else collection.bulk(plan, refresh=refresh)
    finally:
        records_written(record_type, plan.written_ids)
