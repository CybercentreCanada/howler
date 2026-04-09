import argparse
import json
import time

DELAY = 5
INDEX_NAMES = ["analytic", "hit", "view", "template", "overview", "action", "user", "dossier"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Reindex elasticsearch indexes.",
        epilog=f"Valid index names: {', '.join(INDEX_NAMES)}",
    )
    parser.add_argument("indexes", nargs="*", help="Indexes to reindex.")
    parser.add_argument("--all", action="store_true", help="Reindex all indexes.")
    parser.add_argument("--force", action="store_true", help="Skip confirmation prompts and countdown.")
    parser.add_argument("--verbose", action="store_true", help="Print index schema before reindexing.")
    args = parser.parse_args()

    if args.all and args.indexes:
        parser.error("--all cannot be combined with positional index arguments.")

    if not args.indexes and not args.all:
        parser.error("Provide index names as arguments, or use --all.")

    invalid = [name for name in args.indexes if name not in INDEX_NAMES]
    if invalid:
        parser.error(f"Invalid index(es): {', '.join(invalid)}. Valid options: {', '.join(INDEX_NAMES)}")

    from howler.datastore.collection import ESCollection

    ESCollection.IGNORE_ENSURE_COLLECTION = True

    if args.force:
        ESCollection.ENSURE_COLLECTION_WARNED = True

    from howler.common import loader

    ds = loader.datastore(archive_access=False)

    selected = list(dict.fromkeys(INDEX_NAMES if args.all else args.indexes))

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

        result = collection.reindex()
        print(f"Reindex of '{index_name}' complete. Success: {result}.")
