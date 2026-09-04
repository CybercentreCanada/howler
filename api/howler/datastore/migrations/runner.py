from __future__ import annotations

import logging
import math
import os
import time
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from howler.common.exceptions import HowlerRuntimeError
from howler.datastore.collection import CREATE_TOKEN
from howler.datastore.exceptions import DataStoreException, VersionConflictException
from howler.datastore.migrations.action_owner import (
    ActionOwnerLegacyFieldCleanupMigration,
    ActionOwnerMigration,
)
from howler.datastore.migrations.base import Migration
from howler.utils.isotime import now_as_iso

if TYPE_CHECKING:
    from howler.datastore.collection import ESCollection
    from howler.datastore.howler_store import HowlerDatastore


logger = logging.getLogger("howler.datastore.migrations")

MIGRATIONS: tuple[Migration, ...] = (
    ActionOwnerMigration(),
    ActionOwnerLegacyFieldCleanupMigration(),
)
DEFAULT_WAIT_TIMEOUT = 14400.0
DEFAULT_POLL_INTERVAL = 0.5
# Keep this above the default task/retry budget so a live long-running migration is not reclaimed.
DEFAULT_STALE_CLAIM_TIMEOUT = 14400.0


def _get_duration(name: str, default: float) -> float:
    value = os.environ.get(name, str(default))
    try:
        duration = float(value)
    except ValueError as error:
        raise DataStoreException(f"{name} must be a non-negative number, got {value!r}") from error

    if not math.isfinite(duration) or duration < 0:
        raise DataStoreException(f"{name} must be a non-negative number, got {value!r}")

    return duration


def _migration_wait_timeout() -> float:
    return _get_duration("HWL_MIGRATION_WAIT_TIMEOUT", DEFAULT_WAIT_TIMEOUT)


def _migration_poll_interval() -> float:
    return _get_duration("HWL_MIGRATION_POLL_INTERVAL", DEFAULT_POLL_INTERVAL)


def _migration_stale_claim_timeout() -> float:
    return _get_duration("HWL_MIGRATION_STALE_CLAIM_TIMEOUT", DEFAULT_STALE_CLAIM_TIMEOUT)


def _validate_migrations(migrations: Sequence[Migration]) -> None:
    if not migrations:
        raise DataStoreException("At least one datastore migration must be selected.")

    migration_ids = [getattr(migration, "migration_id", None) for migration in migrations]
    if any(not isinstance(migration_id, str) or not migration_id.strip() for migration_id in migration_ids):
        raise DataStoreException("Every datastore migration must define a non-empty migration_id.")

    if len(migration_ids) != len(set(migration_ids)):
        raise DataStoreException("Datastore migration IDs must be unique.")


def _parse_record_timestamp(value: Any, field_name: str, migration_id: str) -> datetime:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as error:
            raise DataStoreException(
                f"Migration {migration_id} has an invalid {field_name} value in the migration index."
            ) from error
    else:
        raise DataStoreException(f"Migration {migration_id} has an invalid {field_name} value in the migration index.")

    if timestamp.tzinfo is None:
        raise DataStoreException(
            f"Migration {migration_id} has a timezone-naive {field_name} value in the migration index."
        )

    return timestamp.astimezone(timezone.utc)


def _record_status(record: dict[str, Any] | None, migration_id: str) -> str | None:
    if record is None:
        return None

    if not isinstance(record, dict):
        raise DataStoreException(f"Migration {migration_id} has an invalid record in the migration index.")
    if record.get("migration_id") != migration_id:
        raise DataStoreException(f"Migration record for {migration_id} has a mismatched migration_id.")

    status = record.get("status")
    if status not in {"running", "applied"}:
        raise DataStoreException(f"Migration {migration_id} has an invalid status {status!r} in the migration index.")

    _parse_record_timestamp(record.get("started_at"), "started_at", migration_id)

    claim_id = record.get("claim_id")
    if claim_id is not None and (not isinstance(claim_id, str) or not claim_id):
        raise DataStoreException(f"Migration {migration_id} has an invalid claim_id in the migration index.")

    affected_documents = record.get("affected_documents")
    if affected_documents is not None and (
        isinstance(affected_documents, bool) or not isinstance(affected_documents, int) or affected_documents < 0
    ):
        raise DataStoreException(
            f"Migration {migration_id} has an invalid affected_documents value in the migration index."
        )

    if status == "applied":
        if record.get("applied_at") is None or affected_documents is None:
            raise DataStoreException(
                f"Migration {migration_id} has an incomplete applied record in the migration index."
            )
        _parse_record_timestamp(record["applied_at"], "applied_at", migration_id)
    elif record.get("applied_at") is not None or affected_documents is not None:
        raise DataStoreException(f"Migration {migration_id} has an inconsistent running record in the migration index.")

    return status


def _is_stale_claim(record: dict[str, Any], migration_id: str) -> bool:
    started_at = _parse_record_timestamp(record.get("started_at"), "started_at", migration_id)
    return datetime.now(tz=timezone.utc) - started_at >= timedelta(seconds=_migration_stale_claim_timeout())


def _claim_record(migration_id: str, claim_id: str) -> dict[str, str]:
    return {
        "migration_id": migration_id,
        "status": "running",
        "started_at": now_as_iso(),
        "claim_id": claim_id,
    }


