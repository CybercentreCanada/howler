"""Verify that the refresh parameter works properly for one of the ingestion endpoints."""

from utils import random_hash

from howler_client.client import Client


def test_create_with_refresh(client: Client):
    res = client.v2.ingest.create(
        "hit",
        {
            "howler.analytic": "Test Refresh",
            "howler.score": 0,
            "howler.hash": random_hash(),
        },
    )

    assert len(res) == 1
    refresh_false_id = res[0]
    assert client.search.hit(f"howler.id:{refresh_false_id}")["total"] == 0, (
        "The record should not be searchable yet when refresh=false"
    )

    res = client.v2.ingest.create(
        "hit",
        {
            "howler.analytic": "Test Refresh",
            "howler.score": 0,
            "howler.hash": random_hash(),
        },
        refresh=True,
    )

    assert len(res) == 1
    refresh_true_id = res[0]
    assert client.search.hit(f"howler.id:{refresh_true_id}")["total"] == 1, (
        "The record should be immediately searchable when refresh=true"
    )

    res = client.v2.ingest.create(
        "hit",
        {
            "howler.analytic": "Test Refresh",
            "howler.score": 0,
            "howler.hash": random_hash(),
        },
        refresh="wait_for",
    )

    assert len(res) == 1
    refresh_wait_id = res[0]
    assert client.search.hit(f"howler.id:{refresh_wait_id}")["total"] == 1, (
        "The record should be searchable after call return when refresh=wait_for"
    )
