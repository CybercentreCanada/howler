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

For bulk writes, the hook is called for every record in the plan once the bulk
request returns, even when the datastore reports errors for some of them, because
the bulk result doesn't say which records failed. Consumers must therefore
tolerate being called for a record whose write failed.
"""

from typing import Iterable, Literal, TypedDict, cast

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
