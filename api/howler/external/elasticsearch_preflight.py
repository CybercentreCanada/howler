"""Collect and evaluate the Elasticsearch 8.19 to 9.x upgrade preflight."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from elasticsearch import Elasticsearch

SOURCE_STACK_VERSION = "8.19.11"
NO_MIGRATION_NEEDED = "NO_MIGRATION_NEEDED"


def _body(response: Any) -> Any:
    return response.body if hasattr(response, "body") else response


def collect_inventory(client: Elasticsearch) -> dict[str, Any]:
    """Collect the cluster state needed to assess an Elasticsearch 9 upgrade."""
    return {
        "cluster_health": _body(client.cluster.health()),
        "cluster_settings": _body(client.cluster.get_settings(flat_settings=True, include_defaults=True)),
        "component_templates": _body(client.cluster.get_component_template()),
        "deprecations": _body(client.migration.deprecations()),
        "feature_upgrade_status": _body(client.migration.get_feature_upgrade_status()),
        "ilm_policies": _body(client.ilm.get_lifecycle(name="*")),
        "index_templates": _body(client.indices.get_index_template(name="*")),
        "indices": _body(
            client.indices.get(
                index="*",
                allow_no_indices=True,
                expand_wildcards="all",
                features=["aliases", "settings"],
                flat_settings=True,
            )
        ),
        "ingest_pipelines": _body(client.ingest.get_pipeline(id="*")),
        "legacy_templates": _body(client.indices.get_template(name="*")),
        "nodes": _body(client.nodes.info(metric=["settings", "plugins"], flat_settings=True)),
        "remote_clusters": _body(client.cluster.remote_info()),
        "snapshot_repositories": _body(client.snapshot.get_repository(name="*")),
        "version": _body(client.info()),
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


def evaluate_inventory(inventory: dict[str, Any]) -> dict[str, Any]:
    """Return deterministic blockers and warnings for a collected inventory."""
    blockers: list[dict[str, Any]] = []
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

    return {
        "blockers": blockers,
        "deprecations": deprecations,
        "pre_8_indices": pre_8_indices,
        "ready": not blockers,
        "unknown_index_versions": unknown_index_versions,
    }


def build_report(client: Elasticsearch) -> dict[str, Any]:
    """Build the complete machine-readable upgrade preflight report."""
    inventory = collect_inventory(client)
    return {
        "checks": evaluate_inventory(inventory),
        "inventory": inventory,
        "source_stack_version": SOURCE_STACK_VERSION,
    }


def _client_from_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Elasticsearch:
    api_key = os.environ.get("ELASTIC_API_KEY")
    username = os.environ.get("ELASTIC_USERNAME")
    password = os.environ.get("ELASTIC_PASSWORD")
    if bool(username) != bool(password):
        parser.error("ELASTIC_USERNAME and ELASTIC_PASSWORD must be set together.")
    if api_key and username:
        parser.error("Use either ELASTIC_API_KEY or ELASTIC_USERNAME/ELASTIC_PASSWORD, not both.")

    options: dict[str, Any] = {
        "request_timeout": args.timeout,
        "verify_certs": not args.insecure,
    }
    if args.ca_certs:
        options["ca_certs"] = str(args.ca_certs)
    if api_key:
        options["api_key"] = api_key
    elif username and password:
        options["basic_auth"] = (username, password)
    return Elasticsearch(args.url, **options)


def main() -> int:
    """Run the Elasticsearch 9 upgrade preflight."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"),
        help="Elasticsearch URL. Defaults to ELASTICSEARCH_URL or http://localhost:9200.",
    )
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path instead of stdout.")
    parser.add_argument("--ca-certs", type=Path, help="Certificate authority bundle for TLS verification.")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification.")
    parser.add_argument("--timeout", type=int, default=60, help="Request timeout in seconds.")
    args = parser.parse_args()

    if args.timeout <= 0:
        parser.error("--timeout must be a positive number of seconds.")

    client = _client_from_args(args, parser)
    try:
        report = build_report(client)
    finally:
        client.close()

    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")

    return 0 if report["checks"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
