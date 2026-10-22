import copy
import json
import logging
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests
import werkzeug
from flask.app import Flask
from howler.common.loader import datastore
from howler.services import hit_service

from sentinel.mapping.xdr_alert import XDRAlert

# No clue why this is necessary
werkzeug.__version__ = "1.0.0"  # type: ignore

with (Path(__file__).parent / "sentinel.json").open() as _alert:
    SENTINEL_ALERT = json.load(_alert)

SAMPLE_TENANT_ID = "020cd98f-1002-45b7-90ff-69fc68bdd027"
OTHER_TENANT_ID = "b3cc6e90-8d5e-4bb0-a73e-1c2bb48f7c14"
SAMPLE_ORGANIZATION = "Briarwood Labs"
OTHER_ORGANIZATION = "Fabrikam Security"


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


@pytest.fixture
def tenant_mapping(monkeypatch):
    from sentinel.config import config

    mapping = {
        SAMPLE_TENANT_ID: SAMPLE_ORGANIZATION,
        OTHER_TENANT_ID: OTHER_ORGANIZATION,
    }
    monkeypatch.setattr(config, "tenant_mapping", mapping)
    return mapping


def _mock_ingest_processing(monkeypatch):
    from sentinel.routes import ingest

    processing_mocks = {}
    for name in ["datastore", "SentinelIncident", "XDRAlert"]:
        mock = Mock(name=name)
        monkeypatch.setattr(ingest, name, mock)
        processing_mocks[name] = mock

    for service_name, methods in {
        "hit_service": ["convert_hit", "create_hit", "get_hit"],
        "analytic_service": ["save_from_hits"],
        "case_service": ["create_case", "append_case_item", "get_parent_from_path"],
        "action_service": ["bulk_execute_on_query"],
    }.items():
        service = getattr(ingest, service_name)
        for method in methods:
            mock = Mock(name=f"{service_name}.{method}")
            monkeypatch.setattr(service, method, mock)
            processing_mocks[f"{service_name}.{method}"] = mock

    return processing_mocks


@patch("requests.post", mock_post)
def test_ingest_endpoint(client, caplog, tenant_mapping):
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

    # Verify child hits are linked via a case, not via howler.hits
    root_hit = datastore().hit.get(result.json["api_response"]["bundle_hit_id"], as_obj=True)
    assert root_hit
    assert root_hit.organization.name == SAMPLE_ORGANIZATION
    assert root_hit.organization.id == SAMPLE_TENANT_ID
    assert len(root_hit.howler.related) > 0, "Root hit should have a case back-reference"
    case = datastore().case.get(root_hit.howler.related[0])
    assert case
    case_hit_values = [item.value for item in case.items if item.type == "hit"]
    for _id in result.json["api_response"]["individual_hit_ids"]:
        assert datastore().hit.exists(_id)
        child_hit = datastore().hit.get(_id, as_obj=True)
        assert child_hit
        assert child_hit.organization.name == SAMPLE_ORGANIZATION
        assert child_hit.organization.id == SAMPLE_TENANT_ID
        assert _id in case_hit_values, f"Child hit {_id} should be in case items"


@pytest.mark.parametrize(
    ("computer_dns_name", "has_computer_dns_name_field", "expected_target"),
    [
        (None, False, None),
        (None, True, None),
        ("", True, None),
        ("   ", True, None),
        ("host.example.com", True, "host.example.com"),
    ],
)
def test_xdr_alert_mapping_handles_optional_computer_dns_name(
    computer_dns_name, has_computer_dns_name_field, expected_target
):
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    if has_computer_dns_name_field:
        alert["computerDnsName"] = computer_dns_name

    mapper = XDRAlert(tid_mapping={alert["tenantId"]: "Acme Corporation"})
    mapped_alert = mapper.map_alert(alert, alert["tenantId"])

    assert mapped_alert is not None
    converted_alert, _ = hit_service.convert_hit(mapped_alert, unique=False, ignore_extra_values=True)
    assert converted_alert.howler.outline.target == expected_target


