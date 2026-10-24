import copy
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
import requests
import werkzeug
from flask.app import Flask
from howler.common.loader import datastore
from howler.datastore.collection import CREATE_TOKEN
from howler.datastore.exceptions import VersionConflictException
from howler.odm.models.case import Case, CaseItem
from howler.services import case_service, hit_service

from sentinel.mapping.xdr_alert import XDRAlert
from sentinel.mapping.xdr_alert_evidence import XDRAlertEvidence

# No clue why this is necessary
werkzeug.__version__ = "1.0.0"  # type: ignore

with (Path(__file__).parent / "sentinel.json").open() as _alert:
    SENTINEL_ALERT = json.load(_alert)

SAMPLE_TENANT_ID = "020cd98f-1002-45b7-90ff-69fc68bdd027"
OTHER_TENANT_ID = "b3cc6e90-8d5e-4bb0-a73e-1c2bb48f7c14"
SAMPLE_ORGANIZATION = "Briarwood Labs"
OTHER_ORGANIZATION = "Fabrikam Security"
_TEST_RUN_ID = uuid4().hex
_OWNED_CASE_IDS: set[str] = set()


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
    incident["id"] = f"ingest-test-{_TEST_RUN_ID}-{incident_id}"
    incident["tenantId"] = tenant_id
    if alerts is not None:
        incident["alerts"] = alerts
    for index, alert in enumerate(incident.get("alerts", [])):
        alert["incidentId"] = incident_id
        alert["id"] = f"{incident_id}-alert-{index}"
    return incident


def _post(client, incident: dict):
    tenant_id = incident.get("tenantId")
    incident_id = incident.get("id")
    if isinstance(tenant_id, str) and isinstance(incident_id, str) and incident_id.strip():
        from sentinel.services.ingest_service import _stable_hit_id

        _OWNED_CASE_IDS.add(_stable_hit_id(tenant_id, incident_id, "case"))
    return client.post("/api/v1/sentinel/ingest", json=incident, headers={"Authorization": "Basic test_key"})


def _register_owned_case(case_id: str) -> str:
    _OWNED_CASE_IDS.add(case_id)
    return case_id


def _new_owned_case_id() -> str:
    return _register_owned_case(str(uuid4()))


def _delete_case_ids(case_ids: set[str]) -> None:
    for case_id in case_ids:
        datastore().case.delete(case_id, refresh="wait_for")


def _cleanup_owned_ingest_cases(case_ids: set[str] | None = None) -> None:
    owned_case_ids = set(_OWNED_CASE_IDS) if case_ids is None else set(case_ids) & _OWNED_CASE_IDS
    _delete_case_ids(owned_case_ids)
    _OWNED_CASE_IDS.difference_update(owned_case_ids)


@pytest.fixture(scope="module", autouse=True)
def cleanup_ingest_test_cases():
    yield
    _cleanup_owned_ingest_cases()


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
    with (
        patch.object(case_service, "append_hits", wraps=case_service.append_hits) as append_hits,
        patch("requests.post", mock_post),
        caplog.at_level(logging.INFO),
    ):
        response = _post(client, incident)

    assert response.status_code == 201
    assert "Successfully mapped Sentinel Incident" in caplog.text
    api_response = _api_response(response)
    assert len(api_response["source_alert_hit_ids"]) == 2
    assert len(api_response["evidence_hit_ids"]) == 4
    assert api_response["total_hits_created"] == 7
    append_hits.assert_called_once()
    assert len(append_hits.call_args.args[1]) == 6
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


def test_initial_ingest_emits_final_case_after_persistence_barrier(client, tenant_mapping, monkeypatch):
    from sentinel.services import ingest_service

    events = []
    milestones = []
    ds = datastore()
    original_commit = ds.case.commit

    def record_commit(*args, **kwargs):
        result = original_commit(*args, **kwargs)
        milestones.append("case-commit")
        return result

    def record_emit(event, data):
        if event == "cases":
            case = copy.deepcopy(data["case"])
            events.append(case)
            hit_count = sum(item["type"] == "hit" for item in case["items"])
            milestones.append(f"case-event-hits:{hit_count}")

    monkeypatch.setattr(ds.case, "commit", record_commit)
    monkeypatch.setattr(ingest_service.comms_service, "emit", record_emit)

    response = _post(client, _incident("initial-completion-event"))

    assert response.status_code == 201
    response_data = _api_response(response)
    assert len(events) == 2
    assert events[0]["case_id"] == response_data["case_id"]
    assert len([item for item in events[0]["items"] if item["type"] == "hit"]) == 1
    assert events[1]["case_id"] == response_data["case_id"]
    final_items = events[1]["items"]
    assert len([item for item in final_items if item["type"] == "hit"]) == 7
    assert milestones.index("case-commit") < milestones.index("case-event-hits:7")


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
    assert XDRAlertEvidence.container_evidence({"name": "worker-container"}) == {
        "container": {"name": "worker-container"}
    }


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


