from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from elasticsearch.exceptions import NotFoundError
from pydantic import ValidationError

from howler import actions
from howler.actions.models import format_validation_error, parse_data_json
from howler.datastore.exceptions import VersionConflictException
from howler.datastore.migrations.base import Migration

if TYPE_CHECKING:
    from howler.datastore.howler_store import HowlerDatastore


logger = logging.getLogger("howler.datastore.migrations")


def _migration_warning(action_id: str, message: str, *args: Any, log_warnings: bool) -> None:
    if log_warnings:
        logger.warning("Action %s: " + message, action_id, *args)


def _migrate_operations(operations: Any, action_id: str, *, log_warnings: bool = True) -> tuple[Any, bool]:
    """Clean known operation arguments without changing malformed or unknown operations."""
    if operations is None:
        return operations, False

    if not isinstance(operations, list):
        _migration_warning(action_id, "operations is not a list; preserving it unchanged.", log_warnings=log_warnings)
        return operations, False

    updated_operations = []
    changed = False
    for operation in operations:
        if not isinstance(operation, Mapping):
            _migration_warning(
                action_id,
                "an operation is not an object; preserving it unchanged.",
                log_warnings=log_warnings,
            )
            updated_operations.append(operation)
            continue

        operation_id = operation.get("operation_id")
        if not isinstance(operation_id, str) or not operation_id:
            _migration_warning(
                action_id,
                "an operation has no non-empty operation_id; preserving it unchanged.",
                log_warnings=log_warnings,
            )
            updated_operations.append(operation)
            continue

        specification = actions.get_specification(operation_id)
        if specification is None:
            _migration_warning(
                action_id,
                "operation %s is unknown or disabled; preserving it unchanged.",
                operation_id,
                log_warnings=log_warnings,
            )
            updated_operations.append(operation)
            continue

        raw_data_json = operation.get("data_json")
        force_rewrite = raw_data_json == ""
        try:
            parsed_data = parse_data_json(raw_data_json)
        except ValueError as error:
            _migration_warning(
                action_id,
                "operation %s has invalid data_json (%s); preserving it unchanged.",
                operation_id,
                error,
                log_warnings=log_warnings,
            )
            updated_operations.append(operation)
            continue

        allowed_keys = set(specification.arguments.model_fields)
        cleaned_data = {key: value for key, value in parsed_data.items() if key in allowed_keys}
        if operation_id == "transition":
            transition_name = cleaned_data.get("transition")
            if (
                isinstance(transition_name, str)
                and transition_name in {"promote", "demote"}
                and not cleaned_data.get("escalation")
            ):
                cleaned_data["escalation"] = "alert" if transition_name == "promote" else "hit"

        try:
            specification.validate_arguments(cleaned_data)
        except ValidationError as error:
            _migration_warning(
                action_id,
                "operation %s has invalid arguments after migration: %s",
                operation_id,
                format_validation_error(error),
                log_warnings=log_warnings,
            )

        if cleaned_data != parsed_data or force_rewrite:
            updated_operations.append({**operation, "data_json": json.dumps(cleaned_data)})
            changed = True
        else:
            updated_operations.append(operation)

    return updated_operations, changed


class ActionArgumentsMigration(Migration):
    """Clean persisted operation arguments so saved actions use strict validation."""

    migration_id = "action-operation-arguments"

    def run(self, datastore: HowlerDatastore) -> int:
        """Strip obsolete/reserved operation arguments using optimistic concurrency."""
        if hasattr(datastore, "ds") and hasattr(datastore.ds, "validate"):
            original_validation = datastore.ds.validate
            try:
                datastore.ds.validate = False
                collection = datastore.action
            finally:
                datastore.ds.validate = original_validation
        else:
            collection = datastore.action

        client = collection.datastore.client
        affected_documents = 0
        for hit in collection.scan_with_retry(query={"match_all": {}}, index=collection.name):
            doc_id = hit["_id"]
            _, changed = _migrate_operations(hit.get("_source", {}).get("operations"), doc_id)
            if not changed:
                continue

            for attempt in range(collection.MAX_VERSION_CONFLICT_ATTEMPTS):
                try:
                    current = collection.with_retries(client.get, index=hit["_index"], id=doc_id)
                    updated_operations, still_changed = _migrate_operations(
                        current.get("_source", {}).get("operations"), doc_id, log_warnings=False
                    )
                    if not still_changed:
                        break

                    collection.with_retries(
                        client.update,
                        index=hit["_index"],
                        id=doc_id,
                        doc={"operations": updated_operations},
                        if_seq_no=current["_seq_no"],
                        if_primary_term=current["_primary_term"],
                        raise_conflicts=True,
                    )
                    affected_documents += 1
                    break
                except NotFoundError:
                    break
                except VersionConflictException:
                    if attempt == collection.MAX_VERSION_CONFLICT_ATTEMPTS - 1:
                        raise

        if affected_documents:
            collection.with_retries(client.indices.refresh, index=collection.name)

        return affected_documents
