"""Offline fail-closed tests for the live Step 9 application rehearsal."""

from __future__ import annotations

import copy
import json
from dataclasses import replace

import pytest

from build_scripts.step9_application_rehearsal import (
    RedisHandle,
    RehearsalAbort,
    _minimal_python_environment,
    acceptance_result,
    assert_acl_expectations,
    assert_case_read_matches_fixture,
    assert_raw_query_equivalent,
    assert_resource_etag_contract,
    build_seed_plan,
    capture_application_state,
    derive_namespace,
    expected_case_items_for_principal,
    finalize_application_checks,
    require_subprocess_success,
    validate_fresh_empty_cluster,
    validate_seed_plan,
    verify_redis_owned,
)


def _redis_inspect(*, run_id: str = "offline-test") -> dict:
    return {
        "Id": "a" * 64,
        "Name": "/howler-step9-offline-test-app-redis",
        "Config": {
            "Image": "redis:7.4.2-alpine",
            "Labels": {
                "howler.step9.rehearsal": "true",
                "howler.step9.run": run_id,
                "howler.step9.role": "application-redis",
            },
        },
        "State": {"Status": "running"},
        "Mounts": [],
        "HostConfig": {
            "NetworkMode": "bridge",
            "Privileged": False,
            "Devices": [],
            "CapAdd": [],
            "Tmpfs": {"/data": "rw,noexec,nosuid,size=16m"},
            "PortBindings": {"6379/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49152"}]},
        },
        "NetworkSettings": {
            "Networks": {"bridge": {"IPAddress": "172.17.0.2"}},
            "Ports": {"6379/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49152"}]},
        },
    }


class _FakeDocker:
    def __init__(self, data: dict):
        self.run_id = "offline-test"
        self.data = data

    def _docker(self, arguments: list[str], *, check: bool = True) -> str:
        assert arguments[:2] == ["inspect", "a" * 64]
        return json.dumps([self.data])


def test_namespaces_and_full_seed_plan_are_strictly_isolated() -> None:
    assert derive_namespace("offline-test") == "step9-app-offline-test"
    plan = build_seed_plan("step9-app-offline-test")
    names = validate_seed_plan(plan, "step9-app-offline-test")
    assert len(names) == 11
    assert len(plan.documents) == 11
    assert all(name.startswith("step9-app-offline-test-howler-") and name.endswith("_hot") for name in names)

    with pytest.raises(RehearsalAbort, match="Invalid Step 9 run ID"):
        derive_namespace("../shared-howler")
    with pytest.raises(ValueError, match="production-like"):
        build_seed_plan("step9-prod")
    with pytest.raises(RehearsalAbort, match="namespace differs"):
        validate_seed_plan(plan, "step9-app-other-run")

    unsafe_index = replace(plan.indexes[0], alias="howler-action")
    unsafe_plan = replace(plan, indexes=(unsafe_index, *plan.indexes[1:]))
    with pytest.raises(RehearsalAbort, match="alias escapes"):
        validate_seed_plan(unsafe_plan, plan.namespace)


def test_fresh_cluster_gate_rejects_wrong_identity_or_nonempty_inventory() -> None:
    info = {
        "cluster_name": "owned-donor",
        "cluster_uuid": "fixture-uuid",
        "version": {"number": "8.19.11"},
    }
    health = {"status": "green"}
    validate_fresh_empty_cluster(info, health, {}, expected_name="owned-donor")

    with pytest.raises(RehearsalAbort, match="Invalid cluster identity"):
        validate_fresh_empty_cluster(info, health, {}, expected_name="not-owned")
    with pytest.raises(RehearsalAbort, match="not empty"):
        validate_fresh_empty_cluster(info, health, {"shared-howler-hit_hot": {}}, expected_name="owned-donor")


def test_explicit_api_root_is_the_only_application_python_path(tmp_path) -> None:
    api_root = tmp_path / "primary-api"
    config_dir = tmp_path / "config"
    plugin_dir = config_dir / "plugins"
    log_dir = tmp_path / "logs"
    environment = _minimal_python_environment(
        api_root=api_root,
        api_endpoint="172.20.0.2:9200",
        redis_port=49152,
        namespace="step9-app-offline",
        config_dir=config_dir,
        plugin_dir=plugin_dir,
        log_dir=log_dir,
    )
    assert environment["PYTHONPATH"] == str(api_root)
    assert environment["HWL_DATASTORE_INDEX_PREFIX"] == "step9-app-offline-howler"
    assert environment["HWL_UI__DEBUG"] == "false"
    assert environment["HWL_USE_JOB_SYSTEM"] == "false"
    assert environment["HWL_AUTH__INTERNAL__ENABLED"] == "false"


def test_redis_ownership_gate_rejects_foreign_container_and_non_loopback_port() -> None:
    handle = RedisHandle("howler-step9-offline-test-app-redis", "a" * 64, "127.0.0.1", 49152)
    verify_redis_owned(_FakeDocker(_redis_inspect()), handle, ping=False)

    foreign = _redis_inspect()
    foreign["Config"]["Labels"]["howler.step9.run"] = "somebody-elses-run"
    with pytest.raises(RehearsalAbort, match="not owned"):
        verify_redis_owned(_FakeDocker(foreign), handle, ping=False)

    exposed = _redis_inspect()
    exposed["HostConfig"]["PortBindings"]["6379/tcp"][0]["HostIp"] = "0.0.0.0"
    with pytest.raises(RehearsalAbort, match="loopback"):
        verify_redis_owned(_FakeDocker(exposed), handle, ping=False)


