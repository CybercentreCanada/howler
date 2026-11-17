from __future__ import annotations

import base64
import io
import sys
import threading
import urllib.error
import urllib.request
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from howler.external.elasticsearch_cutover_verify import (
    _collection_indices,
    _collection_models,
    _configured_ilm,
    _merge_dynamic_templates,
    _prefix,
    _read_baseline,
    _template_checks,
    build_report,
    collect_inventory,
    evaluate_inventory,
    main,
)
from howler.external.elasticsearch_rest import (
    ElasticsearchRestClient,
    ElasticsearchRestError,
    _NoRedirectHandler,
    collect_primary_shard_stats,
    credentials_from_environment,
)


def _mapping() -> dict[str, Any]:
    return {
        "dynamic": True,
        "properties": {
            "id": {"type": "keyword", "store": True, "doc_values": True},
            "label": {"type": "keyword", "ignore_above": 8191},
        },
        "dynamic_templates": [
            {
                "strings_as_keywords": {
                    "match_mapping_type": "string",
                    "mapping": {"type": "keyword", "ignore_above": 8191},
                }
            },
            {"label_tpl": {"path_match": "label", "mapping": {"type": "keyword", "index": True}}},
        ],
    }


@pytest.fixture(autouse=True)
def _stable_test_index_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    from howler.common import loader

    monkeypatch.setattr(loader, "DATASTORE_INDEX_PREFIX", "howler")


def _expectations(*, ilm: bool = False) -> dict[str, dict[str, Any]]:
    return {
        "alpha": {
            "alias": "howler-alpha",
            "ilm": ilm,
            "mapping": _mapping(),
            "model": "alpha-model",
            "total_fields_limit": 1600,
            **(
                {
                    "ilm_template": {
                        "settings": {
                            "index.lifecycle.name": "howler-alpha_policy",
                            "index.lifecycle.rollover_alias": "howler-alpha",
                            "index.mapping.total_fields.limit": 1600,
                        },
                        "mappings": _mapping(),
                    }
                }
                if ilm
                else {}
            ),
        }
    }


def _inventory(*, ilm: bool = False) -> dict[str, Any]:
    index = "howler-alpha-000002" if ilm else "howler-alpha_hot"
    aliases = {"howler-alpha": {"is_write_index": True}} if ilm else {"howler-alpha": {}}
    settings = {
        "index.uuid": "alpha-uuid",
        "index.mapping.total_fields.limit": "1600",
    }
    if ilm:
        settings.update(
            {"index.lifecycle.name": "howler-alpha_policy", "index.lifecycle.rollover_alias": "howler-alpha"}
        )
    live_mapping = {
        "dynamic": True,
        "properties": _mapping()["properties"],
        "dynamic_templates": _mapping()["dynamic_templates"],
    }
    inventory: dict[str, Any] = {
        "cluster_health": {"status": "green"},
        "deprecations": {"cluster_settings": [], "index_settings": {}, "node_settings": []},
        "feature_upgrade_status": {"features": [], "migration_status": "NO_MIGRATION_NEEDED"},
        "field_caps": {
            "alpha": {
                "fields": {
                    "id": {"keyword": {"searchable": True, "aggregatable": True}},
                    "label": {"keyword": {"searchable": True, "aggregatable": True}},
                }
            }
        },
        "ilm_explain": {},
        "ilm_templates": {},
        "ilm_policies": {},
        "index_prefix": "howler",
        "indices": {
            index: {
                "aliases": aliases,
                "doc_count": 4,
                "primary_shards": {"0": {"doc_count": 4, "max_seq_no": 3, "global_checkpoint": 3}},
                "settings": settings,
                "uuid": "alpha-uuid",
            }
        },
        "mappings": {index: {"mappings": live_mapping}},
        "nodes": {"nodes": {"node-1": {"name": "node-a", "version": "9.5.2"}}},
        "version": {"version": {"number": "9.5.2"}},
    }
    if ilm:
        inventory["ilm_explain"] = {
            index: {
                "managed": True,
                "policy": "howler-alpha_policy",
                "phase": "hot",
                "action": "complete",
                "step": "complete",
                "step_info": {},
            }
        }
        inventory["ilm_templates"]["alpha"] = {
            "index_patterns": ["howler-alpha-*"],
            "template": {
                "settings": {
                    "index.lifecycle.name": "howler-alpha_policy",
                    "index.lifecycle.rollover_alias": "howler-alpha",
                    "index.mapping.total_fields.limit": "1600",
                },
                "mappings": live_mapping,
            },
        }
        inventory["ilm_policies"]["alpha"] = {"phases": {"hot": {"actions": {"rollover": {"max_age": "30d"}}}}}
    return inventory


def _baseline(inventory: dict[str, Any]) -> dict[str, Any]:
    return {"index_prefix": "howler", "inventory": {"indices": inventory["indices"]}}


class FakeVerifierRest:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any] | None]] = []
        self.index = "howler-alpha_hot"
        self.index_status = "open"

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        self.calls.append((path, params))
        live_mapping = {
            "dynamic": True,
            "properties": _mapping()["properties"],
            "dynamic_templates": _mapping()["dynamic_templates"],
        }
        response: dict[str, Any] = {
            "/howler-*": {
                self.index: {
                    "aliases": {"howler-alpha": {}},
                    "settings": {
                        "index.uuid": "alpha-uuid",
                        "index.mapping.total_fields.limit": "1600",
                    },
                }
            },
            "/_cat/indices/howler-*": [{"index": self.index, "health": "green", "status": self.index_status}],
            "/howler-*/_stats": {
                "indices": {
                    self.index: {
                        "primaries": {"docs": {"count": 4}},
                        "shards": {
                            "0": [
                                {
                                    "routing": {"primary": True, "shard": 0},
                                    "docs": {"count": 4},
                                    "seq_no": {"max_seq_no": 3, "global_checkpoint": 3},
                                }
                            ]
                        },
                    }
                }
            },
            "/_cluster/health": {"status": "green"},
            "/howler-*/_mapping": {self.index: {"mappings": live_mapping}},
            "/howler-alpha/_field_caps": {
                "fields": {
                    "id": {"keyword": {"searchable": True}},
                    "label": {"keyword": {"searchable": True}},
                }
            },
            "/_migration/deprecations": {},
            "/_migration/system_features": {"migration_status": "NO_MIGRATION_NEEDED"},
            "/_nodes": {"nodes": {"node-1": {"name": "node-a", "version": "9.5.2"}}},
            "/": {"version": {"number": "9.5.2"}},
        }
        return response[path]


def _checks(
    inventory: dict[str, Any],
    *,
    ilm: bool = False,
    baseline: dict[str, Any] | None = None,
    allow_yellow: bool = False,
    integrity_only: bool = False,
    accepted_sequence_drift: set[str] | None = None,
) -> dict[str, Any]:
    return evaluate_inventory(
        inventory,
        _expectations(ilm=ilm),
        baseline=baseline,
        allow_yellow=allow_yellow,
        integrity_only=integrity_only,
        accepted_sequence_drift=accepted_sequence_drift,
    )


def _blockers(report: dict[str, Any], check: str) -> list[dict[str, Any]]:
    return [item for item in report["blockers"] if item["check"] == check]


def test_clean_95_cluster_and_unchanged_quiesced_baseline_pass() -> None:
    inventory = _inventory()

    report = _checks(inventory, baseline=_baseline(inventory))

    assert report["ready"] is True
    assert report["blockers"] == []
    assert report["warnings"] == []


def test_collect_inventory_build_report_are_scoped_and_share_primary_stats(monkeypatch: pytest.MonkeyPatch) -> None:
    import howler.external.elasticsearch_cutover_verify as verifier

    monkeypatch.setattr(verifier, "_expectations", lambda: _expectations())
    client = FakeVerifierRest()

    inventory = collect_inventory(client, _expectations())
    report = build_report(client)

    assert inventory["indices"]["howler-alpha_hot"]["uuid"] == "alpha-uuid"
    assert inventory["indices"]["howler-alpha_hot"]["doc_count"] == 4
    assert inventory["indices"]["howler-alpha_hot"]["primary_shards"]["0"] == {
        "doc_count": 4,
        "max_seq_no": 3,
        "global_checkpoint": 3,
    }
    assert report["checks"]["ready"] is True
    paths = [path for path, _ in client.calls]
    assert "/howler-*/_stats" in paths
    assert "/howler-*/_mapping" in paths
    assert "/howler-alpha/_field_caps" in paths
    assert "/*" not in paths
    assert "/_mapping" not in paths