def test_update_incident_status_only_updates_sentinel_owned_case_hits(client, tenant_mapping, monkeypatch):
    from sentinel.services import ingest_service

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

    monkeypatch.setattr(Case, "save", Mock(side_effect=AssertionError("status-only replay should not save a case")))
    case_events = []
    monkeypatch.setattr(ingest_service.comms_service, "emit", lambda event, data: case_events.append((event, data)))

    managed_hit_ids = {*api_response["source_alert_hit_ids"], *api_response["evidence_hit_ids"]}
    original_hit_get = datastore().hit.get
    descendant_gets = []

    def track_descendant_get(hit_id, *args, **kwargs):
        if hit_id in managed_hit_ids:
            descendant_gets.append(hit_id)
        return original_hit_get(hit_id, *args, **kwargs)

    monkeypatch.setattr(datastore().hit, "get", track_descendant_get)

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
    assert case_events == []
    assert descendant_gets == []

    for hit_id in [
        api_response["incident_hit_id"],
        *api_response["source_alert_hit_ids"],
        *api_response["evidence_hit_ids"],
    ]:
        hit = datastore().hit.get(hit_id, as_obj=True)
        assert hit
        assert hit.howler.status == "resolved"
        if hit.sentinel.record_type == "evidence":
            assert hit.howler.data
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


def test_refresh_barriers_surround_root_creation_child_attachment_and_response(client, tenant_mapping, monkeypatch):
    from sentinel.services import ingest_service

    events = []
    original_create_hit = ingest_service._create_mapped_hit
    original_find_incident = ingest_service._find_existing_incident
    original_create_case = case_service.create_case
    original_append_hits = case_service.append_hits

    def record_refresh():
        events.append("refresh")

    def record_find(*args, **kwargs):
        events.append("lookup")
        return original_find_incident(*args, **kwargs)

    def record_hit_create(mapped_hit, stable_id):
        result = original_create_hit(mapped_hit, stable_id)
        events.append(f"create:{mapped_hit['sentinel']['record_type']}")
        return result

    def record_case_create(*args, **kwargs):
        events.append("create-case")
        return original_create_case(*args, **kwargs)

    def record_append_hits(*args, **kwargs):
        events.append("append-hits")
        return original_append_hits(*args, **kwargs)

    monkeypatch.setattr(ingest_service, "_refresh_hit_alias", record_refresh)
    monkeypatch.setattr(ingest_service, "_find_existing_incident", record_find)
    monkeypatch.setattr(ingest_service, "_create_mapped_hit", record_hit_create)
    monkeypatch.setattr(case_service, "create_case", record_case_create)
    monkeypatch.setattr(case_service, "append_hits", record_append_hits)
    monkeypatch.setattr(
        ingest_service.action_service,
        "bulk_execute_on_query",
        lambda *_args, **_kwargs: events.append("actions"),
    )

    response = _post(client, _incident("refresh-barriers"))

    assert response.status_code == 201
    assert events[0:2] == ["refresh", "lookup"]
    root_index = events.index("create:incident")
    case_index = events.index("create-case")
    append_index = events.index("append-hits")
    action_index = events.index("actions")
    assert events[root_index + 1] == "refresh"
    assert root_index < case_index < append_index
    assert events[append_index - 1] == "refresh"
    assert events[append_index + 1] == "refresh"
    assert events[action_index + 1] == "refresh"
    assert events.count("refresh") == 5
    assert events[-1] == "refresh"


def test_refresh_hit_alias_targets_collection_alias_with_retries():
    from sentinel.services.ingest_service import _refresh_hit_alias

    collection = Mock()
    collection.name = "howler-hit"
    with patch("sentinel.services.ingest_service.datastore") as mock_datastore:
        mock_datastore.return_value.hit = collection

        _refresh_hit_alias()

    collection.with_retries.assert_called_once_with(
        collection.datastore.client.indices.refresh,
        index=collection.name,
    )
    collection.commit.assert_not_called()


