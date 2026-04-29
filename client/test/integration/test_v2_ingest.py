"""Integration tests for the v2 Ingest client module."""

import hashlib
import random
import time

import pytest

from howler_client.client import Client
from howler_client.common.utils import ClientError


def _random_hash() -> str:
    return hashlib.sha256(random.randbytes(128)).hexdigest()


def _sample_hit(**overrides) -> dict:
    data = {
        "howler": {
            "analytic": "Ingest Integration Test",
            "detection": "test_ingest",
            "hash": _random_hash(),
            "score": 0,
        },
    }
    data["howler"].update(overrides)
    return data


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


def test_create_single_hit(client: Client):
    result = client.v2.ingest.create("hit", _sample_hit())

    assert len(result) == 1


def test_create_multiple_hits(client: Client):
    hits = [_sample_hit(), _sample_hit()]

    result = client.v2.ingest.create("hit", hits)

    assert len(result) == 2


def test_create_invalid_hit(client: Client):
    with pytest.raises(ClientError) as exc_info:
        client.v2.ingest.create("hit", {})

    assert exc_info.value.api_response is not None


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def test_validate_valid_hit(client: Client):
    result = client.v2.ingest.validate("hit", _sample_hit())

    assert len(result["valid"]) == 1
    assert len(result["invalid"]) == 0


def test_validate_invalid_hit(client: Client):
    result = client.v2.ingest.validate("hit", {})

    assert len(result["invalid"]) == 1
    assert result["invalid"][0]["error"]


# ---------------------------------------------------------------------------
# overwrite
# ---------------------------------------------------------------------------


def test_overwrite_hit(client: Client):
    hit = _sample_hit()
    result = client.v2.ingest.create("hit", hit)
    hit_id = result[0]

    time.sleep(1)

    updated = client.v2.ingest.overwrite("hit", hit_id, {"howler": {"score": 99}})

    assert updated["howler"]["score"] == 99


# ---------------------------------------------------------------------------
# update_by_query
# ---------------------------------------------------------------------------


def test_update_by_query(client: Client):
    hit = _sample_hit()
    result = client.v2.ingest.create("hit", hit)
    hit_id = result[0]

    time.sleep(1)

    update_result = client.v2.ingest.update_by_query(
        "hit",
        f"howler.id:{hit_id}",
        [("SET", "howler.score", 42)],
    )

    assert update_result["success"] is True


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


def test_delete_hits(client: Client):
    result = client.v2.ingest.create("hit", _sample_hit())
    hit_id = result[0]

    time.sleep(1)

    # delete returns no_content (204) → None
    client.v2.ingest.delete("hit", [hit_id])