def test_collect_inventory_skips_field_caps_for_closed_configured_backer() -> None:
    client = FakeVerifierRest()
    client.index_status = "close"

    inventory = collect_inventory(client, _expectations())
    report = evaluate_inventory(inventory, _expectations())

    assert inventory["indices"]["howler-alpha_hot"]["status"] == "close"
    assert "alpha" not in inventory["field_caps"]
    assert "/howler-alpha/_field_caps" not in [path for path, _ in client.calls]
    assert not _blockers(report, "field_caps_missing")


def test_integrity_only_collects_no_contract_mapping_or_field_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    import howler.external.elasticsearch_cutover_verify as verifier

    monkeypatch.setattr(verifier, "_expectations", lambda: _expectations())
    inventory = _inventory()
    client = FakeVerifierRest()

    report = build_report(client, baseline=_baseline(inventory), integrity_only=True)

    assert report["checks"]["ready"] is True
    assert report["checks"]["integrity_only"] is True
    paths = [path for path, _ in client.calls]
    assert "/howler-*/_mapping" not in paths
    assert "/howler-alpha/_field_caps" not in paths


def test_integrity_only_cli_requires_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, "argv", ["elasticsearch_cutover_verify", "--integrity-only"])

    with pytest.raises(SystemExit):
        main()


def test_main_writes_blocking_json_with_safe_known_error_detail(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import json
    import sys

    import howler.external.elasticsearch_cutover_verify as verifier

    output = tmp_path / "error-report.json"
    monkeypatch.setattr(sys, "argv", ["elasticsearch_cutover_verify", "--output", str(output)])
    monkeypatch.setattr(verifier, "_client_from_args", lambda args, parser: object())
    monkeypatch.setattr(
        verifier,
        "build_report",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("legacy-plugin uses modify_odm")),
    )

    status = main()
    report = json.loads(output.read_text(encoding="utf-8"))

    assert status == 1
    assert report["checks"]["ready"] is False
    assert "legacy-plugin" in report["checks"]["blockers"][0]["message"]


def test_main_writes_valid_report_after_reading_clean_baseline(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import json
    import sys

    import howler.external.elasticsearch_cutover_verify as verifier

    baseline_path = tmp_path / "baseline.json"
    output_path = tmp_path / "cutover.json"
    baseline = {
        "index_prefix": "howler",
        "baseline_capture": True,
        "source_stack_version": "8.19.11",
        "checks": {"ready": True},
        "inventory": {
            "indices": {"howler-alpha_hot": {}},
            "version": {"version": {"number": "8.19.11"}},
        },
    }
    baseline_path.write_text(json.dumps(baseline), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "elasticsearch_cutover_verify",
            "--baseline",
            str(baseline_path),
            "--accept-sequence-drift",
            "howler-user_hot",
            "--accept-sequence-drift",
            "howler-user_avatar_hot",
            "--output",
            str(output_path),
        ],
    )
    monkeypatch.setattr(verifier, "_client_from_args", lambda args, parser: object())
    received: dict[str, Any] = {}

    def fake_build_report(client: Any, *, baseline: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        received["baseline"] = baseline
        received["accepted_sequence_drift"] = kwargs.get("accepted_sequence_drift")
        return {"checks": {"ready": True}, "target_version": "9.5.2"}

    monkeypatch.setattr(verifier, "build_report", fake_build_report)

    assert main() == 0
    assert received["baseline"] == baseline
    assert received["accepted_sequence_drift"] == {"howler-user_hot", "howler-user_avatar_hot"}
    assert json.loads(output_path.read_text(encoding="utf-8"))["checks"]["ready"] is True


def test_sequence_drift_acceptance_cli_requires_baseline(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(
        sys,
        "argv",
        ["elasticsearch_cutover_verify", "--accept-sequence-drift", "howler-user_hot"],
    )

    with pytest.raises(SystemExit) as error:
        main()

    assert error.value.code == 2


@pytest.mark.parametrize(
    ("error", "visible_detail"),
    [
        (ValueError("legacy-plugin uses modify_odm"), "legacy-plugin uses modify_odm"),
        pytest.param(None, "typed model extensions", id="howler-attribute-error"),
        (RuntimeError("private token detail"), "details were omitted"),
    ],
)
def test_main_only_exposes_known_safe_exception_messages(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    error: Exception | None,
    visible_detail: str,
) -> None:
    import json
    import sys

    import howler.external.elasticsearch_cutover_verify as verifier
    from howler.common.exceptions import HowlerAttributeError

    output = tmp_path / "error-report.json"
    monkeypatch.setattr(sys, "argv", ["elasticsearch_cutover_verify", "--output", str(output)])
    monkeypatch.setattr(verifier, "_client_from_args", lambda args, parser: object())
    raised_error = HowlerAttributeError("legacy-plugin requires typed model extensions") if error is None else error
    monkeypatch.setattr(
        verifier,
        "build_report",
        lambda *args, **kwargs: (_ for _ in ()).throw(raised_error),
    )

    assert main() == 1
    message = json.loads(output.read_text(encoding="utf-8"))["checks"]["blockers"][0]["message"]
    assert visible_detail in message
    if isinstance(raised_error, RuntimeError):
        assert "private token detail" not in message


def test_baseline_reader_rejects_wrong_version_and_unclean_preflight(tmp_path) -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser()
    path = tmp_path / "baseline.json"
    invalid = {
        "index_prefix": "howler",
        "source_stack_version": "8.19.11",
        "checks": {"ready": False},
        "inventory": {"indices": {}, "version": {"version": {"number": "8.19.11"}}},
    }
    path.write_text(json.dumps(invalid), encoding="utf-8")

    with pytest.raises(SystemExit):
        _read_baseline(path, parser)


def test_baseline_reader_accepts_clean_819_preflight(tmp_path) -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser()
    path = tmp_path / "baseline.json"
    valid = {
        "index_prefix": "howler",
        "baseline_capture": True,
        "source_stack_version": "8.19.11",
        "checks": {"ready": True},
        "inventory": {"indices": {"howler-alpha_hot": {}}, "version": {"version": {"number": "8.19.11"}}},
    }
    path.write_text(json.dumps(valid), encoding="utf-8")

    assert _read_baseline(path, parser) == valid


def test_baseline_reader_rejects_prefix_overlap(tmp_path) -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser()
    path = tmp_path / "baseline.json"
    overlapping = {
        "index_prefix": "howler-prod",
        "baseline_capture": True,
        "source_stack_version": "8.19.11",
        "checks": {"ready": True},
        "inventory": {
            "indices": {"howler-prod-hit_hot": {}},
            "version": {"version": {"number": "8.19.11"}},
        },
    }
    path.write_text(json.dumps(overlapping), encoding="utf-8")

    with pytest.raises(SystemExit):
        _read_baseline(path, parser)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda baseline: baseline.update(source_stack_version="8.18.7"),
        lambda baseline: baseline["inventory"]["version"]["version"].update(number="8.18.7"),
    ],
)
def test_baseline_reader_rejects_wrong_source_versions(tmp_path, mutate: Any) -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser()
    path = tmp_path / "baseline.json"
    invalid = {
        "index_prefix": "howler",
        "source_stack_version": "8.19.11",
        "checks": {"ready": True},
        "inventory": {"indices": {"howler-alpha_hot": {}}, "version": {"version": {"number": "8.19.11"}}},
    }
    mutate(invalid)
    path.write_text(json.dumps(invalid), encoding="utf-8")

    with pytest.raises(SystemExit):
        _read_baseline(path, parser)