def test_case_descendants_searches_large_membership_in_bounded_shuffled_batches():
    from howler.utils.str_utils import sanitize_lucene_query

    from sentinel.services import ingest_service

    tenant_id = "tenant-for-batch-test"
    incident_identity = "incident-for-batch-test"
    hit_ids = [str(uuid4()) for _ in range(1003)]
    records = {}
    for index, hit_id in enumerate(hit_ids):
        membership_kind = index % 37
        if membership_kind == 0:
            continue  # Deleted/missing hit referenced by the case.
        record_tenant = "foreign-tenant" if membership_kind == 1 else tenant_id
        record_incident = "foreign-incident" if membership_kind == 2 else incident_identity
        record_type = "incident" if membership_kind == 3 else ("alert" if index % 2 == 0 else "evidence")
        records[hit_id] = SimpleNamespace(
            howler=SimpleNamespace(id=hit_id),
            sentinel=SimpleNamespace(
                tenant_id=record_tenant,
                incident_id=record_incident,
                record_type=record_type,
            ),
        )

    case = SimpleNamespace(
        items=[SimpleNamespace(type="hit", value=hit_id) for hit_id in hit_ids]
        + [SimpleNamespace(type="hit", value=hit_ids[0]), SimpleNamespace(type="folder", value="ignored")]
    )
    expected_chunks = [hit_ids[offset : offset + 250] for offset in range(0, len(hit_ids), 250)]
    search_calls = []
    hit_collection = Mock()

    def shuffled_search(query, *, rows, fl, as_obj):
        call_index = len(search_calls)
        batch = expected_chunks[call_index]
        expected_query = f"howler.id:({' OR '.join(sanitize_lucene_query(hit_id) for hit_id in batch)})"
        assert query == expected_query
        assert rows == len(batch)
        assert fl == "*"
        assert as_obj is True
        search_calls.append((query, rows))
        return {"items": [records[hit_id] for hit_id in reversed(batch) if hit_id in records]}

    hit_collection.search.side_effect = shuffled_search
    with patch.object(ingest_service, "datastore", return_value=SimpleNamespace(hit=hit_collection)):
        descendants = ingest_service._case_descendants(case, tenant_id, incident_identity)
        alert_ids, evidence_ids = ingest_service._case_record_ids(descendants)

    expected_descendants = [
        records[hit_id]
        for hit_id in hit_ids
        if hit_id in records
        and records[hit_id].sentinel.tenant_id == tenant_id
        and records[hit_id].sentinel.incident_id == incident_identity
        and records[hit_id].sentinel.record_type in {"alert", "evidence"}
    ]
    assert [hit.howler.id for hit in descendants] == [hit.howler.id for hit in expected_descendants]
    assert alert_ids == [hit.howler.id for hit in expected_descendants if hit.sentinel.record_type == "alert"]
    assert evidence_ids == [hit.howler.id for hit in expected_descendants if hit.sentinel.record_type == "evidence"]
    assert len(search_calls) == 5
    assert all(0 < rows <= 250 for _, rows in search_calls)
    hit_collection.get.assert_not_called()


def test_concurrent_same_incident_ingest_is_serialized_and_reuses_case(client, tenant_mapping):
    incident = _incident("serialized-ingest", alerts=[])
    app = client.application

    def post_once():
        with app.test_client() as isolated_client:
            return _post(isolated_client, incident)

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: post_once(), range(2)))

    assert sorted(response.status_code for response in responses) == [200, 201]
    response_data = [_api_response(response) for response in responses]
    assert len({data["incident_hit_id"] for data in response_data}) == 1
    assert len({data["case_id"] for data in response_data}) == 1
    root = datastore().hit.get(response_data[0]["incident_hit_id"], as_obj=True)
    case = datastore().case.get(response_data[0]["case_id"])
    assert root and case
    assert root.howler.related == [case.case_id]
    assert len([item for item in case.items if item.type == "hit" and item.value == root.howler.id]) == 1


def test_ingest_lock_acquisition_failure_does_not_fall_back_to_unlocked_work(client, tenant_mapping, monkeypatch):
    from sentinel.services import ingest_service

    lock_args = []

    class FailingLock:
        def __init__(self, name, timeout):
            self.name = name
            self.timeout = timeout
            lock_args.append((name, timeout))

        def __enter__(self):
            raise RuntimeError("simulated Redis lock acquisition failure")

        def __exit__(self, *_args):
            raise AssertionError("an unacquired lock must not be released")

    monkeypatch.setattr(ingest_service, "RedisLock", FailingLock)
    incident = _incident("lock-acquisition-failure", alerts=[])
    with patch.object(ingest_service, "_find_existing_incident") as lookup:
        response = _post(client, incident)

    assert response.status_code == 500
    lookup.assert_not_called()
    root_hit_id = ingest_service._stable_hit_id(SAMPLE_TENANT_ID, incident["id"], "incident")
    expected_lock_name = f"sentinel-ingest:{datastore().hit.name}:{root_hit_id}"
    assert lock_args == [(expected_lock_name, 600)]


@pytest.mark.parametrize("missing_link", ["root-backreference", "case-root-item"])
def test_replay_repairs_missing_root_case_link_without_duplicate_case(client, tenant_mapping, missing_link):
    incident = _incident(f"repair-{missing_link}", alerts=[])
    first = _post(client, incident)
    assert first.status_code == 201
    first_data = _api_response(first)
    root = datastore().hit.get(first_data["incident_hit_id"], as_obj=True)
    case, case_version = datastore().case.get(first_data["case_id"], as_obj=True, version=True)
    assert root and case and case_version

    if missing_link == "root-backreference":
        root.howler.related.remove(case.case_id)
        root.save(version=datastore().hit.get(root.howler.id, as_obj=True, version=True)[1])
    else:
        case.items = [item for item in case.items if item.value != root.howler.id]
        case.save(version=case_version)

    retry = _post(client, incident)

    assert retry.status_code == 200
    retry_data = _api_response(retry)
    assert retry_data["case_id"] == first_data["case_id"]
    repaired_root = datastore().hit.get(root.howler.id, as_obj=True)
    repaired_case = datastore().case.get(first_data["case_id"])
    assert repaired_root and repaired_case
    assert repaired_root.howler.related == [repaired_case.case_id]
    assert len([item for item in repaired_case.items if item.type == "hit" and item.value == root.howler.id]) == 1


