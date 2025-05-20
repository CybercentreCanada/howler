import json
from typing import Any

from conftest import get_api_data


def test_create_valid_hits(datastore_connection, login_session):
    """Test that /api/v1/hit creates hits using valid data"""
    session, host = login_session

    data: list[dict[str, Any]] = [
        {
            "howler": {
                "analytic": "A test for creating a hit",
                "hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
                "score": "0.8",
                "outline": {
                    "threat": "10.0.0.3",
                    "target": "third target",
                    "indicators": ["test.ps1"],
                    "summary": "This is a summary",
                },
            },
            "process": {
                "start": "2024-06-05 12:23:53.170770+00:00",
                "end": "2024-06-05 12:23:53.170770+00:00",
                "user": {"domain": "google.ca"},
                "parent": {
                    "start": "2024-06-05 12:23:53.170770+00:00",
                    "end": "2024-06-05 12:23:53.170770+00:00",
                },
            },
        },
    ]

    # POST hits
    response = get_api_data(session=session, url=f"{host}/api/v1/hit/", data=json.dumps(data), method="POST")
    assert len(response["invalid"]) == 0
