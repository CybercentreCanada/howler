import json
from argparse import Namespace
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

import build_scripts.upgrade_rehearsal as rehearsal
from build_scripts.upgrade_rehearsal import (
    SYNTHETIC_ALIASES,
    SYNTHETIC_CASE,
    SYNTHETIC_CASE_ID,
    SYNTHETIC_CASE_INDEX,
    SYNTHETIC_HIT_INDEX,
    SYNTHETIC_HITS,
    SYNTHETIC_INDICES,
    SYNTHETIC_MAPPINGS,
    ClusterHandle,
    DockerRuntime,
    RehearsalAbort,
    RestClient,
    _document_digest,
    _selected_names,
    assert_fresh_rollback_volume,
    assert_index_uuids_equal,
    assert_same_data_volume,
    prepare_synthetic_seed,
    restore_snapshot,
    run_workflow,
    synthetic_fixture_checksum,
    upgrade_preflight,
    upgrade_same_volume,
    validate_cluster_info,
    validate_snapshot_version,
    verify_data_identity,
    verify_synthetic_fixture,
)


def _cluster_info(name="howler-step9-run-cutover", version="8.19.11", cluster_uuid="cluster-uuid"):
    return {"cluster_name": name, "cluster_uuid": cluster_uuid, "version": {"number": version}}


def _data_state(*, uuid="index-uuid", digest="docs-a"):
    return {
        "aliases": {"howler-hit": {"howler-hit-000001": {"is_write_index": True}}},
        "counts": {"howler-hit-000001": 2},
        "document_sha256": {"howler-hit-000001": digest},
        "index_uuids": {"howler-hit-000001": uuid},
        "mappings": {"howler-hit-000001": {"mappings": {"properties": {"id": {"type": "keyword"}}}}},
    }


def test_rejects_wrong_cluster_name_version_and_missing_uuid():
    with pytest.raises(RehearsalAbort, match="Invalid cluster identity"):
        validate_cluster_info(_cluster_info("shared-dev"), "howler-step9-run-cutover", "8.19.11")
    with pytest.raises(RehearsalAbort, match="Invalid cluster version"):
        validate_cluster_info(_cluster_info(version="9.5.2"), "howler-step9-run-cutover", "8.19.11")
    with pytest.raises(RehearsalAbort, match="Cluster UUID is missing"):
        validate_cluster_info(_cluster_info(cluster_uuid="_na_"), "howler-step9-run-cutover", "8.19.11")


def test_readiness_waits_for_elected_cluster_uuid_but_rejects_wrong_version(monkeypatch):
    class FakeRestClient:
        responses = []

        def __init__(self, _url, _timeout):
            pass

        def request(self, method, path):
            assert (method, path) == ("GET", "/")
            return self.responses.pop(0)

    monkeypatch.setattr(rehearsal, "RestClient", FakeRestClient)
    monkeypatch.setattr(rehearsal.time, "sleep", lambda _seconds: None)
    runtime = SimpleNamespace(verify_owned=MagicMock())
    handle = ClusterHandle(
        "cutover", "owned", "id", "volume", "howler-step9-run-cutover", "9.5.2", "http://172.28.5.2:9200"
    )
    FakeRestClient.responses = [
        _cluster_info(version="9.5.2", cluster_uuid="_na_"),
        _cluster_info(version="9.5.2", cluster_uuid="elected-cluster"),
    ]
    _client, info = rehearsal.wait_for_cluster(handle, runtime, 5)
    assert info["cluster_uuid"] == "elected-cluster"
    assert runtime.verify_owned.call_count == 2

    FakeRestClient.responses = [_cluster_info(version="8.19.11")]
    with pytest.raises(RehearsalAbort, match="Invalid cluster version"):
        rehearsal.wait_for_cluster(handle, runtime, 5)


def test_equal_document_counts_do_not_allow_changed_document_identity_or_content():
    donor = _data_state(digest="original-document-content")
    substituted = _data_state(digest="different-document-with-same-count")

    with pytest.raises(RehearsalAbort, match="document_sha256 mismatch"):
        verify_data_identity(donor, substituted, phase="restore", require_uuid_match=False)


def test_uuid_must_survive_the_same_volume_major_upgrade():
    with pytest.raises(RehearsalAbort, match="index UUID changed"):
        assert_index_uuids_equal({"index": "uuid-before"}, {"index": "uuid-after"}, "upgrade")
    assert_index_uuids_equal({"index": "same"}, {"index": "same"}, "upgrade")


