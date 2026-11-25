from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import urllib.error
import urllib.request
from copy import deepcopy
from typing import Any

import pytest

from howler.common import loader
from howler.common.exceptions import HowlerAttributeError
from howler.config_models import ILMIndexConfig, config
from howler.external import elasticsearch_cutover_verify as verifier
from howler.external.elasticsearch_cutover_verify import (
    _collection_indices,
    _collection_models,
    _configured_ilm_policy,
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
    canonical_ilm_generation,
    credentials_from_environment,
    index_setting,
    strict_int,
)
from howler.plugins import PLUGINS


@pytest.fixture(autouse=True)
def _stable_prefix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(loader, "DATASTORE_INDEX_PREFIX", "howler")


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


def _expectations(*, ilm: bool = False) -> dict[str, dict[str, Any]]:
    extra: dict[str, Any] = (
        {
            "ilm_policy": {
                "phases": {
                    "hot": {
                        "min_age": "0ms",
                        "actions": {"rollover": {"max_age": "30d", "max_primary_shard_size": "50gb"}},
                    }
                }
            },
            "ilm_template": {
                "settings": {
                    "index.lifecycle.name": "howler-alpha_policy",
                    "index.lifecycle.rollover_alias": "howler-alpha",
                    "index.mapping.total_fields.limit": 1600,
                },
                "mappings": _mapping(),
            },
        }
        if ilm
        else {}
    )
    return {
        "alpha": {
            "alias": "howler-alpha",
            "ilm": ilm,
            "mapping": _mapping(),
            "model": "alpha-model",
            "total_fields_limit": 1600,
            **extra,
        }
    }


