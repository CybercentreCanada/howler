"""Collect and evaluate the Elasticsearch 8.19 to 9.x upgrade preflight."""

from __future__ import annotations

import argparse
import os
from typing import Any
from urllib.parse import quote

from howler.external.elasticsearch_rest import (
    NO_MIGRATION_NEEDED,
    SOURCE_STACK_VERSION,
    ElasticsearchRestClient,
    ElasticsearchRestError,
    add_connection_arguments,
    add_issue,
    canonical_ilm_generation,
    client_from_args,
    collect_index_inventory,
    index_setting,
    is_closed_index,
    primary_shard_sync_issues,
    walk_deprecations,
    write_json_report,
)

HOWLER_COLLECTION_NAMES = (
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
)


def _index_prefix() -> str:
    return os.environ.get("HWL_DATASTORE_INDEX_PREFIX", os.environ.get("APP_NAME", "howler"))


def _backs_configured_collection(index: str, index_data: dict[str, Any], prefix: str) -> bool:
    aliases = index_data.get("aliases")
    alias_map = aliases if isinstance(aliases, dict) else {}
    return any(
        (alias := f"{prefix}-{collection}") in alias_map
        or index == f"{alias}_hot"
        or canonical_ilm_generation(alias, index) is not None
        for collection in HOWLER_COLLECTION_NAMES
    )


def collect_inventory(client: ElasticsearchRestClient) -> dict[str, Any]:
    """Collect upgrade state using plain, read-only REST requests."""
    prefix = _index_prefix()
    indices = collect_index_inventory(client, prefix, scoped=False)
    health = client.get("/_cluster/health", {"level": "indices"})
    index_health = health.get("indices", {})
    for name, index_data in indices.items():
        index_data["health"] = index_health.get(name, {}).get("status", index_data.get("health"))

    return {
        "cluster_health": health,
        "cluster_settings": client.get("/_cluster/settings", {"flat_settings": "true", "include_defaults": "true"}),
        "component_templates": client.get("/_component_template/*"),
        "deprecations": client.get("/_migration/deprecations"),
        "feature_upgrade_status": client.get("/_migration/system_features"),
        "ilm_explain": (
            client.get_optional(f"/{quote(prefix, safe='-_.')}-*/_ilm/explain", {"only_managed": "false"}) or {}
        ),
        "ilm_policies": client.get("/_ilm/policy/*"),
        "index_templates": client.get("/_index_template/*"),
        "indices": indices,
        "index_prefix": prefix,
        "ingest_pipelines": client.get("/_ingest/pipeline/*"),
        "legacy_templates": client.get("/_template/*"),
        "nodes": client.get(
            "/_nodes",
            {
                "flat_settings": "true",
                "filter_path": "nodes.*.name,nodes.*.version,nodes.*.roles,nodes.*.settings,nodes.*.plugins",
            },
        ),
        "remote_clusters": client.get("/_remote/info"),
        "snapshot_repositories": client.get("/_snapshot/*"),
        "version": client.get("/"),
    }


def _deprecation_issues(value: Any) -> list[dict[str, Any]]:
    return [
        {"level": issue["level"], "message": issue["message"], "path": ".".join(path), "url": issue.get("url")}
        for path, issue in walk_deprecations(value)
        if isinstance(issue.get("message"), str)
    ]


def _index_creation_major(index_data: dict[str, Any]) -> int | None:
    version = index_setting(index_data, "index.version.created")
    if version is None:
        return None
    version_string = str(version)
    return int(version_string.partition(".")[0]) if "." in version_string else int(version_string) // 1_000_000


