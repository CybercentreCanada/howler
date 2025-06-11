import json
import os
from pathlib import Path
from unittest.mock import patch

import requests
from howler.app import app
from howler.datastore.howler_store import HowlerDatastore

with (Path(__file__).parent / "sentinel.json").open() as _alert:
    SENTINEL_ALERT = json.load(_alert)


def mock_post(url: str, **kwargs):
    res = requests.Response()
    res.status_code = 200
    res.headers["Content-Type"] = "application/json"
    if url.startswith("https://login.microsoftonline.com"):
        res._content = json.dumps({"access_token": "potato"}).encode()
    elif "ingest" in url:
        assert (
            url
            == "https://dcething.ingest.monitor.azure.com/dataCollectionRules/dcrthing/streams/Custom-Howler?api-version=2021-11-01-preview"
        )

    return res


def mock_get(url: str, **kwargs):
    res = requests.Response()
    res.status_code = 200
    res.headers["Content-Type"] = "application/json"
    if url.startswith("https://graph.microsoft.com"):
        res._content = json.dumps(SENTINEL_ALERT).encode()

    return res


def mock_patch(url: str, **kwargs):
    res = requests.Response()
    res.status_code = 200
    res.headers["Content-Type"] = "application/json"

    return res


@patch("requests.post", mock_post)
def test_send_to_sentinel(datastore_connection: HowlerDatastore):
    with app.test_request_context():
        from sentinel.actions.send_to_sentinel import execute

        hit_id = datastore_connection.hit.search("howler.id:*", fl="howler.id", rows=1)["items"][0].howler.id

        result = execute(f"howler.id:{hit_id}")

        assert result[0] == {
            "query": f"howler.id:{hit_id}",
            "outcome": "success",
            "title": "Alert updated in Sentinel",
            "message": "Howler has successfully propagated changes to this alert to Sentinel.",
        }


@patch("requests.post", mock_post)
@patch("requests.get", mock_get)
@patch("requests.patch", mock_patch)
def test_update_defender_xdr_alert(datastore_connection: HowlerDatastore):
    with app.test_request_context():
        from sentinel.actions.update_defender_xdr_alert import execute

        hit_id = datastore_connection.hit.search("howler.id:*", fl="howler.id", rows=1)["items"][0].howler.id

        if "HOWLER_SENTINEL_INGEST_CREDENTIALS" not in os.environ:
            os.environ["HOWLER_SENTINEL_INGEST_CREDENTIALS"] = (
                '{"client_secret": "client secret", "client_id": "client id", "tenant_id": "tenant id", "dce": "dceth'
                'ing", "dcr": "dcrthing", "table": "Custom-Howler"}'
            )

        result = execute(f"howler.id:{hit_id}")

        assert result[0] == {
            "query": f"howler.id:{hit_id}",
            "outcome": "success",
            "title": "Alert updated in XDR Defender",
            "message": "Howler has successfully propagated changes to this alert to XDR Defender.",
        }
