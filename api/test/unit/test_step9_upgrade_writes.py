"""Offline safety gates for the live Step 9 registered-collection write probe."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest

from build_scripts import step9_upgrade_writes as write_probe


def _owned_context(*, endpoint: str = "http://172.20.0.2:9200"):
    run_id = "offline-write"
    plan = write_probe.application_rehearsal.build_seed_plan(f"step9-app-{run_id}")
    handle = write_probe.es_rehearsal.ClusterHandle(
        role="cutover",
        name=f"howler-step9-{run_id}-cutover",
        container_id="a" * 64,
        volume=f"howler-step9-{run_id}-cutover-data",
        cluster_name=f"howler-step9-{run_id}-cutover",
        version=write_probe.es_rehearsal.TARGET_VERSION,
        base_url=endpoint,
        repository_readonly=True,
    )
    runtime = SimpleNamespace(
        run_id=run_id,
        handles={"cutover": handle},
        volumes={"cutover": handle.volume},
    )
    return runtime, handle, plan


def test_legacy_storage_plan_uses_captured_sources_without_seed_mutation() -> None:
    namespace = "step9-app-legacy-write"
    fixture_plan = write_probe.application_fixture.build_seed_plan(namespace)
    fixture_documents = {document.document_id: document.source.copy() for document in fixture_plan.documents}

    actual_plan = write_probe.validate_legacy_storage_plan(fixture_plan)

    assert actual_plan is fixture_plan
    assert all(document.source == fixture_documents[document.document_id] for document in fixture_plan.documents)
    assert {
        document.collection: document.source.get("__index")
        for document in actual_plan.documents
        if document.collection in {"hit", "case"}
    } == {"hit": "hit", "case": "case"}
    fixture = write_probe.application_fixture.load_application_fixture()
    assert all(
        entry["source"].get("__index") == collection and entry["model_primitives"].get("__index") == collection
        for collection in ("hit", "case")
        for entry in fixture["documents"][collection]
    )
    assert all(
        "__index" not in document.source
        for document in actual_plan.documents
        if document.collection not in {"hit", "case"}
    )


def test_legacy_storage_plan_rejects_corrupt_or_missing_captured_source_helper() -> None:
    plan = write_probe.application_fixture.build_seed_plan("step9-app-corrupt-source")
    hit_index = next(index for index, document in enumerate(plan.documents) if document.collection == "hit")
    documents = list(plan.documents)

    corrupt_id_source = dict(documents[hit_index].source)
    corrupt_id_source["id"] = "not-the-fixture-document-id"
    documents[hit_index] = replace(documents[hit_index], source=corrupt_id_source)
    with pytest.raises(write_probe.RehearsalAbort, match="ID/source mismatch"):
        write_probe.validate_legacy_storage_plan(replace(plan, documents=tuple(documents)))

    plan = write_probe.application_fixture.build_seed_plan("step9-app-missing-source-helper")
    documents = list(plan.documents)
    hit_index = next(index for index, document in enumerate(plan.documents) if document.collection == "hit")
    missing_source = dict(documents[hit_index].source)
    del missing_source["__index"]
    documents[hit_index] = replace(documents[hit_index], source=missing_source)
    with pytest.raises(write_probe.RehearsalAbort, match="missing persisted __index=hit"):
        write_probe.validate_legacy_storage_plan(replace(plan, documents=tuple(documents)))

    documents[hit_index] = replace(documents[hit_index], source={**missing_source, "__index": "case"})
    with pytest.raises(write_probe.RehearsalAbort, match="missing persisted __index=hit"):
        write_probe.validate_legacy_storage_plan(replace(plan, documents=tuple(documents)))


def test_legacy_index_helper_provenance_proves_origin_main_save_payload() -> None:
    provenance = write_probe.validate_legacy_helper_provenance(write_probe.API_ROOT)

    assert provenance["source_commit"] == write_probe._SOURCE_COMMIT
    assert provenance["serializer_contract"] == {
        "hit": {"git_path": "api/howler/odm/models/record.py", "emitted_value": "hit"},
        "case": {"git_path": "api/howler/odm/models/case.py", "emitted_value": "case"},
    }
    assert provenance["persistence_contract"]["serializes_hidden_fields"] is True
    assert provenance["persistence_contract"]["removes___index_before_write"] is False
    assert provenance["fixture_representation"]["source_postprocessing_removed___index"] is False
    assert provenance["fixture_representation"]["conclusion"].startswith("application-v2 preserves")
    assert provenance["capture_command"].startswith("HWL_CONF_FOLDER=")


def test_write_target_requires_run_identity_private_target_and_namespaced_physical_indices() -> None:
    runtime, handle, plan = _owned_context()

    target = write_probe.validate_write_probe_target(runtime, handle, plan)

    assert target["run_id"] == runtime.run_id
    assert target["namespace"] == plan.namespace
    assert target["cluster_name"] == handle.cluster_name
    assert target["cluster_version"] == write_probe.es_rehearsal.TARGET_VERSION

    with pytest.raises(write_probe.RehearsalAbort, match="private bridge IPv4"):
        foreign_runtime, foreign_handle, foreign_plan = _owned_context(endpoint="http://es.shared.example:9200")
        write_probe.validate_write_probe_target(foreign_runtime, foreign_handle, foreign_plan)

    with pytest.raises(write_probe.RehearsalAbort, match="namespace differs"):
        default_runtime, default_handle, default_plan = _owned_context()
        unsafe_plan = replace(default_plan, namespace="howler")
        write_probe.validate_write_probe_target(default_runtime, default_handle, unsafe_plan)

    with pytest.raises(write_probe.RehearsalAbort, match="cutover handle"):
        wrong_handle = replace(handle, container_id="b" * 64)
        write_probe.validate_write_probe_target(runtime, wrong_handle, plan)


@pytest.mark.parametrize(
    "observation",
    [
        {
            "exception_type": "RuntimeError",
            "source_unchanged": True,
            "version_before": "4---1",
            "version_after": "4---1",
        },
        {
            "exception_type": "VersionConflictException",
            "source_unchanged": False,
            "version_before": "4---1",
            "version_after": "4---1",
        },
        {
            "exception_type": "VersionConflictException",
            "source_unchanged": True,
            "version_before": "4---1",
            "version_after": "5---1",
        },
    ],
)
def test_stale_version_observation_rejects_missing_conflict_or_mutation(observation: dict) -> None:
    with pytest.raises(write_probe.RehearsalAbort):
        write_probe.validate_stale_version_observation(observation)


def test_stale_version_observation_accepts_only_conflict_without_source_or_token_change() -> None:
    write_probe.validate_stale_version_observation(
        {
            "exception_type": "VersionConflictException",
            "source_unchanged": True,
            "version_before": "4---1",
            "version_after": "4---1",
        }
    )


def test_owned_clone_cleanup_ids_cannot_target_fixture_documents_or_foreign_ids() -> None:
    write_probe.validate_owned_clone_ids(
        ["00000000-0000-4000-8000-000000000901", "00000000-0000-4000-8000-000000000902"],
        {"00000000-0000-4000-8000-000000000001"},
    )
    with pytest.raises(write_probe.RehearsalAbort, match="overlaps"):
        write_probe.validate_owned_clone_ids(
            ["00000000-0000-4000-8000-000000000001", "00000000-0000-4000-8000-000000000902"],
            {"00000000-0000-4000-8000-000000000001"},
        )
    with pytest.raises(write_probe.RehearsalAbort, match="not a UUID"):
        write_probe.validate_owned_clone_ids(["shared-hit", "another-hit"], set())


def test_state_guard_rejects_mapping_alias_uuid_inventory_or_reindex_drift() -> None:
    before = {
        "inventory": ["step9-app-test-howler-hit_hot"],
        "application_state": {
            "index_uuids": {"step9-app-test-howler-hit_hot": "uuid-a"},
            "aliases": {"step9-app-test-howler-hit_hot": {"step9-app-test-howler-hit": {}}},
            "mappings": {"step9-app-test-howler-hit_hot": {"properties": {"__index": {"type": "keyword"}}}},
            "counts": {"step9-app-test-howler-hit_hot": 8},
            "document_sha256": {"step9-app-test-howler-hit_hot": "source-a"},
        },
    }
    after = {
        "inventory": list(before["inventory"]),
        "application_state": {key: dict(value) for key, value in before["application_state"].items()},
    }

    assert write_probe.validate_write_state(before, after, ["step9-app-test-howler-hit_hot"])["result"] == "PASS"

    drifted = {"inventory": list(after["inventory"]), "application_state": {**after["application_state"]}}
    drifted["application_state"]["mappings"] = {"unexpected": {}}
    with pytest.raises(write_probe.RehearsalAbort, match="mappings outside the exact allowance"):
        write_probe.validate_write_state(before, drifted, ["step9-app-test-howler-hit_hot"])

    reindex = {"inventory": [*after["inventory"], "step9-app-test-howler-hit__reindex"]}
    reindex["application_state"] = after["application_state"]
    with pytest.raises(write_probe.RehearsalAbort, match="inventory"):
        write_probe.validate_write_state(before, reindex, ["step9-app-test-howler-hit_hot"])


def test_state_guard_accepts_only_the_exact_recorded_labels_dynamic_mapping_change() -> None:
    index = "step9-app-test-howler-hit_hot"
    marker = "step9-write-probe-run"
    before: dict[str, Any] = {
        "inventory": [index],
        "application_state": {
            "index_uuids": {index: "uuid-a"},
            "aliases": {index: {"step9-app-test-howler-hit": {}}},
            "mappings": {
                index: {
                    "mappings": {
                        "properties": {"labels": {"type": "object"}},
                        "dynamic_templates": [
                            {"strings_as_keywords": {"mapping": {"ignore_above": 8191, "type": "keyword"}}}
                        ],
                    }
                }
            },
            "counts": {index: 8},
            "document_sha256": {index: "source-a"},
        },
    }
    expected_after_mapping = {
        "mappings": {
            "properties": {"labels": {"properties": {marker: {"ignore_above": 8191, "type": "keyword"}}}},
            "dynamic_templates": before["application_state"]["mappings"][index]["mappings"]["dynamic_templates"],
        }
    }
    after = {
        "inventory": list(before["inventory"]),
        "application_state": {
            **before["application_state"],
            "mappings": {index: expected_after_mapping},
        },
    }

    result = write_probe.validate_write_state(
        before,
        after,
        [index],
        expected_dynamic_fields={index: marker},
    )

    assert result["result"] == "PASS"
    assert result["mappings_unchanged"] is False
    assert result["explained_mapping_changes"][index] == {
        "field": f"labels.{marker}",
        "mapping": {"ignore_above": 8191, "type": "keyword"},
        "reason": (
            "Typed SET temporarily added a string key to the previously empty labels object; "
            "Elasticsearch applied the first strings_as_keywords dynamic template. The source was restored."
        ),
    }

    unexpected = {"inventory": list(after["inventory"]), "application_state": dict(after["application_state"])}
    unexpected["application_state"]["mappings"] = {index: {"mappings": {"properties": {"extra": {"type": "keyword"}}}}}
    with pytest.raises(write_probe.RehearsalAbort, match="differs from the exact allowed template output"):
        write_probe.validate_write_state(
            before,
            unexpected,
            [index],
            expected_dynamic_fields={index: marker},
        )


def test_probe_refuses_unowned_cutover_container_before_any_child_or_cleanup_action(monkeypatch, tmp_path) -> None:
    runtime, handle, plan = _owned_context()
    runtime.work_dir = tmp_path
    verify_calls = []

    def refuse_foreign(_handle):
        verify_calls.append(_handle.container_id)
        raise write_probe.RehearsalAbort("Container ownership labels failed for cutover.")

    runtime.verify_owned = refuse_foreign
    monkeypatch.setattr(
        write_probe.application_rehearsal,
        "verify_redis_owned",
        lambda *_args, **_kwargs: pytest.fail("Redis verification must not occur before ES ownership passes"),
    )
    monkeypatch.setattr(
        write_probe.subprocess,
        "run",
        lambda *_args, **_kwargs: pytest.fail("Foreign container must never start the write child"),
    )

    with pytest.raises(write_probe.RehearsalAbort, match="ownership labels failed"):
        write_probe.run_registered_collection_probe(
            runtime,
            handle=handle,
            plan=plan,
            redis=SimpleNamespace(port=49152),
            api_root=tmp_path,
            timeout=1,
        )
    assert verify_calls == [handle.container_id]


def test_redis_cleanup_refuses_foreign_labels_without_stop_or_remove() -> None:
    handle = write_probe.application_rehearsal.RedisHandle(
        name="howler-step9-offline-write-app-redis",
        container_id="c" * 64,
        host="127.0.0.1",
        port=49152,
        network="howler-step9-offline-write-app-redis-network",
    )

    class ForeignRedisRuntime:
        run_id = "offline-write"

        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def _docker(self, arguments: list[str], *, check: bool = True) -> str:
            self.calls.append(arguments)
            if arguments[0] == "inspect":
                return (
                    '[{"Id":"' + handle.container_id + '","Name":"/' + handle.name + '",'
                    '"Config":{"Image":"redis:7.4.2-alpine","Labels":{'
                    '"howler.step9.rehearsal":"true","howler.step9.run":"somebody-else",'
                    '"howler.step9.role":"application-redis"}},"State":{"Status":"running"}}]'
                )
            raise AssertionError(f"Foreign Redis must not be destructively managed: {arguments!r}")

    runtime = ForeignRedisRuntime()
    with pytest.raises(write_probe.RehearsalAbort, match="not owned"):
        write_probe.application_rehearsal.remove_owned_redis(runtime, handle)
    assert runtime.calls == [["inspect", handle.container_id]]


def test_cleanup_container_requires_exact_run_role_name_and_image() -> None:
    response: dict[str, Any] = {
        "Id": "d" * 64,
        "Name": "/howler-step9-offline-write-donor",
        "Config": {
            "Image": write_probe.es_rehearsal.SOURCE_IMAGE,
            "Labels": {
                "howler.step9.rehearsal": "true",
                "howler.step9.run": "offline-write",
                "howler.step9.role": "donor",
            },
        },
    }

    assert (
        write_probe.validate_cleanup_container(
            response,
            run_id="offline-write",
            name="howler-step9-offline-write-donor",
            role="donor",
            image=write_probe.es_rehearsal.SOURCE_IMAGE,
        )
        == "d" * 64
    )
    foreign = {**response, "Config": {**response["Config"], "Labels": {**response["Config"]["Labels"]}}}
    foreign["Config"]["Labels"]["howler.step9.run"] = "foreign-run"
    with pytest.raises(write_probe.RehearsalAbort, match="ownership, role, or image"):
        write_probe.validate_cleanup_container(
            foreign,
            run_id="offline-write",
            name="howler-step9-offline-write-donor",
            role="donor",
            image=write_probe.es_rehearsal.SOURCE_IMAGE,
        )


def test_cleanup_volume_and_network_require_exact_run_owned_label() -> None:
    resource = {
        "Name": "howler-step9-offline-write-cutover-data",
        "Labels": {
            "howler.step9.rehearsal": "true",
            "howler.step9.run": "offline-write",
            "howler.step9.role": "cutover",
        },
    }
    write_probe.validate_cleanup_resource(
        resource,
        run_id="offline-write",
        name="howler-step9-offline-write-cutover-data",
        role="cutover",
        kind="volume",
    )

    with pytest.raises(write_probe.RehearsalAbort, match="ownership labels"):
        write_probe.validate_cleanup_resource(
            resource,
            run_id="offline-write",
            name="howler-step9-offline-write-cutover",
            role="network",
            kind="network",
        )


def test_cleanup_does_not_stop_or_remove_a_foreign_run_name() -> None:
    redis_name = "howler-step9-offline-write-app-redis"

    class ForeignRuntime:
        run_id = "offline-write"
        network = "howler-step9-offline-write"
        volumes = {"donor": "howler-step9-offline-write-donor-data"}
        handles = {}

        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def _docker(self, arguments: list[str], *, check: bool = True) -> str:
            self.calls.append(arguments)
            if arguments == ["ps", "-a", "--format", "{{.Names}}"]:
                return redis_name
            if arguments == ["inspect", redis_name]:
                return (
                    '[{"Id":"' + "e" * 64 + '","Name":"/' + redis_name + '",'
                    '"Config":{"Image":"redis:7.4.2-alpine","Labels":{'
                    '"howler.step9.rehearsal":"true","howler.step9.run":"foreign-run",'
                    '"howler.step9.role":"application-redis"}}}]'
                )
            raise AssertionError(f"Foreign resources must not be destructively managed: {arguments!r}")

    runtime = ForeignRuntime()
    result = write_probe.cleanup_owned_resources(runtime)

    assert result["result"] == "FAIL"
    assert runtime.calls == [["ps", "-a", "--format", "{{.Names}}"], ["inspect", redis_name]]