def test_baseline_reader_rejects_report_not_captured_in_baseline_mode(tmp_path) -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser()
    path = tmp_path / "baseline.json"
    report = {
        "index_prefix": "howler",
        "baseline_capture": False,
        "source_stack_version": "8.19.11",
        "checks": {"ready": True},
        "inventory": {
            "indices": {"howler-alpha_hot": {}},
            "version": {"version": {"number": "8.19.11"}},
        },
    }
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(SystemExit):
        _read_baseline(path, parser)


def test_yellow_is_blocked_unless_explicitly_accepted_and_reported() -> None:
    inventory = _inventory()
    inventory["cluster_health"]["status"] = "yellow"

    blocked = _checks(inventory)
    accepted = _checks(inventory, allow_yellow=True)

    assert [item["check"] for item in blocked["blockers"]] == ["cluster_health"]
    assert blocked["warnings"] == []
    assert accepted["ready"] is True
    assert accepted["warnings"] == [
        {"check": "cluster_health_override", "message": "Yellow health was explicitly accepted using --allow-yellow."}
    ]


def test_yellow_health_does_not_hide_uninitialized_collection_blockers() -> None:
    inventory = _inventory()
    inventory["cluster_health"]["status"] = "yellow"
    inventory["indices"] = {}
    inventory["mappings"] = {}
    inventory["field_caps"] = {}

    report = _checks(inventory)

    assert {blocker["check"] for blocker in report["blockers"]} == {
        "cluster_health",
        "collection_not_initialized",
    }


def test_incomplete_cluster_health_response_is_blocked() -> None:
    inventory = _inventory()
    inventory["cluster_health"]["timed_out"] = True

    report = _checks(inventory)

    assert _blockers(report, "cluster_health_timeout")


def test_empty_node_version_inventory_blocks() -> None:
    inventory = _inventory()
    inventory["nodes"]["nodes"] = {}

    assert _blockers(_checks(inventory), "node_versions")


def test_each_cluster_gate_blocks_unhealthy_versions_features_and_critical_deprecations() -> None:
    inventory = _inventory()
    inventory["version"]["version"]["number"] = "9.5.1"
    inventory["nodes"]["nodes"]["node-1"]["version"] = "9.5.1"
    inventory["deprecations"]["index_settings"] = {"howler-alpha_hot": [{"level": "critical", "message": "unresolved"}]}

    report = _checks(inventory)

    assert _blockers(report, "cluster_version")
    assert _blockers(report, "node_version")
    assert _blockers(report, "critical_deprecations")


def test_real_95_migration_deprecations_shape_warns_for_next_major_index_compatibility() -> None:
    inventory = _inventory()
    # Shape returned by Elasticsearch 9.5.2 GET /_migration/deprecations.
    inventory["deprecations"] = {
        "cluster_settings": [],
        "node_settings": [],
        "index_settings": {
            "howler-alpha_hot": [
                {
                    "level": "critical",
                    "message": "Old index with a compatibility version < 9.0",
                    "url": "https://ela.st/es-deprecation-9-index-version",
                    "details": "This index has version: 8.19.9-8.19.20",
                    "resolve_during_rolling_upgrade": False,
                    "_meta": {"reindex_required": True},
                }
            ]
        },
    }

    report = _checks(inventory)

    assert report["ready"] is True
    assert report["warnings"][0]["check"] == "es10_readiness"
    assert report["warnings"][0]["resources"][0]["message"] == "Old index with a compatibility version < 9.0"
    assert not _blockers(report, "critical_deprecations")