def test_replay_prefers_deterministic_case_over_changed_root_association(client, tenant_mapping):
    from sentinel.services import ingest_service

    incident = _incident("deterministic-case-precedence", alerts=[])
    first = _post(client, incident)
    assert first.status_code == 201
    first_data = _api_response(first)
    root = datastore().hit.get(first_data["incident_hit_id"], as_obj=True)
    stable_case, stable_case_version = datastore().case.get(first_data["case_id"], as_obj=True, version=True)
    assert root and stable_case and stable_case_version

    analyst_case_id = _new_owned_case_id()
    analyst_case = case_service.create_case(
        {
            "title": "Analyst-owned case",
            "summary": "Unrelated analyst case",
            "classification": root.classification,
            "items": [{"type": "hit", "value": root.howler.id, "name": "Analyst reference"}],
        },
        user=ingest_service.SYSTEM_USER,
        case_id=analyst_case_id,
    )
    analyst_case_before = analyst_case.as_primitives()

    stable_case.items = [item for item in stable_case.items if item.value != root.howler.id]
    stable_case.save(version=stable_case_version)
    root, root_version = datastore().hit.get(root.howler.id, as_obj=True, version=True)
    assert root and root_version
    root.howler.related = [analyst_case_id]
    root.save(version=root_version)

    replay = copy.deepcopy(incident)
    replay.pop("alerts")
    replay["status"] = "resolved"
    with patch.object(
        ingest_service, "_find_case_for_incident", wraps=ingest_service._find_case_for_incident
    ) as fallback:
        response = _post(client, replay)
        fallback.assert_not_called()

    assert response.status_code == 200
    response_data = _api_response(response)
    assert response_data["case_id"] == first_data["case_id"]
    repaired_case = datastore().case.get(first_data["case_id"])
    updated_root = datastore().hit.get(first_data["incident_hit_id"], as_obj=True)
    analyst_case_after = datastore().case.get(analyst_case_id, as_obj=True)
    assert repaired_case and updated_root and analyst_case_after
    assert any(item.type == "hit" and item.value == updated_root.howler.id for item in repaired_case.items)
    assert first_data["case_id"] in updated_root.howler.related
    assert updated_root.howler.status == "resolved"
    assert analyst_case_after.as_primitives() == analyst_case_before


def test_legacy_case_fallback_is_used_when_deterministic_case_is_absent(client, tenant_mapping):
    from sentinel.services import ingest_service

    incident = _incident("legacy-case-fallback", alerts=[])
    first = _post(client, incident)
    assert first.status_code == 201
    first_data = _api_response(first)
    root = datastore().hit.get(first_data["incident_hit_id"], as_obj=True)
    assert root

    legacy_case_id = _new_owned_case_id()
    datastore().case.delete(first_data["case_id"], refresh="wait_for")
    legacy_case = case_service.create_case(
        {
            "title": "Legacy Sentinel case",
            "summary": "Legacy related case recovery",
            "classification": root.classification,
            "items": [{"type": "hit", "value": root.howler.id, "name": "Sentinel"}],
        },
        user=ingest_service.SYSTEM_USER,
        case_id=legacy_case_id,
    )
    root, root_version = datastore().hit.get(root.howler.id, as_obj=True, version=True)
    assert root and root_version
    root.howler.related = [legacy_case.case_id]
    root.save(version=root_version)

    replay = copy.deepcopy(incident)
    replay.pop("alerts")
    with patch.object(
        ingest_service, "_find_case_for_incident", wraps=ingest_service._find_case_for_incident
    ) as fallback:
        response = _post(client, replay)
        fallback.assert_called_once()

    assert response.status_code == 200
    assert _api_response(response)["case_id"] == legacy_case_id
    assert datastore().case.get(first_data["case_id"]) is None


def test_ingest_case_cleanup_preserves_unowned_preexisting_and_concurrent_cases(monkeypatch):
    from sentinel.services import ingest_service

    ds = datastore()
    owned_case_id = _new_owned_case_id()
    preexisting_case_id = _new_owned_case_id()
    concurrent_case_id = _new_owned_case_id()

    def create_case(case_id, title):
        return case_service.create_case(
            {
                "title": title,
                "summary": title,
                "classification": ingest_service.SYSTEM_USER.classification,
            },
            user=ingest_service.SYSTEM_USER,
            case_id=case_id,
        )

    original_delete = ds.case.delete
    concurrent_created = False

    def create_unrelated_during_cleanup(case_id, **kwargs):
        nonlocal concurrent_created
        if not concurrent_created:
            create_case(concurrent_case_id, "Concurrent unrelated case")
            concurrent_created = True
        return original_delete(case_id, **kwargs)

    try:
        preexisting_case = create_case(preexisting_case_id, "Preexisting unrelated case")
        owned_case = create_case(owned_case_id, "Owned ingest test case")
        assert preexisting_case.case_id == preexisting_case_id
        assert owned_case.case_id == owned_case_id

        monkeypatch.setattr(ds.case, "delete", create_unrelated_during_cleanup)
        _delete_case_ids({owned_case_id})
        assert ds.case.get(owned_case_id) is None
        assert ds.case.get(preexisting_case_id) is not None
        assert ds.case.get(concurrent_case_id) is not None
    finally:
        monkeypatch.setattr(ds.case, "delete", original_delete)
        _delete_case_ids({owned_case_id, preexisting_case_id, concurrent_case_id})