def test_cutover_requires_same_owned_volume_and_rollback_requires_fresh_volume():
    before = ClusterHandle("cutover", "eight", "container8", "cutover-volume", "c", "8.19.11", "")
    after = ClusterHandle("cutover", "nine", "container9", "cutover-volume", "c", "9.5.2", "")
    rollback = ClusterHandle("rollback", "rollback", "rollback-id", "rollback-volume", "r", "8.19.11", "")
    assert_same_data_volume(before, after)
    assert_fresh_rollback_volume(after, rollback)
    with pytest.raises(RehearsalAbort, match="same exclusively-owned Docker data volume"):
        assert_same_data_volume(before, ClusterHandle("cutover", "nine", "id", "other", "c", "9.5.2", ""))
    with pytest.raises(RehearsalAbort, match="separate, fresh Docker data volume"):
        assert_fresh_rollback_volume(after, ClusterHandle("rollback", "r", "r", "cutover-volume", "r", "8.19.11", ""))


def test_upgrade_stops_8_container_then_starts_95_on_its_same_volume():
    before = ClusterHandle("cutover", "eight", "container8", "cutover-volume", "c", "8.19.11", "")
    after = ClusterHandle("cutover", "nine", "container9", "cutover-volume", "c", "9.5.2", "")
    runtime = MagicMock()
    runtime.start.return_value = after

    assert upgrade_same_volume(runtime, before) == after
    runtime.stop_and_remove_container.assert_called_once_with(before)
    runtime.start.assert_called_once_with("cutover", "9.5.2", "cutover", repository_readonly=True)


def test_hidden_and_temporary_indices_are_never_silently_exempted():
    with pytest.raises(RehearsalAbort, match="must not select hidden/system"):
        _selected_names({".private-user-data": {}}, "*user*")
    with pytest.raises(RehearsalAbort, match="__reindex"):
        _selected_names({"howler-hit__reindex": {}}, "howler-*")
    with pytest.raises(RehearsalAbort, match="Temporary __reindex"):
        _selected_names({"howler-hit-1": {}, "elsewhere__reindex": {}}, "howler-*")


def test_raw_rest_restore_uses_8_compatible_request_without_external_client():
    client = MagicMock(spec=RestClient)
    client.request.return_value = {
        "snapshot": {
            "snapshot": "step9-run",
            "indices": ["howler-hit-000001"],
            "shards": {"total": 1, "successful": 1, "failed": 0},
        }
    }

    restore_snapshot(client, "step9-rehearsal", "step9-run", ["howler-hit-000001"])

    client.request.assert_called_once_with(
        "POST",
        "/_snapshot/step9-rehearsal/step9-run/_restore?wait_for_completion=true",
        {"indices": "howler-hit-000001", "include_global_state": False, "include_aliases": True},
    )


def test_restore_response_requires_proof_of_completed_expected_shards():
    client = MagicMock(spec=RestClient)
    client.request.return_value = {"snapshot": {"snapshot": "step9-run", "indices": ["howler-hit-000001"]}}
    with pytest.raises(RehearsalAbort, match="missing shard completion details"):
        restore_snapshot(client, "repo", "step9-run", ["howler-hit-000001"])

    client.request.return_value = {
        "snapshot": {
            "snapshot": "step9-run",
            "indices": ["howler-hit-000001"],
            "shards": {"total": 2, "successful": 1, "failed": 1},
        }
    }
    with pytest.raises(RehearsalAbort, match="did not complete every shard"):
        restore_snapshot(client, "repo", "step9-run", ["howler-hit-000001"])


def test_raw_8_19_upgrade_preflight_requires_clean_health_deprecations_and_features():
    client = MagicMock(spec=RestClient)
    client.request.side_effect = [
        _cluster_info(),
        {"status": "green"},
        {"cluster_settings": [], "node_settings": [], "index_settings": {}},
        {"features": [{"migration_status": "NO_MIGRATION_NEEDED"}]},
    ]
    inventory = {"howler-hit-000001": {"settings": {"index.version.created": "8191199"}}}

    result = upgrade_preflight(client, "howler-step9-run-cutover", inventory)

    assert result["ready"] is True
    assert result["index_count"] == 1
    assert [call.args[:2] for call in client.request.call_args_list] == [
        ("GET", "/"),
        ("GET", "/_cluster/health"),
        ("GET", "/_migration/deprecations"),
        ("GET", "/_migration/system_features"),
    ]


