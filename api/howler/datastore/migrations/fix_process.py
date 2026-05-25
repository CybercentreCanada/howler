from howler.common.loader import datastore
from howler.common.logging import get_logger

logger = get_logger(__file__)


def migrate():
    logger.info("Checking for migration preconditions")

    collection = datastore().hit

    result = collection.search("_exists_:process.parent.start", as_obj=False, track_total_hits=True, rows=0)

    if result["total"] > 0:
        logger.info("Preconditions met, continuing.")

        db_size = collection.search("howler.id:*", track_total_hits=True, rows=0)["total"]
        logger.info("Database size pre-migration: %s", db_size)
    else:
        logger.info("Preconditions not met, stopping")
        return

    logger.info("We will delete %s hits. Continue?", result["total"])
    prompt_result = input("y/[n]")

    if prompt_result.lower() != "y":
        logger.warning("Did not receive an OK, stopping")
        return

    logger.info("Deleting...")
    collection.delete_by_query("_exists_:process.parent.start")
    collection.commit()

    db_size_after = collection.search("howler.id:*", track_total_hits=True, rows=0)["total"]
    logger.info("Database size post-migration: %s", db_size_after)

    logger.info("Migration complete")


if __name__ == "__main__":
    migrate()