def _try_claim(record_collection: ESCollection, migration_id: str, claim_id: str) -> bool:
    try:
        record_collection.save(
            migration_id,
            _claim_record(migration_id, claim_id),
            version=CREATE_TOKEN,
            refresh="wait_for",
        )
    except VersionConflictException:
        return False

    return True


def _replace_stale_claim(record_collection: ESCollection, migration_id: str, version: str, claim_id: str) -> bool:
    if version == CREATE_TOKEN:
        return False

    try:
        record_collection.save(
            migration_id,
            _claim_record(migration_id, claim_id),
            version=version,
            refresh="wait_for",
        )
    except VersionConflictException:
        return False

    return True


def _wait_for_existing_claim(record_collection: ESCollection, migration_id: str) -> str:
    deadline = time.monotonic() + _migration_wait_timeout()
    poll_interval = _migration_poll_interval()

    while True:
        record = record_collection.get_if_exists(migration_id, as_obj=False)
        status = _record_status(record, migration_id)
        if status is None:
            return "missing"
        if status == "applied":
            return "applied"
        if _is_stale_claim(record, migration_id):
            return "stale"

        if time.monotonic() >= deadline:
            raise HowlerRuntimeError(
                f"Timed out waiting for datastore migration {migration_id} to finish in another process."
            )

        time.sleep(poll_interval)


def _acquire_claim(record_collection: ESCollection, migration_id: str, claim_id: str) -> bool:
    while True:
        record, version = record_collection.get_if_exists(migration_id, as_obj=False, version=True)
        status = _record_status(record, migration_id)
        if status == "applied":
            return False

        if status is None:
            if _try_claim(record_collection, migration_id, claim_id):
                return True
            continue

        if _is_stale_claim(record, migration_id):
            if _replace_stale_claim(record_collection, migration_id, version, claim_id):
                return True
            continue

        outcome = _wait_for_existing_claim(record_collection, migration_id)
        if outcome == "applied":
            return False


def _mark_applied(
    record_collection: ESCollection,
    migration_id: str,
    claim_id: str,
    affected_documents: int,
) -> None:
    record, version = record_collection.get_if_exists(migration_id, as_obj=False, version=True)
    if record is None or version == CREATE_TOKEN:
        raise DataStoreException(f"Migration claim for {migration_id} disappeared before it could be completed.")
    if _record_status(record, migration_id) != "running" or record.get("claim_id") != claim_id:
        raise DataStoreException(f"Migration claim for {migration_id} is no longer owned by this execution.")

    record.update(
        {
            "status": "applied",
            "applied_at": now_as_iso(),
            "affected_documents": affected_documents,
        }
    )
    try:
        record_collection.save(migration_id, record, version=version, refresh="wait_for")
    except VersionConflictException as error:
        raise DataStoreException(
            f"Migration claim for {migration_id} was lost before it could be completed."
        ) from error


def _release_claim(record_collection: ESCollection, migration_id: str, claim_id: str) -> None:
    for _ in range(2):
        record, version = record_collection.get_if_exists(migration_id, as_obj=False, version=True)
        if record is None or version == CREATE_TOKEN:
            raise DataStoreException(f"Migration claim for {migration_id} disappeared before it could be released.")
        if _record_status(record, migration_id) != "running" or record.get("claim_id") != claim_id:
            raise DataStoreException(f"Migration claim for {migration_id} is no longer owned by this execution.")

        try:
            if record_collection.delete(migration_id, version=version, refresh="wait_for"):
                return
        except VersionConflictException:
            continue

        raise DataStoreException(f"Migration claim for {migration_id} disappeared before it could be released.")

    raise DataStoreException(f"Migration claim for {migration_id} was lost before it could be released.")


def _execute_migration(
    datastore: "HowlerDatastore",
    record_collection: ESCollection,
    migration: Migration,
    claim_id: str,
) -> None:
    affected_documents = migration.run(datastore)
    if isinstance(affected_documents, bool) or not isinstance(affected_documents, int) or affected_documents < 0:
        raise DataStoreException(
            f"Datastore migration {migration.migration_id} returned an invalid affected-document count: "
            f"{affected_documents!r}."
        )

    _mark_applied(record_collection, migration.migration_id, claim_id, affected_documents)
    logger.info(
        "Applied datastore migration %s; affected %s document(s).",
        migration.migration_id,
        affected_documents,
    )


def _run_migration(datastore: "HowlerDatastore", record_collection: ESCollection, migration: Migration) -> None:
    migration_id = migration.migration_id
    claim_id = uuid4().hex

    if not _acquire_claim(record_collection, migration_id, claim_id):
        logger.info("Datastore migration %s has already been applied by another process.", migration_id)
        return

    try:
        _execute_migration(datastore, record_collection, migration, claim_id)
    except Exception:  # noqa: BLE001
        try:
            _release_claim(record_collection, migration_id, claim_id)
        except Exception:  # noqa: BLE001
            logger.exception("Could not release the claim for failed datastore migration %s.", migration_id)
        raise


def run_migrations(
    datastore: "HowlerDatastore",
    migrations: Sequence[Migration] | None = None,
) -> None:
    """Run selected migrations once, recording successful executions."""
    selected_migrations = MIGRATIONS if migrations is None else tuple(migrations)
    _validate_migrations(selected_migrations)

    for migration in selected_migrations:
        _run_migration(datastore, datastore.migration, migration)