def test_raw_8_19_upgrade_preflight_blocks_critical_deprecation():
    client = MagicMock(spec=RestClient)
    client.request.side_effect = [
        _cluster_info(),
        {"status": "yellow"},
        {"index_settings": {"idx": [{"level": "critical", "message": "unsupported"}]}},
    ]

    with pytest.raises(RehearsalAbort, match="Critical Elasticsearch deprecations"):
        upgrade_preflight(
            client,
            "howler-step9-run-cutover",
            {"howler-hit-000001": {"settings": {"index.version.created": "8191199"}}},
        )


def test_seed_snapshot_version_range_must_include_81911_and_preserve_version_id():
    metadata = {"version": "8.19.9-8.19.11", "version_id": 8537000}
    assert validate_snapshot_version(metadata, "8.19.11") == {
        "version": "8.19.9-8.19.11",
        "version_id": 8537000,
        "compatible_with": "8.19.11",
    }
    assert validate_snapshot_version({"version": "8.19.11", "version_id": 8191199}, "8.19.11")["version_id"] == 8191199

    with pytest.raises(RehearsalAbort, match="does not contain compatible"):
        validate_snapshot_version({"version": "8.19.7-8.19.10", "version_id": 8191099}, "8.19.11")
    with pytest.raises(RehearsalAbort, match="no valid numeric version_id"):
        validate_snapshot_version({"version": "8.19.11", "version_id": "8191199"}, "8.19.11")


def test_content_digest_detects_equal_count_substitution_and_clears_scroll():
    client = MagicMock(spec=RestClient)
    client.request.side_effect = [
        {"_scroll_id": "scroll-1", "hits": {"hits": [{"_id": "1", "_source": {"value": "original"}}]}},
        {"_scroll_id": "scroll-1", "hits": {"hits": [{"_id": "2", "_source": {"value": "same"}}]}},
        {"_scroll_id": "scroll-1", "hits": {"hits": []}},
        {"succeeded": True},
    ]

    digest = _document_digest(client, "howler-hit-000001", count=2, max_docs=10)

    assert len(digest) == 64
    client.request.assert_any_call("DELETE", "/_search/scroll", {"scroll_id": ["scroll-1"]})


def test_document_digest_enforces_cap_before_search():
    client = MagicMock(spec=RestClient)
    with pytest.raises(RehearsalAbort, match="digest cap"):
        _document_digest(client, "howler-hit-1", count=11, max_docs=10)
    client.request.assert_not_called()


def test_synthetic_fixture_requires_fixed_indices_classifications_case_link_and_content():
    client = MagicMock(spec=RestClient)
    case = json.loads(json.dumps(SYNTHETIC_CASE))
    client.request.side_effect = [
        {SYNTHETIC_HIT_INDEX: {"aliases": {SYNTHETIC_ALIASES[SYNTHETIC_HIT_INDEX]: {"is_write_index": True}}}},
        {SYNTHETIC_HIT_INDEX: {"mappings": SYNTHETIC_MAPPINGS[SYNTHETIC_HIT_INDEX]}},
        {"count": 2},
        *[{"found": True, "_source": source} for source in SYNTHETIC_HITS.values()],
        {SYNTHETIC_CASE_INDEX: {"aliases": {SYNTHETIC_ALIASES[SYNTHETIC_CASE_INDEX]: {"is_write_index": True}}}},
        {SYNTHETIC_CASE_INDEX: {"mappings": SYNTHETIC_MAPPINGS[SYNTHETIC_CASE_INDEX]}},
        {"count": 1},
        {"found": True, "_source": case},
    ]

    verify_synthetic_fixture(client, SYNTHETIC_INDICES)
    assert [(call.args[0], call.args[1]) for call in client.request.call_args_list] == [
        ("GET", f"/{SYNTHETIC_HIT_INDEX}/_alias"),
        ("GET", f"/{SYNTHETIC_HIT_INDEX}/_mapping"),
        ("POST", f"/{SYNTHETIC_HIT_INDEX}/_count"),
        ("GET", f"/{SYNTHETIC_HIT_INDEX}/_doc/step9-hit-unrestricted-001"),
        ("GET", f"/{SYNTHETIC_HIT_INDEX}/_doc/step9-hit-restricted-002"),
        ("GET", f"/{SYNTHETIC_CASE_INDEX}/_alias"),
        ("GET", f"/{SYNTHETIC_CASE_INDEX}/_mapping"),
        ("POST", f"/{SYNTHETIC_CASE_INDEX}/_count"),
        ("GET", f"/{SYNTHETIC_CASE_INDEX}/_doc/{SYNTHETIC_CASE_ID}"),
    ]

    client.request.side_effect = [
        {SYNTHETIC_HIT_INDEX: {"aliases": {SYNTHETIC_ALIASES[SYNTHETIC_HIT_INDEX]: {"is_write_index": True}}}},
        {SYNTHETIC_HIT_INDEX: {"mappings": SYNTHETIC_MAPPINGS[SYNTHETIC_HIT_INDEX]}},
        {"count": 2},
        {"found": True, "_source": {**SYNTHETIC_HITS["step9-hit-unrestricted-001"], "classification": "RESTRICTED"}},
    ]
    with pytest.raises(RehearsalAbort, match="unexpected content"):
        verify_synthetic_fixture(client, SYNTHETIC_INDICES)


