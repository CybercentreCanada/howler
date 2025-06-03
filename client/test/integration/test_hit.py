import datetime
import time

import pytest
from utils import create_and_get_comment, random_hash

from howler_client.client import Client
from howler_client.common.utils import ClientError
from howler_client.module.hit import UPDATE_INC, UPDATE_SET

TOOL_NAME = "test"

MAP = {
    "file.sha256": ["file.hash.sha256", "howler.hash"],
    "file.name": ["file.name"],
    "src_ip": ["source.ip", "related.ip"],
    "dest_ip": ["destination.ip", "related.ip"],
    "time.created": ["event.start"],
    "time.completed": ["event.end"],
    "cloud.availability_zone": ["cloud.availability_zone"],
    # TODO: Uncomment this once ignore extra values is permitted
    # "additional_field": ["additional_field"],
}


HITS = [
    {
        "src_ip": "43.228.141.216",
        "dest_ip": "31.46.39.115",
        "file": {
            "name": "cool_file.exe",
            "sha256": random_hash(),
        },
        "time": {
            "created": datetime.datetime(2020, 5, 17).isoformat() + "Z",
            "completed": datetime.datetime(2020, 5, 18).isoformat() + "Z",
        },
        "cloud": {"availability_zone": "deprecated"},
    },
    {
        "src_ip": "248.59.92.198",
        "dest_ip": "148.252.23.152",
        "file": {
            "name": "lame_file.exe",
            "sha256": random_hash(),
        },
        "time": {
            "created": datetime.datetime(2022, 5, 17).isoformat() + "Z",
            "completed": datetime.datetime(2022, 9, 18).isoformat() + "Z",
        },
        # TODO: Uncomment this once ignore extra values is permitted
        # "additional_field": "additional_value",
    },
]


def test_create_from_map(client, caplog):
    res = client.hit.create_from_map(TOOL_NAME, MAP, HITS)

    assert len(res) == len(HITS)
    for hit in res:
        assert "warn" in hit
        assert "error" in hit
        assert "id" in hit
        assert hit["error"] is None
        assert isinstance(hit["id"], str)

    assert all("deprecated" in msg for msg in caplog.messages)


def test_broken_map(client):
    # Test broken map
    broken_map = {
        "file.sha256": ["file.sha256"],
    }

    with pytest.raises(ClientError):
        client.hit.create_from_map(TOOL_NAME, broken_map, HITS)


def test_invalid_data(client):
    invalid_hits = [
        {
            "src_ip": "uh oh",
            "dest_ip": "this data",
            "file": {"name": "doesn't seem", "sha256": "very good"},
            "time": {
                "created": "oh no",
                "completed": "send help",
            },
        }
    ]

    with pytest.raises(ClientError):
        client.hit.create_from_map(TOOL_NAME, MAP, invalid_hits)


def test_deprecated_data(client, caplog):
    deprecated_hits = [
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
            "cloud": {"availability_zone": "deprecated"},
        }
    ]

    res = client.hit.create_from_map(TOOL_NAME, MAP, deprecated_hits)

    for hit in res:
        assert len(hit["warn"]) == 1

    assert all("deprecated" in msg for msg in caplog.messages)


def test_create(client):
    res = client.hit.create(
        {
            "howler": {
                "analytic": "A test for creating a hit",
                "score": 0.8,
                "hash": random_hash(),
                "outline": {
                    "threat": "10.0.0.1",
                    "target": "asdf123",
                    "indicators": ["me.ps1"],
                    "summary": "This is a summary",
                },
            },
        }
    )

    assert len(res["valid"]) == 1
    assert len(res["invalid"]) == 0


def test_duplicate(client):
    _random_hash = random_hash()
    client.hit.create(
        {
            "howler.analytic": "Test Dupes",
            "howler.score": 0,
            "howler.hash": _random_hash,
        }
    )

    time.sleep(1)

    total = client.search.hit("howler.id:*")["total"]

    client.hit.create(
        [
            {
                "howler.analytic": "Test Dupes",
                "howler.score": 0,
                "howler.hash": _random_hash,
            },
            {
                "howler.analytic": "Test Dupes",
                "howler.score": 0,
                "howler.hash": random_hash(),
            },
        ]
    )

    time.sleep(1)

    assert client.search.hit("howler.id:*")["total"] == total + 1


