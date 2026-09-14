"""Run selected datastore migrations as an explicit operator command."""

import argparse
import os
import sys
from collections.abc import Sequence
from typing import Any

from dotenv import load_dotenv


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run selected Howler datastore migrations.")
    parser.add_argument("--list", action="store_true", help="List registered migration IDs and exit.")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--all", action="store_true", help="Run every registered migration.")
    selection.add_argument(
        "--migration-id",
        action="append",
        default=[],
        help="Run one migration ID. Repeat this option to select multiple migrations.",
    )
    parser.add_argument(
        "--timeout",
        "--transport-timeout",
        type=int,
        help="Elasticsearch transport timeout in seconds. Defaults to HWL_DATASTORE_TRANSPORT_TIMEOUT or 10.",
    )
    return parser


def _load_migrations() -> tuple[Sequence[Any], Any]:
    """Import the registry only after CLI configuration is ready."""
    from howler.datastore.migrations.runner import MIGRATIONS, run_migrations

    return MIGRATIONS, run_migrations


def _load_datastore() -> Any:
    """Construct the normal datastore after migration selection is validated."""
    from howler.common.loader import datastore

    return datastore()


def _select_migrations(migrations: Sequence[Any], requested_ids: list[str], run_all: bool) -> tuple[Any, ...]:
    if not migrations:
        raise ValueError("The registered migration set is empty.")

    migration_ids = [getattr(migration, "migration_id", None) for migration in migrations]
    if any(not isinstance(migration_id, str) or not migration_id.strip() for migration_id in migration_ids):
        raise ValueError("The registered migration IDs are invalid or duplicated.")
    if len(set(migration_ids)) != len(migration_ids):
        raise ValueError("The registered migration IDs are invalid or duplicated.")
    migration_by_id = dict(zip(migration_ids, migrations, strict=True))

    if run_all:
        return tuple(migrations)

    if len(set(requested_ids)) != len(requested_ids):
        raise ValueError("Migration IDs may only be selected once.")

    unknown_ids = [migration_id for migration_id in requested_ids if migration_id not in migration_by_id]
    if unknown_ids:
        raise ValueError(f"Unknown migration ID(s): {', '.join(unknown_ids)}")

    return tuple(migration_by_id[migration_id] for migration_id in dict.fromkeys(requested_ids))


def _parse_arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    """Parse and validate CLI arguments before importing datastore modules."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.timeout is not None and args.timeout <= 0:
        parser.error("--timeout must be a positive number of seconds.")
    if args.list and (args.all or args.migration_id):
        parser.error("--list cannot be combined with a migration selection.")
    if not args.list and not args.all and not args.migration_id:
        parser.error("Use --all or provide at least one --migration-id.")
    return args


def _run_selected_migrations(run_migrations: Any, selected_migrations: Sequence[Any]) -> int:
    """Run migrations with a normal datastore lifecycle."""
    datastore = None
    exit_status = 0
    try:
        datastore = _load_datastore()
        run_migrations(datastore, selected_migrations)
    except Exception as error:  # noqa: BLE001
        print(f"ERROR: Datastore migration failed: {error}", file=sys.stderr)
        exit_status = 1
    finally:
        if datastore is not None:
            try:
                datastore.ds.close()
            except Exception as error:  # noqa: BLE001
                print(f"ERROR: Could not close datastore: {error}", file=sys.stderr)
                exit_status = 1

    return exit_status


def main(argv: Sequence[str] | None = None) -> int:
    """Parse arguments, run selected migrations, and return a shell exit status."""
    args = _parse_arguments(argv)

    # Match local API configuration without importing the Flask application. CLI input wins over .env.
    load_dotenv()
    if args.timeout is not None:
        os.environ["HWL_DATASTORE_TRANSPORT_TIMEOUT"] = str(args.timeout)

    try:
        migrations, run_migrations = _load_migrations()
    except Exception as error:  # noqa: BLE001
        print(f"ERROR: Could not load datastore migrations: {error}", file=sys.stderr)
        return 1

    if args.list:
        try:
            selected_migrations = _select_migrations(migrations, [], True)
        except ValueError as error:
            print(f"ERROR: {error}", file=sys.stderr)
            return 2
        for migration in selected_migrations:
            print(migration.migration_id)
        return 0

    try:
        selected_migrations = _select_migrations(migrations, args.migration_id, args.all)
    except ValueError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    return _run_selected_migrations(run_migrations, selected_migrations)


if __name__ == "__main__":
    sys.exit(main())