def test_application_state_capture_rejects_unrecognized_system_index() -> None:
    class ExtraIndexClient:
        @staticmethod
        def request(method: str, path: str, body=None):
            assert method == "GET"
            assert path == "/_all/_settings?flat_settings=true&expand_wildcards=all"
            return {"step9-app-test-howler-hit_hot": {}, "somebody-elses-index": {}}

    with pytest.raises(RehearsalAbort, match="Unexpected non-application indices"):
        capture_application_state(ExtraIndexClient(), ["step9-app-test-howler-hit_hot"], 100)


def test_acl_comparison_rejects_count_or_identity_expectation_mismatch() -> None:
    assert_acl_expectations(
        "step9-reader", {"ids": ["00000000-0000-4000-8000-000000000001"], "count": 1, "facets": {"open": 1}}
    )
    with pytest.raises(RehearsalAbort, match="ACL/query response differs"):
        assert_acl_expectations(
            "step9-reader",
            {
                "ids": [
                    "00000000-0000-4000-8000-000000000001",
                    "00000000-0000-4000-8000-000000000003",
                ],
                "count": 2,
                "facets": {"in-progress": 1, "open": 1},
            },
        )


def test_hit_etag_is_required_but_existing_case_get_etag_is_optional() -> None:
    assert_resource_etag_contract("hit", '"5---1"')
    with pytest.raises(RehearsalAbort, match="GET Hit did not return the required ETag"):
        assert_resource_etag_contract("hit", None)
    assert_resource_etag_contract("case", None)
    with pytest.raises(RehearsalAbort, match="Unknown ETag contract resource"):
        assert_resource_etag_contract("case_items", None)


def test_case_read_verifies_full_classification_and_item_payload() -> None:
    case = {
        "id": "10000000-0000-4000-8000-000000000001",
        "case_id": "10000000-0000-4000-8000-000000000001",
        "classification": "UNRESTRICTED",
        "items": [
            {
                "id": "20000000-0000-4000-8000-000000000001",
                "classification": "UNRESTRICTED",
                "type": "hit",
                "value": "00000000-0000-4000-8000-000000000001",
            }
        ],
    }
    assert_case_read_matches_fixture(case, case)
    altered = {**case, "items": [{**case["items"][0], "classification": "RESTRICTED"}]}
    with pytest.raises(RehearsalAbort, match="Case data/classification/items differ"):
        assert_case_read_matches_fixture(altered, case)


def test_expected_case_items_use_fixture_principal_and_linked_hit_acl_helpers() -> None:
    plan = build_seed_plan("step9-app-case-acl")
    case_source = copy.deepcopy(next(document.source for document in plan.documents if document.collection == "case"))
    restricted = next(
        document.source
        for document in plan.documents
        if document.collection == "user" and document.document_id == "step9-restricted-reader"
    )
    hit_sources = {document.document_id: document.source for document in plan.documents if document.collection == "hit"}
    d1_hit = hit_sources["00000000-0000-4000-8000-000000000002"]
    d2_hit = hit_sources["00000000-0000-4000-8000-000000000003"]
    case_source["items"].extend(
        [
            {
                "id": "20000000-0000-4000-8000-000000000002",
                "name": "D1-only synthetic item",
                "type": "hit",
                "value": "00000000-0000-4000-8000-000000000002",
                "visible": True,
                "classification": d1_hit["classification"],
            },
            {
                "id": "20000000-0000-4000-8000-000000000003",
                "name": "D2 synthetic item",
                "type": "hit",
                "value": "00000000-0000-4000-8000-000000000003",
                "visible": True,
                "classification": d2_hit["classification"],
            },
        ]
    )

    visible = expected_case_items_for_principal(plan, case_source, restricted)
    assert [item["id"] for item in visible] == [
        "20000000-0000-4000-8000-000000000001",
        "20000000-0000-4000-8000-000000000003",
    ]


@pytest.mark.parametrize(
    ("baseline_hits", "target_hits"),
    [
        (
            [{"_id": "a", "_score": 3.0}, {"_id": "b", "_score": 2.0}],
            [{"_id": "b", "_score": 2.0}, {"_id": "a", "_score": 3.0}],
        ),
        ([{"_id": "a", "_score": 3.0}], [{"_id": "a", "_score": 3.000001}]),
    ],
)
def test_raw_query_comparison_rejects_order_and_score_drift(baseline_hits: list, target_hits: list) -> None:
    request = {
        "method": "POST",
        "path": "/step9-howler-hit/_search",
        "index_alias": "step9-howler-hit",
        "body": {"query": {"match_all": {}}},
    }
    baseline = {
        "request": request,
        "response": {"hits": {"hits": baseline_hits}, "aggregations": {"s": {"buckets": []}}},
    }
    target = {"request": request, "response": {"hits": {"hits": target_hits}, "aggregations": {"s": {"buckets": []}}}}
    with pytest.raises(RehearsalAbort, match="ordered ES hits"):
        assert_raw_query_equivalent(baseline, target, query_name="relevance")


def test_child_failure_is_an_application_failure_and_cannot_yield_acceptance_pass() -> None:
    with pytest.raises(RehearsalAbort, match="subprocess failed"):
        require_subprocess_success(7, "mapping parity", "child import failed")

    class FailedChild:
        @staticmethod
        def poll() -> int:
            return 23

    result = finalize_application_checks(FailedChild(), {"failures": []})
    assert result["result"] == "FAIL"
    assert "return code 23" in result["failures"][0]

    gates = {
        "mapping_parity": "PASS",
        "upgrade": "PASS",
        "raw_queries": "PASS",
        "application": result["result"],
        "no_app_mutation": "PASS",
        "rollback": "PASS",
    }
    assert acceptance_result(gates) == "FAIL"
    assert acceptance_result({key: "PASS" for key in gates if key != "rollback"}) == "BLOCKED"
