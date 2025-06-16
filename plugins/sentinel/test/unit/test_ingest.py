import copy
import json
import logging
from pathlib import Path
from unittest.mock import patch

import pytest
import requests
import werkzeug
from flask.app import Flask
from howler.common.loader import datastore

# No clue why this is necessary
werkzeug.__version__ = "1.0.0"  # type: ignore

with (Path(__file__).parent / "sentinel.json").open() as _alert:
    SENTINEL_ALERT = json.load(_alert)


def mock_post(url: str, **kwargs):
    res = requests.Response()
    res.status_code = 200
    res.headers["Content-Type"] = "application/json"
    if url.startswith("https://login.microsoftonline.com"):
        res._content = json.dumps({"access_token": "potato"}).encode()

    return res


@pytest.fixture(scope="module")
def client():
    # Arrange: Setup Flask app and register blueprint
    from sentinel.routes.ingest import sentinel_api

    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test", TESTING=True)
    app.register_blueprint(sentinel_api)

    # Act & Assert: Return test client for use in tests
    return app.test_client()


@patch("requests.post", mock_post)
def test_ingest_endpoint(client, caplog):
    # Arrange: Prepare request data and logging
    with caplog.at_level(logging.INFO):
        # Act: Post incident to ingest endpoint
        result = client.post(
            "/api/v1/sentinel/ingest", json=SENTINEL_ALERT, headers={"Authorization": "Basic test_key"}
        )

    # Assert: Check log, response, and datastore state
    assert "Successfully mapped Sentinel Incident" in caplog.text
    assert result.json["api_response"]["bundle_size"] == 2
    assert len(result.json["api_response"]["individual_hit_ids"]) == 2
    assert datastore().hit.exists(result.json["api_response"]["bundle_hit_id"])
    assert (
        datastore().hit.get(result.json["api_response"]["bundle_hit_id"], as_obj=True).howler.hits
        == result.json["api_response"]["individual_hit_ids"]
    )
    for _id in result.json["api_response"]["individual_hit_ids"]:
        assert datastore().hit.exists(_id)


def test_update_incident_status(client):
    """Test updating the status of an existing incident."""
    # Arrange: Ingest incident and underlying alert as bundle
    incident = copy.deepcopy(SENTINEL_ALERT)
    incident_id = "test-update-incident-id"
    incident["id"] = incident_id
    for idx, alert in enumerate(incident.get("alerts", [])):
        alert["incidentId"] = incident_id
        alert["id"] = f"test-update-alert-id-{idx}"
    response = client.post("/api/v1/sentinel/ingest", json=incident, headers={"Authorization": "Basic test_key"})
    assert response.status_code == 201
    bundle_hit_id = response.json["api_response"]["bundle_hit_id"]
    # Assert: Checking that underlying alerts in the incident are open
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][0], as_obj=True)
    assert alert.howler.status == "open"
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][1], as_obj=True)
    assert alert.howler.status == "open"

    # Act: Update the incident status. This should also update the underlying alerts.
    updated_incident = copy.deepcopy(incident)
    updated_incident["status"] = "resolved"
    for idx, alert in enumerate(updated_incident.get("alerts", [])):
        alert["id"] = f"test-update-alert-id-{idx}"
        alert["incidentId"] = incident_id
    update_response = client.post(
        "/api/v1/sentinel/ingest", json=updated_incident, headers={"Authorization": "Basic test_key"}
    )
    # Assert: Check update response and status propagation
    assert update_response.status_code == 200
    assert update_response.json["api_response"]["updated"] is True
    assert update_response.json["api_response"]["bundle_hit_id"] == bundle_hit_id
    bundle = datastore().hit.get(bundle_hit_id, as_obj=True)
    assert bundle.howler.status == "resolved"
    # Assert: Checking that underlying alerts in the incident are resolved
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][0], as_obj=True)
    assert alert.howler.status == "resolved"
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][1], as_obj=True)
    assert alert.howler.status == "resolved"


