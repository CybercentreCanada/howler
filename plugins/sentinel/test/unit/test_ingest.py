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
from howler.services import case_service, hit_service

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
    from sentinel.routes.ingest import sentinel_api

    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test", TESTING=True)
    app.register_blueprint(sentinel_api)
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


def _incident(incident_id: str, *, alerts: list[dict] | None = None, tenant_id: str = SAMPLE_TENANT_ID) -> dict:
    incident = copy.deepcopy(SENTINEL_ALERT)
    incident["id"] = incident_id
    incident["tenantId"] = tenant_id
    if alerts is not None:
        incident["alerts"] = alerts
    for index, alert in enumerate(incident.get("alerts", [])):
        alert["incidentId"] = incident_id
        alert["id"] = f"{incident_id}-alert-{index}"
    return incident


def _post(client, incident: dict):
    return client.post("/api/v1/sentinel/ingest", json=incident, headers={"Authorization": "Basic test_key"})


def _api_response(response):
    assert "api_response" in response.json
    return response.json["api_response"]


def _case_for_root(root_hit):
    assert root_hit.howler.related, "Incident summary hit should link to its case"
    case = datastore().case.get(root_hit.howler.related[0])
    assert case
    return case


def _folder_path(case, item):
    folders = {folder.id: folder for folder in case.items if folder.type == "folder"}
    path = []
    parent = item.parent
    while parent is not None:
        folder = folders[parent]
        path.append(folder.name)
        parent = folder.parent
    return list(reversed(path))


def test_ingest_creates_native_case_hierarchy_without_evidence_plugin(client, caplog, tenant_mapping):
    from howler.config import config

    assert "evidence" not in config.core.plugins
    incident = _incident("case-hierarchy")
    with patch("requests.post", mock_post), caplog.at_level(logging.INFO):
        response = _post(client, incident)

    assert response.status_code == 201
    assert "Successfully mapped Sentinel Incident" in caplog.text
    api_response = _api_response(response)
    assert len(api_response["source_alert_hit_ids"]) == 2
    assert len(api_response["evidence_hit_ids"]) == 4
    assert api_response["total_hits_created"] == 7
    assert api_response["incident_id"] == incident["id"]
    assert not {"bundle_hit_id", "bundle_id", "individual_hit_ids", "bundle_size"} & api_response.keys()

    root_hit = datastore().hit.get(api_response["incident_hit_id"], as_obj=True)
    assert root_hit
    assert root_hit.organization.name == SAMPLE_ORGANIZATION
    assert root_hit.organization.id == SAMPLE_TENANT_ID
    assert root_hit.howler.id != incident["id"]
    assert root_hit.sentinel.record_type == "incident"
    assert "evidence" not in root_hit.as_primitives()

    case = datastore().case.get(api_response["case_id"])
    assert case
    assert api_response["case_id"] in root_hit.howler.related
    root_items = [item for item in case.items if item.type == "hit" and item.value == root_hit.howler.id]
    assert len(root_items) == 1
    assert root_items[0].parent is None

    case_hit_items = {item.value: item for item in case.items if item.type == "hit"}
    assert set(api_response["source_alert_hit_ids"]).issubset(case_hit_items)
    assert set(api_response["evidence_hit_ids"]).issubset(case_hit_items)
    alert_folder_by_source = {}
    for alert_id in api_response["source_alert_hit_ids"]:
        alert_hit = datastore().hit.get(alert_id, as_obj=True)
        assert alert_hit
        assert alert_hit.organization.name == SAMPLE_ORGANIZATION
        assert alert_hit.organization.id == SAMPLE_TENANT_ID
        assert alert_hit.sentinel.record_type == "alert"
        assert alert_hit.sentinel.incident_id == incident["id"]
        assert alert_hit.howler.id != alert_hit.sentinel.alert_id
        assert alert_hit.rule.id == alert_hit.sentinel.alert_id
        alert_folder_by_source[alert_hit.sentinel.alert_id] = alert_id
        assert api_response["case_id"] in alert_hit.howler.related
        assert _folder_path(case, case_hit_items[alert_id]) == ["alerts", alert_id]
        assert "evidence" not in alert_hit.as_primitives()

    evidence_hits = []
    for evidence_id in api_response["evidence_hit_ids"]:
        evidence_hit = datastore().hit.get(evidence_id, as_obj=True)
        assert evidence_hit
        evidence_hits.append(evidence_hit)
        assert evidence_hit.organization.name == SAMPLE_ORGANIZATION
        assert evidence_hit.organization.id == SAMPLE_TENANT_ID
        assert evidence_hit.sentinel.record_type == "evidence"
        assert evidence_hit.sentinel.incident_id == incident["id"]
        assert evidence_hit.sentinel.alert_id in {
            incident["alerts"][0]["id"],
            incident["alerts"][1]["id"],
        }
        assert not getattr(getattr(evidence_hit, "rule", None), "id", None)
        assert evidence_hit.classification == root_hit.classification
        assert evidence_hit.howler.escalation == "hit"
        assert api_response["case_id"] in evidence_hit.howler.related
        assert _folder_path(case, case_hit_items[evidence_id]) == [
            "alerts",
            alert_folder_by_source[evidence_hit.sentinel.alert_id],
        ]
        assert "evidence" not in evidence_hit.as_primitives()
        raw_values = [json.loads(raw) for raw in evidence_hit.howler.data]
        assert raw_values

    expected_raw_evidence = {
        json.dumps(evidence, sort_keys=True) for alert in incident["alerts"] for evidence in alert["evidence"]
    }
    actual_raw_evidence = {json.dumps(json.loads(hit.howler.data[0]), sort_keys=True) for hit in evidence_hits}
    assert actual_raw_evidence == expected_raw_evidence

    # The fixture exercises the user, host, and IP ECS projections.
    assert any(getattr(hit, "user", None) and hit.user.name == "Velma Dinkley" for hit in evidence_hits)
    assert any(getattr(hit, "host", None) and hit.host.name == "MysteryMachine" for hit in evidence_hits)
    assert any(getattr(hit, "host", None) and "249.246.138.221" in hit.host.ip for hit in evidence_hits)


