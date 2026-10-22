import json
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from howler.app import app
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.hit import Hit
from howler.odm.randomizer import random_model_obj
from howler.services import hit_service

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

        hit, _ = hit_service.convert_hit(
            {
                "howler.analytic": "MSGraph",
                "howler.detection": "Source alert",
                "organization": {"name": "Example", "id": "tenant-id"},
                "rule": {"id": "graph-alert-id"},
                "sentinel": {
                    "id": "graph-alert-id",
                    "tenant_id": "tenant-id",
                    "record_type": "alert",
                    "incident_id": "graph-incident-id",
                    "alert_id": "graph-alert-id",
                },
            },
            unique=False,
        )
        datastore_connection.hit.save(hit.howler.id, hit)
        datastore_connection.hit.commit()
        hit_id = hit.howler.id

        result = execute(f"howler.id:{hit_id}")

        assert result[0] == {
            "query": f"howler.id:{hit_id}",
            "outcome": "success",
            "title": "Alert updated in XDR Defender",
            "message": "Howler has successfully propagated changes to this alert to XDR Defender.",
        }


def test_update_defender_xdr_incident_uses_full_token(datastore_connection: HowlerDatastore, monkeypatch):
    from sentinel.actions import update_defender_xdr_incident

    incident_hit, _ = hit_service.convert_hit(
        {
            "howler.analytic": "Sentinel",
            "howler.detection": "Incident summary",
            "organization": {"name": "Example", "id": "tenant-id"},
            "sentinel": {
                "id": "graph-incident-id",
                "tenant_id": "tenant-id",
                "record_type": "incident",
                "incident_id": "graph-incident-id",
            },
        },
        unique=False,
    )
    datastore_connection.hit.save(incident_hit.howler.id, incident_hit)
    datastore_connection.hit.commit()
    token_provider = Mock(return_value="test-access-token")
    monkeypatch.setattr(update_defender_xdr_incident, "get_token", token_provider)

    graph_response = Mock(ok=True)
    graph_response.json.return_value = {
        "classification": "unknown",
        "determination": "unknown",
        "assignedTo": "analyst@example.test",
    }
    with (
        app.test_request_context(),
        patch("requests.get", return_value=graph_response) as graph_get,
        patch("requests.patch", return_value=Mock(ok=True)) as graph_patch,
    ):
        result = update_defender_xdr_incident.execute(f"howler.id:{incident_hit.howler.id}")

    assert result[0]["outcome"] == "success"
    token_provider.assert_called_once_with("tenant-id", "https://graph.microsoft.com/.default")
    assert graph_get.call_args.kwargs["headers"]["Authorization"] == "Bearer test-access-token"
    assert graph_patch.call_args.kwargs["headers"]["Authorization"] == "Bearer test-access-token"


def test_derived_evidence_is_not_sent_as_graph_alert_or_incident(datastore_connection: HowlerDatastore):
    evidence_hit, _ = hit_service.convert_hit(
        {
            "howler.analytic": "Sentinel Evidence",
            "howler.detection": "Sentinel Evidence",
            "organization": {"name": "Example", "id": "tenant-id"},
            "sentinel": {
                "tenant_id": "tenant-id",
                "record_type": "evidence",
                "incident_id": "incident-id",
                "alert_id": "alert-id",
                "evidence_id": "evidence-key",
            },
        },
        unique=False,
    )
    datastore_connection.hit.save(evidence_hit.howler.id, evidence_hit)
    datastore_connection.hit.commit()

    with (
        app.test_request_context(),
        patch("requests.get") as graph_get,
        patch("requests.patch") as graph_patch,
        patch("requests.post") as external_post,
    ):
        from sentinel.actions.azure_emit_hash import execute as emit_hash
        from sentinel.actions.send_to_sentinel import execute as send_to_sentinel
        from sentinel.actions.update_defender_xdr_alert import execute as update_alert
        from sentinel.actions.update_defender_xdr_incident import execute as update_incident

        query = f"howler.id:{evidence_hit.howler.id}"
        for result in (
            update_alert(query),
            update_incident(query),
            send_to_sentinel(query),
            emit_hash(query, url="https://example.test/webhook"),
        ):
            assert result[0]["outcome"] == "skipped"

    graph_get.assert_not_called()
    graph_patch.assert_not_called()
    external_post.assert_not_called()
