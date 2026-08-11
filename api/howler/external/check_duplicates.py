"""Find and optionally remove duplicate documents from an ILM collection."""

import argparse
import heapq
import sys
from collections.abc import Iterator
from typing import Any


def iter_index_ids(collection: Any, index: str, batch_size: int) -> Iterator[str]:
    """Yield document IDs from *index* in sorted order without retaining prior pages."""
    search_after = None

    while True:
        search_args = {
            "index": index,
            "query": {"match_all": {}},
            "sort": [{"id": "asc"}],
            "size": batch_size,
            "_source": False,
            "track_total_hits": False,
        }
        if search_after is not None:
            search_args["search_after"] = search_after

        response = collection.with_retries(collection.datastore.client.search, **search_args)
        hits = response["hits"]["hits"]
        if not hits:
            return

        for hit in hits:
            yield hit["_id"]

        search_after = hits[-1]["sort"]


def _push_next_id(heap: list[tuple[str, str, Iterator[str]]], index: str, document_ids: Iterator[str]) -> None:
    try:
        heapq.heappush(heap, (next(document_ids), index, document_ids))
    except StopIteration:
        pass


def iter_duplicates(collection: Any, indexes: list[str], batch_size: int) -> Iterator[tuple[str, list[str]]]:
    """Yield each duplicated ID and the physical indexes that contain it.

    This is a k-way merge over paginated, sorted searches. Its memory use is bounded by
    the number of physical indexes and one Elasticsearch result page per active iterator.
    """
    heap: list[tuple[str, str, Iterator[str]]] = []
    for index in indexes:
        document_ids = iter_index_ids(collection, index, batch_size)
        _push_next_id(heap, index, document_ids)

    while heap:
        document_id, index, document_ids = heapq.heappop(heap)
        duplicate_indexes = [index]
        _push_next_id(heap, index, document_ids)

        while heap and heap[0][0] == document_id:
            _, index, document_ids = heapq.heappop(heap)
            duplicate_indexes.append(index)
            _push_next_id(heap, index, document_ids)

        if len(duplicate_indexes) > 1:
            yield document_id, duplicate_indexes


def delete_duplicates(collection: Any, document_id: str, indexes: list[str]) -> int:
    """Delete all supplied physical-index copies of a document ID."""
    deleted = 0
    for index in indexes:
        response = collection.with_retries(collection.datastore.client.delete, index=index, id=document_id)
        if response["result"] == "deleted":
            deleted += 1
    return deleted


def main() -> int:
    """Run the interactive duplicate scan for an ILM collection."""
    parser = argparse.ArgumentParser(
        description="Find duplicate document IDs across an ILM collection's physical indexes."
    )
    parser.add_argument("collection", help="Collection name registered in the datastore.")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1_000,
        help="IDs fetched from each physical index per Elasticsearch request (default: 1000).",
    )
    args = parser.parse_args()

    if args.batch_size <= 0:
        parser.error("--batch-size must be a positive integer.")

    from howler.datastore.collection import ESCollection

    # Checking duplicates must not create collections or alter their ILM configuration.
    ESCollection.IGNORE_ENSURE_COLLECTION = True
    ESCollection.ENSURE_COLLECTION_WARNED = True

    from howler.common import loader

    datastore = loader.datastore(archive_access=False)
    collection_names = datastore.ds.get_models()
    if args.collection not in collection_names:
        parser.error(
            f"Unknown collection '{args.collection}'. Valid collections: {', '.join(sorted(collection_names))}"
        )

    collection = getattr(datastore, args.collection)
    if collection.ilm_config is None:
        print(f"Collection '{args.collection}' is not ILM-enabled; nothing to check.")
        return 0

    collection._refresh_ilm_index_name()
    indexes = collection.index_list_full
    if len(indexes) < 2:
        print(f"Collection '{args.collection}' has fewer than two physical ILM indexes; nothing to check.")
        return 0

    print(f"Scanning for duplicate IDs in: {', '.join(indexes)}")
    duplicates_found = 0
    copies_deleted = 0
    index_order = {index: position for position, index in enumerate(indexes)}

    try:
        for document_id, duplicate_indexes in iter_duplicates(collection, indexes, args.batch_size):
            duplicates_found += 1
            keep_index = min(duplicate_indexes, key=index_order.__getitem__)
            stale_indexes = [index for index in duplicate_indexes if index != keep_index]
            print(
                f"Duplicate ID '{document_id}' found in {', '.join(duplicate_indexes)}. "
                f"Keeping the newest copy in '{keep_index}'."
            )
            answer = input(f"Delete copies from {', '.join(stale_indexes)}? [yes/NO] ")
            if answer.lower() in {"y", "yes"}:
                deleted_count = delete_duplicates(collection, document_id, stale_indexes)
                copies_deleted += deleted_count
                print(f"Deleted {deleted_count} copy/copies of '{document_id}'.")
    except KeyboardInterrupt:
        print("\nInterrupted; all completed deletions have been retained.", file=sys.stderr)
        return 130
    finally:
        datastore.ds.close()

    print(f"Scan complete. Found {duplicates_found} duplicate ID(s); deleted {copies_deleted} stale copy/copies.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