def test_synthetic_fixture_rejects_missing_or_non_write_alias():
    client = MagicMock(spec=RestClient)
    client.request.return_value = {
        SYNTHETIC_HIT_INDEX: {"aliases": {SYNTHETIC_ALIASES[SYNTHETIC_HIT_INDEX]: {"is_write_index": False}}}
    }

    with pytest.raises(RehearsalAbort, match="explicit write alias"):
        verify_synthetic_fixture(client, SYNTHETIC_INDICES)


def test_synthetic_fixture_rejects_extra_indices():
    with pytest.raises(RehearsalAbort, match="exactly"):
        verify_synthetic_fixture(MagicMock(spec=RestClient), [*SYNTHETIC_INDICES, "howler-other"])


def test_synthetic_fixture_rejects_missing_write_alias():
    client = MagicMock(spec=RestClient)
    client.request.return_value = {SYNTHETIC_HIT_INDEX: {"aliases": {}}}

    with pytest.raises(RehearsalAbort, match="explicit write alias"):
        verify_synthetic_fixture(client, SYNTHETIC_INDICES)


def test_canonical_synthetic_fixture_manifest_checksum_is_stable():
    assert synthetic_fixture_checksum() == "e8eccdeb9c1219ac50c7ad4e72e42991a08eccba39a3aa7aeb4d6604c0d5652e"


def test_docker_container_safety_rejects_unowned_or_nonisolated_container(tmp_path):
    run_id = "test-run"
    name = f"howler-step9-{run_id}"
    volume = f"howler-step9-{run_id}-cutover-data"
    container_id = "container-id"
    inspect = {
        "Id": container_id,
        "Name": "/howler-step9-test-run-cutover",
        "Config": {
            "Image": "docker.elastic.co/elasticsearch/elasticsearch:8.19.11",
            "Labels": {
                "howler.step9.rehearsal": "true",
                "howler.step9.run": run_id,
                "howler.step9.role": "cutover",
            },
        },
        "State": {"Status": "running"},
        "Mounts": [
            {"Type": "volume", "Name": volume, "Destination": "/usr/share/elasticsearch/data", "RW": True},
            {"Type": "bind", "Source": str(tmp_path), "Destination": "/usr/share/elasticsearch/snapshots", "RW": True},
        ],
        "HostConfig": {
            "PortBindings": None,
            "NetworkMode": name,
        },
        "NetworkSettings": {
            "Ports": None,
            "Networks": {name: {"IPAddress": "172.20.0.2"}},
        },
    }
    network = {
        "Internal": True,
        "Driver": "bridge",
        "Labels": {
            "howler.step9.rehearsal": "true",
            "howler.step9.run": run_id,
            "howler.step9.role": "network",
        },
        "IPAM": {"Config": [{"Subnet": "172.20.0.0/16"}]},
        "Containers": {container_id: {"Name": "howler-step9-test-run-cutover", "IPv4Address": "172.20.0.2/16"}},
    }
    command = MagicMock(side_effect=[json.dumps([inspect]), json.dumps([network])])
    runtime = DockerRuntime(run_id, tmp_path, 30, command=command)
    handle = ClusterHandle(
        "cutover", "howler-step9-test-run-cutover", container_id, volume, "howler-step9-test-run-cutover", "8.19.11", ""
    )
    runtime.handles["cutover"] = handle
    assert runtime._verify_container(handle, expected_state="running") == "172.20.0.2"

    published_inspect = json.loads(json.dumps(inspect))
    published_inspect["HostConfig"]["PortBindings"] = {"9200/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49100"}]}
    runtime.command = MagicMock(return_value=json.dumps([published_inspect]))
    with pytest.raises(RehearsalAbort, match="must not publish host ports"):
        runtime._verify_container(handle, expected_state="running")

    network_published = json.loads(json.dumps(inspect))
    network_published["NetworkSettings"]["Ports"] = {"9200/tcp": [{"HostIp": "127.0.0.1", "HostPort": "49100"}]}
    runtime.command = MagicMock(return_value=json.dumps([network_published]))
    with pytest.raises(RehearsalAbort, match="unexpectedly has host-published ports"):
        runtime._verify_container(handle, expected_state="running")

    bad_inspect = json.loads(json.dumps(inspect))
    bad_inspect["Config"]["Labels"]["howler.step9.run"] = "other-run"
    runtime.command = MagicMock(return_value=json.dumps([bad_inspect]))
    with pytest.raises(RehearsalAbort, match="ownership labels failed"):
        runtime._verify_container(handle, expected_state="running")


