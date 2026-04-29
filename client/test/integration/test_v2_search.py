"""Integration tests for the v2 Search client module."""

import hashlib
import random
import time

from howler_client.client import Client


def _random_hash() -> str:
    return hashlib.sha256(random.randbytes(128)).hexdigest()


def _create_hit(client: Client, analytic: str = "Search Integration Test") -> str:
    """Create a hit and return its howler.id."""
    result = client.v2.ingest.create(
        "hit",
        {
            "howler": {
                "analytic": analytic,
                "detection": "test_search_v2",
                "hash": _random_hash(),
                "score": 0,
            },
        },
    )
    return result["valid"][0]["howler"]["id"]


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------


def test_search_single_index(client: Client):
    hit_id = _create_hit(client)
    time.sleep(1)

    result = client.v2.search("hit", f"howler.id:{hit_id}")

    assert result["total"] >= 1
    found_ids = [item["howler"]["id"] for item in result["items"]]
    assert hit_id in found_ids


def test_search_with_fl(client: Client):
    hit_id = _create_hit(client)
    time.sleep(1)

    result = client.v2.search("hit", f"howler.id:{hit_id}", fl="howler.id")

    assert result["total"] >= 1
    item = result["items"][0]
    assert "howler" in item


def test_search_with_sort(client: Client):
    _create_hit(client)
    time.sleep(1)

    result = client.v2.search("hit", "*:*", sort="event.created desc", rows=5)

    assert result["total"] >= 1
    assert len(result["items"]) <= 5


def test_search_with_offset(client: Client):
    _create_hit(client)
    _create_hit(client)
    time.sleep(1)

    page1 = client.v2.search("hit", "*:*", rows=1, offset=0)
    page2 = client.v2.search("hit", "*:*", rows=1, offset=1)

    assert page1["total"] == page2["total"]
    if page1["total"] > 1:
        assert page1["items"][0]["howler"]["id"] != page2["items"][0]["howler"]["id"]


# ---------------------------------------------------------------------------
# count
# ---------------------------------------------------------------------------


def test_count(client: Client):
    _create_hit(client)
    time.sleep(1)

    count = client.v2.search.count("hit", "*:*")

    assert count >= 1


# ---------------------------------------------------------------------------
# explain
# ---------------------------------------------------------------------------


def test_explain_valid_query(client: Client):
    result = client.v2.search.explain("hit", "howler.id:*")

    assert result is not None


# ---------------------------------------------------------------------------
# facet
# ---------------------------------------------------------------------------


def test_facet_single_field(client: Client):
    _create_hit(client, analytic="FacetAnalytic")
    time.sleep(1)

    result = client.v2.search.facet("hit", ["howler.analytic"], "*:*")

    assert "howler.analytic" in result
    assert "FacetAnalytic" in result["howler.analytic"]


def test_facet_multiple_fields(client: Client):
    _create_hit(client)
    time.sleep(1)

    result = client.v2.search.facet("hit", ["howler.analytic", "howler.detection"], "*:*")

    assert "howler.analytic" in result
    assert "howler.detection" in result
