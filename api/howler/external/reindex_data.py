import argparse
import json
import os
import sys
import time

DELAY = 5


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reindex elasticsearch indexes.",
        epilog="Valid index names are derived from the datastore configuration.",
    )
    parser.add_argument("indexes", nargs="*", help="Indexes to reindex.")
    parser.add_argument("--all", action="store_true", help="Reindex all indexes.")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts and countdown.")
    parser.add_argument("--verbose", action="store_true", help="Print index schema before reindexing.")
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Recover from a failed or interrupted reindex by restoring the source index and "
        "deleting leftover '__reindex' indexes.",
    )
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="DESTRUCTIVE: proceed even if the reindex reports document failures, version conflicts, "
        "or a document count mismatch. Documents that cannot be converted to the new mappings will be "
        "permanently dropped. Only use this for intentional lossy migrations.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Elasticsearch transport timeout in seconds for synchronous operations. Increase this if "
        "large indexes time out during the clone/settings steps. Default: 3600.",
    )
    args = parser.parse_args()

    if args.all and args.indexes:
        parser.error("--all cannot be combined with positional index arguments.")

    if not args.indexes and not args.all:
        parser.error("Provide index names as arguments, or use --all.")

    if args.timeout <= 0:
        parser.error("--timeout must be a positive number of seconds.")

    # Raise the Elasticsearch transport timeout before the datastore is imported so the value is
    # baked into every connection (including connections rebuilt after a reset). This lets long
    # running synchronous operations complete without timing out the client.
    os.environ["HWL_DATASTORE_TRANSPORT_TIMEOUT"] = str(args.timeout)

    from howler.datastore.collection import ESCollection

    ESCollection.IGNORE_ENSURE_COLLECTION = True

    if args.force:
        ESCollection.ENSURE_COLLECTION_WARNED = True

    from howler.common import loader

    ds = loader.datastore(archive_access=False)

    # Derive the set of reindexable indexes from the datastore configuration. Collections without
    # an ODM model (e.g. user_avatar) cannot be reindexed and are excluded.
    index_names = sorted(name for name, model in ds.ds.get_models().items() if model is not None)

    invalid = [name for name in args.indexes if name not in index_names]
    if invalid:
        parser.error(f"Invalid index(es): {', '.join(invalid)}. Valid options: {', '.join(index_names)}")

    selected = list(dict.fromkeys(index_names if args.all else args.indexes))

    if args.cleanup:
        for index_name in selected:
            collection: ESCollection = getattr(ds, index_name)
            print(f"Cleaning up leftover reindex state for '{index_name}'.")
            collection.reindex_cleanup()
            print(f"Cleanup of '{index_name}' complete.")
        sys.exit(0)

    if args.allow_failures and not args.force:
        print(
            "WARNING: --allow-failures is DESTRUCTIVE. Documents that cannot be converted to the new "
            "mappings will be permanently dropped, and count mismatches will be ignored."
        )
        answer = input("Are you sure you want to proceed with --allow-failures? [yes/NO] ")
        if not answer.startswith("y"):
            print("Confirmation not provided, aborting.")
            sys.exit(1)

    for index_name in selected:
        collection: ESCollection = getattr(ds, index_name)

        if args.verbose:
            print(f"Index schema for '{index_name}':")
            print(json.dumps(collection._get_index_mappings(), indent=2))

        print(f"Reindexing: {', '.join(collection.index_list_full)}")

        if not args.force:
            answer = input(f"Are you sure you want to reindex '{index_name}'? [yes/NO] ")
            if not answer.startswith("y"):
                print("Confirmation not provided, skipping.")
                continue

            for i in range(2 * DELAY):
                print(f"Reindexing in {2 * DELAY - i}...", end="\r")
                time.sleep(1)
            print()

        try:
            result = collection.reindex(allow_failures=args.allow_failures, request_timeout=args.timeout)
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: Reindex of '{index_name}' failed: {e}", file=sys.stderr)
            print(
                "The source index has been preserved. Run this script with --cleanup to remove any "
                "leftover '__reindex' index and restore the original, then investigate the failure "
                "before retrying.",
                file=sys.stderr,
            )
            sys.exit(1)

        print(f"Reindex of '{index_name}' complete. Success: {result}.")