def test_create_invalid(caplog, client: Client):
    try:
        client.hit.create(
            [
                {
                    "howler.analytic": "Matt Test",
                    "howler.score": 0.8,
                    "howler.outline.threat": "10.0.0.1",
                    "howler.outline.target": "asdf123",
                    "howler.outline.indicators": ["me.ps1"],
                    "howler.outline.summary": "This is a summary",
                },
                {
                    "howler.analytic": "Matt Test",
                    # "howler.score": 0.8,
                    "howler.outline.threat": "10.0.0.1",
                    "howler.outline.target": "asdf123",
                    "howler.outline.indicators": ["me.ps1"],
                    "howler.outline.summary": "This is a summary",
                },
            ]
        )
    except ClientError as e:
        assert len(e.api_response["valid"]) == 1
        assert len(e.api_response["invalid"]) == 1
        assert e.api_response["invalid"][0]["error"] == "[hit.howler.score]: value is missing from the object!"


def test_add_comment(client: Client):
    result, comment = create_and_get_comment(client, "this is a very unique test comment")

    assert comment is not None

    result["howler"]["log"][len(result["howler"]["log"]) - 1]["explanation"] == "Hit updated by admin"


def test_update_comment(client: Client):
    result, comment = create_and_get_comment(client, "this is a very unique test comment made by me")

    comment_value = "this comment was updated by the howler-client."

    result = client.hit.comment.edit(
        result["howler"]["id"],
        comment_value,
        comment["id"],
    )

    comment = next((c for c in result["howler"]["comment"] if c["value"] == comment_value), None)

    assert comment is not None

    result["howler"]["log"][len(result["howler"]["log"]) - 1]["explanation"] == "Hit updated by admin"


def test_delete_comment(client: Client):
    comment_value = "this is a very unique test comment made by me that's going to be deleted"
    result, comment = create_and_get_comment(client, comment_value)
    comments_count = len(result["howler"]["comment"])

    result = client.hit.comment.delete(
        result["howler"]["id"],
        [comment["id"]],
    )

    comment = next((c for c in result["howler"]["comment"] if c["value"] == comment_value), None)
    comments_count = comments_count - len(result["howler"]["comment"])

    assert comment is None
    assert comments_count == 1

    result["howler"]["log"][len(result["howler"]["log"]) - 1]["explanation"] == "Hit updated by admin"


def test_update(client: Client):
    hit_to_update = client.search.hit("howler.id:*", rows=1)["items"][0]

    result = client.hit.update(
        hit_to_update["howler"]["id"],
        [
            (
                UPDATE_SET,
                "howler.score",
                hit_to_update["howler"]["score"] + 100,
            )
        ],
    )
    assert result["howler"]["score"] == hit_to_update["howler"]["score"] + 100

    result["howler"]["log"][len(result["howler"]["log"]) - 1]["explanation"] == "Hit updated by admin"


def test_update_by_query(client: Client):
    hit_to_check = client.search.hit("howler.id:*", rows=1)["items"][0]

    client.hit.update_by_query(
        "howler.id:*",
        [
            (
                UPDATE_INC,
                "howler.score",
                100,
            )
        ],
    )

    time.sleep(2)

    hit_to_check_after = client.search.hit(f"howler.id:{hit_to_check['howler']['id']}", rows=1)["items"][0]

    assert hit_to_check_after["howler"]["score"] == hit_to_check["howler"]["score"] + 100

    hit_to_check_after["howler"]["log"][len(hit_to_check_after["howler"]["log"]) - 1][
        "explanation"
    ] == "Hit updated by admin"


def test_delete(client: Client):
    total = client.search.hit("howler.id:*")["total"]

    res = client.hit.create_from_map(TOOL_NAME, MAP, HITS)

    assert client.hit.delete([new_hit["id"] for new_hit in res]) is None

    assert total == client.search.hit("howler.id:*")["total"]