@pytest.mark.parametrize(
    "evidence",
    [
        {"@odata.type": "#microsoft.graph.security.futureEvidence", "newField": {"value": 7}},
        {
            "@odata.type": "#microsoft.graph.security.teamsMessageEvidence",
            "campaignId": "campaign-1",
            "urls": [{"url": "https://example.test"}],
        },
        {"untypedPayload": ["raw", "value"]},
        None,
    ],
    ids=["unknown-type", "unsupported-namespace", "missing-type", "non-dict-value"],
)
def test_unknown_or_missing_evidence_type_is_preserved_as_child_hit(client, tenant_mapping, evidence, request):
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    alert["id"] = "unknown-evidence-alert"
    alert["evidence"] = [evidence]
    incident = _incident(f"unknown-evidence-{request.node.name.rsplit('[', 1)[-1].rstrip(']')}", alerts=[alert])

    response = _post(client, incident)

    assert response.status_code == 201
    api_response = _api_response(response)
    assert len(api_response["evidence_hit_ids"]) == 1
    child = datastore().hit.get(api_response["evidence_hit_ids"][0], as_obj=True)
    assert child
    assert json.loads(child.howler.data[0]) == evidence
    assert child.sentinel.record_type == "evidence"
    assert "evidence" not in child.as_primitives()
    assert "teams" not in child.as_primitives()


def test_populated_evidence_mappings_match_howler_ecs_compounds(client, tenant_mapping):
    evidence_values = [
        {
            "@odata.type": "#microsoft.graph.security.mailboxEvidence",
            "primaryAddress": "mailbox@example.test",
            "userAccount": {
                "accountName": "Mailbox User",
                "azureAdUserId": "user-id",
                "domainName": "example.test",
                "userPrincipalName": "mailbox@example.test",
            },
        },
        {
            "@odata.type": "#microsoft.graph.security.analyzedMessageEvidence",
            "antiSpamDirection": "inbound",
            "networkMessageId": "message-id",
            "p1Sender": {"emailAddress": "sender@example.test"},
            "recipientEmailAddress": "recipient@example.test",
            "senderIp": "192.0.2.10",
            "subject": "Suspicious attachment",
            "urls": ["https://example.test/path"],
        },
        {
            "@odata.type": "#microsoft.graph.security.containerEvidence",
            "containerId": "container-id",
            "name": "api-container",
            "image": {"digestImage": "registry.example.test/api@sha256:abcdef"},
        },
    ]
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    alert["id"] = "ecs-evidence-alert"
    alert["evidence"] = evidence_values
    incident = _incident("ecs-evidence-shapes", alerts=[alert])

    response = _post(client, incident)

    assert response.status_code == 201
    response_data = _api_response(response)
    evidence_hits = [datastore().hit.get(hit_id, as_obj=True) for hit_id in response_data["evidence_hit_ids"]]
    hits_by_type = {json.loads(hit.howler.data[0])["@odata.type"].rsplit(".", 1)[-1]: hit for hit in evidence_hits}

    mailbox = hits_by_type["mailboxEvidence"]
    assert mailbox.email.to.address == "mailbox@example.test"
    assert mailbox.user.name == "Mailbox User"
    assert mailbox.user.domain == "example.test"

    analyzed_message = hits_by_type["analyzedMessageEvidence"]
    assert analyzed_message.email.to.address == "recipient@example.test"
    assert analyzed_message.email.sender.address == "sender@example.test"
    assert analyzed_message.email.subject == "Suspicious attachment"
    assert analyzed_message.email.local_id == "message-id"
    assert "192.0.2.10" in analyzed_message.host.ip

    container = hits_by_type["containerEvidence"]
    assert container.container.id == "container-id"
    assert container.container.name == "api-container"
    assert container.container.image.name == "registry.example.test/api@sha256:abcdef"