def _inventory(*, ilm: bool = False) -> dict[str, Any]:
    index = "howler-alpha-000002" if ilm else "howler-alpha_hot"
    aliases = {"howler-alpha": {"is_write_index": True}} if ilm else {"howler-alpha": {}}
    settings = {"index.uuid": "alpha-uuid", "index.number_of_shards": "1", "index.mapping.total_fields.limit": "1600"}
    if ilm:
        settings.update(
            {"index.lifecycle.name": "howler-alpha_policy", "index.lifecycle.rollover_alias": "howler-alpha"}
        )
    live_mapping = _mapping()
    inv: dict[str, Any] = {
        "cluster_health": {"status": "green"},
        "deprecations": {"cluster_settings": [], "index_settings": {}, "node_settings": []},
        "feature_upgrade_status": {"features": [], "migration_status": "NO_MIGRATION_NEEDED"},
        "field_caps": {
            "alpha": {"fields": {"id": {"keyword": {"searchable": True}}, "label": {"keyword": {"searchable": True}}}}
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
        inv["ilm_explain"] = {
            index: {"managed": True, "policy": "howler-alpha_policy", "step": "complete", "step_info": {}}
        }
        inv["ilm_templates"]["alpha"] = {
            "index_patterns": ["howler-alpha-*"],
            "template": {"settings": dict(settings), "mappings": deepcopy(live_mapping)},
        }
        inv["ilm_policies"]["alpha"] = {
            "phases": {"hot": {"actions": {"rollover": {"max_age": "30d", "max_primary_shard_size": "50gb"}}}}
        }
    return inv


def _baseline(inventory: dict[str, Any]) -> dict[str, Any]:
    return {"index_prefix": "howler", "inventory": {"indices": inventory["indices"]}}


def _add_ilm_read_index(inventory: dict[str, Any], index: str) -> None:
    for key in ("indices", "mappings", "ilm_explain"):
        inventory[key][index] = deepcopy(inventory[key]["howler-alpha-000002"])
    inventory["indices"][index]["settings"]["index.uuid"] = inventory["indices"][index]["uuid"] = "older"
    inventory["indices"][index]["aliases"]["howler-alpha"]["is_write_index"] = False


def _checks(inventory: dict[str, Any], *, ilm: bool = False, **kwargs: Any) -> dict[str, Any]:
    return evaluate_inventory(inventory, _expectations(ilm=ilm), **kwargs)


def _blockers(report: dict[str, Any], check: str) -> list[dict[str, Any]]:
    return [item for item in report["blockers"] if item["check"] == check]


def test_clean_cluster_baseline_and_scoped_collection(monkeypatch: pytest.MonkeyPatch) -> None:
    inv = _inventory()
    assert _checks(inv, baseline=_baseline(inv))["ready"] is True

    class FakeRest:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.status = "open"

        def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
            self.calls.append(path)
            return {
                "/howler-*": {
                    "howler-alpha_hot": {
                        "aliases": {"howler-alpha": {}},
                        "settings": {
                            "index.uuid": "alpha-uuid",
                            "index.number_of_shards": "1",
                            "index.mapping.total_fields.limit": "1600",
                        },
                    }
                },
                "/_cat/indices/howler-*": [{"index": "howler-alpha_hot", "health": "green", "status": self.status}],
                "/howler-*/_stats": {
                    "indices": {
                        "howler-alpha_hot": {
                            "shards": {
                                "0": [
                                    {
                                        "routing": {"primary": True},
                                        "docs": {"count": 4},
                                        "seq_no": {"max_seq_no": 3, "global_checkpoint": 3},
                                    }
                                ]
                            }
                        }
                    }
                },
                "/_cluster/health": {"status": "green"},
                "/howler-*/_mapping": {"howler-alpha_hot": {"mappings": _mapping()}},
                "/howler-alpha/_field_caps": {
                    "fields": {"id": {"keyword": {"searchable": True}}, "label": {"keyword": {"searchable": True}}}
                },
                "/_migration/deprecations": {},
                "/_migration/system_features": {"migration_status": "NO_MIGRATION_NEEDED"},
                "/_nodes": {"nodes": {"node-1": {"name": "node-a", "version": "9.5.2"}}},
                "/": {"version": {"number": "9.5.2"}},
            }[path]

        def get_optional(self, path: str, params: dict[str, Any] | None = None) -> Any | None:
            return None

    monkeypatch.setattr(verifier, "_expectations", lambda: _expectations())
    client = FakeRest()
    report = build_report(client)  # type: ignore[arg-type]
    assert report["checks"]["ready"] is True and "/*" not in client.calls

    client.status = "close"
    collected = collect_inventory(client, _expectations())  # type: ignore[arg-type]
    assert "alpha" not in collected["field_caps"]

    client.status = "open"
    integrity = build_report(client, baseline=_baseline(inv), integrity_only=True)  # type: ignore[arg-type]
    assert integrity["checks"]["ready"] is True and integrity["checks"]["integrity_only"] is True


def test_cli_baseline_validation_and_safe_error_reporting(monkeypatch: pytest.MonkeyPatch, tmp_path, capsys) -> None:
    for flag in (["--integrity-only"], ["--accept-sequence-drift", "howler-user_hot"]):
        monkeypatch.setattr(sys, "argv", ["elasticsearch_cutover_verify", *flag])
        with pytest.raises(SystemExit) as err:
            main()
        assert err.value.code == 2

    valid = {
        "index_prefix": "howler",
        "baseline_capture": True,
        "source_stack_version": "8.19.11",
        "checks": {"ready": True},
        "inventory": {"indices": {"howler-alpha_hot": {}}, "version": {"version": {"number": "8.19.11"}}},
    }
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(valid), encoding="utf-8")
    assert _read_baseline(path, argparse.ArgumentParser()) == valid

    for mutate in (
        lambda b: b["inventory"].update(indices=None),
        lambda b: b["inventory"]["version"]["version"].update(number="8.18.7"),
        lambda b: b["checks"].update(ready=False),
        lambda b: b.update(source_stack_version="8.18.7"),
        lambda b: b.update(baseline_capture=False),
        lambda b: b.update(index_prefix="other"),
    ):
        bad = deepcopy(valid)
        mutate(bad)
        path.write_text(json.dumps(bad), encoding="utf-8")
        with pytest.raises(SystemExit):
            _read_baseline(path, argparse.ArgumentParser())

    out = tmp_path / "out.json"
    monkeypatch.setattr(sys, "argv", ["elasticsearch_cutover_verify", "--output", str(out)])
    monkeypatch.setattr(verifier, "client_from_args", lambda *_: object())
    monkeypatch.setattr(
        verifier, "build_report", lambda *_, **__: (_ for _ in ()).throw(HowlerAttributeError("typed model extensions"))
    )
    assert main() == 1
    assert "typed model extensions" in json.loads(out.read_text())["checks"]["blockers"][0]["message"]

    monkeypatch.setattr(verifier, "build_report", lambda *_, **__: (_ for _ in ()).throw(RuntimeError("secret-val")))
    assert main() == 1
    assert "secret-val" not in out.read_text()


def test_missing_configured_plugin_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    orig = dict(PLUGINS)
    PLUGINS.clear()
    try:
        out = tmp_path / "missing-plugin.json"
        monkeypatch.setenv("HWL_PLUGIN_DIRECTORY", str(tmp_path))
        monkeypatch.setattr(sys, "path", list(sys.path))
        monkeypatch.setattr(config.core, "plugins", {"missing-cutover-plugin"})
        monkeypatch.setattr(sys, "argv", ["elasticsearch_cutover_verify", "--output", str(out)])
        monkeypatch.setattr(verifier, "client_from_args", lambda *_: object())
        assert main() == 1
        assert "missing-cutover-plugin" in out.read_text()
    finally:
        PLUGINS.clear()
        PLUGINS.update(orig)


def test_cluster_gates_and_es10_readiness() -> None:
    for status, allow_yellow, expected in [
        ("yellow", False, "cluster_health"),
        ("yellow", True, None),
        ("red", False, "cluster_health"),
    ]:
        inv = _inventory()
        inv["cluster_health"]["status"] = status
        rep = _checks(inv, allow_yellow=allow_yellow)
        assert rep["ready"] is (expected is None)

    inv = _inventory()
    inv["version"]["version"]["number"] = "9.5.1"
    inv["nodes"]["nodes"]["node-1"]["version"] = "9.5.1"
    inv["feature_upgrade_status"]["migration_status"] = "ERROR"
    inv["deprecations"]["index_settings"] = {"howler-alpha_hot": [{"level": "critical", "message": "breaking"}]}
    rep = _checks(inv)
    assert {"cluster_version", "node_version", "system_features", "critical_deprecations"} <= {
        b["check"] for b in rep["blockers"]
    }

    inv = _inventory()
    inv["feature_upgrade_status"]["migration_status"] = "MIGRATION_NEEDED"
    inv["deprecations"]["index_settings"] = {
        "howler-alpha_hot": [
            {
                "level": "critical",
                "message": "Old index with a compatibility version < 9.0",
                "_meta": {"reindex_required": True},
            }
        ]
    }
    rep = _checks(inv)
    assert rep["ready"] is True and {w["check"] for w in rep["warnings"]} == {
        "es10_readiness_system_features",
        "es10_readiness",
    }


def test_collection_layout_mappings_templates_limits_and_ilm(monkeypatch: pytest.MonkeyPatch) -> None:
    from howler.datastore import howler_store
    from howler.models.schema_defaults import default_dynamic_templates

    monkeypatch.setattr(verifier, "_COLLECTION_MODELS", ())
    monkeypatch.setattr(verifier, "load_configured_plugins", lambda: [])
    monkeypatch.setattr(howler_store, "finalize_models", lambda _: {"hit": object(), "user_avatar": None})
    assert len(_collection_models()) == 2 and _prefix() == "howler"

    monkeypatch.setattr(config.datastore.ilm, "enabled", True)
    monkeypatch.setattr(config.datastore.ilm, "indices", {"hit": ILMIndexConfig(enabled=False)})
    assert _configured_ilm_policy("case") is not None and _configured_ilm_policy("hit") is None

    # ILM layout, explicit write index, _source, dynamic, templates, field limits, field_caps
    inv = _inventory(ilm=True)
    _add_ilm_read_index(inv, "howler-alpha-000001")
    assert _checks(inv, ilm=True)["ready"] is True

    del inv["indices"]["howler-alpha-000002"]["aliases"]["howler-alpha"]["is_write_index"]
    assert _blockers(_checks(inv, ilm=True), "ilm_write_index")

    inv = _inventory(ilm=True)
    inv["mappings"]["howler-alpha-000002"]["mappings"]["_source"] = {"enabled": False}
    inv["ilm_templates"]["alpha"]["template"]["mappings"]["_source"] = {"enabled": False}
    inv["mappings"]["howler-alpha-000002"]["mappings"]["dynamic"] = "strict"
    inv["mappings"]["howler-alpha-000002"]["mappings"]["properties"]["label"]["type"] = "text"
    inv["mappings"]["howler-alpha-000002"]["mappings"]["dynamic_templates"].insert(
        0, {"old": {"path_match": "*", "mapping": {"type": "text"}}}
    )
    inv["indices"]["howler-alpha-000002"]["settings"]["index.mapping.total_fields.limit"] = "1"
    inv["field_caps"]["alpha"]["fields"]["label"]["text"] = {"searchable": True}
    inv["ilm_explain"]["howler-alpha-000002"].update(
        managed=False, policy="bad", step="ERROR", step_info={"reason": "x"}
    )
    inv["ilm_policies"]["alpha"]["phases"]["hot"]["actions"]["rollover"]["max_primary_shard_size"] = "bad"
    checks = {b["check"] for b in _checks(inv, ilm=True)["blockers"]}
    assert {
        "mapping_source_disabled",
        "ilm_template_source_disabled",
        "mapping_dynamic",
        "mapping_property_mismatch",
        "dynamic_templates",
        "total_fields_limit",
        "field_caps_conflict",
        "ilm_managed",
        "ilm_policy",
        "ilm_step",
        "ilm_policy_phases",
    } <= checks

    # Default schema-less duplicate date template warning
    merged = _merge_dynamic_templates(deepcopy(default_dynamic_templates))
    blockers, warnings = [], []
    _template_checks(
        "user_avatar", "howler-user_avatar_hot", default_dynamic_templates, merged, blockers, warnings, schema_less=True
    )
    assert blockers == [] and any(w["check"] == "shadowed_dynamic_template_name" for w in warnings)

    # ByteSizeValue normalization
    exp = _expectations(ilm=True)
    inv = _inventory(ilm=True)
    exp["alpha"]["ilm_policy"]["phases"]["hot"]["actions"]["rollover"]["max_primary_shard_size"] = ".5gb"
    inv["ilm_policies"]["alpha"]["phases"]["hot"]["actions"]["rollover"]["max_primary_shard_size"] = "536870912b"
    assert evaluate_inventory(inv, exp)["ready"] is True


def test_baseline_comparisons_rollover_and_drift() -> None:
    before = _inventory(ilm=True)
    current = deepcopy(before)
    current["indices"]["howler-alpha-000002"]["aliases"]["howler-alpha"]["is_write_index"] = False
    current["indices"]["howler-alpha-000003"] = {
        "aliases": {"howler-alpha": {"is_write_index": True}},
        "doc_count": 0,
        "primary_shards": {"0": {"doc_count": 0, "max_seq_no": -1, "global_checkpoint": -1}},
        "settings": {"index.uuid": "new", "index.number_of_shards": "1"},
        "uuid": "new",
    }
    rep = _checks(current, ilm=True, baseline=_baseline(before), integrity_only=True)
    assert rep["ready"] is True and [w["check"] for w in rep["warnings"]] == ["baseline_ilm_rollover"]

    # Drift acceptance vs decrease
    before = _inventory()
    current = deepcopy(before)
    current["indices"]["howler-alpha_hot"]["doc_count"] = 5
    current["indices"]["howler-alpha_hot"]["primary_shards"]["0"].update(doc_count=5, max_seq_no=4, global_checkpoint=4)
    assert _blockers(_checks(current, baseline=_baseline(before), integrity_only=True), "baseline_sequence_numbers")
    accepted = _checks(
        current, baseline=_baseline(before), integrity_only=True, accepted_sequence_drift={"howler-alpha_hot"}
    )
    assert accepted["ready"] is True and accepted["warnings"][0]["check"] == "baseline_sequence_drift_accepted"

    current["indices"]["howler-alpha_hot"]["primary_shards"]["0"].update(max_seq_no=2, global_checkpoint=2)
    assert _blockers(
        _checks(current, baseline=_baseline(before), integrity_only=True, accepted_sequence_drift={"howler-alpha_hot"}),
        "baseline_sequence_decrease",
    )

    # Prefix, UUID, alias, missing index
    bad_prefix = _baseline(before)
    bad_prefix["index_prefix"] = "other"
    assert _blockers(_checks(before, baseline=bad_prefix, integrity_only=True), "baseline_index_prefix")
    assert canonical_ilm_generation("howler-hit", "howler-hit-000009") == 9
    assert _collection_indices(
        "howler-alpha", True, {"howler-alpha-000001": {"aliases": {}}, "howler-alpha-000001__reindex": {"aliases": {}}}
    )[0] == ["howler-alpha-000001"]


def test_rest_client_security_and_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Opener:
        def __init__(self, body: bytes = b'{"ok":true}') -> None:
            self.requests: list[tuple[Any, int]] = []
            self.body = body

        def open(self, request: Any, timeout: int) -> io.BytesIO:
            self.requests.append((request, timeout))
            return io.BytesIO(self.body)

    opener = _Opener()
    monkeypatch.setattr("urllib.request.build_opener", lambda *_: opener)
    client = ElasticsearchRestClient("https://example.invalid/es", api_key="secret-token", timeout=7)
    assert client.get("/cluster/health") == {"ok": True}
    req, timeout = opener.requests[0]
    assert req.get_header("Authorization") == "ApiKey secret-token" and timeout == 7

    basic = ElasticsearchRestClient(
        "http://example.invalid", username="alice", password="p@ss", allow_insecure_http_auth=True
    )
    basic._opener = opener  # noqa: SLF001
    basic.get("/")
    assert opener.requests[1][0].get_header("Authorization") == "Basic " + base64.b64encode(b"alice:p@ss").decode()

    with pytest.raises(ValueError, match="credentials over HTTP"):
        ElasticsearchRestClient("http://example.invalid", api_key="k")
    with pytest.raises(ValueError, match="refuses HTTP method"):
        client.request("POST", "/_cluster/settings")
    with pytest.raises(ValueError, match="absolute paths"):
        client.get("//evil.example/path")

    class _ErrorOpener:
        def open(self, request: Any, timeout: int) -> None:
            raise urllib.error.HTTPError(
                request.full_url, 403, "denied", {}, io.BytesIO(b'{"error":{"reason":"denied secret-token"}}')
            )

    monkeypatch.setattr("urllib.request.build_opener", lambda *_: _ErrorOpener())
    err_client = ElasticsearchRestClient("https://example.invalid", api_key="secret-token")
    with pytest.raises(ElasticsearchRestError) as err:
        err_client.get("/secure")
    assert "secret-token" not in str(err.value) and err.value.status == 403

    assert (
        _NoRedirectHandler().redirect_request(
            urllib.request.Request("https://example.invalid/a"), None, 307, "", {}, "https://other.invalid/"
        )
        is None
    )
    assert index_setting({"settings": {"index": {"lifecycle": {"name": "p"}}}}, "index.lifecycle.name") == "p"
    assert strict_int(True) is None and strict_int(3) == 3

    monkeypatch.setenv("ELASTIC_USERNAME", "u")
    monkeypatch.setenv("ELASTIC_PASSWORD", "p")
    assert credentials_from_environment() == {"username": "u", "password": "p"}
