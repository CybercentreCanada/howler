from unittest.mock import MagicMock

import pytest

from howler.datastore.collection import ESCollection


@pytest.fixture()
def collection(monkeypatch):
    monkeypatch.setattr(ESCollection, "IGNORE_ENSURE_COLLECTION", True)
    datastore = MagicMock()
    datastore.client.count.return_value = {"count": 8}
    return ESCollection(datastore, "testcol")


@pytest.mark.parametrize(
    ("filters", "expected_filters"),
    [
        (["status:open", "owner:alice"], ["status:open", "owner:alice", "classification:U"]),
        ("status:open", ["status:open", "classification:U"]),
        (None, ["classification:U"]),
    ],
)
def test_count_applies_access_control_without_mutating_filters(collection, filters, expected_filters):
    original_filters = filters.copy() if isinstance(filters, list) else filters

    result = collection.count("id:*", filters, access_control="classification:U")

    assert result == {"count": 8}
    collection.datastore.client.count.assert_called_once_with(
        index=collection.name,
        query={
            "bool": {
                "must": {"query_string": {"query": "id:*"}},
                "filter": [{"query_string": {"query": value}} for value in expected_filters],
            }
        },
    )
    assert filters == original_filters


@pytest.mark.parametrize("access_control", [None, ""])
def test_count_keeps_admin_count_unrestricted_by_empty_access_control(collection, access_control):
    filters = ["status:open"]

    result = collection.count("id:*", filters, access_control=access_control)

    assert result == {"count": 8}
    collection.datastore.client.count.assert_called_once_with(
        index=collection.name,
        query={
            "bool": {
                "must": {"query_string": {"query": "id:*"}},
                "filter": [{"query_string": {"query": "status:open"}}],
            }
        },
    )
    assert filters == ["status:open"]
