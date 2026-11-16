"""Explicitly initialize all registered Howler collections before cutover verification.

WARNING: this operator command is not read-only. Accessing a collection can
create or reconcile its index, mappings, ILM policy, and index template exactly
as normal application startup does.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any

from howler.common.exceptions import HowlerAttributeError, HowlerRuntimeError, HowlerValueError
from howler.external.elasticsearch_rest import load_configured_plugins


class CollectionInitializationError(RuntimeError):
    """Associate a lazy collection-initialization failure with its collection name."""

    def __init__(self, collection: str, cause: Exception) -> None:
        super().__init__(f"Failed to initialize collection {collection}.")
        self.collection = collection
        self.cause = cause


def _registered_collection_names() -> tuple[str, ...]:
    """Return Howler's registered collection names in application order."""
    from howler.datastore.howler_store import INDEXES

    return tuple(INDEXES)


def initialize_collections(storage: Any, collection_names: tuple[str, ...]) -> list[str]:
    """Touch only ``datastore.<collection>`` attributes to trigger normal initialization."""
    initialized: list[str] = []
    for collection_name in collection_names:
        _touch_collection(storage, collection_name)
        initialized.append(collection_name)
    return initialized


def _touch_collection(storage: Any, collection_name: str) -> None:
    try:
        getattr(storage, collection_name)
    except Exception as error:  # noqa: BLE001 - add the collection context before reporting the failure
        raise CollectionInitializationError(collection_name, error) from error


def _safe_error_detail(error: Exception) -> str:
    if isinstance(error, (HowlerAttributeError, HowlerRuntimeError, HowlerValueError)):
        return str(error)
    return type(error).__name__


def main(argv: list[str] | None = None) -> int:
    """Initialize all collections using the deployed Howler datastore configuration."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm-reconciliation",
        action="store_true",
        help="Acknowledge that this command can create/reconcile Elasticsearch resources.",
    )
    args = parser.parse_args(argv)
    if not args.confirm_reconciliation:
        parser.error("This command can write Elasticsearch resources; pass --confirm-reconciliation to proceed.")

    storage = None
    try:
        load_configured_plugins()
        from howler.common.loader import datastore

        storage = datastore()
        if storage is None:
            error = HowlerRuntimeError("The datastore factory returned no storage object.")
            print(
                f"ERROR: collection initialization failed ({_safe_error_detail(error)}).",
                file=sys.stderr,
            )  # noqa: T201
            return 1
        initialized = initialize_collections(storage, _registered_collection_names())
        for name in initialized:
            print(f"Initialized collection {name}.")  # noqa: T201
    except CollectionInitializationError as error:
        print(
            f"ERROR: collection {error.collection} initialization failed ({_safe_error_detail(error.cause)}).",
            file=sys.stderr,
        )  # noqa: T201
        return 1
    except Exception as error:  # noqa: BLE001
        print(f"ERROR: collection initialization failed ({_safe_error_detail(error)}).", file=sys.stderr)  # noqa: T201
        return 1
    finally:
        if storage is not None:
            storage.ds.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