def test_ingest_case_registry_cleans_partial_case_creation_and_preserves_unrelated_case(monkeypatch):
    from sentinel.services import ingest_service

    ds = datastore()
    first_case_id = _new_owned_case_id()
    absent_case_id = _new_owned_case_id()
    unrelated_case_id = str(uuid4())
    original_create = case_service.create_case
    create_calls = 0
    unrelated_case_created = False

    def case_data(title):
        return {
            "title": title,
            "summary": title,
            "classification": ingest_service.SYSTEM_USER.classification,
        }

    try:
        unrelated_case_created = True
        unrelated = original_create(
            case_data("Unrelated case outside the ingest registry"),
            user=ingest_service.SYSTEM_USER,
            case_id=unrelated_case_id,
        )

        def fail_second_create(*args, **kwargs):
            nonlocal create_calls
            create_calls += 1
            if create_calls == 2:
                raise RuntimeError("simulated failure after first case was persisted")
            return original_create(*args, **kwargs)

        monkeypatch.setattr(case_service, "create_case", fail_second_create)
        first_case = case_service.create_case(
            case_data("First owned case"), user=ingest_service.SYSTEM_USER, case_id=first_case_id
        )
        assert first_case.case_id == first_case_id
        with pytest.raises(RuntimeError, match="after first case was persisted"):
            case_service.create_case(
                case_data("Second owned case fails"), user=ingest_service.SYSTEM_USER, case_id=absent_case_id
            )

        assert ds.case.get(first_case_id) is not None
        assert ds.case.get(absent_case_id) is None
        _cleanup_owned_ingest_cases({first_case_id, absent_case_id})
        assert ds.case.get(first_case_id) is None
        assert ds.case.get(absent_case_id) is None
        assert ds.case.get(unrelated.case_id) is not None
    finally:
        try:
            _cleanup_owned_ingest_cases({first_case_id, absent_case_id})
        finally:
            if unrelated_case_created:
                _delete_case_ids({unrelated_case_id})


def test_case_creation_version_conflict_retries_same_deterministic_id(client, tenant_mapping, monkeypatch):
    from sentinel.services.ingest_service import _stable_hit_id

    incident = _incident("case-create-version-conflict", alerts=[])
    stable_case_id = _stable_hit_id(SAMPLE_TENANT_ID, incident["id"], "case")
    original_save = Case.save
    conflict_state = {"pending": True}

    def conflict_before_first_case_save(case, *args, **kwargs):
        if case.case_id == stable_case_id and conflict_state["pending"]:
            conflict_state["pending"] = False
            raise VersionConflictException("simulated case create conflict")
        return original_save(case, *args, **kwargs)

    monkeypatch.setattr(Case, "save", conflict_before_first_case_save)
    response = _post(client, incident)

    assert response.status_code == 201
    response_data = _api_response(response)
    assert response_data["case_id"] == stable_case_id
    root = datastore().hit.get(response_data["incident_hit_id"], as_obj=True)
    case = datastore().case.get(stable_case_id)
    assert root and case
    assert root.howler.related == [stable_case_id]
    assert len([item for item in case.items if item.type == "hit" and item.value == root.howler.id]) == 1


def test_initial_case_save_conflict_preserves_concurrent_analyst_edits(client, tenant_mapping, monkeypatch):
    incident = _incident("initial-case-save-conflict")
    original_save = Case.save
    conflict_pending = True

    def save_with_concurrent_analyst_edit(case, *args, **kwargs):
        nonlocal conflict_pending
        if case.case_id and kwargs.get("version") != CREATE_TOKEN and conflict_pending:
            conflict_pending = False
            concurrent, version = datastore().case.get(case.case_id, as_obj=True, version=True)
            concurrent.title = "Analyst-edited title"
            concurrent.items.append(CaseItem({"type": "folder", "name": "Analyst notes"}))
            original_save(concurrent, version=version)
            raise VersionConflictException("simulated overlapping analyst update")
        return original_save(case, *args, **kwargs)

    monkeypatch.setattr(Case, "save", save_with_concurrent_analyst_edit)
    response = _post(client, incident)

    assert response.status_code == 201
    response_data = _api_response(response)
    case = datastore().case.get(response_data["case_id"])
    assert case
    assert case.title == "Analyst-edited title"
    assert any(item.type == "folder" and item.name == "Analyst notes" for item in case.items)
    assert set(response_data["source_alert_hit_ids"]).issubset(
        {item.value for item in case.items if item.type == "hit"}
    )
    assert set(response_data["evidence_hit_ids"]).issubset({item.value for item in case.items if item.type == "hit"})


