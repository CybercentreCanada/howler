import sys
import time

DELAY = 5

if __name__ == "__main__":
    print("This script will allow you to reindex all indexes in elasticsearch.")
    print("For obvious reasons, be EXTREMELY CAREFUL running this code.")

    for i in range(DELAY):
        print(f"Continuing in {str(DELAY - i)}...", end="\r")
        time.sleep(1)
    print()
    answer = input("Are you sure you want to reindex all data in this cluster? [yes/NO]\n")

    if not answer.startswith("y"):
        print("Confirmation not provided, stopping.")
        sys.exit(1)

    from howler.datastore.collection import ESCollection

    ESCollection.IGNORE_ENSURE_COLLECTION = True

    from howler.common import loader

    ds = loader.datastore(archive_access=False)

    print("You will be reindexing the following indexes:")
    print("\n".join(ds.hit.index_list_full))

    answer = input(("\nAre you sure you want to reindex all indexes? [yes/NO]\n"))
    print()

    if not answer.startswith("y"):
        print("Confirmation not provided, stopping.")
        sys.exit(1)

    for i in range(2 * DELAY):
        print(f"Reindexing in {2 * DELAY - i}...", end="\r")
        time.sleep(1)

    print()

    result = ds.hit.reindex()

    print(f"Reindex complete. Success: {result}.")
