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

    def get_optional(self, path: str, params: dict[str, Any] | None = None) -> Any | None:
        return ElasticsearchRestClient.get_optional(self, path, params)  # type: ignore[arg-type]


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


@pytest.mark.parametrize("baseline_capture", [False, True])
def test_preflight_unsynced_checkpoint_is_warning_or_blocker(baseline_capture: bool) -> None:
    inventory = _inventory()
    inventory["indices"]["howler-hit_hot"]["primary_shards"]["0"]["global_checkpoint"] = 6

    checks = evaluate_inventory(inventory, baseline_capture=baseline_capture)

    findings = checks["blockers"] if baseline_capture else checks["warnings"]
    finding = next(item for item in findings if item["check"] == "primary_sequence_sync")
    assert checks["ready"] is (not baseline_capture)
    assert "flush" in finding["message"]
    assert "rerun the preflight" in finding["message"]
    assert finding["resources"]["howler-hit_hot"] == [
        {
            "shard": "0",
            "reason": "unsynced",
            "max_seq_no": 7,
            "global_checkpoint": 6,
        }
    ]


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


@pytest.mark.parametrize("status", [404, 403])
def test_preflight_optional_ilm_explain_only_tolerates_404(status: int) -> None:
    class FailedIlmRestClient(FakeRestClient):
        def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
            if path == "/howler-*/_ilm/explain":
                raise ElasticsearchRestError("not found", status=status)
            return super().get(path, params)

    if status == 404:
        report = build_report(FailedIlmRestClient())  # type: ignore[arg-type]
        assert report["inventory"]["ilm_explain"] == {}
        assert report["checks"]["ready"] is True
    else:
        with pytest.raises(ElasticsearchRestError) as error:
            build_report(FailedIlmRestClient())  # type: ignore[arg-type]
        assert error.value.status == status


@pytest.mark.parametrize("baseline_capture", [False, True])
def test_preflight_main_writes_report(monkeypatch: pytest.MonkeyPatch, tmp_path, baseline_capture: bool) -> None:
    output = tmp_path / "preflight.json"
    flags = ["--baseline-capture"] if baseline_capture else []
    monkeypatch.setattr(sys, "argv", ["elasticsearch_preflight", *flags, "--output", str(output)])
    monkeypatch.setattr(preflight, "client_from_args", lambda args, parser: FakeRestClient())

    assert preflight.main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["checks"]["ready"] is True
    assert report["source_stack_version"] == SOURCE_STACK_VERSION
    assert report["baseline_capture"] is baseline_capture


@pytest.mark.parametrize(
    ("tls_flags", "expected_ca", "expected_insecure"),
    [
        (["--ca-certs", "/tmp/approved-ca.pem"], Path("/tmp/approved-ca.pem"), False),
        (["--insecure"], None, True),
    ],
)
def test_preflight_main_accepts_shared_connection_flags(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    tls_flags: list[str],
    expected_ca: Path | None,
    expected_insecure: bool,
) -> None:
    output = tmp_path / "preflight.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "elasticsearch_preflight",
            "--url",
            "https://example.invalid",
            *tls_flags,
            "--allow-insecure-http-auth",
            "--timeout",
            "17",
            "--output",
            str(output),
        ],
    )
    received: dict[str, Any] = {}

    def fake_client_from_args(args: Any, parser: Any) -> FakeRestClient:
        received.update(vars(args))
        return FakeRestClient()

    monkeypatch.setattr(preflight, "client_from_args", fake_client_from_args)

    assert preflight.main() == 0
    assert received["url"] == "https://example.invalid"
    assert received["ca_certs"] == expected_ca
    assert received["insecure"] is expected_insecure
    assert received["allow_insecure_http_auth"] is True
    assert received["timeout"] == 17
    assert received["output"] == output


def test_preflight_main_reports_rest_failure_without_hiding_http_status(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setattr(sys, "argv", ["elasticsearch_preflight"])
    monkeypatch.setattr(preflight, "client_from_args", lambda args, parser: object())
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