@pytest.mark.parametrize("concurrent_replay", [False, True], ids=["missing-items", "already-attached"])
def test_zero_alert_incident_reconciles_alerts_after_case_conflict(
    client, tenant_mapping, monkeypatch, concurrent_replay
):
    from sentinel.services import ingest_service

    incident = _incident(f"add-alert-later-{concurrent_replay}", alerts=[])
    first = _post(client, incident)
    assert first.status_code == 201
    first_data = _api_response(first)

    later = copy.deepcopy(incident)
    later["status"] = "resolved"
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    alert["id"] = "late-added-alert"
    alert["incidentId"] = incident["id"]
    later["alerts"] = [alert]

    original_save = Case.save
    conflict_pending = True
    save_calls = 0

    def save_with_concurrent_edit(case, *args, **kwargs):
        nonlocal conflict_pending, save_calls
        if case.case_id == first_data["case_id"]:
            save_calls += 1
        if case.case_id == first_data["case_id"] and conflict_pending:
            conflict_pending = False
            concurrent, version = datastore().case.get(case.case_id, as_obj=True, version=True)
            if concurrent_replay:
                concurrent.items = case.items
            concurrent.items.append(CaseItem({"type": "folder", "name": "Analyst notes"}))
            original_save(concurrent, version=version)
            raise VersionConflictException("simulated overlapping update")
        return original_save(case, *args, **kwargs)

    emitted_cases = []
    monkeypatch.setattr(
        ingest_service.comms_service,
        "emit",
        lambda event, data: emitted_cases.append((event, copy.deepcopy(data["case"]))),
    )
    monkeypatch.setattr(Case, "save", save_with_concurrent_edit)
    second = _post(client, later)

    assert second.status_code == 200
    second_data = _api_response(second)
    assert second_data["incident_hit_id"] == first_data["incident_hit_id"]
    assert second_data["case_id"] == first_data["case_id"]
    assert len(second_data["source_alert_hit_ids"]) == 1
    assert len(second_data["evidence_hit_ids"]) == 1
    assert second_data["total_hits_created"] == 2
    case = datastore().case.get(second_data["case_id"])
    assert case
    assert any(item.type == "folder" and item.name == "Analyst notes" for item in case.items)
    assert save_calls == (1 if concurrent_replay else 2)
    assert len(emitted_cases) == 1
    assert emitted_cases[0][0] == "cases"
    emitted_case = emitted_cases[0][1]
    assert emitted_case["case_id"] == case.case_id
    assert emitted_case["title"] == case.title
    assert any(item["type"] == "folder" and item["name"] == "Analyst notes" for item in emitted_case["items"])
    assert set(second_data["source_alert_hit_ids"]).issubset(
        {item["value"] for item in emitted_case["items"] if item["type"] == "hit"}
    )
    for hit_id in [*second_data["source_alert_hit_ids"], *second_data["evidence_hit_ids"]]:
        hit = datastore().hit.get(hit_id, as_obj=True)
        assert hit and hit.howler.status == "resolved"


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
    user_evidence = next(
        evidence
        for alert in reordered["alerts"]
        for evidence in alert["evidence"]
        if evidence.get("@odata.type", "").endswith("userEvidence")
    )
    user_evidence.update(verdict="malicious", remediationStatus="remediated")
    second = _post(client, reordered)

    assert second.status_code == 200
    second_data = _api_response(second)
    assert second_data["incident_hit_id"] == first_data["incident_hit_id"]
    assert second_data["case_id"] == first_data["case_id"]
    assert set(second_data["source_alert_hit_ids"]) == set(first_data["source_alert_hit_ids"])
    assert set(second_data["evidence_hit_ids"]) == set(first_data["evidence_hit_ids"])
    expected_alert_by_raw_evidence = {
        json.dumps(evidence, sort_keys=True): alert["id"]
        for alert in incident["alerts"]
        for evidence in alert["evidence"]
    }
    for hit_id in second_data["evidence_hit_ids"]:
        hit = datastore().hit.get(hit_id, as_obj=True)
        assert hit
        raw_evidence = json.loads(hit.howler.data[0])
        assert hit.sentinel.alert_id == expected_alert_by_raw_evidence[json.dumps(raw_evidence, sort_keys=True)]

    subset = copy.deepcopy(reordered)
    subset["alerts"] = [subset["alerts"][0]]
    subset["alerts"][0]["evidence"] = [subset["alerts"][0]["evidence"][0]]
    subset_response = _post(client, subset)
    assert subset_response.status_code == 200
    subset_data = _api_response(subset_response)
    assert set(subset_data["source_alert_hit_ids"]) == set(first_data["source_alert_hit_ids"])
    assert set(subset_data["evidence_hit_ids"]) == set(first_data["evidence_hit_ids"])
    assert subset_data["total_hits_created"] == 0

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
    lifecycle_replay = copy.deepcopy(extended)
    lifecycle_replay["alerts"][-1]["evidence"][0]["verdict"] = "malicious"
    fourth = _post(client, lifecycle_replay)
    assert fourth.status_code == 200
    fourth_data = _api_response(fourth)
    assert fourth_data["evidence_hit_ids"] == third_data["evidence_hit_ids"]
    assert fourth_data["total_hits_created"] == 0
    case = datastore().case.get(first_data["case_id"])
    assert case
    assert len([item for item in case.items if item.type == "hit"]) == initial_hit_count + 2