def test_start_uses_verified_internal_ip_without_host_published_ports(tmp_path, monkeypatch):
    runtime = DockerRuntime("test-run", tmp_path, 30)
    monkeypatch.setattr(runtime, "_assert_local_context", lambda: None)
    commands = []

    def fake_docker(arguments, *, check=True):
        commands.append(arguments)
        return "container-id"

    monkeypatch.setattr(runtime, "_docker", fake_docker)
    monkeypatch.setattr(runtime, "_verify_container", lambda *_args, **_kwargs: "172.28.3.2")

    handle = runtime.start("donor", "8.19.11", "donor", repository_readonly=False)

    assert handle.base_url == "http://172.28.3.2:9200"
    assert "-p" not in commands[0]
    assert runtime.resources["containers"]["donor-8.19.11"]["base_url"] == handle.base_url


def test_remote_docker_context_is_rejected_before_any_resource_creation(tmp_path):
    command = MagicMock(return_value='"ssh://shared-dev-docker"')
    runtime = DockerRuntime("test-run", tmp_path, 30, command=command)

    with pytest.raises(RehearsalAbort, match="non-local Docker context"):
        runtime.create_base_resources()

    command.assert_called_once()


def test_work_directory_cannot_mutate_seed_repository(tmp_path):
    seed_repository = tmp_path / "seed"
    seed_repository.mkdir()
    args = Namespace(
        run_id="test-run",
        seed_repository=str(seed_repository),
        work_dir=str(seed_repository / "rehearsal"),
        timeout=30,
        max_docs=100,
        index_pattern="howler-*",
        seed_snapshot="fixture",
    )

    with pytest.raises(RehearsalAbort, match="must not be nested inside"):
        run_workflow(args)

    assert list(seed_repository.iterdir()) == []


def _seed_prepare_args(repository):
    return Namespace(
        seed_run_id="canonical-seed-test",
        seed_container="howler-step9-canonical-seed",
        seed_network="howler-step9-canonical-seed-network",
        seed_volume="howler-step9-canonical-seed-data",
        confirm_seed_cluster="howler-step9-seed-canonical-test",
        seed_repository=str(repository),
        seed_snapshot="step9-canonical-test",
        timeout=30,
    )


def _seed_container_inspect(tmp_path, *, run_id="canonical-seed-test", role="seed") -> dict[str, Any]:
    return {
        "Id": "seed-container-id",
        "Name": "/howler-step9-canonical-seed",
        "Config": {
            "Image": "docker.elastic.co/elasticsearch/elasticsearch:8.19.11",
            "Labels": {
                "howler.step9.rehearsal": "true",
                "howler.step9.run": run_id,
                "howler.step9.role": role,
            },
        },
        "Mounts": [
            {
                "Type": "volume",
                "Name": "howler-step9-canonical-seed-data",
                "Destination": "/usr/share/elasticsearch/data",
                "RW": True,
            },
            {
                "Type": "bind",
                "Source": str(tmp_path),
                "Destination": "/usr/share/elasticsearch/snapshots",
                "RW": True,
            },
        ],
        "NetworkSettings": {"Networks": {"howler-step9-canonical-seed-network": {"IPAddress": "172.28.3.2"}}},
    }


def test_seed_preparation_fails_ownership_gate_before_any_rest_request(tmp_path, monkeypatch):
    repository = tmp_path / "seed-repo"
    repository.mkdir()
    runtime = MagicMock()
    runtime._docker.return_value = json.dumps([_seed_container_inspect(tmp_path, run_id="wrong-run")])
    monkeypatch.setattr(rehearsal, "DockerRuntime", lambda *_args: runtime)
    rest_client = MagicMock(side_effect=AssertionError("REST must not be contacted before ownership gate"))
    monkeypatch.setattr(rehearsal, "RestClient", rest_client)

    with pytest.raises(RehearsalAbort, match="not labelled for this exact rehearsal run"):
        prepare_synthetic_seed(_seed_prepare_args(repository))

    rest_client.assert_not_called()