def test_update_incident_status_noalerts(client):
    """Test updating the status of an existing incident.
    This test verifies that when an incident is updated without alerts in the payload,
    underlying alerts in the bundle still transition to the resolved state.
    """
    # Arrange: Ingest incident and underlying alert as bundle
    incident = copy.deepcopy(SENTINEL_ALERT)
    incident_id = "test-update-incident-id2"
    incident["id"] = incident_id
    for idx, alert in enumerate(incident.get("alerts", [])):
        alert["incidentId"] = incident_id
        alert["id"] = f"test-update-alert-id2-{idx}"
    response = client.post("/api/v1/sentinel/ingest", json=incident, headers={"Authorization": "Basic test_key"})
    assert response.status_code == 201
    bundle_hit_id = response.json["api_response"]["bundle_hit_id"]
    # Assert: Checking that underlying alerts in the incident are open
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][0], as_obj=True)
    assert alert.howler.status == "open"
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][1], as_obj=True)
    assert alert.howler.status == "open"

    # Act: Update the incident status. This should also update the underlying alerts.
    updated_incident = copy.deepcopy(incident)
    # Remove the alerts
    updated_incident.pop("alerts", None)
    updated_incident["status"] = "resolved"
    update_response = client.post(
        "/api/v1/sentinel/ingest", json=updated_incident, headers={"Authorization": "Basic test_key"}
    )
    # Assert: Check update response and status propagation
    assert update_response.status_code == 200
    assert update_response.json["api_response"]["updated"] is True
    assert update_response.json["api_response"]["bundle_hit_id"] == bundle_hit_id
    bundle = datastore().hit.get(bundle_hit_id, as_obj=True)
    assert bundle.howler.status == "resolved"
    # Assert: Checking that underlying alerts in the (incident) bundle are resolved
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][0], as_obj=True)
    assert alert.howler.status == "resolved"
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][1], as_obj=True)
    assert alert.howler.status == "resolved"


def test_ingest_incident_without_alerts(client):
    """Test ingesting an incident with no alerts."""
    # Arrange: Prepare incident with no alerts
    incident = copy.deepcopy(SENTINEL_ALERT)
    incident_id = "test-no-alerts-id"
    incident["id"] = incident_id
    for idx, alert in enumerate(incident.get("alerts", [])):
        alert["incidentId"] = incident_id
        alert["id"] = f"test-no-alerts-id-{idx}"
    incident["alerts"] = []
    # Act: Ingest the incident
    response = client.post("/api/v1/sentinel/ingest", json=incident, headers={"Authorization": "Basic test_key"})
    # Assert: Check response and bundle state
    assert response.status_code == 201
    api_response = response.json["api_response"]
    assert api_response["bundle_size"] == 0
    assert api_response["individual_hit_ids"] == []
    assert datastore().hit.exists(api_response["bundle_hit_id"])
    bundle = datastore().hit.get(api_response["bundle_hit_id"], as_obj=True)
    assert not bundle.howler.is_bundle
    assert bundle.howler.status == "open"
    assert bundle.howler.hits == []


def test_ingest_incident_without_alerts_key(client):
    """Test ingesting an incident with no 'alerts' key at all."""
    # Arrange: Prepare incident and remove 'alerts' key
    incident = copy.deepcopy(SENTINEL_ALERT)
    incident_id = "test-no-alerts-key-id"
    incident["id"] = incident_id
    for idx, alert in enumerate(incident.get("alerts", [])):
        alert["incidentId"] = incident_id
        alert["id"] = f"test-no-alerts-key-id-{idx}"
    # Remove the 'alerts' key entirely
    incident.pop("alerts", None)
    # Act: Ingest the incident
    response = client.post("/api/v1/sentinel/ingest", json=incident, headers={"Authorization": "Basic test_key"})
    # Assert: Check response and bundle state
    assert response.status_code == 201
    api_response = response.json["api_response"]
    assert api_response["bundle_size"] == 0
    assert api_response["individual_hit_ids"] == []
    assert datastore().hit.exists(api_response["bundle_hit_id"])
    bundle = datastore().hit.get(api_response["bundle_hit_id"], as_obj=True)
    assert not bundle.howler.is_bundle
    assert bundle.howler.status == "open"
    assert bundle.howler.hits == []


def test_bundle_alert_linking_consistency(client):
    """Test that bundle and alert linking is consistent after ingestion."""
    # Arrange: Prepare a unique incident with two alerts
    incident = copy.deepcopy(SENTINEL_ALERT)
    incident_id = "test-linking-consistency-id"
    incident["id"] = incident_id
    for idx, alert in enumerate(incident.get("alerts", [])):
        alert["incidentId"] = incident_id
        alert["id"] = f"test-linking-alert-id-{idx}"
    # Act: Ingest the incident
    response = client.post("/api/v1/sentinel/ingest", json=incident, headers={"Authorization": "Basic test_key"})
    assert response.status_code == 201
    api_response = response.json["api_response"]
    bundle_id = api_response["bundle_hit_id"]
    alert_ids = api_response["individual_hit_ids"]
    # Assert: Bundle's hits field contains all alert IDs
    bundle = datastore().hit.get(bundle_id, as_obj=True)
    assert set(bundle.howler.hits) == set(alert_ids)
    # Assert: Each alert's bundles field contains the bundle ID
    for alert_id in alert_ids:
        alert = datastore().hit.get(alert_id, as_obj=True)
        assert bundle_id in getattr(alert.howler, "bundles", [])