def test_xdr_alert_mapping_accepts_explicit_unknown_customer():
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    mapper = XDRAlert(tid_mapping={SAMPLE_TENANT_ID: XDRAlert.DEFAULT_CUSTOMER_NAME})

    mapped_alert = mapper.map_alert(alert, SAMPLE_TENANT_ID)

    assert mapped_alert is not None
    assert mapped_alert["organization"] == {"name": XDRAlert.DEFAULT_CUSTOMER_NAME, "id": SAMPLE_TENANT_ID}


def test_xdr_alert_mapping_preserves_custom_unmapped_default():
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    mapper = XDRAlert(default_customer_name="Configured Fallback")

    mapped_alert = mapper.map_alert(alert, "unmapped-tenant")

    assert mapped_alert is not None
    assert mapped_alert["organization"] == {"name": "Configured Fallback", "id": "unmapped-tenant"}


def test_update_incident_status(client, tenant_mapping):
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
    # Changing the mapping affects only new ingests, not status-only updates to
    # this already persisted root hit and its child alerts.
    tenant_mapping[SAMPLE_TENANT_ID] = "Changed Organization Name"
    # Assert: Checking that underlying alerts in the incident are open
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][0], as_obj=True)
    assert alert
    assert alert.howler.status == "open"
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][1], as_obj=True)
    assert alert
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
    assert bundle
    assert bundle.howler.status == "resolved"
    assert bundle.organization.name == SAMPLE_ORGANIZATION
    assert bundle.organization.id == SAMPLE_TENANT_ID
    # Assert: Checking that underlying alerts in the incident are resolved
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][0], as_obj=True)
    assert alert
    assert alert.howler.status == "resolved"
    assert alert.organization.name == SAMPLE_ORGANIZATION
    assert alert.organization.id == SAMPLE_TENANT_ID
    second_alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][1], as_obj=True)
    assert second_alert
    assert second_alert.howler.status == "resolved"
    assert second_alert.organization.name == SAMPLE_ORGANIZATION
    assert second_alert.organization.id == SAMPLE_TENANT_ID


def test_update_incident_status_noalerts(client, tenant_mapping):
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
    assert alert
    assert alert.howler.status == "open"
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][1], as_obj=True)
    assert alert
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
    assert bundle
    assert bundle.howler.status == "resolved"
    # Assert: Checking that underlying alerts in the (incident) bundle are resolved
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][0], as_obj=True)
    assert alert
    assert alert.howler.status == "resolved"
    alert = datastore().hit.get(response.json["api_response"]["individual_hit_ids"][1], as_obj=True)
    assert alert
    assert alert.howler.status == "resolved"


def test_ingest_incident_without_alerts(client, tenant_mapping):
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
    assert bundle
    assert bundle.howler.status == "open"
    # No case should be created when there are no alerts
    assert len(bundle.howler.related) == 0


def test_ingest_incident_without_alerts_key(client, tenant_mapping):
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
    assert bundle
    assert bundle.howler.status == "open"
    # No case should be created when there are no alerts
    assert len(bundle.howler.related) == 0


def test_bundle_alert_linking_consistency(client, tenant_mapping):
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
    # Assert: Root hit should have a case back-reference, and case items should contain all alerts
    root_hit = datastore().hit.get(bundle_id, as_obj=True)
    assert root_hit
    assert len(root_hit.howler.related) > 0, "Root hit should have a case back-reference"
    case = datastore().case.get(root_hit.howler.related[0])
    assert case
    case_hit_values = {item.value for item in case.items if item.type == "hit" and item.value != bundle_id}
    assert case_hit_values == set(alert_ids)
    # Assert: Each alert should have a case back-reference
    for alert_id in alert_ids:
        alert = datastore().hit.get(alert_id, as_obj=True)
        assert alert
        assert any(rid == case.case_id for rid in alert.howler.related)