def test_invalid_projection_does_not_discard_valid_evidence_fields(client, tenant_mapping, monkeypatch):
    original_mapper = XDRAlert.map_evidence_to_hit

    def add_invalid_ip_projection(self, graph_evidence, customer_id, **kwargs):
        mapped = original_mapper(self, graph_evidence, customer_id, **kwargs)
        mapped["host"] = {"name": "evidence-host.example.test", "ip": {"not": "an IP list"}}
        return mapped

    monkeypatch.setattr(XDRAlert, "map_evidence_to_hit", add_invalid_ip_projection)
    evidence = {
        "@odata.type": "#microsoft.graph.security.userEvidence",
        "userAccount": {"accountName": "Preserved User", "azureAdUserId": "preserved-user-id"},
    }
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    alert["id"] = "invalid-projection-alert"
    alert["evidence"] = [evidence]
    incident = _incident("invalid-projection", alerts=[alert])

    response = _post(client, incident)

    assert response.status_code == 201
    child = datastore().hit.get(_api_response(response)["evidence_hit_ids"][0], as_obj=True)
    assert child
    assert child.user.name == "Preserved User"
    assert child.user.id == "preserved-user-id"
    assert child.host.name == "evidence-host.example.test"
    assert child.host.ip == []
    assert json.loads(child.howler.data[0]) == evidence


def test_update_incident_status_only_updates_sentinel_owned_case_hits(client, tenant_mapping):
    incident = _incident("status-only")
    response = _post(client, incident)
    assert response.status_code == 201
    api_response = _api_response(response)
    root_hit = datastore().hit.get(api_response["incident_hit_id"], as_obj=True)
    assert root_hit
    case = datastore().case.get(api_response["case_id"])
    assert case

    analyst_hit, _ = hit_service.convert_hit(
        {
            "howler.analytic": "Analyst Data",
            "howler.detection": "Analyst Data",
            "organization": {"name": SAMPLE_ORGANIZATION, "id": SAMPLE_TENANT_ID},
        },
        unique=False,
    )
    hit_service.create_hit(analyst_hit.howler.id, analyst_hit, user="system")
    case_service.append_case_item(
        case,
        item_type="hit",
        item_value=analyst_hit.howler.id,
        item_name="Analyst-added hit",
    )
    case.save()
    datastore().case.commit()
    datastore().hit.commit()

    update = copy.deepcopy(incident)
    update.pop("alerts")
    update["status"] = "resolved"
    update_response = _post(client, update)

    assert update_response.status_code == 200
    updated = _api_response(update_response)
    assert updated["updated"] is True
    assert updated["incident_hit_id"] == api_response["incident_hit_id"]
    assert updated["case_id"] == api_response["case_id"]
    assert set(updated["source_alert_hit_ids"]) == set(api_response["source_alert_hit_ids"])
    assert updated["total_hits_updated"] == 1 + len(api_response["source_alert_hit_ids"]) + len(
        api_response["evidence_hit_ids"]
    )

    for hit_id in [
        api_response["incident_hit_id"],
        *api_response["source_alert_hit_ids"],
        *api_response["evidence_hit_ids"],
    ]:
        hit = datastore().hit.get(hit_id, as_obj=True)
        assert hit
        assert hit.howler.status == "resolved"
    analyst = datastore().hit.get(analyst_hit.howler.id, as_obj=True)
    assert analyst
    assert analyst.howler.status == "open"