def test_file_evidence_identity_combines_device_path_name_and_hash(client, tenant_mapping):
    file_a = {
        "@odata.type": "#microsoft.graph.security.fileEvidence",
        "mdeDeviceId": "device-file-1",
        "fileDetails": {
            "filePath": "C:\\Temp\\alpha",
            "fileName": "sample-a.dll",
            "sha256": "same-file-content-hash",
        },
    }
    file_b = {
        "@odata.type": "#microsoft.graph.security.fileEvidence",
        "mdeDeviceId": "device-file-1",
        "fileDetails": {
            "filePath": "C:\\Users\\analyst\\Downloads",
            "fileName": "renamed-sample.dll",
            "sha256": "same-file-content-hash",
        },
    }
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    alert["evidence"] = [file_a]
    incident = _incident("file-composite-identity", alerts=[alert])

    first = _post(client, incident)
    assert first.status_code == 201
    first_data = _api_response(first)
    first_id = first_data["evidence_hit_ids"][0]

    replay = copy.deepcopy(incident)
    replay["alerts"][0]["evidence"] = [copy.deepcopy(file_b), copy.deepcopy(file_a)]
    replay["alerts"][0]["evidence"][1].update(verdict="malicious", remediationStatus="remediated")
    second = _post(client, replay)

    assert second.status_code == 200
    second_data = _api_response(second)
    assert len(second_data["evidence_hit_ids"]) == 2
    evidence_by_file = {}
    for hit_id in second_data["evidence_hit_ids"]:
        hit = datastore().hit.get(hit_id, as_obj=True)
        assert hit
        raw = json.loads(hit.howler.data[0])
        details = raw["fileDetails"]
        evidence_by_file[(details["filePath"], details["fileName"])] = hit_id
        assert hit.sentinel.alert_id == replay["alerts"][0]["id"]

    assert evidence_by_file[(file_a["fileDetails"]["filePath"], file_a["fileDetails"]["fileName"])] == first_id
    assert evidence_by_file[(file_b["fileDetails"]["filePath"], file_b["fileDetails"]["fileName"])] != first_id
    case = datastore().case.get(second_data["case_id"])
    assert case
    assert set(evidence_by_file.values()).issubset({item.value for item in case.items if item.type == "hit"})


def test_explicit_evidence_id_remains_authoritative_over_composite_fields(client, tenant_mapping):
    evidence = {
        "@odata.type": "#microsoft.graph.security.fileEvidence",
        "id": "graph-evidence-id",
        "mdeDeviceId": "device-external-id",
        "fileDetails": {
            "filePath": "C:\\Temp\\first",
            "fileName": "first.dll",
            "sha256": "first-content-hash",
        },
    }
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    alert["evidence"] = [evidence]
    incident = _incident("external-evidence-id", alerts=[alert])

    first = _post(client, incident)
    assert first.status_code == 201
    first_data = _api_response(first)
    first_evidence_id = first_data["evidence_hit_ids"][0]

    replay = copy.deepcopy(incident)
    replay["alerts"][0]["evidence"][0]["fileDetails"] = {
        "filePath": "C:\\Users\\analyst\\second",
        "fileName": "second.dll",
        "sha256": "different-content-hash",
    }
    second = _post(client, replay)

    assert second.status_code == 200
    second_data = _api_response(second)
    assert second_data["evidence_hit_ids"] == [first_evidence_id]
    assert second_data["total_hits_created"] == 0


