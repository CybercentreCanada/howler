from __future__ import annotations

from typing import Any

import pytest

from howler.external.elasticsearch_preflight import (
    NO_MIGRATION_NEEDED,
    SOURCE_STACK_VERSION,
    build_report,
    evaluate_inventory,
)
from howler.external.elasticsearch_rest import ElasticsearchRestError


@pytest.fixture(autouse=True)
def _stable_test_index_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HWL_DATASTORE_INDEX_PREFIX", "howler")


def _inventory() -> dict[str, Any]:
    return {
        "cluster_health": {"status": "green", "indices": {"howler-hit_hot": {"status": "green"}}},
        "cluster_settings": {},
        "component_templates": {},
        "deprecations": {"cluster_settings": [], "index_settings": {}, "node_settings": []},
        "feature_upgrade_status": {"features": [], "migration_status": NO_MIGRATION_NEEDED},
        "ilm_explain": {},
        "ilm_policies": {},
        "index_templates": {},
        "indices": {
            "howler-hit_hot": {
                "aliases": {"howler-hit": {}},
                "doc_count": 2,
                "health": "green",
                "primary_shards": {"0": {"doc_count": 2, "max_seq_no": 7, "global_checkpoint": 7}},
                "settings": {"index.version.created": "8191199", "index.uuid": "uuid-1"},
                "status": "open",
                "uuid": "uuid-1",
            }
        },
        "index_prefix": "howler",
        "ingest_pipelines": {},
        "legacy_templates": {},
        "nodes": {"nodes": {"node-1": {"version": "8.19.11"}}},
        "remote_clusters": {},
        "snapshot_repositories": {},
        "version": {"version": {"number": SOURCE_STACK_VERSION}},
    }


class FakeRestClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((path, params))
        responses = {
            "/": {"version": {"number": SOURCE_STACK_VERSION}},
            "/*": {
                "howler-hit_hot": {
                    "aliases": {"howler-hit": {}},
                    "settings": {"index.version.created": "8191199", "index.uuid": "uuid-1"},
                }
            },
            "/_cat/indices": [{"index": "howler-hit_hot", "health": "green", "status": "open", "docs.count": "2"}],
            "/howler-*/_stats": {
                "indices": {
                    "howler-hit_hot": {
                        "primaries": {"docs": {"count": 2}},
                        "shards": {
                            "0": [
                                {
                                    "routing": {"primary": True, "shard": 0},
                                    "docs": {"count": 2},
                                    "seq_no": {"max_seq_no": 7, "global_checkpoint": 7},
                                }
                            ]
                        },
                    }
                }
            },
            "/_cluster/health": {"status": "green", "indices": {"howler-hit_hot": {"status": "green"}}},
            "/_cluster/settings": {},
            "/_component_template/*": {"component_templates": []},
            "/_migration/deprecations": {"cluster_settings": [], "index_settings": {}, "node_settings": []},
            "/_migration/system_features": {"features": [], "migration_status": NO_MIGRATION_NEEDED},
            "/_ilm/policy/*": {},
            "/_index_template/*": {"index_templates": []},
            "/_ingest/pipeline/*": {},
            "/_template/*": {},
            "/_nodes": {"nodes": {"node-1": {"version": "8.19.11"}}},
            "/_remote/info": {},
            "/_snapshot/*": {},
            "/howler-*/_ilm/explain": {"indices": {"howler-hit_hot": {"managed": False}}},
        }
        return responses[path]


def test_evaluate_inventory_accepts_clean_8_19_cluster() -> None:
    checks = evaluate_inventory(_inventory())

    assert checks == {
        "blockers": [],
        "deprecations": [],
        "pre_8_indices": [],
        "ready": True,
        "unknown_index_versions": [],
        "warnings": [],
    }


def test_evaluate_inventory_reports_every_upgrade_blocker() -> None:
    inventory = _inventory()
    inventory["version"]["version"]["number"] = "8.18.7"
    inventory["cluster_health"]["status"] = "red"
    inventory["deprecations"]["index_settings"] = {
        "legacy": [{"level": "critical", "message": "Legacy setting is unsupported.", "url": "https://example.invalid"}]
    }
    inventory["feature_upgrade_status"]["migration_status"] = "MIGRATION_NEEDED"
    inventory["indices"]["legacy-index"] = {"settings": {"index": {"version": {"created": "7170099"}}}}

    checks = evaluate_inventory(inventory)

    assert checks["ready"] is False
    assert checks["pre_8_indices"] == ["legacy-index"]
    assert [blocker["check"] for blocker in checks["blockers"]] == [
        "source_version",
        "cluster_health",
        "critical_deprecations",
        "system_features",
        "index_creation_versions",
    ]
    assert checks["deprecations"] == [
        {
            "level": "critical",
            "message": "Legacy setting is unsupported.",
            "path": "index_settings.legacy.0",
            "url": "https://example.invalid",
        }
    ]


def test_evaluate_inventory_blocks_unknown_index_creation_version() -> None:
    inventory = _inventory()
    inventory["indices"]["unknown-index"] = {"settings": {}}

    checks = evaluate_inventory(inventory)

    assert checks["ready"] is False
    assert checks["unknown_index_versions"] == ["unknown-index"]
    assert checks["blockers"] == [
        {
            "check": "unknown_index_creation_versions",
            "message": "Determine the creation version of 1 index(es).",
            "resources": ["unknown-index"],
        }
    ]