@pytest.mark.parametrize("alerts", [[], None], ids=["empty-list", "omitted"])
def test_incident_without_alerts_still_has_one_case(client, tenant_mapping, alerts):
    incident_id = "zero-alerts-empty" if alerts == [] else "zero-alerts-omitted"
    incident = _incident(incident_id, alerts=[])
    if alerts is None:
        incident.pop("alerts")

    response = _post(client, incident)

    assert response.status_code == 201
    api_response = _api_response(response)
    assert api_response["source_alert_hit_ids"] == []
    assert api_response["evidence_hit_ids"] == []
    assert api_response["total_hits_created"] == 1
    root_hit = datastore().hit.get(api_response["incident_hit_id"], as_obj=True)
    assert root_hit
    case = datastore().case.get(api_response["case_id"])
    assert case
    assert len([item for item in case.items if item.type == "hit"]) == 1
    assert case.items[0].value == root_hit.howler.id
    assert api_response["case_id"] in root_hit.howler.related


def test_zero_alert_incident_reconciles_alerts_on_later_replay(client, tenant_mapping):
    incident = _incident("add-alert-later", alerts=[])
    first = _post(client, incident)
    assert first.status_code == 201
    first_data = _api_response(first)

    later = copy.deepcopy(incident)
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    alert["id"] = "late-added-alert"
    alert["incidentId"] = incident["id"]
    later["alerts"] = [alert]
    second = _post(client, later)

    assert second.status_code == 200
    second_data = _api_response(second)
    assert second_data["incident_hit_id"] == first_data["incident_hit_id"]
    assert second_data["case_id"] == first_data["case_id"]
    assert len(second_data["source_alert_hit_ids"]) == 1
    assert len(second_data["evidence_hit_ids"]) == 1
    assert second_data["total_hits_created"] == 2


def test_graph_classification_does_not_set_howler_evidence_escalation(client, tenant_mapping):
    incident = _incident("classification-is-not-disposition", alerts=[])
    incident["status"] = "resolved"
    incident["classification"] = "truePositive"
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    alert["id"] = "classification-alert"
    alert["incidentId"] = incident["id"]
    alert["classification"] = "truePositive"
    alert["evidence"] = [{"@odata.type": "#microsoft.graph.security.urlEvidence", "url": "https://example.test"}]
    incident["alerts"] = [alert]

    response = _post(client, incident)

    assert response.status_code == 201
    response_data = _api_response(response)
    hit_ids = [
        response_data["incident_hit_id"],
        *response_data["source_alert_hit_ids"],
        *response_data["evidence_hit_ids"],
    ]
    for hit_id in hit_ids:
        hit = datastore().hit.get(hit_id, as_obj=True)
        assert hit
        assert hit.howler.escalation == "hit"


def test_replay_reorders_and_adds_alerts_and_evidence_idempotently(client, tenant_mapping):
    incident = _incident("reorder-replay")
    first = _post(client, incident)
    assert first.status_code == 201
    first_data = _api_response(first)

    reordered = copy.deepcopy(incident)
    reordered["alerts"].reverse()
    for alert in reordered["alerts"]:
        alert["evidence"].reverse()
    second = _post(client, reordered)

    assert second.status_code == 200
    second_data = _api_response(second)
    assert second_data["incident_hit_id"] == first_data["incident_hit_id"]
    assert second_data["case_id"] == first_data["case_id"]
    assert set(second_data["source_alert_hit_ids"]) == set(first_data["source_alert_hit_ids"])
    assert set(second_data["evidence_hit_ids"]) == set(first_data["evidence_hit_ids"])
    case = datastore().case.get(first_data["case_id"])
    assert case
    initial_hit_count = len([item for item in case.items if item.type == "hit"])
    assert initial_hit_count == 7

    new_alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    new_alert["id"] = "replay-new-alert"
    new_alert["incidentId"] = incident["id"]
    new_alert["evidence"] = [{"@odata.type": "#futureEvidence", "value": "new"}]
    extended = copy.deepcopy(reordered)
    extended["alerts"].append(new_alert)
    third = _post(client, extended)

    assert third.status_code == 200
    third_data = _api_response(third)
    assert third_data["total_hits_created"] == 2
    assert len(third_data["source_alert_hit_ids"]) == 3
    assert len(third_data["evidence_hit_ids"]) == 5
    case = datastore().case.get(first_data["case_id"])
    assert case
    assert len([item for item in case.items if item.type == "hit"]) == initial_hit_count + 2