def test_process_evidence_identity_distinguishes_pid_reuse_and_device(client, tenant_mapping):
    def process(device_id, created, path):
        return {
            "@odata.type": "#microsoft.graph.security.processEvidence",
            "mdeDeviceId": device_id,
            "processId": "4242",
            "processCreationDateTime": created,
            "imageFile": {
                "filePath": path,
                "fileName": "worker.exe",
                "sha256": "worker-image-hash",
            },
        }

    process_a = process("device-process-1", "2025-01-01T00:00:00Z", "C:\\Tools")
    pid_reuse = process("device-process-1", "2025-02-01T00:00:00Z", "C:\\Tools")
    another_device = process("device-process-2", "2025-01-01T00:00:00Z", "C:\\Tools")
    alert = copy.deepcopy(SENTINEL_ALERT["alerts"][0])
    alert["evidence"] = [process_a]
    incident = _incident("process-composite-identity", alerts=[alert])

    first = _post(client, incident)
    assert first.status_code == 201
    first_data = _api_response(first)
    first_id = first_data["evidence_hit_ids"][0]

    replay = copy.deepcopy(incident)
    replay["alerts"][0]["evidence"] = [
        copy.deepcopy(another_device),
        copy.deepcopy(pid_reuse),
        copy.deepcopy(process_a),
    ]
    for evidence in replay["alerts"][0]["evidence"]:
        evidence.update(verdict="malicious", detectionStatus="remediated")
    second = _post(client, replay)

    assert second.status_code == 200
    second_data = _api_response(second)
    assert len(second_data["evidence_hit_ids"]) == 3
    evidence_by_process = {}
    for hit_id in second_data["evidence_hit_ids"]:
        hit = datastore().hit.get(hit_id, as_obj=True)
        assert hit
        raw = json.loads(hit.howler.data[0])
        evidence_by_process[(raw["mdeDeviceId"], raw["processCreationDateTime"])] = hit_id
        assert hit.sentinel.alert_id == replay["alerts"][0]["id"]

    assert evidence_by_process[("device-process-1", "2025-01-01T00:00:00Z")] == first_id
    assert evidence_by_process[("device-process-1", "2025-02-01T00:00:00Z")] != first_id
    assert evidence_by_process[("device-process-2", "2025-01-01T00:00:00Z")] != first_id


def test_failed_child_case_link_is_reported_and_replay_repairs_it(client, tenant_mapping, monkeypatch):
    incident = _incident("retry-link-failure")
    original_append = case_service.append_hits
    failure_state = {"pending": True}

    def fail_first_batch(case, items, **kwargs):
        if failure_state["pending"]:
            failure_state["pending"] = False
            raise RuntimeError("simulated case-link failure")
        return original_append(case, items, **kwargs)

    monkeypatch.setattr(case_service, "append_hits", fail_first_batch)
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


def test_failed_case_save_does_not_emit_completion_until_retry(client, tenant_mapping, monkeypatch):
    from sentinel.services import ingest_service

    incident = _incident("completion-save-retry")
    original_save = Case.save
    save_failure_pending = True
    emitted_cases = []

    def fail_first_completion_save(case, *args, **kwargs):
        nonlocal save_failure_pending
        if case.case_id and kwargs.get("version") != CREATE_TOKEN and save_failure_pending:
            save_failure_pending = False
            raise RuntimeError("simulated final case save failure")
        return original_save(case, *args, **kwargs)

    monkeypatch.setattr(Case, "save", fail_first_completion_save)
    monkeypatch.setattr(
        ingest_service.comms_service,
        "emit",
        lambda event, data: emitted_cases.append((event, copy.deepcopy(data["case"]))),
    )

    failed = _post(client, incident)

    assert failed.status_code == 500
    assert len(emitted_cases) == 1
    assert emitted_cases[0][0] == "cases"
    assert len([item for item in emitted_cases[0][1]["items"] if item["type"] == "hit"]) == 1

    retried = _post(client, incident)

    assert retried.status_code == 200
    response_data = _api_response(retried)
    assert len(emitted_cases) == 2
    completed_case = emitted_cases[-1][1]
    assert completed_case["case_id"] == response_data["case_id"]
    completed_hit_ids = {item["value"] for item in completed_case["items"] if item["type"] == "hit"}
    assert response_data["incident_hit_id"] in completed_hit_ids
    assert set(response_data["source_alert_hit_ids"]).issubset(completed_hit_ids)
    assert set(response_data["evidence_hit_ids"]).issubset(completed_hit_ids)


def test_status_replay_after_case_creation_failure_preserves_single_case_backreference(
    client, tenant_mapping, monkeypatch
):
    from sentinel.services import ingest_service

    incident = _incident("case-create-retry", alerts=[])
    original_create_case = case_service.create_case
    failure_state = {"pending": True}
    case_events = []

    monkeypatch.setattr(
        ingest_service.comms_service,
        "emit",
        lambda event, data: case_events.append((event, copy.deepcopy(data["case"]))),
    )

    def fail_case_creation_once(*args, **kwargs):
        if failure_state["pending"]:
            failure_state["pending"] = False
            raise RuntimeError("simulated initial case creation failure")
        return original_create_case(*args, **kwargs)

    monkeypatch.setattr(case_service, "create_case", fail_case_creation_once)
    first = _post(client, incident)
    assert first.status_code == 500
    assert case_events == []

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
    assert len(case_events) == 2
    assert all(event == "cases" for event, _ in case_events)
    assert case_events[-1][1]["case_id"] == second_data["case_id"]
    assert len([item for item in case_events[-1][1]["items"] if item["type"] == "hit"]) == 1

    second_replay = copy.deepcopy(incident)
    second_replay["status"] = "active"
    third = _post(client, second_replay)
    assert third.status_code == 200
    third_data = _api_response(third)
    assert third_data["case_id"] == second_data["case_id"]
    assert len(case_events) == 2

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
