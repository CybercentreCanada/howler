import sys
import time

DELAY = 5

if __name__ == "__main__":
    print("This script will allow you to completely remove all howler data and indexes from elasticsearch.")
    print("For obvious reasons, be EXTREMELY CAREFUL running this code.")

    for i in range(DELAY):
        print(f"Continuing in {str(DELAY - i)}...", end="\r")
        time.sleep(1)
    print()
    index = input("\nWhat index do you want to wipe? (Supported options are [hit, user]):\n")

    if index not in ["hit", "user"]:
        print("Invalid index.")
        sys.exit(1)

    answer = input(f"\nSelected index is {index}. Are you sure you want to wipe all data in this index? [yes/NO]\n")

    if not answer.startswith("y"):
        print("Confirmation not provided, stopping.")
        sys.exit(1)

    answer = input(
        (
            "\nSeriously, this will completely wipe the index. It'll go poof.\n"
            "Are you sure you want to wipe all data in this index? [yes/NO]\n"
        )
    )
    print()

    if not answer.startswith("y"):
        print("Confirmation not provided, stopping.")
        sys.exit(1)

    for i in range(2 * DELAY):
        print(f"Deleting {index} in {2 * DELAY - i}...", end="\r")
        time.sleep(1)

    print()

    from howler.datastore.collection import ESCollection

    ESCollection.IGNORE_ENSURE_COLLECTION = True

    from howler.common import loader
    from howler.odm.random_data import wipe_hits, wipe_users

    ds = loader.datastore(archive_access=False)

    if index == "user":
        wipe_users(ds)
    else:
        wipe_hits(ds)

    print(f"Wiped {index}.")