def test_ingest_uses_parent_tenant_for_all_alerts(client, tenant_mapping):
    incident = copy.deepcopy(SENTINEL_ALERT)
    incident_id = "test-parent-tenant-organization-id"
    incident["id"] = incident_id
    incident["tenantId"] = OTHER_TENANT_ID
    for idx, alert in enumerate(incident.get("alerts", [])):
        alert["incidentId"] = incident_id
        alert["id"] = f"test-parent-tenant-alert-{idx}"
        # The parent incident tenant is authoritative, even when a child has a
        # different tenant ID that is itself present in the mapping.
        alert["tenantId"] = SAMPLE_TENANT_ID

    response = client.post("/api/v1/sentinel/ingest", json=incident, headers={"Authorization": "Basic test_key"})

    assert response.status_code == 201
    api_response = response.json["api_response"]
    assert len(api_response["individual_hit_ids"]) == len(incident["alerts"])
    root_hit = datastore().hit.get(api_response["bundle_hit_id"], as_obj=True)
    assert root_hit
    assert root_hit.organization.name == OTHER_ORGANIZATION
    assert root_hit.organization.id == OTHER_TENANT_ID
    for child_id in api_response["individual_hit_ids"]:
        child_hit = datastore().hit.get(child_id, as_obj=True)
        assert child_hit
        assert child_hit.organization.name == OTHER_ORGANIZATION
        assert child_hit.organization.id == OTHER_TENANT_ID


@pytest.mark.parametrize(
    ("payload", "mapping_override"),
    [
        pytest.param([], None, id="array-body"),
        pytest.param("incident", None, id="string-body"),
        pytest.param(3, None, id="number-body"),
        pytest.param(None, None, id="null-body"),
        pytest.param({}, None, id="missing-tenant-id"),
        pytest.param({"tenantId": None}, None, id="null-tenant-id"),
        pytest.param({"tenantId": 42}, None, id="non-string-tenant-id"),
        pytest.param({"tenantId": ""}, None, id="empty-tenant-id"),
        pytest.param({"tenantId": "   "}, None, id="blank-tenant-id"),
        pytest.param({"tenantId": "unmapped-tenant"}, None, id="unmapped-tenant-id"),
        pytest.param({"tenantId": SAMPLE_TENANT_ID.upper()}, None, id="tenant-id-is-exact"),
        pytest.param({"tenantId": SAMPLE_TENANT_ID}, {}, id="empty-tenant-mapping"),
        pytest.param({"id": "existing-incident", "status": "resolved"}, None, id="update-missing-tenant"),
        pytest.param(
            {"id": "existing-incident", "tenantId": "unknown-update-tenant", "status": "resolved"},
            None,
            id="unmapped-update-tenant",
        ),
        pytest.param(
            {"tenantId": SAMPLE_TENANT_ID},
            {SAMPLE_TENANT_ID: "  "},
            id="blank-configured-organization",
        ),
    ],
)
def test_invalid_incidents_are_rejected_before_processing(
    client, monkeypatch, tenant_mapping, payload, mapping_override
):
    if mapping_override is not None:
        tenant_mapping.clear()
        tenant_mapping.update(mapping_override)

    processing_mocks = _mock_ingest_processing(monkeypatch)

    response = client.post("/api/v1/sentinel/ingest", json=payload, headers={"Authorization": "Basic test_key"})

    assert response.status_code == 400
    for mock in processing_mocks.values():
        mock.assert_not_called()


def test_malformed_json_is_rejected_before_processing(client, monkeypatch, tenant_mapping):
    processing_mocks = _mock_ingest_processing(monkeypatch)

    response = client.post(
        "/api/v1/sentinel/ingest",
        data="{",
        content_type="application/json",
        headers={"Authorization": "Basic test_key"},
    )

    assert response.status_code == 400
    for mock in processing_mocks.values():
        mock.assert_not_called()