def test_failed_child_case_link_is_reported_and_replay_repairs_it(client, tenant_mapping, monkeypatch):
    incident = _incident("retry-link-failure")
    original_append = case_service.append_case_item
    failure_state = {"pending": True}

    def append_with_one_evidence_failure(*args, **kwargs):
        item_value = kwargs.get("item_value")
        if failure_state["pending"] and item_value:
            hit = datastore().hit.get(item_value, as_obj=True)
            if hit is not None and hit.sentinel.record_type == "evidence":
                failure_state["pending"] = False
                raise RuntimeError("simulated case-link failure")
        return original_append(*args, **kwargs)

    monkeypatch.setattr(case_service, "append_case_item", append_with_one_evidence_failure)
    failed = _post(client, incident)
    assert failed.status_code == 500

    retry = _post(client, incident)
    assert retry.status_code == 200
    response = _api_response(retry)
    case = datastore().case.get(response["case_id"])
    assert case
    case_hit_values = {item.value for item in case.items if item.type == "hit"}
    assert response["incident_hit_id"] in case_hit_values
    assert set(response["source_alert_hit_ids"]).issubset(case_hit_values)
    assert set(response["evidence_hit_ids"]).issubset(case_hit_values)
    assert len(case_hit_values) == 1 + len(response["source_alert_hit_ids"]) + len(response["evidence_hit_ids"])


def test_status_replay_after_case_creation_failure_preserves_single_case_backreference(
    client, tenant_mapping, monkeypatch
):
    incident = _incident("case-create-retry", alerts=[])
    original_create_case = case_service.create_case
    failure_state = {"pending": True}

    def fail_case_creation_once(*args, **kwargs):
        if failure_state["pending"]:
            failure_state["pending"] = False
            raise RuntimeError("simulated initial case creation failure")
        return original_create_case(*args, **kwargs)

    monkeypatch.setattr(case_service, "create_case", fail_case_creation_once)
    first = _post(client, incident)
    assert first.status_code == 500

    from sentinel.services.ingest_service import _stable_hit_id

    root_hit_id = _stable_hit_id(SAMPLE_TENANT_ID, incident["id"], "incident")
    root = datastore().hit.get(root_hit_id, as_obj=True)
    assert root
    assert not root.howler.related

    first_replay = copy.deepcopy(incident)
    first_replay["status"] = "resolved"
    second = _post(client, first_replay)
    assert second.status_code == 200
    second_data = _api_response(second)

    second_replay = copy.deepcopy(incident)
    second_replay["status"] = "active"
    third = _post(client, second_replay)
    assert third.status_code == 200
    third_data = _api_response(third)
    assert third_data["case_id"] == second_data["case_id"]

    persisted_root = datastore().hit.get(root.howler.id, as_obj=True)
    assert persisted_root
    assert persisted_root.howler.related == [second_data["case_id"]]
    case = datastore().case.get(second_data["case_id"])
    assert case
    root_items = [item for item in case.items if item.type == "hit" and item.value == root.howler.id]
    assert len(root_items) == 1


def test_same_incident_id_is_tenant_scoped(client, tenant_mapping):
    sample = _incident("tenant-collision", alerts=[])
    other = _incident("tenant-collision", alerts=[], tenant_id=OTHER_TENANT_ID)

    sample_response = _post(client, sample)
    other_response = _post(client, other)

    assert sample_response.status_code == 201
    assert other_response.status_code == 201
    sample_data = _api_response(sample_response)
    other_data = _api_response(other_response)
    assert sample_data["incident_hit_id"] != other_data["incident_hit_id"]
    assert sample_data["case_id"] != other_data["case_id"]
    sample_root = datastore().hit.get(sample_data["incident_hit_id"], as_obj=True)
    other_root = datastore().hit.get(other_data["incident_hit_id"], as_obj=True)
    assert sample_root.organization.id == SAMPLE_TENANT_ID
    assert other_root.organization.id == OTHER_TENANT_ID


def test_incident_tenant_is_authoritative_for_source_and_evidence_hits(client, tenant_mapping):
    incident = _incident("parent-tenant-context", tenant_id=OTHER_TENANT_ID)
    for alert in incident["alerts"]:
        alert["tenantId"] = SAMPLE_TENANT_ID

    response = _post(client, incident)

    assert response.status_code == 201
    response_data = _api_response(response)
    hit_ids = [
        response_data["incident_hit_id"],
        *response_data["source_alert_hit_ids"],
        *response_data["evidence_hit_ids"],
    ]
    for hit_id in hit_ids:
        hit = datastore().hit.get(hit_id, as_obj=True)
        assert hit
        assert hit.organization.name == OTHER_ORGANIZATION
        assert hit.organization.id == OTHER_TENANT_ID


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
    assert "evidence" not in mapped_alert
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


def _mock_ingest_processing(monkeypatch):
    from sentinel.routes import ingest

    ingest_mock = Mock(name="ingest_service.ingest_incident")
    monkeypatch.setattr(ingest.ingest_service, "ingest_incident", ingest_mock)
    return {"ingest_service.ingest_incident": ingest_mock}


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
