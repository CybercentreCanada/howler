import json
from pathlib import Path
from unittest.mock import patch

import requests
from howler.app import app
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.hit import Hit
from howler.odm.randomizer import random_model_obj

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

        broken_hit = random_model_obj(Hit)

        datastore_connection.hit.save(broken_hit.howler.id, broken_hit)
        datastore_connection.hit.commit()

        result = execute(f"howler.id:{broken_hit.howler.id}")

        assert result[0] == {
            "query": f"howler.id:{broken_hit.howler.id}",
            "outcome": "error",
            "title": "Invalid Tenant ID",
            "message": (
                f"The tenant ID ({broken_hit.azure.tenant_id}) associated with this alert has not been correctly "
                "configured."
            ),
        }


@patch("requests.post", mock_post)
@patch("requests.get", mock_get)
@patch("requests.patch", mock_patch)
def test_update_defender_xdr_alert(datastore_connection: HowlerDatastore):
    with app.test_request_context():
        from sentinel.actions.update_defender_xdr_alert import execute

        hit: Hit = datastore_connection.hit.search("howler.id:*", fl="howler.id", rows=1)["items"][0]
        hit_id = hit.howler.id

        result = execute(f"howler.id:{hit_id}")

        assert result[0] == {
            "query": f"howler.id:{hit_id}",
            "outcome": "success",
            "title": "Alert updated in XDR Defender",
            "message": "Howler has successfully propagated changes to this alert to XDR Defender.",
        }