def test_seed_preparation_rejects_a_different_labelled_volume_before_rest_or_volume_inspection(tmp_path, monkeypatch):
    repository = tmp_path / "seed-repo"
    repository.mkdir()
    container_data = _seed_container_inspect(tmp_path)
    container_data["Mounts"][0]["Name"] = "other-labelled-seed-volume"
    runtime = MagicMock()
    runtime._docker.side_effect = [
        json.dumps([container_data]),
        json.dumps(
            [
                {
                    "Name": "other-labelled-seed-volume",
                    "Driver": "local",
                    "Labels": {
                        "howler.step9.rehearsal": "true",
                        "howler.step9.run": "canonical-seed-test",
                        "howler.step9.role": "seed",
                    },
                }
            ]
        ),
    ]
    monkeypatch.setattr(rehearsal, "DockerRuntime", lambda *_args: runtime)
    rest_client = MagicMock(side_effect=AssertionError("REST must not be contacted for a wrong volume"))
    monkeypatch.setattr(rehearsal, "RestClient", rest_client)

    with pytest.raises(RehearsalAbort, match="not the explicitly confirmed"):
        prepare_synthetic_seed(_seed_prepare_args(repository))

    runtime._docker.assert_called_once()
    rest_client.assert_not_called()


def test_seed_preparation_checks_empty_owned_cluster_before_fixture_puts(tmp_path, monkeypatch):
    repository = tmp_path / "seed-repo"
    repository.mkdir()
    runtime = MagicMock()
    runtime._docker.side_effect = [
        json.dumps([_seed_container_inspect(tmp_path)]),
        json.dumps(
            [
                {
                    "Name": "howler-step9-canonical-seed-data",
                    "Driver": "local",
                    "Labels": {
                        "howler.step9.rehearsal": "true",
                        "howler.step9.run": "canonical-seed-test",
                        "howler.step9.role": "seed",
                    },
                }
            ]
        ),
        "",
    ]
    runtime._verify_container.return_value = "172.28.3.2"
    monkeypatch.setattr(rehearsal, "DockerRuntime", lambda *_args: runtime)

    class EmptyClusterClient:
        calls = []

        def __init__(self, *_args):
            pass

        def request(self, method, path, body=None):
            self.calls.append((method, path))
            if path == "/":
                return _cluster_info("howler-step9-seed-canonical-test", "8.19.11", "seed-uuid")
            if path == "/_cluster/health":
                return {"status": "green"}
            if path == "/_all/_settings?flat_settings=true&expand_wildcards=all":
                return {"howler-existing": {"settings": {}}}
            raise AssertionError(f"unexpected API request: {method} {path}")

    monkeypatch.setattr(rehearsal, "RestClient", EmptyClusterClient)
    args = _seed_prepare_args(repository)

    with pytest.raises(RehearsalAbort, match="must be empty"):
        prepare_synthetic_seed(args)

    assert all(method != "PUT" for method, _path in EmptyClusterClient.calls)


