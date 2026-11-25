from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from howler.external import elasticsearch_preflight as preflight
from howler.external.elasticsearch_preflight import (
    NO_MIGRATION_NEEDED,
    SOURCE_STACK_VERSION,
    build_report,
    evaluate_inventory,
)
from howler.external.elasticsearch_rest import ElasticsearchRestClient, ElasticsearchRestError


@pytest.fixture(autouse=True)
def _stable_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
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
                "settings": {"index.version.created": "8191199", "index.uuid": "uuid-1", "index.number_of_shards": "1"},
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
                    "settings": {
                        "index.version.created": "8191199",
                        "index.uuid": "uuid-1",
                        "index.number_of_shards": "1",
                    },
                }
            },
            "/_cat/indices": [{"index": "howler-hit_hot", "health": "green", "status": "open", "docs.count": "2"}],
            "/howler-*/_stats": {
                "indices": {
                    "howler-hit_hot": {
                        "shards": {
                            "0": [
                                {
                                    "routing": {"primary": True},
                                    "docs": {"count": 2},
                                    "seq_no": {"max_seq_no": 7, "global_checkpoint": 7},
                                }
                            ]
                        }
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

    def get_optional(self, path: str, params: dict[str, Any] | None = None) -> Any | None:
        return ElasticsearchRestClient.get_optional(self, path, params)  # type: ignore[arg-type]


def test_evaluate_inventory_clean_and_blockers() -> None:
    assert evaluate_inventory(_inventory())["ready"] is True

    inv = _inventory()
    inv["version"]["version"]["number"] = "8.18.7"
    inv["cluster_health"]["status"] = "red"
    inv["deprecations"]["index_settings"] = {"legacy": [{"level": "critical", "message": "Unsupported."}]}
    inv["feature_upgrade_status"]["migration_status"] = "MIGRATION_NEEDED"
    inv["indices"]["legacy-index"] = {"settings": {"index": {"version": {"created": "7170099"}}}}
    inv["indices"]["unknown-index"] = {"settings": {}}
    checks = evaluate_inventory(inv)
    assert checks["ready"] is False
    assert [b["check"] for b in checks["blockers"]] == [
        "source_version",
        "cluster_health",
        "critical_deprecations",
        "system_features",
        "index_creation_versions",
        "unknown_index_creation_versions",
    ]


@pytest.mark.parametrize("baseline_capture", [False, True])
def test_preflight_sync_and_closed_indices(baseline_capture: bool) -> None:
    inv = _inventory()
    inv["indices"]["howler-hit_hot"]["primary_shards"]["0"]["global_checkpoint"] = 6
    inv["indices"]["howler-archive_closed"] = {
        "aliases": {},
        "settings": {"index.version.created": "8191199", "index.uuid": "arch"},
        "status": "close",
    }
    checks = evaluate_inventory(inv, baseline_capture=baseline_capture)
    assert checks["ready"] is (not baseline_capture)
    findings = checks["blockers"] if baseline_capture else checks["warnings"]
    assert {item["check"] for item in findings} == {"primary_sequence_sync", "closed_howler_index"}


def test_build_report_partial_shards_and_optional_ilm(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class PartialClient(FakeRestClient):
        def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
            if path == "/howler-*/_ilm/explain":
                raise ElasticsearchRestError("not found", status=404)
            data = super().get(path, params)
            if path == "/*":
                data["howler-hit_hot"]["settings"]["index.number_of_shards"] = "2"
            return data

    report = build_report(PartialClient(), baseline_capture=True)  # type: ignore[arg-type]
    assert report["inventory"]["ilm_explain"] == {}
    assert report["inventory"]["indices"]["howler-hit_hot"]["doc_count"] is None
    assert report["checks"]["ready"] is False

    output = tmp_path / "preflight.json"
    monkeypatch.setattr(sys, "argv", ["elasticsearch_preflight", "--baseline-capture", "--output", str(output)])
    monkeypatch.setattr(preflight, "client_from_args", lambda args, parser: FakeRestClient())
    assert preflight.main() == 0
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["baseline_capture"] is True and saved["checks"]["ready"] is True
