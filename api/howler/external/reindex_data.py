import json
import sys
import time
from typing import Callable

DELAY = 5


if __name__ == "__main__":
    print("This script will allow you to reindex all indexes in elasticsearch.")
    print("For obvious reasons, be EXTREMELY CAREFUL running this code.")
    print()
    answer = input("Are you sure you want to reindex data for an index in this cluster? [yes/NO]\n")

    if not answer.startswith("y"):
        print("Confirmation not provided, stopping.")
        sys.exit(1)

    from howler.datastore.collection import ESCollection

    ESCollection.IGNORE_ENSURE_COLLECTION = True

    from howler.common import loader

    ds = loader.datastore(archive_access=False)

    indexes: dict[str, tuple[ESCollection, Callable]] = {
        "analytic": (ds.analytic, ds.analytic.reindex),
        "hit": (ds.hit, ds.hit.reindex),
        "view": (ds.view, ds.view.reindex),
        "template": (ds.template, ds.template.reindex),
        "overview": (ds.overview, ds.overview.reindex),
        "action": (ds.action, ds.action.reindex),
        "user": (ds.user, ds.user.reindex),
        "dossier": (ds.dossier, ds.dossier.reindex),
    }

    print("Which index will you reindex?")
    index_answer = input(", ".join(indexes.keys()) + "\n> ")

    if index_answer not in indexes:
        print("Invalid index provided, stopping.")
        sys.exit(1)

    print("Index schema:")
    print(json.dumps(indexes[index_answer][0]._get_index_mappings(), indent=2))

    print("\nYou will be reindexing the following indexes:")
    print("\n".join(indexes[index_answer][0].index_list_full))

    answer = input(("\nAre you sure you want to reindex these indexes? [yes/NO]\n"))
    print()

    if not answer.startswith("y"):
        print("Confirmation not provided, stopping.")
        sys.exit(1)

    for i in range(2 * DELAY):
        print(f"Reindexing in {2 * DELAY - i}...", end="\r")
        time.sleep(1)

    print()

    result = indexes[index_answer][1]()

    print(f"Reindex complete. Success: {result}.")