def test_preflight_blocks_unsynced_primary_checkpoint_with_rerun_guidance() -> None:
    inventory = _inventory()
    inventory["indices"]["howler-hit_hot"]["primary_shards"]["0"]["global_checkpoint"] = 6

    checks = evaluate_inventory(inventory, baseline_capture=True)

    blocker = next(item for item in checks["blockers"] if item["check"] == "primary_sequence_sync")
    assert "flush" in blocker["message"]
    assert "rerun the preflight" in blocker["message"]
    assert blocker["resources"]["howler-hit_hot"] == [
        {
            "shard": "0",
            "reason": "unsynced",
            "max_seq_no": 7,
            "global_checkpoint": 6,
        }
    ]


def test_preflight_checkpoint_sync_is_warning_live_and_blocker_for_baseline_capture() -> None:
    inventory = _inventory()
    inventory["indices"]["howler-hit_hot"]["primary_shards"]["0"]["global_checkpoint"] = 6

    live_checks = evaluate_inventory(inventory)
    capture_checks = evaluate_inventory(inventory, baseline_capture=True)

    assert live_checks["ready"] is True
    assert any(warning["check"] == "primary_sequence_sync" for warning in live_checks["warnings"])
    assert capture_checks["ready"] is False
    assert any(blocker["check"] == "primary_sequence_sync" for blocker in capture_checks["blockers"])


def test_closed_howler_indices_are_classified_for_preflight_and_baseline_capture() -> None:
    configured = _inventory()
    configured["indices"]["howler-hit_hot"]["status"] = "close"
    assert any(blocker["check"] == "closed_howler_index" for blocker in evaluate_inventory(configured)["blockers"])

    unrelated = _inventory()
    unrelated["indices"]["howler-archive_closed"] = {
        "aliases": {},
        "settings": {"index.version.created": "8191199", "index.uuid": "archive-uuid"},
        "status": "close",
        "uuid": "archive-uuid",
    }
    live_checks = evaluate_inventory(unrelated)
    assert live_checks["ready"] is True
    assert any(
        warning["check"] == "closed_howler_index" and warning["index"] == "howler-archive_closed"
        for warning in live_checks["warnings"]
    )

    capture_checks = evaluate_inventory(unrelated, baseline_capture=True)
    assert any(
        blocker["check"] == "closed_howler_index" and blocker["index"] == "howler-archive_closed"
        for blocker in capture_checks["blockers"]
    )


def test_build_report_uses_plain_get_inventory_and_adds_baseline_fields() -> None:
    client = FakeRestClient()

    report = build_report(client)  # type: ignore[arg-type]

    index_data = report["inventory"]["indices"]["howler-hit_hot"]
    assert report["source_stack_version"] == SOURCE_STACK_VERSION
    assert report["index_prefix"] == "howler"
    assert index_data["uuid"] == "uuid-1"
    assert index_data["doc_count"] == 2
    assert index_data["primary_shards"] == {"0": {"doc_count": 2, "max_seq_no": 7, "global_checkpoint": 7}}
    assert index_data["health"] == "green"
    assert index_data["status"] == "open"
    assert report["checks"]["ready"] is True
    assert {path for path, _ in client.calls} >= {
        "/_cat/indices",
        "/howler-*/_stats",
        "/_migration/system_features",
        "/_migration/deprecations",
    }
    assert all(path.startswith("/") for path, _ in client.calls)


def test_preflight_only_tolerates_status_404_for_optional_ilm_explain() -> None:
    class NoIlmRestClient(FakeRestClient):
        def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
            if path == "/howler-*/_ilm/explain":
                raise ElasticsearchRestError("not found", status=404)
            return super().get(path, params)

    report = build_report(NoIlmRestClient())  # type: ignore[arg-type]

    assert report["inventory"]["ilm_explain"] == {}
    assert report["checks"]["ready"] is True


def test_preflight_propagates_non_404_ilm_explain_errors() -> None:
    class FailedIlmRestClient(FakeRestClient):
        def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
            if path == "/howler-*/_ilm/explain":
                raise ElasticsearchRestError("forbidden", status=403)
            return super().get(path, params)

    with pytest.raises(ElasticsearchRestError) as error:
        build_report(FailedIlmRestClient())  # type: ignore[arg-type]
    assert error.value.status == 403


def test_preflight_main_writes_report_and_returns_ready_status(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import json
    import sys

    import howler.external.elasticsearch_preflight as preflight

    output = tmp_path / "preflight.json"
    monkeypatch.setattr(sys, "argv", ["elasticsearch_preflight", "--output", str(output)])
    monkeypatch.setattr(preflight, "_client_from_args", lambda args, parser: FakeRestClient())

    assert preflight.main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["checks"]["ready"] is True
    assert report["source_stack_version"] == "8.19.11"
    assert report["baseline_capture"] is False


def test_preflight_main_records_baseline_capture_mode(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import json
    import sys

    import howler.external.elasticsearch_preflight as preflight

    output = tmp_path / "baseline.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["elasticsearch_preflight", "--baseline-capture", "--output", str(output)],
    )
    monkeypatch.setattr(preflight, "_client_from_args", lambda args, parser: FakeRestClient())

    assert preflight.main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["baseline_capture"] is True


def test_preflight_main_reports_rest_failure_without_hiding_http_status(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    import sys

    import howler.external.elasticsearch_preflight as preflight

    monkeypatch.setattr(sys, "argv", ["elasticsearch_preflight"])
    monkeypatch.setattr(preflight, "_client_from_args", lambda args, parser: object())
    monkeypatch.setattr(
        preflight,
        "build_report",
        lambda client, **kwargs: (_ for _ in ()).throw(
            ElasticsearchRestError("Elasticsearch GET /_cluster/health returned HTTP 403.", status=403)
        ),
    )

    with pytest.raises(SystemExit) as error:
        preflight.main()

    assert error.value.code == 2
    assert "HTTP 403" in capsys.readouterr().err