def test_collection_models_follow_application_finalization_order(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    from howler import plugins as plugin_loader
    from howler.config_models import config
    from howler.external import elasticsearch_cutover_verify as verifier
    from howler.models import model_extensions, schema
    from howler.plugins import PLUGINS

    monkeypatch.setenv("HWL_PLUGIN_DIRECTORY", str(tmp_path / "plugins"))
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(plugin_loader, "get_plugins", lambda: [])
    monkeypatch.setattr(config.core, "plugins", set())
    monkeypatch.setattr(config.core.clue, "enabled", False)
    monkeypatch.setattr(verifier, "_COLLECTION_MODELS", ())
    finalized: list[str] = []
    mapped: list[str | None] = []
    monkeypatch.setattr(model_extensions, "finalize", lambda model: finalized.append(model.__name__) or model)
    monkeypatch.setattr(
        schema,
        "document_mapping",
        lambda model: mapped.append(model.__name__ if model is not None else None) or {},
    )
    old_plugin_cache = dict(PLUGINS)
    PLUGINS.clear()
    model_extensions.clear()
    try:
        models = _collection_models()
    finally:
        model_extensions.clear()
        PLUGINS.update(old_plugin_cache)

    expected_order = [
        "hit",
        "event",
        "case",
        "template",
        "overview",
        "analytic",
        "action",
        "migration",
        "user",
        "view",
        "dossier",
        "user_avatar",
    ]
    assert [name for name, _ in models] == expected_order
    expected_model_names = [
        "Hit",
        "Event",
        "Case",
        "Template",
        "Overview",
        "Analytic",
        "Action",
        "MigrationRecord",
        "User",
        "View",
        "Dossier",
    ]
    assert finalized == expected_model_names
    assert mapped == [*expected_model_names, None]


def test_expectations_apply_prefix_ilm_and_schema_contracts(monkeypatch: pytest.MonkeyPatch) -> None:
    from howler.external import elasticsearch_cutover_verify as verifier
    from howler.models import schema

    monkeypatch.setattr(verifier, "_collection_models", lambda: (("alpha", object), ("avatar", None)))
    monkeypatch.setattr(verifier, "_prefix", lambda: "cutover")
    monkeypatch.setattr(verifier, "_configured_ilm", lambda name: name == "alpha")
    monkeypatch.setattr(verifier, "_collection_shards_replicas", lambda _: (3, 2))
    monkeypatch.setattr(schema, "document_mapping", lambda model: {"model": model})
    monkeypatch.setattr(schema, "total_fields_limit", lambda model: 2161 if model is object else 1000)
    monkeypatch.setattr(
        schema,
        "ilm_template_body",
        lambda model, **kwargs: {"model": model, "options": kwargs},
    )

    expectations = verifier._expectations()

    assert expectations["alpha"]["alias"] == "cutover-alpha"
    assert expectations["alpha"]["ilm"] is True
    assert expectations["alpha"]["total_fields_limit"] == 2161
    assert expectations["alpha"]["ilm_template"]["options"] == {
        "shards": 3,
        "replicas": 2,
        "policy_name": "cutover-alpha_policy",
        "rollover_alias": "cutover-alpha",
    }
    assert expectations["avatar"]["alias"] == "cutover-avatar"
    assert expectations["avatar"]["ilm"] is False
    assert "ilm_template" not in expectations["avatar"]


@pytest.mark.parametrize("status", ["IN_PROGRESS", "ERROR"])
def test_system_feature_active_or_failed_migration_blocks(status: str) -> None:
    inventory = _inventory()
    inventory["feature_upgrade_status"]["migration_status"] = status

    assert _blockers(_checks(inventory), "system_features")


def test_system_feature_migration_needed_is_es10_readiness_warning() -> None:
    inventory = _inventory()
    inventory["feature_upgrade_status"]["migration_status"] = "MIGRATION_NEEDED"

    report = _checks(inventory)

    assert report["ready"] is True
    assert report["warnings"][0]["check"] == "es10_readiness_system_features"


@pytest.mark.parametrize(
    ("issue", "expected_check"),
    [
        (
            {
                "level": "critical",
                "message": "Old index with a compatibility version < 9.0",
                "url": "https://ela.st/es-deprecation-9-index-version",
                "details": "This index has version: 8.19.9-8.19.20",
                "resolve_during_rolling_upgrade": False,
                "_meta": {"reindex_required": True},
            },
            "es10_readiness",
        ),
        (
            {
                "level": "critical",
                "message": "Old data stream with a compatibility version < 9.0",
                "url": "https://ela.st/es-deprecation-9-data-stream-version",
                "details": "This data stream has backing indices created before 9.0",
                "resolve_during_rolling_upgrade": False,
                "_meta": {"reindex_required": True},
            },
            "es10_readiness",
        ),
        (
            {
                "level": "critical",
                "message": "Unresolved critical setting required for 9.x operation",
                "url": "https://ela.st/es-deprecation-example",
                "details": "This issue is not a next-major compatibility notice.",
                "resolve_during_rolling_upgrade": False,
            },
            "critical_deprecations",
        ),
    ],
)
def test_95_deprecation_response_shapes_are_classified(issue: dict[str, Any], expected_check: str) -> None:
    inventory = _inventory()
    inventory["deprecations"]["index_settings"] = {"howler-alpha_hot": [issue]}

    report = _checks(inventory)

    assert any(item["check"] == expected_check for item in (report["warnings"] + report["blockers"]))
    if expected_check == "es10_readiness":
        assert report["ready"] is True
        assert not _blockers(report, "critical_deprecations")
    else:
        assert report["ready"] is False


def test_missing_alias_and_multiple_write_indices_block() -> None:
    inventory = _inventory()
    inventory["indices"]["howler-alpha_hot"]["aliases"] = {}
    missing = _checks(inventory)
    inventory = _inventory()
    inventory["indices"]["howler-alpha_hot"]["aliases"]["howler-alpha"]["is_write_index"] = True
    inventory["indices"]["howler-alpha-000002"] = {
        "aliases": {"howler-alpha": {"is_write_index": True}},
        "settings": {"index.uuid": "second", "index.mapping.total_fields.limit": "1600"},
        "uuid": "second",
    }
    multiple = _checks(inventory)

    assert _blockers(missing, "alias_missing")
    assert _blockers(missing, "alias_write_index")
    assert _blockers(multiple, "alias_write_index")


def test_full_mode_blocks_uninitialized_collection_and_integrity_mode_skips_it() -> None:
    inventory = _inventory()
    inventory["indices"] = {}
    inventory["mappings"] = {}
    inventory["field_caps"] = {}
    absent = _checks(inventory)
    old = _inventory()
    lost = _checks(inventory, baseline=_baseline(old))
    integrity = _checks(inventory, baseline=_baseline(old), integrity_only=True)

    assert _blockers(absent, "collection_not_initialized")
    assert _blockers(lost, "collection_missing_after_baseline")
    assert not _blockers(integrity, "collection_not_initialized")


def test_legacy_layout_blocks_when_hot_index_is_detached_and_alias_targets_stray() -> None:
    inventory = _inventory()
    inventory["indices"]["howler-alpha_hot"]["aliases"] = {}
    inventory["indices"]["howler-alpha_stray"] = {
        "aliases": {"howler-alpha": {"is_write_index": True}},
        "settings": {"index.uuid": "stray", "index.mapping.total_fields.limit": "1600"},
        "uuid": "stray",
    }
    inventory["mappings"]["howler-alpha_stray"] = inventory["mappings"]["howler-alpha_hot"]
    inventory["field_caps"]["alpha"]["fields"] = {}

    report = _checks(inventory)

    assert _blockers(report, "legacy_write_index")


def test_legacy_alias_implicit_single_write_and_hot_layout_are_required() -> None:
    inventory = _inventory()
    inventory["indices"]["howler-alpha_hot"]["aliases"]["howler-alpha"]["is_write_index"] = False
    explicit_false = _checks(inventory)
    inventory = _inventory()
    inventory["indices"].pop("howler-alpha_hot")
    inventory["mappings"].pop("howler-alpha_hot")
    missing_hot = _checks(inventory)

    assert _blockers(explicit_false, "alias_write_index")
    assert not _blockers(missing_hot, "legacy_hot_index")
    assert _blockers(missing_hot, "collection_not_initialized")


def test_expected_properties_must_exist_and_match_definition_on_each_backing_index() -> None:
    inventory = _inventory()
    del inventory["mappings"]["howler-alpha_hot"]["mappings"]["properties"]["label"]
    missing = _checks(inventory)
    inventory = _inventory()
    inventory["mappings"]["howler-alpha_hot"]["mappings"]["properties"]["label"]["type"] = "text"
    mismatched = _checks(inventory)

    assert _blockers(missing, "mapping_property_missing")
    assert _blockers(mismatched, "mapping_property_mismatch")


def test_schema_less_property_and_template_drift_is_warning_only() -> None:
    inventory = _inventory()
    del inventory["mappings"]["howler-alpha_hot"]["mappings"]["properties"]["label"]
    expectations = _expectations()
    expectations["alpha"]["model"] = None

    report = evaluate_inventory(inventory, expectations)

    assert report["ready"] is True
    assert any(warning["check"] == "schema_less_mapping_property_missing" for warning in report["warnings"])


def test_active_dynamic_template_order_is_preserved_and_extra_template_warns() -> None:
    inventory = _inventory()
    templates = inventory["mappings"]["howler-alpha_hot"]["mappings"]["dynamic_templates"]
    templates.reverse()
    reordered = _checks(inventory)
    assert _blockers(reordered, "dynamic_templates")

    inventory = _inventory()
    inventory["mappings"]["howler-alpha_hot"]["mappings"]["dynamic_templates"].append(
        {"disabled_plugin_template": {"match": "legacy", "mapping": {"type": "keyword"}}}
    )
    extra = _checks(inventory)
    assert extra["ready"] is True
    assert extra["warnings"][0]["templates"] == ["disabled_plugin_template"]


def test_real_schema_less_default_templates_merge_to_live_15_entry_shape() -> None:
    from howler.models.schema_defaults import default_dynamic_templates

    expected = deepcopy(default_dynamic_templates)
    live = _merge_dynamic_templates(expected)
    assert len(live) == 15
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    _template_checks(
        "user_avatar",
        "howler-user_avatar",
        "howler-user_avatar_hot",
        expected,
        live,
        blockers,
        warnings,
        schema_less=True,
    )
    assert blockers == []
    shadow_warning = next(warning for warning in warnings if warning["check"] == "shadowed_dynamic_template_name")
    assert shadow_warning["names"] == ["date"]
    assert shadow_warning["shadowed_definitions"]["date"]["shadowed"][0]["path_match"] == "*_dt"
    assert shadow_warning["shadowed_definitions"]["date"]["effective"]["path_match"] == "*_dts"

    changed = deepcopy(live)
    changed[-1] = {"date": {"path_match": "*_dts", "mapping": {"type": "keyword"}}}
    _template_checks(
        "user_avatar",
        "howler-user_avatar",
        "howler-user_avatar_hot",
        expected,
        changed,
        blockers,
        warnings,
        schema_less=True,
    )

    assert blockers == []
    assert any(warning["check"] == "schema_less_dynamic_templates" for warning in warnings)


def test_configured_backing_layout_excludes_ilm_reindex_temporaries() -> None:
    indices = {
        "howler-alpha-000001": {"aliases": {"howler-alpha": {"is_write_index": False}}},
        "howler-alpha-000002": {"aliases": {"howler-alpha": {"is_write_index": True}}},
        "howler-alpha-000003__reindex": {"aliases": {}},
        "howler-alpha_hot": {"aliases": {}},
    }

    ilm_backers, ilm_attached = _collection_indices("howler-alpha", True, indices)

    assert ilm_backers == ["howler-alpha-000001", "howler-alpha-000002"]
    assert ilm_attached == ilm_backers
    legacy_indices = {
        **indices,
        "howler-alpha-000001": {"aliases": {}},
        "howler-alpha-000002": {"aliases": {}},
    }
    legacy_backers, legacy_attached = _collection_indices("howler-alpha", False, legacy_indices)
    assert legacy_backers == ["howler-alpha_hot"]
    assert legacy_attached == []


def test_total_field_limit_is_computed_from_finalized_extension_model(monkeypatch: pytest.MonkeyPatch) -> None:
    from howler.models import model_extensions
    from howler.models.fields import keyword
    from howler.models.hit import Hit
    from howler.models.registry import model_registry
    from howler.models.schema import flat_field_count, total_fields_limit

    monkeypatch.setattr(model_registry, "_models", dict(model_registry._models))
    model_extensions.clear()
    original_flat_count = flat_field_count(Hit)
    model_extensions.declare(Hit, "cutover_probe", keyword(), plugin="cutover-test")
    finalized_hit = model_extensions.finalize(Hit)
    finalized_flat_count = flat_field_count(finalized_hit)
    model_extensions.clear()

    assert finalized_flat_count == original_flat_count + 1
    assert total_fields_limit(finalized_hit) == max(1500, finalized_flat_count + 500)


def test_real_clue_evidence_sentinel_hit_composition_matches_application_finalization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pathlib import Path

    from howler.config_models import config
    from howler.datastore.howler_store import HowlerDatastore
    from howler.external import elasticsearch_cutover_verify as verifier
    from howler.models import model_extensions
    from howler.models.registry import model_registry
    from howler.models.schema import flat_field_count, total_fields_limit
    from howler.plugins import PLUGINS

    class MockESStore:
        def __init__(self) -> None:
            self.registrations: dict[str, dict[str, Any]] = {}

        def register(
            self,
            name: str,
            model: Any,
            *,
            ilm_config: Any,
            schema_model: Any,
        ) -> None:
            self.registrations[name] = {
                "model": model,
                "ilm_config": ilm_config,
                "schema_model": schema_model,
            }

    plugin_root = Path(__file__).resolve().parents[3] / "plugins"
    monkeypatch.setenv("HWL_PLUGIN_DIRECTORY", str(plugin_root))
    monkeypatch.setattr(config.core, "plugins", {"evidence", "sentinel"})
    monkeypatch.setattr(config.core.clue, "enabled", True)
    monkeypatch.setattr(
        sys,
        "path",
        [str(plugin_root / "evidence"), str(plugin_root / "sentinel"), *sys.path],
    )
    monkeypatch.setattr(verifier, "_COLLECTION_MODELS", ())
    monkeypatch.setattr(model_registry, "_models", dict(model_registry._models))
    old_plugin_cache = dict(PLUGINS)
    PLUGINS.clear()
    model_extensions.clear()
    try:
        verifier_hit = dict(verifier._collection_models())["hit"]
        assert verifier_hit is not None
        verifier_count = flat_field_count(verifier_hit)
        verifier_limit = total_fields_limit(verifier_hit)

        # Run the application's real finalization/registration path without constructing ESStore.
        application_store = MockESStore()
        HowlerDatastore(application_store)  # type: ignore[arg-type]
        application_hit = application_store.registrations["hit"]["schema_model"]
        assert application_hit is not None
        application_count = flat_field_count(application_hit)
        application_limit = total_fields_limit(application_hit)
    finally:
        model_extensions.clear()
        PLUGINS.clear()
        PLUGINS.update(old_plugin_cache)

    assert verifier_count == application_count == 1661
    assert verifier_limit == application_limit == 2161


def test_runtime_prefix_and_per_collection_ilm_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    from howler.common import loader
    from howler.config_models import ILMIndexConfig, config

    monkeypatch.setattr(loader, "DATASTORE_INDEX_PREFIX", "cutover-test")
    monkeypatch.setattr(config.datastore.ilm, "enabled", True)
    monkeypatch.setattr(config.datastore.ilm, "indices", {"hit": ILMIndexConfig(enabled=False)})

    assert _prefix() == "cutover-test"
    assert _configured_ilm("case") is True
    assert _configured_ilm("hit") is False


def test_legacy_modify_odm_plugin_rejection_includes_plugin_name(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from howler import plugins as plugin_loader
    from howler.common.exceptions import HowlerAttributeError
    from howler.config_models import config
    from howler.external import elasticsearch_cutover_verify as verifier
    from howler.models import model_extensions
    from howler.plugins import PLUGINS

    fake_plugin = SimpleNamespace(
        name="legacy-plugin",
        modules=SimpleNamespace(
            odm=SimpleNamespace(modify_odm={"hit": object()}),
            models=SimpleNamespace(declare_extensions={}),
        ),
    )
    monkeypatch.setattr(plugin_loader, "get_plugins", lambda: [fake_plugin])
    monkeypatch.setattr(config.core, "plugins", set())
    monkeypatch.setattr(config.core.clue, "enabled", False)
    monkeypatch.setattr(verifier, "_COLLECTION_MODELS", ())
    monkeypatch.setenv("HWL_PLUGIN_DIRECTORY", "/path/without/plugins")
    monkeypatch.setattr(sys, "path", list(sys.path))
    old_plugin_cache = dict(PLUGINS)
    PLUGINS.clear()
    model_extensions.clear()
    try:
        with pytest.raises(HowlerAttributeError, match="legacy-plugin"):
            _collection_models()
    finally:
        model_extensions.clear()
        PLUGINS.update(old_plugin_cache)


def test_verifier_fails_closed_for_missing_configured_plugin(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    import json
    from pathlib import Path

    from howler.config_models import config
    from howler.external import elasticsearch_cutover_verify as verifier
    from howler.plugins import PLUGINS

    plugin_root = Path(__file__).resolve().parents[3] / "plugins"
    monkeypatch.setenv("HWL_PLUGIN_DIRECTORY", str(plugin_root))
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(config.core, "plugins", {"missing-cutover-plugin"})
    output = tmp_path / "missing-plugin.json"
    monkeypatch.setattr(sys, "argv", ["elasticsearch_cutover_verify", "--output", str(output)])
    monkeypatch.setattr(verifier, "_client_from_args", lambda args, parser: object())
    old_plugin_cache = dict(PLUGINS)
    PLUGINS.clear()
    try:
        assert main() == 1
    finally:
        PLUGINS.clear()
        PLUGINS.update(old_plugin_cache)

    report = json.loads(output.read_text(encoding="utf-8"))
    assert "missing-cutover-plugin" in report["checks"]["blockers"][0]["message"]


def test_total_field_limit_and_field_caps_conflicts_block() -> None:
    inventory = _inventory()
    inventory["indices"]["howler-alpha_hot"]["settings"]["index.mapping.total_fields.limit"] = "1599"
    inventory["field_caps"]["alpha"]["fields"]["label"]["text"] = {"searchable": True}

    report = _checks(inventory)

    assert _blockers(report, "total_fields_limit")
    assert _blockers(report, "field_caps_conflict")


def test_field_caps_conflict_on_non_schema_field_warns_only() -> None:
    inventory = _inventory()
    inventory["field_caps"]["alpha"]["fields"]["dynamic.value"] = {
        "keyword": {"searchable": True},
        "long": {"searchable": True},
    }

    report = _checks(inventory)

    assert report["ready"] is True
    assert not _blockers(report, "field_caps_conflict")
    assert any(
        warning["check"] == "field_caps_non_schema_conflict" and warning["field"] == "dynamic.value"
        for warning in report["warnings"]
    )


def test_lower_legacy_limit_warns_only_when_current_mapping_fits() -> None:
    inventory = _inventory(ilm=True)
    inventory["indices"]["howler-alpha-000001"] = {
        "aliases": {"howler-alpha": {"is_write_index": False}},
        "doc_count": 4,
        "primary_shards": {"0": {"doc_count": 4, "max_seq_no": 3, "global_checkpoint": 3}},
        "settings": {
            "index.uuid": "older",
            "index.mapping.total_fields.limit": "2",
            "index.lifecycle.name": "howler-alpha_policy",
            "index.lifecycle.rollover_alias": "howler-alpha",
        },
        "uuid": "older",
    }
    inventory["mappings"]["howler-alpha-000001"] = inventory["mappings"]["howler-alpha-000002"]
    inventory["ilm_explain"]["howler-alpha-000001"] = inventory["ilm_explain"]["howler-alpha-000002"]

    report = _checks(inventory, ilm=True)

    assert report["ready"] is True
    assert any(warning["check"] == "total_fields_limit_legacy_lower" for warning in report["warnings"])


def test_legacy_limit_below_actual_mapping_count_blocks() -> None:
    inventory = _inventory(ilm=True)
    inventory["indices"]["howler-alpha-000001"] = {
        "aliases": {"howler-alpha": {"is_write_index": False}},
        "settings": {
            "index.uuid": "older",
            "index.mapping.total_fields.limit": "1",
            "index.lifecycle.name": "howler-alpha_policy",
            "index.lifecycle.rollover_alias": "howler-alpha",
        },
        "uuid": "older",
    }
    inventory["mappings"]["howler-alpha-000001"] = inventory["mappings"]["howler-alpha-000002"]
    inventory["ilm_explain"]["howler-alpha-000001"] = inventory["ilm_explain"]["howler-alpha-000002"]

    report = _checks(inventory, ilm=True)

    assert _blockers(report, "total_fields_limit_below_mapped_fields")


def test_missing_mapping_or_field_caps_data_blocks() -> None:
    inventory = _inventory()
    inventory["mappings"] = {}
    missing_mapping = _checks(inventory)
    inventory = _inventory()
    inventory["field_caps"] = {}
    missing_caps = _checks(inventory)
    inventory = _inventory()
    inventory["field_caps"]["alpha"] = {"not_fields": {}}
    malformed_caps = _checks(inventory)

    assert _blockers(missing_mapping, "mapping_missing")
    assert _blockers(missing_caps, "field_caps_missing")
    assert _blockers(malformed_caps, "field_caps_missing")


def test_ilm_latest_write_index_policy_and_error_step_are_verified() -> None:
    inventory = _inventory(ilm=True)
    assert _checks(inventory, ilm=True)["ready"] is True

    inventory["indices"]["howler-alpha-000001"] = {
        "aliases": {"howler-alpha": {"is_write_index": True}},
        "settings": {"index.uuid": "older", "index.mapping.total_fields.limit": "1600"},
        "uuid": "older",
    }
    inventory["mappings"]["howler-alpha-000001"] = inventory["mappings"]["howler-alpha-000002"]
    inventory["ilm_explain"]["howler-alpha-000001"] = {
        "managed": True,
        "policy": "howler-alpha_policy",
        "step": "ERROR",
        "step_info": {"reason": "failed"},
    }
    report = _checks(inventory, ilm=True)

    assert _blockers(report, "alias_write_index")
    assert _blockers(report, "ilm_write_index")
    assert _blockers(report, "ilm_step")


def test_ilm_without_canonical_generation_blocks() -> None:
    inventory = _inventory(ilm=True)
    inventory["indices"] = {"howler-alpha_hot": inventory["indices"]["howler-alpha-000002"]}
    inventory["indices"]["howler-alpha_hot"]["aliases"] = {"howler-alpha": {"is_write_index": True}}
    inventory["mappings"] = {"howler-alpha_hot": inventory["mappings"]["howler-alpha-000002"]}
    inventory["ilm_explain"] = {"howler-alpha_hot": inventory["ilm_explain"]["howler-alpha-000002"]}

    assert _blockers(_checks(inventory, ilm=True), "ilm_backing_indices")


def test_ilm_explain_unmanaged_index_blocks() -> None:
    inventory = _inventory(ilm=True)
    inventory["ilm_explain"]["howler-alpha-000002"]["managed"] = False

    assert _blockers(_checks(inventory, ilm=True), "ilm_managed")


def test_ilm_requires_policy_and_rollover_alias_settings() -> None:
    inventory = _inventory(ilm=True)
    inventory["indices"]["howler-alpha-000002"]["settings"]["index.lifecycle.rollover_alias"] = "wrong"
    inventory["ilm_explain"]["howler-alpha-000002"]["policy"] = "wrong_policy"

    report = _checks(inventory, ilm=True)

    assert _blockers(report, "ilm_settings")
    assert _blockers(report, "ilm_policy")


def test_ilm_future_template_and_rollover_policy_are_verified() -> None:
    inventory = _inventory(ilm=True)
    inventory["ilm_templates"]["alpha"]["index_patterns"] = ["wrong-pattern-*"]
    inventory["ilm_policies"]["alpha"]["phases"]["hot"]["actions"] = {}

    report = _checks(inventory, ilm=True)

    assert _blockers(report, "ilm_template_patterns")
    assert _blockers(report, "ilm_policy_rollover")

    inventory = _inventory(ilm=True)
    inventory["ilm_templates"]["alpha"] = None
    assert _blockers(_checks(inventory, ilm=True), "ilm_template_missing")

    inventory = _inventory(ilm=True)
    template_mapping = inventory["ilm_templates"]["alpha"]["template"]["mappings"]
    template_mapping["properties"]["label"]["type"] = "text"
    template_mapping["dynamic_templates"].reverse()
    report = _checks(inventory, ilm=True)
    assert _blockers(report, "ilm_template_property")
    assert _blockers(report, "dynamic_templates")


@pytest.mark.parametrize(
    ("mutate", "expected_check"),
    [
        (
            lambda inventory: inventory["indices"].update(
                {"howler-alpha_new": inventory["indices"]["howler-alpha_hot"]}
            ),
            "baseline_unexpected_indices",
        ),
        (lambda inventory: inventory["indices"]["howler-alpha_hot"].update(uuid="changed"), "baseline_uuid"),
        (
            lambda inventory: inventory["indices"]["howler-alpha_hot"]["aliases"].update(
                {"other-alias": {"is_write_index": True}}
            ),
            "baseline_aliases",
        ),
        (
            lambda inventory: inventory["indices"]["howler-alpha_hot"]["aliases"]["howler-alpha"].update(
                {"is_write_index": True}
            ),
            "baseline_aliases",
        ),
        (
            lambda inventory: (
                inventory["indices"]["howler-alpha_hot"].update(doc_count=5),
                inventory["indices"]["howler-alpha_hot"]["primary_shards"]["0"].update(doc_count=5),
            ),
            "baseline_doc_count",
        ),
    ],
)
def test_baseline_set_uuid_alias_and_count_drift_block(mutate: Any, expected_check: str) -> None:
    before = _inventory()
    current = _inventory()
    mutate(current)

    report = _checks(current, baseline=_baseline(before))

    assert _blockers(report, expected_check)


def test_baseline_alias_filter_or_routing_drift_blocks() -> None:
    before = _inventory()
    before["indices"]["howler-alpha_hot"]["aliases"]["howler-alpha"] = {"filter": {"term": {"kind": "approved"}}}
    current = deepcopy(before)
    current["indices"]["howler-alpha_hot"]["aliases"]["howler-alpha"]["filter"] = {"term": {"kind": "different"}}

    report = _checks(current, baseline=_baseline(before), integrity_only=True)

    assert _blockers(report, "baseline_aliases")


def test_baseline_missing_index_blocks() -> None:
    before = _inventory()
    current = _inventory()
    current["indices"] = {}

    report = _checks(current, baseline=_baseline(before))

    assert _blockers(report, "baseline_index_missing")


def test_baseline_plus_one_max_sequence_number_blocks() -> None:
    before = _inventory()
    current = _inventory()
    current["indices"]["howler-alpha_hot"]["primary_shards"]["0"].update(
        max_seq_no=4,
        global_checkpoint=4,
    )

    report = _checks(current, baseline=_baseline(before), integrity_only=True)

    assert _blockers(report, "baseline_sequence_numbers")


def test_baseline_max_sequence_decrease_blocks_even_when_explicitly_accepted() -> None:
    before = _inventory()
    current = _inventory()
    current["indices"]["howler-alpha_hot"]["primary_shards"]["0"].update(max_seq_no=2, global_checkpoint=2)

    report = _checks(
        current,
        baseline=_baseline(before),
        integrity_only=True,
        accepted_sequence_drift={"howler-alpha_hot"},
    )

    assert _blockers(report, "baseline_sequence_decrease")


def test_unsynced_primary_checkpoint_blocks_verification() -> None:
    before = _inventory()
    current = _inventory()
    current["indices"]["howler-alpha_hot"]["primary_shards"]["0"]["global_checkpoint"] = 2

    report = _checks(current, baseline=_baseline(before), integrity_only=True)

    assert _blockers(report, "sequence_checkpoint_unsynced")


def test_unsynced_baseline_checkpoint_blocks_with_recapture_guidance() -> None:
    before = _inventory()
    before["indices"]["howler-alpha_hot"]["primary_shards"]["0"]["global_checkpoint"] = 2
    current = _inventory()

    report = _checks(current, baseline=_baseline(before), integrity_only=True)

    blocker = next(item for item in report["blockers"] if item["check"] == "sequence_checkpoint_unsynced")
    assert "capture a new baseline" in blocker["message"]


def test_explicit_sequence_drift_acceptance_warns_and_records_per_shard_changes() -> None:
    before = _inventory()
    current = _inventory()
    current["indices"]["howler-alpha_hot"]["primary_shards"]["0"].update(
        doc_count=5,
        max_seq_no=4,
        global_checkpoint=4,
    )
    current["indices"]["howler-alpha_hot"]["doc_count"] = 5

    report = _checks(
        current,
        baseline=_baseline(before),
        integrity_only=True,
        accepted_sequence_drift={"howler-alpha_hot"},
    )

    assert report["ready"] is True
    assert not _blockers(report, "baseline_sequence_numbers")
    assert report["warnings"] == [
        {
            "check": "baseline_sequence_drift_accepted",
            "index": "howler-alpha_hot",
            "shards": {
                "0": {
                    "baseline": {"doc_count": 4, "max_seq_no": 3},
                    "current": {"doc_count": 5, "max_seq_no": 4},
                }
            },
            "message": (
                "The cutover lead explicitly accepted primary document-count/max_seq_no drift for this index; "
                "record the decision in the change record."
            ),
        }
    ]


def test_unknown_sequence_drift_acceptance_is_ignored_with_warning() -> None:
    inventory = _inventory()

    report = _checks(
        inventory,
        baseline=_baseline(inventory),
        integrity_only=True,
        accepted_sequence_drift={"howler-does-not-exist_hot"},
    )

    assert report["ready"] is True
    assert report["warnings"] == [
        {
            "check": "unknown_sequence_drift_acceptance",
            "index": "howler-does-not-exist_hot",
            "message": "No baseline/current index pair matched this acceptance; no drift was accepted.",
        }
    ]


def test_baseline_allows_one_empty_new_ilm_generation_with_write_alias_swap() -> None:
    before = _inventory(ilm=True)
    current = deepcopy(before)
    old_index = "howler-alpha-000002"
    new_index = "howler-alpha-000003"
    current["indices"][old_index]["aliases"]["howler-alpha"]["is_write_index"] = False
    current["indices"][new_index] = {
        "aliases": {"howler-alpha": {"is_write_index": True}},
        "doc_count": 0,
        "primary_shards": {"0": {"doc_count": 0, "max_seq_no": -1, "global_checkpoint": -1}},
        "settings": {"index.uuid": "new", "index.mapping.total_fields.limit": "1600"},
        "uuid": "new",
    }

    report = _checks(current, ilm=True, baseline=_baseline(before), integrity_only=True)

    assert report["ready"] is True
    assert [warning["check"] for warning in report["warnings"]] == ["baseline_ilm_rollover"]


def test_baseline_allows_empty_new_configured_collection() -> None:
    before = _inventory()
    before["indices"].pop("howler-alpha_hot")
    before["indices"]["howler-beta_hot"] = {
        "aliases": {"howler-beta": {}},
        "doc_count": 0,
        "primary_shards": {"0": {"doc_count": 0, "max_seq_no": -1, "global_checkpoint": -1}},
        "uuid": "beta",
    }
    current = deepcopy(before)
    current["indices"]["howler-alpha_hot"] = {
        "aliases": {"howler-alpha": {}},
        "doc_count": 0,
        "primary_shards": {"0": {"doc_count": 0, "max_seq_no": -1, "global_checkpoint": -1}},
        "uuid": "alpha",
    }

    report = _checks(current, baseline=_baseline(before), integrity_only=True)

    assert report["ready"] is True
    assert report["warnings"] == [
        {
            "check": "baseline_new_empty_collection",
            "collection": "alpha",
            "indices": ["howler-alpha_hot"],
            "message": "A configured collection absent from the baseline was initialized empty after it.",
        }
    ]


def test_baseline_blocks_multiple_new_ilm_generations_for_uninitialized_collection() -> None:
    before = _inventory(ilm=True)
    before["indices"] = {
        "howler-beta_hot": {
            "aliases": {"howler-beta": {}},
            "doc_count": 1,
            "primary_shards": {"0": {"doc_count": 1, "max_seq_no": 0, "global_checkpoint": 0}},
            "uuid": "beta",
        }
    }
    current = deepcopy(before)
    current["indices"].update(
        {
            "howler-alpha-000001": {
                "aliases": {"howler-alpha": {"is_write_index": False}},
                "doc_count": 0,
                "primary_shards": {"0": {"doc_count": 0, "max_seq_no": -1, "global_checkpoint": -1}},
                "uuid": "alpha-1",
            },
            "howler-alpha-000002": {
                "aliases": {"howler-alpha": {"is_write_index": True}},
                "doc_count": 0,
                "primary_shards": {"0": {"doc_count": 0, "max_seq_no": -1, "global_checkpoint": -1}},
                "uuid": "alpha-2",
            },
        }
    )

    report = _checks(current, ilm=True, baseline=_baseline(before), integrity_only=True)

    assert _blockers(report, "baseline_new_collection_layout")


def test_closed_indices_block_for_configured_or_baseline_and_warn_otherwise() -> None:
    configured_closed = _inventory()
    configured_closed["indices"]["howler-alpha_hot"]["status"] = "close"
    configured_closed["indices"]["howler-alpha_hot"]["primary_shards"] = {}
    configured_report = _checks(configured_closed)
    assert _blockers(configured_report, "closed_howler_index")

    unrelated_closed = _inventory()
    unrelated_closed["indices"]["howler-archive_closed"] = {
        "aliases": {},
        "settings": {"index.uuid": "archive-uuid"},
        "status": "close",
        "uuid": "archive-uuid",
    }
    unrelated_report = _checks(unrelated_closed)
    assert unrelated_report["ready"] is True
    assert any(
        warning["check"] == "closed_howler_index" and warning["index"] == "howler-archive_closed"
        for warning in unrelated_report["warnings"]
    )

    baseline = _inventory()
    baseline["indices"]["howler-archive_closed"] = {
        "aliases": {},
        "settings": {"index.uuid": "archive-uuid"},
        "status": "close",
        "uuid": "archive-uuid",
    }
    baseline_report = _checks(
        deepcopy(baseline),
        baseline=_baseline(baseline),
        integrity_only=True,
    )
    assert _blockers(baseline_report, "closed_howler_index")


def test_baseline_rejects_new_unconfigured_prefix_index() -> None:
    before = _inventory()
    current = _inventory()
    current["indices"]["howler-rogue_hot"] = {
        "aliases": {"howler-rogue": {}},
        "doc_count": 0,
        "primary_shards": {"0": {"doc_count": 0, "max_seq_no": -1, "global_checkpoint": -1}},
        "uuid": "rogue",
    }

    report = _checks(current, baseline=_baseline(before), integrity_only=True)

    assert _blockers(report, "baseline_unexpected_indices")


def test_baseline_allows_new_closed_unconfigured_prefix_index() -> None:
    before = _inventory()
    current = deepcopy(before)
    current["indices"]["howler-archive_closed"] = {
        "aliases": {},
        "settings": {"index.uuid": "archive-uuid"},
        "status": "close",
        "uuid": "archive-uuid",
    }

    report = _checks(current, baseline=_baseline(before), integrity_only=True)

    assert report["ready"] is True
    assert not _blockers(report, "baseline_unexpected_indices")
    assert any(
        warning["check"] == "closed_howler_index" and warning["index"] == "howler-archive_closed"
        for warning in report["warnings"]
    )


def test_baseline_without_prefix_indices_and_missing_metrics_block() -> None:
    inventory = _inventory()
    no_prefix = {"index_prefix": "howler", "inventory": {"indices": {"unrelated": {}}}}
    report = _checks(inventory, baseline=no_prefix, integrity_only=True)
    assert _blockers(report, "baseline_no_prefix_indices")

    before = _inventory()
    before["indices"]["howler-alpha_hot"]["uuid"] = None
    before["indices"]["howler-alpha_hot"]["doc_count"] = None
    missing_metrics = _checks(inventory, baseline=_baseline(before), integrity_only=True)
    assert _blockers(missing_metrics, "baseline_uuid")
    assert _blockers(missing_metrics, "baseline_doc_count")


def test_baseline_comparison_blocks_prefix_mismatch_even_when_names_overlap() -> None:
    inventory = _inventory()
    baseline = _baseline(inventory)
    baseline["index_prefix"] = "howler-prod"

    report = _checks(inventory, baseline=baseline, integrity_only=True)

    blocker = next(item for item in report["blockers"] if item["check"] == "baseline_index_prefix")
    assert blocker["expected"] == "howler"
    assert blocker["actual"] == "howler-prod"


def test_baseline_reader_requires_clean_819_report(tmp_path) -> None:
    import argparse
    import json

    parser = argparse.ArgumentParser()
    baseline_path = tmp_path / "baseline.json"
    invalid = {
        "index_prefix": "howler",
        "source_stack_version": "8.18.7",
        "checks": {"ready": False},
        "inventory": {"indices": {}, "version": {"version": {"number": "8.18.7"}}},
    }
    baseline_path.write_text(json.dumps(invalid), encoding="utf-8")

    with pytest.raises(SystemExit):
        _read_baseline(baseline_path, parser)


class _Response(io.BytesIO):
    pass


class _Opener:
    def __init__(self, response: bytes = b'{"ok":true}') -> None:
        self.response = response
        self.requests: list[tuple[Any, int]] = []

    def open(self, request: Any, timeout: int) -> _Response:
        self.requests.append((request, timeout))
        return _Response(self.response)


def test_primary_stats_use_one_scoped_shard_stats_request() -> None:
    class StatsClient:
        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any] | None]] = []

        def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            self.calls.append((path, params))
            return {
                "indices": {
                    "howler-hit_hot": {
                        "primaries": {"docs": {"count": 1}},
                        "shards": {
                            "0": [
                                {
                                    "routing": {"primary": True, "shard": 0},
                                    "docs": {"count": 1},
                                    "seq_no": {"max_seq_no": 2, "global_checkpoint": 2},
                                },
                                {
                                    "routing": {"primary": False, "shard": 0},
                                    "docs": {"count": 1},
                                    "seq_no": {"max_seq_no": 2, "global_checkpoint": 2},
                                },
                            ]
                        },
                    }
                }
            }

    client = StatsClient()
    stats = collect_primary_shard_stats(client, "howler")  # type: ignore[arg-type]

    assert client.calls == [
        (
            "/howler-*/_stats",
            {"level": "shards", "allow_no_indices": "true", "expand_wildcards": "open"},
        )
    ]
    assert stats["howler-hit_hot"] == {
        "doc_count": 1,
        "primary_shards": {"0": {"doc_count": 1, "max_seq_no": 2, "global_checkpoint": 2}},
    }


