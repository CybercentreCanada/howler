"""Collect and evaluate the Elasticsearch 8.19 to 9.x upgrade preflight."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import quote

from howler.external.elasticsearch_rest import (
    HOWLER_COLLECTION_NAMES,
    ElasticsearchRestClient,
    ElasticsearchRestError,
    collect_primary_shard_stats,
    credentials_from_environment,
    primary_shard_sync_issues,
)

SOURCE_STACK_VERSION = "8.19.11"
NO_MIGRATION_NEEDED = "NO_MIGRATION_NEEDED"


def _index_prefix() -> str:
    """Return the same index prefix selected by the Howler runtime."""
    return os.environ.get("HWL_DATASTORE_INDEX_PREFIX", os.environ.get("APP_NAME", "howler"))


def _mapping_settings(index_data: dict[str, Any]) -> dict[str, Any]:
    settings = index_data.get("settings", {})
    nested = settings.get("index", {})
    return {**nested, **settings} if isinstance(nested, dict) else settings


def _is_closed(index_data: dict[str, Any]) -> bool:
    return str(index_data.get("status", "")).lower() in {"close", "closed"}


def _backs_configured_collection(index: str, index_data: dict[str, Any], prefix: str) -> bool:
    aliases = index_data.get("aliases", {})
    if not isinstance(aliases, dict):
        aliases = {}
    for collection in HOWLER_COLLECTION_NAMES:
        alias = f"{prefix}-{collection}"
        if alias in aliases or index == f"{alias}_hot" or re.fullmatch(rf"{re.escape(alias)}-\d{{6}}", index):
            return True
    return False


def collect_inventory(client: ElasticsearchRestClient) -> dict[str, Any]:
    """Collect upgrade state using plain, read-only REST requests."""
    prefix = _index_prefix()
    indices = client.get(
        "/*",
        {
            "features": "aliases,settings",
            "flat_settings": "true",
            "expand_wildcards": "all",
            "allow_no_indices": "true",
        },
    )
    catalog_rows = client.get(
        "/_cat/indices",
        {
            "format": "json",
            "h": "index,health,status,docs.count",
            "expand_wildcards": "all",
        },
    )
    stats = collect_primary_shard_stats(client, prefix)
    catalog = {row.get("index"): row for row in catalog_rows if row.get("index")}
    health = client.get("/_cluster/health", {"level": "indices"})
    index_health = health.get("indices", {})
    for name, index_data in indices.items():
        row = catalog.get(name, {})
        index_stats = stats.get(name, {})
        settings = _mapping_settings(index_data)
        index_data["uuid"] = settings.get("index.uuid") or settings.get("uuid") or index_data.get("uuid")
        index_data["doc_count"] = index_stats.get("doc_count")
        index_data["primary_shards"] = index_stats.get("primary_shards", {})
        index_data["health"] = index_health.get(name, {}).get("status", row.get("health"))
        index_data["status"] = row.get("status")

    try:
        ilm_explain = client.get(
            f"/{quote(prefix, safe='-_.')}-*/_ilm/explain",
            {"only_managed": "false"},
        )
    except ElasticsearchRestError as error:
        if error.status != 404:
            raise
        ilm_explain = {}

    return {
        "cluster_health": health,
        "cluster_settings": client.get("/_cluster/settings", {"flat_settings": "true", "include_defaults": "true"}),
        "component_templates": client.get("/_component_template/*"),
        "deprecations": client.get("/_migration/deprecations"),
        "feature_upgrade_status": client.get("/_migration/system_features"),
        "ilm_explain": ilm_explain,
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


def _deprecation_issues(value: Any, path: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    issues = []
    if isinstance(value, dict):
        if isinstance(value.get("level"), str) and isinstance(value.get("message"), str):
            issues.append(
                {
                    "level": value["level"],
                    "message": value["message"],
                    "path": ".".join(path),
                    "url": value.get("url"),
                }
            )
        for key, child in value.items():
            issues.extend(_deprecation_issues(child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(_deprecation_issues(child, (*path, str(index))))
    return issues


def _index_creation_major(index_data: dict[str, Any]) -> int | None:
    settings = index_data.get("settings", {})
    version = settings.get("index.version.created")
    if version is None:
        version = settings.get("index", {}).get("version", {}).get("created")
    if version is None:
        return None

    version_string = str(version)
    if "." in version_string:
        major, _, _ = version_string.partition(".")
        return int(major)
    return int(version_string) // 1_000_000


def evaluate_inventory(  # noqa: C901
    inventory: dict[str, Any], *, baseline_capture: bool = False
) -> dict[str, Any]:
    """Return deterministic blockers and warnings for a collected inventory."""
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    version = inventory["version"].get("version", {}).get("number")
    if version != SOURCE_STACK_VERSION:
        blockers.append(
            {
                "check": "source_version",
                "message": f"Expected Elasticsearch {SOURCE_STACK_VERSION}, found {version or 'unknown'}.",
            }
        )

    health = inventory["cluster_health"].get("status")
    if health not in {"green", "yellow"}:
        blockers.append(
            {
                "check": "cluster_health",
                "message": f"Cluster health must be green or yellow, found {health or 'unknown'}.",
            }
        )

    deprecations = _deprecation_issues(inventory["deprecations"])
    critical_deprecations = [issue for issue in deprecations if issue["level"] == "critical"]
    if critical_deprecations:
        blockers.append(
            {
                "check": "critical_deprecations",
                "message": f"Resolve {len(critical_deprecations)} critical deprecation(s).",
                "resources": [issue["path"] for issue in critical_deprecations],
            }
        )

    feature_status = inventory["feature_upgrade_status"].get("migration_status")
    if feature_status != NO_MIGRATION_NEEDED:
        blockers.append(
            {
                "check": "system_features",
                "message": f"System feature migration status is {feature_status or 'unknown'}.",
            }
        )

    index_creation_majors = {
        index: _index_creation_major(index_data) for index, index_data in inventory["indices"].items()
    }
    pre_8_indices = sorted(index for index, major in index_creation_majors.items() if major is not None and major < 8)
    if pre_8_indices:
        blockers.append(
            {
                "check": "index_creation_versions",
                "message": f"Reindex, delete, or archive {len(pre_8_indices)} pre-8.0 index(es).",
                "resources": pre_8_indices,
            }
        )
    unknown_index_versions = sorted(index for index, major in index_creation_majors.items() if major is None)
    if unknown_index_versions:
        blockers.append(
            {
                "check": "unknown_index_creation_versions",
                "message": f"Determine the creation version of {len(unknown_index_versions)} index(es).",
                "resources": unknown_index_versions,
            }
        )

    prefix = inventory.get("index_prefix", _index_prefix())
    sequence_sync_issues = {
        index: primary_shard_sync_issues(index_data.get("primary_shards"))
        for index, index_data in inventory["indices"].items()
        if index.startswith(f"{prefix}-") and not _is_closed(index_data)
    }
    sequence_sync_issues = {index: issues for index, issues in sequence_sync_issues.items() if issues}
    if sequence_sync_issues:
        finding = {
            "check": "primary_sequence_sync",
            "message": (
                "Howler primary shard statistics are incomplete or unsynced. Quiesce writers, flush, wait for "
                "global checkpoints to catch up, and rerun the preflight with --baseline-capture."
            ),
            "resources": sequence_sync_issues,
        }
        (blockers if baseline_capture else warnings).append(finding)

    for index, index_data in sorted(inventory["indices"].items()):
        if not index.startswith(f"{prefix}-") or not _is_closed(index_data):
            continue
        finding = {
            "check": "closed_howler_index",
            "index": index,
            "message": "Closed Howler-prefixed indices are not covered by the open-index statistics snapshot.",
        }
        if baseline_capture or _backs_configured_collection(index, index_data, prefix):
            finding["message"] = (
                "A closed Howler index backs a configured collection or is being included in the baseline; "
                "reopen or archive it before cutover."
            )
            blockers.append(finding)
        else:
            finding["message"] = (
                "Closed Howler-prefixed index is not a configured collection; review and disposition it."
            )
            warnings.append(finding)

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


def _client_from_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> ElasticsearchRestClient:
    try:
        credentials = credentials_from_environment()
        return ElasticsearchRestClient(
            args.url,
            **credentials,
            ca_certs=args.ca_certs,
            insecure=args.insecure,
            timeout=args.timeout,
            allow_insecure_http_auth=args.allow_insecure_http_auth,
        )
    except ValueError as error:
        parser.error(str(error))
        raise AssertionError("argparse parser.error must exit")  # pragma: no cover


def main() -> int:
    """Run the Elasticsearch 9 upgrade preflight."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"),
        help="Elasticsearch URL. Defaults to ELASTICSEARCH_URL or http://localhost:9200.",
    )
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path instead of stdout.")
    parser.add_argument(
        "--baseline-capture",
        action="store_true",
        help="Require synced Howler primary checkpoints before producing a cutover baseline.",
    )
    tls = parser.add_mutually_exclusive_group()
    tls.add_argument("--ca-certs", type=Path, help="Certificate authority bundle for TLS verification.")
    tls.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification.")
    parser.add_argument(
        "--allow-insecure-http-auth",
        action="store_true",
        help="Explicitly allow sending credentials over plain HTTP (not recommended).",
    )
    parser.add_argument("--timeout", type=int, default=60, help="Request timeout in seconds.")
    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error("--timeout must be a positive number of seconds.")

    client = _client_from_args(args, parser)
    try:
        report = build_report(client, baseline_capture=args.baseline_capture)
    except ElasticsearchRestError as error:
        parser.error(str(error))
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")  # noqa: T201

    return 0 if report["checks"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
