import sys
import time
from typing import Callable

DELAY = 5


if __name__ == "__main__":
    print("This script will allow you to reindex all indexes in elasticsearch.")
    print("For obvious reasons, be EXTREMELY CAREFUL running this code.")

    for i in range(DELAY):
        print(f"Continuing in {str(DELAY - i)}...", end="\r")
        time.sleep(1)
    print()
    answer = input("Are you sure you want to reindex data for an index in this cluster? [yes/NO]\n")

    if not answer.startswith("y"):
        print("Confirmation not provided, stopping.")
        sys.exit(1)

    from howler.datastore.collection import ESCollection

    ESCollection.IGNORE_ENSURE_COLLECTION = True

    from howler.common import loader

    ds = loader.datastore(archive_access=False)

    indexes: dict[str, tuple[list[str], Callable]] = {
        "analytic": (ds.analytic.index_list_full, ds.analytic.reindex),
        "hit": (ds.hit.index_list_full, ds.hit.reindex),
        "view": (ds.view.index_list_full, ds.view.reindex),
        "template": (ds.template.index_list_full, ds.template.reindex),
        "overview": (ds.overview.index_list_full, ds.overview.reindex),
        "action": (ds.action.index_list_full, ds.action.reindex),
        "user": (ds.user.index_list_full, ds.user.reindex),
        "dossier": (ds.dossier.index_list_full, ds.dossier.reindex),
    }

    print("Which index will you reindex?")
    index_answer = input(", ".join(indexes.keys()) + "\n> ")

    if index_answer not in indexes:
        print("Invalid index provided, stopping.")
        sys.exit(1)

    print("You will be reindexing the following indexes:")
    print("\n".join(indexes[index_answer][0]))

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
