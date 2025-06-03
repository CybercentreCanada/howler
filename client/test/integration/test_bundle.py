import datetime

import pytest

from howler_client.client import Client
from howler_client.common.utils import ClientError

TOOL_NAME = "Bundle Test Client"

MAP = {
    "file.sha256": ["file.hash.sha256", "howler.hash"],
    "file.name": ["file.name"],
    "src_ip": ["source.ip", "related.ip"],
    "dest_ip": ["destination.ip", "related.ip"],
    "time.created": ["event.start"],
    "time.completed": ["event.end"],
    "score": ["howler.score"],
}

BUNDLE = {"score": 0.5}

HITS = [
    {
        "src_ip": "43.228.141.216",
        "dest_ip": "31.46.39.115",
        "file": {
            "name": "cool_file.exe",
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        },
        "time": {
            "created": datetime.datetime(2020, 5, 17).isoformat() + "Z",
            "completed": datetime.datetime(2020, 5, 18).isoformat() + "Z",
        },
    },
    {
        "src_ip": "248.59.92.198",
        "dest_ip": "148.252.23.152",
        "file": {
            "name": "lame_file.exe",
            "sha256": "abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890",
        },
        "time": {
            "created": datetime.datetime(2022, 5, 17).isoformat() + "Z",
            "completed": datetime.datetime(2022, 9, 18).isoformat() + "Z",
        },
    },
]


def test_create_from_map(client: Client):
    res = client.bundle.create_from_map(TOOL_NAME, BUNDLE, MAP, HITS)

    assert len(res) == (len(HITS) + 1)
    for hit in res:
        assert "error" in hit
        assert "id" in hit
        assert hit["error"] is None
        assert isinstance(hit["id"], str)


def test_create(client: Client):
    res = client.bundle.create(
        {
            "howler": {"analytic": "Bundle Test Stuff", "score": 0.8},
        },
        {
            "howler": {
                "analytic": "A test for creating a hit",
                "score": 0.8,
                "outline": {
                    "threat": "10.0.0.1",
                    "target": "asdf123",
                    "indicators": ["me.ps1"],
                    "summary": "This is a summary",
                },
            },
        },
    )

    assert res["howler"]["is_bundle"]


def test_remove(client: Client):
    bundles = client.search.hit("howler.is_bundle:true")["items"]

    client.bundle.remove(bundles[0]["howler"]["id"], bundles[0]["howler"]["hits"])

    with pytest.raises(AttributeError):
        client.bundle(bundles[0]["howler"]["id"])

    client.bundle.remove(bundles[1]["howler"]["id"], "*")

    with pytest.raises(AttributeError):
        client.bundle(bundles[1]["howler"]["id"])


def test_create_no_children(client: Client):
    with pytest.raises(ClientError):
        client.bundle.create(
            {
                "howler": {
                    "analytic": "Bundle testerino",
                    "score": 0.8,
                }
            }
        )


def test_create_existing_children(client: Client):
    not_bundles = client.search.hit("howler.is_bundle:false", rows=3)["items"]
    client.bundle.create(
        {
            "howler": {
                "analytic": "Bundle testerino",
                "score": 0.8,
                "hits": [hit["howler"]["id"] for hit in not_bundles],
            }
        }
    )
