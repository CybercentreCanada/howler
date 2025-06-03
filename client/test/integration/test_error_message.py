from howler_client.client import Client
from utils import random_hash


def test_create_error(client: Client, caplog):
    client._connection.throw_on_bad_request = False
    client._connection.throw_on_max_retries = False

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
            "process": {"end": "2023-10-11, 6:38:05.081 p.m."},
        }
    )

    assert res is None

    assert "400:" in caplog.text and "Max retry reached" in caplog.text
