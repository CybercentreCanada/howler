"""Integration tests for the v2 Case client module."""

import time

import pytest

from howler_client.client import Client
from howler_client.common.utils import ClientError


def _create_case(client: Client, title: str = "Integration Test Case", summary: str = "Auto-generated") -> dict:
    """Helper: create a case and return its data."""
    return client.v2.case.create({"title": title, "summary": summary})


def _create_hit_id(client: Client) -> str:
    """Helper: create a hit via v2 ingest and return its howler.id."""
    import hashlib
    import random

    _hash = hashlib.sha256(random.randbytes(128)).hexdigest()
    result = client.v2.ingest.create(
        "hit",
        {
            "howler": {
                "analytic": "Case Integration Test",
                "detection": "test_case_integration",
                "hash": _hash,
                "score": 0,
            },
        },
    )
    assert len(result["valid"]) == 1
    hit_id = result["valid"][0]["howler"]["id"]
    time.sleep(1)
    return hit_id


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_create_case(client: Client):
    case = _create_case(client, "Create Test")

    assert case["case_id"]
    assert case["title"] == "Create Test"


def test_get_case(client: Client):
    case = _create_case(client)

    fetched = client.v2.case(case["case_id"])

    assert fetched["case_id"] == case["case_id"]
    assert fetched["title"] == case["title"]


def test_update_case(client: Client):
    case = _create_case(client)

    updated = client.v2.case.update(case["case_id"], {"title": "Updated Title"})

    assert updated["title"] == "Updated Title"
    assert updated["case_id"] == case["case_id"]


def test_delete_case(client: Client):
    case = _create_case(client)

    client.v2.case.delete([case["case_id"]])

    with pytest.raises(ClientError):
        client.v2.case(case["case_id"])


def test_hide_case(client: Client):
    case = _create_case(client)

    client.v2.case.hide([case["case_id"]])

    hidden = client.v2.case(case["case_id"])
    assert hidden["visible"] is False


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


def test_append_hit_item(client: Client):
    case = _create_case(client)
    hit_id = _create_hit_id(client)

    updated = client.v2.case.append_item(case["case_id"], "hit", hit_id, "alerts/test")

    assert any(item["value"] == hit_id for item in updated["items"])


def test_append_reference_item(client: Client):
    case = _create_case(client)

    updated = client.v2.case.append_item(case["case_id"], "reference", "https://example.com", "refs/example")

    assert any(item["value"] == "https://example.com" for item in updated["items"])


def test_delete_items(client: Client):
    case = _create_case(client)
    client.v2.case.append_item(case["case_id"], "reference", "https://to-delete.com", "refs/delete")

    updated = client.v2.case.delete_items(case["case_id"], ["https://to-delete.com"])

    assert not any(item["value"] == "https://to-delete.com" for item in updated["items"])


def test_rename_item(client: Client):
    case = _create_case(client)
    client.v2.case.append_item(case["case_id"], "reference", "https://rename.com", "refs/old-name")

    updated = client.v2.case.rename_item(case["case_id"], "https://rename.com", "refs/new-name")

    item = next(i for i in updated["items"] if i["value"] == "https://rename.com")
    assert item["path"] == "refs/new-name"


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def test_add_rule(client: Client):
    case = _create_case(client)
    rule_data = {"query": "howler.analytic:IntegrationTest*", "destination": "alerts"}

    updated = client.v2.case.add_rule(case["case_id"], rule_data)

    assert len(updated["rules"]) == 1
    assert updated["rules"][0]["query"] == "howler.analytic:IntegrationTest*"
    assert updated["rules"][0]["destination"] == "alerts"


def test_delete_rule(client: Client):
    case = _create_case(client)
    updated = client.v2.case.add_rule(case["case_id"], {"query": "*:*", "destination": "alerts"})
    rule_id = updated["rules"][0]["rule_id"]

    updated = client.v2.case.delete_rule(case["case_id"], rule_id)

    assert len(updated["rules"]) == 0


def test_update_rule(client: Client):
    case = _create_case(client)
    updated = client.v2.case.add_rule(case["case_id"], {"query": "*:*", "destination": "alerts"})
    rule_id = updated["rules"][0]["rule_id"]

    updated = client.v2.case.update_rule(case["case_id"], rule_id, {"enabled": False})

    rule = next(r for r in updated["rules"] if r["rule_id"] == rule_id)
    assert rule["enabled"] is False