def test_rest_client_sends_plain_json_headers_and_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    opener = _Opener()
    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: opener)
    client = ElasticsearchRestClient("https://example.invalid/es", api_key="secret-token", timeout=7)

    assert client.get("/cluster/health") == {"ok": True}

    request, timeout = opener.requests[0]
    assert request.method == "GET"
    assert request.get_header("Accept") == "application/json"
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header("Authorization") == "ApiKey secret-token"
    assert request.full_url == "https://example.invalid/es/cluster/health"
    assert timeout == 7


def test_rest_client_basic_auth_header_and_credentials_validation() -> None:
    opener = _Opener()
    client = ElasticsearchRestClient(
        "http://example.invalid",
        username="alice",
        password="p@ss",
        allow_insecure_http_auth=True,
    )
    # Replace the opener after construction to avoid making any network requests.
    client._opener = opener  # noqa: SLF001
    client.get("/")
    request, _ = opener.requests[0]

    assert request.get_header("Authorization") == "Basic " + base64.b64encode(b"alice:p@ss").decode()
    with pytest.raises(ValueError, match="must be set together"):
        ElasticsearchRestClient("http://example.invalid", username="alice")
    with pytest.raises(ValueError, match="either ELASTIC_API_KEY"):
        ElasticsearchRestClient("http://example.invalid", api_key="k", username="alice", password="p")
    with pytest.raises(ValueError, match="not the URL"):
        ElasticsearchRestClient("http://alice:p%40ss@example.invalid")