def test_seed_preparation_reuses_owned_internal_container_and_writes_aliases_before_snapshot(tmp_path, monkeypatch):  # noqa: C901
    repository = tmp_path / "seed-repo"
    repository.mkdir()
    events = []
    container_data = _seed_container_inspect(tmp_path)
    volume_data = {
        "Name": "howler-step9-canonical-seed-data",
        "Driver": "local",
        "Labels": {
            "howler.step9.rehearsal": "true",
            "howler.step9.run": "canonical-seed-test",
            "howler.step9.role": "seed",
        },
    }

    class FakeRuntime:
        def __init__(self, *_args):
            self.handles = {}

        def _assert_local_context(self):
            events.append("local-context-verified")

        def _docker(self, command):
            events.append(f"docker:{command[0]}")
            if command[0] == "inspect":
                return json.dumps([container_data])
            if command[0] == "volume":
                return json.dumps([volume_data])
            if command[0] == "exec":
                return ""
            raise AssertionError(f"unexpected docker command: {command}")

        def _verify_container(self, handle, *, expected_state):
            assert expected_state == "running"
            assert handle.container_id == "seed-container-id"
            events.append("container-network-mounts-verified")
            return "172.28.3.2"

        def verify_owned(self, handle):
            assert handle is self.handles["seed"]
            assert handle.base_url == "http://172.28.3.2:9200"
            events.append("seed-owned-during-readiness-check")

    class FakeRestClient:
        calls = []
        responses = []

        def __init__(self, url, _timeout):
            assert url == "http://172.28.3.2:9200"

        def request(self, method, path, body=None):
            self.calls.append((method, path, body))
            events.append(f"api:{method}:{path}")
            return self.responses.pop(0)

    monkeypatch.setattr(rehearsal, "DockerRuntime", FakeRuntime)
    monkeypatch.setattr(rehearsal, "RestClient", FakeRestClient)
    fixture_responses = []
    for index in (SYNTHETIC_HIT_INDEX, SYNTHETIC_CASE_INDEX):
        fixture_responses.extend(
            [
                {index: {"aliases": {rehearsal.SYNTHETIC_ALIASES[index]: {"is_write_index": True}}}},
                {index: {"mappings": rehearsal.SYNTHETIC_MAPPINGS[index]}},
                {
                    "count": len(
                        rehearsal.SYNTHETIC_HITS
                        if index == SYNTHETIC_HIT_INDEX
                        else {SYNTHETIC_CASE_ID: SYNTHETIC_CASE}
                    )
                },
            ]
        )
        documents = rehearsal.SYNTHETIC_HITS if index == SYNTHETIC_HIT_INDEX else {SYNTHETIC_CASE_ID: SYNTHETIC_CASE}
        fixture_responses.extend({"found": True, "_source": source} for source in documents.values())
    FakeRestClient.responses = [
        _cluster_info("howler-step9-seed-canonical-test", "8.19.11", "seed-cluster-uuid"),
        _cluster_info("howler-step9-seed-canonical-test", "8.19.11", "seed-cluster-uuid"),
        {"status": "green"},
        {},
        {"nodes": {"node": {"settings": {"path": {"repo": ["/usr/share/elasticsearch/snapshots"]}}}}},
        {},
        *[{"acknowledged": True} for _ in SYNTHETIC_INDICES],
        *[{"result": "created"} for _ in [*SYNTHETIC_HITS, SYNTHETIC_CASE_ID]],
        *fixture_responses,
        {"acknowledged": True},
        {"snapshot": {"state": "SUCCESS"}},
        {
            "snapshots": [
                {
                    "snapshot": "step9-canonical-test",
                    "state": "SUCCESS",
                    "version": "8.19.11",
                    "version_id": 8537000,
                    "indices": SYNTHETIC_INDICES,
                }
            ]
        },
    ]

    result = prepare_synthetic_seed(_seed_prepare_args(repository))

    assert result["result"] == "SEED_READY"
    assert result["manifest_sha256"] == synthetic_fixture_checksum()
    assert events.index("container-network-mounts-verified") < next(
        index for index, event in enumerate(events) if event.startswith("api:PUT:")
    )
    first_cluster_write = next(index for index, event in enumerate(events) if event.startswith("api:PUT:"))
    assert events.index("api:GET:/_snapshot/_all") < events.index("docker:exec") < first_cluster_write
    for index in SYNTHETIC_INDICES:
        index_create = next(
            body for method, path, body in FakeRestClient.calls if method == "PUT" and path == f"/{index}"
        )
        assert index_create["aliases"] == {rehearsal.SYNTHETIC_ALIASES[index]: {"is_write_index": True}}
    snapshot_event = next(
        i for i, event in enumerate(events) if event.startswith("api:PUT:/_snapshot/step9-seed/step9-canonical-test")
    )
    assert snapshot_event > max(i for i, event in enumerate(events) if "/_alias" in event)
    index_requests = {
        path: body
        for method, path, body in FakeRestClient.calls
        if method == "PUT" and path in {f"/{index}" for index in SYNTHETIC_INDICES}
    }
    assert set(index_requests) == {f"/{index}" for index in SYNTHETIC_INDICES}
    for index in SYNTHETIC_INDICES:
        assert index_requests[f"/{index}"]["aliases"] == {rehearsal.SYNTHETIC_ALIASES[index]: {"is_write_index": True}}


