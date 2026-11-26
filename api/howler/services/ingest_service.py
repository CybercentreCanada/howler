from typing import Any, Literal

from howler.common.loader import datastore
from howler.odm.base import Model
from howler.services import post_write_service


def overwrite_record(
    index: str,
    id: str,
    record: Model | dict[str, Any],
    version: str | None,
    refresh: Literal["true", "false", "wait_for"] | None = None,
) -> bool:
    """Replace a record in an index, guarded by its version.

    Hits and events reach the post-write hook once the save succeeds.

    Args:
        index: The index containing the record.
        id: The ID of the record to replace.
        record: The full replacement record.
        version: The version the record must still be at for the save to succeed.
        refresh: Optional datastore refresh strategy ("true", "false", "wait_for").

    Returns:
        bool: True if the record was saved.
    """
    result = datastore()[index].save(id, record, version=version, refresh=refresh)
    post_write_service.record_saved(index, id)

    return result