def test_rest_client_refuses_cleartext_auth_unless_explicitly_allowed() -> None:
    with pytest.raises(ValueError, match="credentials over HTTP"):
        ElasticsearchRestClient("http://example.invalid", api_key="key")

    assert ElasticsearchRestClient("http://example.invalid", api_key="key", allow_insecure_http_auth=True)


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
def test_rest_client_refuses_all_mutating_methods(method: str) -> None:
    client = ElasticsearchRestClient("http://example.invalid")

    with pytest.raises(ValueError, match="refuses HTTP method"):
        client.request(method, "/_cluster/settings")


def test_rest_client_only_allows_host_relative_absolute_paths() -> None:
    client = ElasticsearchRestClient("http://example.invalid")

    with pytest.raises(ValueError, match="absolute paths"):
        client.get("_cluster/health")
    with pytest.raises(ValueError, match="absolute paths"):
        client.get("//evil.example/path")
    with pytest.raises(ValueError, match="absolute paths"):
        client.get("/secure?credential=never-log-this")


def test_credentials_from_environment_validates_supported_auth_options(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELASTIC_API_KEY", raising=False)
    monkeypatch.delenv("ELASTIC_USERNAME", raising=False)
    monkeypatch.delenv("ELASTIC_PASSWORD", raising=False)
    assert credentials_from_environment() == {}
    monkeypatch.setenv("ELASTIC_USERNAME", "alice")
    with pytest.raises(ValueError, match="must be set together"):
        credentials_from_environment()
    monkeypatch.setenv("ELASTIC_PASSWORD", "secret")
    assert credentials_from_environment() == {"username": "alice", "password": "secret"}
    monkeypatch.setenv("ELASTIC_API_KEY", "key")
    with pytest.raises(ValueError, match="either ELASTIC_API_KEY"):
        credentials_from_environment()


def test_rest_errors_do_not_include_auth_headers_or_url_userinfo(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailedOpener:
        def open(self, request: Any, timeout: int) -> None:
            raise urllib.error.HTTPError(
                request.full_url,
                403,
                "denied",
                {},
                io.BytesIO(b'{"error":{"type":"security_exception","reason":"denied never-log-this"}}'),
            )

    monkeypatch.setattr("urllib.request.build_opener", lambda *handlers: FailedOpener())
    client = ElasticsearchRestClient("https://example.invalid", api_key="never-log-this")

    with pytest.raises(ElasticsearchRestError) as error:
        client.get("/secure")

    assert "never-log-this" not in str(error.value)
    assert "HTTP 403" in str(error.value)
    assert error.value.status == 403
    assert error.value.error_type == "security_exception"
    assert error.value.reason == "denied [redacted]"


def test_redirect_handler_refuses_to_forward_credentials() -> None:
    handler = _NoRedirectHandler()
    request = urllib.request.Request("https://example.invalid/source")

    assert handler.redirect_request(request, None, 307, "temporary redirect", {}, "https://other.invalid/") is None


def test_rest_client_does_not_follow_redirect_or_forward_credentials() -> None:
    class RedirectServer(HTTPServer):
        requests: list[tuple[str, str | None]]

        def __init__(self) -> None:
            super().__init__(("127.0.0.1", 0), RedirectHandler)
            self.requests = []

    class RedirectHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.server.requests.append((self.path, self.headers.get("Authorization")))  # type: ignore[attr-defined]
            self.send_response(302)
            self.send_header("Location", "/credential-target")
            self.end_headers()

        def log_message(self, format: str, *args: Any) -> None:
            return

    server = RedirectServer()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    client = ElasticsearchRestClient(
        f"http://127.0.0.1:{server.server_port}",
        api_key="redirect-secret",
        allow_insecure_http_auth=True,
    )
    try:
        with pytest.raises(ElasticsearchRestError) as error:
            client.get("/source")
        assert error.value.status == 302
        assert server.requests == [("/source", "ApiKey redirect-secret")]
    finally:
        server.shutdown()
        thread.join()
        server.server_close()
