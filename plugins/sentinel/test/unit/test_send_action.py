import json
import os
from unittest.mock import patch

import requests
from howler.app import app
from howler.datastore.howler_store import HowlerDatastore


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


@patch("requests.post", mock_post)
def test_send_to_sentinel(datastore_connection: HowlerDatastore):
    with app.test_request_context():
        from sentinel.actions.send_to_sentinel import execute

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
            "title": "Alert updated in Sentinel",
            "message": "Howler has successfuly propagated changes to this alert to Sentinel.",
        }
