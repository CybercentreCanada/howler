from unittest.mock import MagicMock, call

from howler.external.check_duplicates import delete_duplicates, iter_duplicates


class FakeClient:
    """In-memory Elasticsearch client with search_after pagination."""

    def __init__(self, documents: dict[str, list[str]]):
        self.documents = documents
        self.delete = MagicMock(return_value={"result": "deleted"})

    def search(self, *, index, search_after=None, size, **kwargs):
        document_ids = self.documents[index]
        if search_after is not None:
            document_ids = [document_id for document_id in document_ids if document_id > search_after[0]]

        hits = [{"_id": document_id, "sort": [document_id]} for document_id in document_ids[:size]]
        return {"hits": {"hits": hits}}


class FakeCollection:
    """Collection wrapper that delegates retry calls to the in-memory client."""

    def __init__(self, documents: dict[str, list[str]]):
        self.datastore = MagicMock()
        self.datastore.client = FakeClient(documents)

    def with_retries(self, func, *args, **kwargs):
        return func(*args, **kwargs)


def test_iter_duplicates_merges_paginated_physical_indexes():
    """Duplicate IDs are found without loading every physical index into memory."""
    indexes = ["howler-hit-000003", "howler-hit-000002", "howler-hit-000001"]
    collection = FakeCollection(
        {
            indexes[0]: ["a", "b", "e"],
            indexes[1]: ["b", "c", "e"],
            indexes[2]: ["a", "e"],
        }
    )

    assert list(iter_duplicates(collection, indexes, batch_size=1)) == [
        ("a", [indexes[2], indexes[0]]),
        ("b", [indexes[1], indexes[0]]),
        ("e", [indexes[2], indexes[1], indexes[0]]),
    ]


def test_delete_duplicates_deletes_only_requested_physical_copies():
    """Deletion calls target old indexes directly rather than the rollover alias."""
    collection = FakeCollection({})

    assert delete_duplicates(collection, "duplicate-id", ["howler-hit-000001", "howler-hit-000002"]) == 2

    assert collection.datastore.client.delete.call_args_list == [
        call(index="howler-hit-000001", id="duplicate-id"),
        call(index="howler-hit-000002", id="duplicate-id"),
    ]