def _check_closed_and_sync_indices(
    inventory: dict[str, Any],
    prefix: str,
    baseline_capture: bool,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    sync_issues = {
        index: issues
        for index, data in inventory["indices"].items()
        if index.startswith(f"{prefix}-") and not is_closed_index(data) and (issues := primary_shard_sync_issues(data))
    }
    if sync_issues:
        add_issue(
            blockers if baseline_capture else warnings,
            "primary_sequence_sync",
            "Howler primary shard statistics are incomplete or unsynced. Quiesce writers, flush, wait for "
            "global checkpoints to catch up, and rerun the preflight with --baseline-capture.",
            resources=sync_issues,
        )

    for index, index_data in sorted(inventory["indices"].items()):
        if not index.startswith(f"{prefix}-") or not is_closed_index(index_data):
            continue
        if baseline_capture or _backs_configured_collection(index, index_data, prefix):
            add_issue(
                blockers,
                "closed_howler_index",
                "A closed Howler index backs a configured collection or is being included in the baseline; "
                "reopen or archive it before cutover.",
                index=index,
            )
        else:
            add_issue(
                warnings,
                "closed_howler_index",
                "Closed Howler-prefixed index is not a configured collection; review and disposition it.",
                index=index,
            )


def evaluate_inventory(inventory: dict[str, Any], *, baseline_capture: bool = False) -> dict[str, Any]:
    """Return deterministic blockers and warnings for a collected inventory."""
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    version = inventory["version"].get("version", {}).get("number")
    if version != SOURCE_STACK_VERSION:
        add_issue(
            blockers, "source_version", f"Expected Elasticsearch {SOURCE_STACK_VERSION}, found {version or 'unknown'}."
        )

    health = inventory["cluster_health"].get("status")
    if health not in {"green", "yellow"}:
        add_issue(blockers, "cluster_health", f"Cluster health must be green or yellow, found {health or 'unknown'}.")

    deprecations = _deprecation_issues(inventory["deprecations"])
    if critical := [issue for issue in deprecations if issue["level"] == "critical"]:
        add_issue(
            blockers,
            "critical_deprecations",
            f"Resolve {len(critical)} critical deprecation(s).",
            resources=[issue["path"] for issue in critical],
        )

    feature_status = inventory["feature_upgrade_status"].get("migration_status")
    if feature_status != NO_MIGRATION_NEEDED:
        add_issue(blockers, "system_features", f"System feature migration status is {feature_status or 'unknown'}.")

    majors = {index: _index_creation_major(data) for index, data in inventory["indices"].items()}
    pre_8_indices = sorted(index for index, major in majors.items() if major is not None and major < 8)
    if pre_8_indices:
        add_issue(
            blockers,
            "index_creation_versions",
            f"Reindex, delete, or archive {len(pre_8_indices)} pre-8.0 index(es).",
            resources=pre_8_indices,
        )
    unknown_index_versions = sorted(index for index, major in majors.items() if major is None)
    if unknown_index_versions:
        add_issue(
            blockers,
            "unknown_index_creation_versions",
            f"Determine the creation version of {len(unknown_index_versions)} index(es).",
            resources=unknown_index_versions,
        )

    _check_closed_and_sync_indices(
        inventory, inventory.get("index_prefix", _index_prefix()), baseline_capture, blockers, warnings
    )
    return {
        "blockers": blockers,
        "deprecations": deprecations,
        "pre_8_indices": pre_8_indices,
        "ready": not blockers,
        "unknown_index_versions": unknown_index_versions,
        "warnings": warnings,
    }


def build_report(client: ElasticsearchRestClient, *, baseline_capture: bool = False) -> dict[str, Any]:
    """Build the complete machine-readable upgrade preflight report."""
    inventory = collect_inventory(client)
    return {
        "baseline_capture": baseline_capture,
        "checks": evaluate_inventory(inventory, baseline_capture=baseline_capture),
        "index_prefix": inventory["index_prefix"],
        "inventory": inventory,
        "source_stack_version": SOURCE_STACK_VERSION,
    }


def main() -> int:
    """Run the Elasticsearch 9 upgrade preflight."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_connection_arguments(parser)
    parser.add_argument(
        "--baseline-capture",
        action="store_true",
        help="Require synced Howler primary checkpoints before producing a cutover baseline.",
    )
    args = parser.parse_args()

    client = client_from_args(args, parser)
    try:
        report = build_report(client, baseline_capture=args.baseline_capture)
    except ElasticsearchRestError as error:
        parser.error(str(error))
    write_json_report(report, args.output)
    return 0 if report["checks"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