def test_orchestration_orders_fresh_8_restore_same_volume_upgrade_and_fresh_8_rollback(tmp_path, monkeypatch):
    seed_repository = tmp_path / "seed"
    seed_repository.mkdir()
    (seed_repository / "repository-index").write_text("fixture", encoding="utf-8")
    work_dir = tmp_path / "run"
    args = Namespace(
        run_id="ordered-run",
        seed_repository=str(seed_repository),
        seed_snapshot="seed-fixture",
        work_dir=str(work_dir),
        timeout=30,
        max_docs=10,
        index_pattern="howler-*",
        synthetic_fixture=True,
    )
    events = []

    class FakeRuntime:
        def __init__(self):
            self.resources = {"containers": {}}
            self.volumes = {"donor": "donor-volume", "cutover": "cutover-volume", "rollback": "rollback-volume"}

        def create_base_resources(self):
            events.append("resources")

        def start(self, role, version, volume_role, repository_readonly):
            events.append(f"start:{role}:{version}")
            volume = self.volumes[volume_role]
            handle = ClusterHandle(
                role,
                f"{role}-{version}",
                f"container-{role}-{version}",
                volume,
                f"howler-step9-ordered-run-{role}",
                version,
                f"http://{role}-{version}:9200",
                repository_readonly,
            )
            return handle

        def stop_and_remove_container(self, handle):
            events.append(f"stop:{handle.role}:{handle.version}")

    class FakeClient:
        def __init__(self, handle):
            self.handle = handle

        def request(self, method, path, body=None):
            return {"status": "green"}

    runtime = FakeRuntime()
    monkeypatch.setattr(rehearsal, "DockerRuntime", lambda *args: runtime)

    def api_wait(handle, _runtime, _timeout):
        cluster_uuid = "cutover-cluster" if handle.role == "cutover" else f"{handle.role}-cluster"
        return FakeClient(handle), _cluster_info(handle.cluster_name, handle.version, cluster_uuid)

    monkeypatch.setattr(
        rehearsal,
        "_docker_api_wait",
        api_wait,
    )
    inventory = {"howler-hit-000001": {"settings": {"index.version.created": "8191199"}}}
    inventories = [{}, inventory, {}, inventory, inventory, {}, inventory]
    monkeypatch.setattr(rehearsal, "_index_inventory", lambda _client: inventories.pop(0))
    monkeypatch.setattr(rehearsal, "upgrade_preflight", lambda *_args: {"ready": True})
    monkeypatch.setattr(
        rehearsal,
        "verify_synthetic_fixture",
        lambda client, _names: events.append(f"fixture-verified:{client.handle.role}:{client.handle.version}"),
    )
    state_donor = _data_state(uuid="donor-index-uuid")
    state8 = _data_state(uuid="cutover-index-uuid")
    state9 = _data_state(uuid="cutover-index-uuid")
    state_rollback = _data_state(uuid="rollback-index-uuid")
    states = [state_donor, state8, state9, state_rollback]
    monkeypatch.setattr(rehearsal, "capture_data_state", lambda *_args: states.pop(0))

    def metadata(_client, repository, snapshot):
        events.append(f"metadata:{repository}:{snapshot}")
        return {
            "state": "SUCCESS",
            "version": "8.19.11",
            "version_id": 8537000,
            "indices": ["howler-hit-000001"],
        }

    monkeypatch.setattr(rehearsal, "snapshot_metadata", metadata)
    monkeypatch.setattr(
        rehearsal,
        "register_repository",
        lambda client, repo, _path, readonly: events.append(f"repo:{client.handle.role}:{repo}:{readonly}"),
    )
    monkeypatch.setattr(rehearsal, "create_snapshot", lambda *_args: events.append("snapshot:donor"))
    monkeypatch.setattr(
        rehearsal,
        "restore_snapshot",
        lambda client, repo, _snapshot, _indices: events.append(f"restore:{client.handle.role}:{repo}"),
    )

    report = run_workflow(args)

    assert report["workflow_result"] == "BLOCKED_APPLICATION_VERIFICATION_UNAVAILABLE"
    assert report["application_verification"]["result"] == "BLOCKED_UNAVAILABLE"
    assert events.index("restore:donor:step9-seed") < events.index("snapshot:donor")
    assert events.index("snapshot:donor") < events.index("start:cutover:8.19.11")
    assert events.index("restore:cutover:step9-rehearsal") < events.index("stop:cutover:8.19.11")
    assert events.index("stop:cutover:8.19.11") < events.index("start:cutover:9.5.2")
    assert events.index("start:cutover:9.5.2") < events.index("stop:cutover:9.5.2")
    assert events.index("stop:cutover:9.5.2") < events.index("start:rollback:8.19.11")
    assert events.index("start:rollback:8.19.11") < events.index("restore:rollback:step9-rehearsal")
    assert [event for event in events if event.startswith("fixture-verified:")] == [
        "fixture-verified:donor:8.19.11",
        "fixture-verified:cutover:8.19.11",
        "fixture-verified:cutover:9.5.2",
        "fixture-verified:rollback:8.19.11",
    ]
    assert runtime.volumes["cutover"] == "cutover-volume"
    assert (work_dir / "rehearsal-report.json").exists()
