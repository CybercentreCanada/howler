from unittest.mock import MagicMock

from howler.external.elasticsearch_preflight import (
    NO_MIGRATION_NEEDED,
    SOURCE_STACK_VERSION,
    build_report,
    evaluate_inventory,
)


def _inventory() -> dict:
    return {
        "cluster_health": {"status": "green"},
        "cluster_settings": {},
        "component_templates": {},
        "deprecations": {"cluster_settings": [], "index_settings": {}, "node_settings": []},
        "feature_upgrade_status": {"features": [], "migration_status": NO_MIGRATION_NEEDED},
        "ilm_policies": {},
        "index_templates": {},
        "indices": {"howler-hit_hot": {"settings": {"index.version.created": "8191199"}}},
        "ingest_pipelines": {},
        "legacy_templates": {},
        "nodes": {},
        "remote_clusters": {},
        "snapshot_repositories": {},
        "version": {"version": {"number": SOURCE_STACK_VERSION}},
    }


def test_evaluate_inventory_accepts_clean_8_19_cluster():
    checks = evaluate_inventory(_inventory())

    assert checks == {
        "blockers": [],
        "deprecations": [],
        "pre_8_indices": [],
        "ready": True,
        "unknown_index_versions": [],
    }


def test_evaluate_inventory_reports_every_upgrade_blocker():
    inventory = _inventory()
    inventory["version"]["version"]["number"] = "8.18.7"
    inventory["cluster_health"]["status"] = "red"
    inventory["deprecations"]["index_settings"] = {
        "legacy": [
            {
                "level": "critical",
                "message": "Legacy setting is unsupported.",
                "url": "https://example.invalid/deprecation",
            }
        ]
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
            "url": "https://example.invalid/deprecation",
        }
    ]


def test_evaluate_inventory_blocks_unknown_index_creation_version():
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


def test_build_report_collects_upgrade_inventory():
    inventory = _inventory()
    client = MagicMock()
    client.info.return_value = inventory["version"]
    client.cluster.health.return_value = inventory["cluster_health"]
    client.cluster.get_settings.return_value = inventory["cluster_settings"]
    client.cluster.get_component_template.return_value = inventory["component_templates"]
    client.cluster.remote_info.return_value = inventory["remote_clusters"]
    client.migration.deprecations.return_value = inventory["deprecations"]
    client.migration.get_feature_upgrade_status.return_value = inventory["feature_upgrade_status"]
    client.ilm.get_lifecycle.return_value = inventory["ilm_policies"]
    client.indices.get_index_template.return_value = inventory["index_templates"]
    client.indices.get.return_value = inventory["indices"]
    client.indices.get_template.return_value = inventory["legacy_templates"]
    client.ingest.get_pipeline.return_value = inventory["ingest_pipelines"]
    client.nodes.info.return_value = inventory["nodes"]
    client.snapshot.get_repository.return_value = inventory["snapshot_repositories"]

    report = build_report(client)

    assert report["source_stack_version"] == SOURCE_STACK_VERSION
    assert report["inventory"] == inventory
    assert report["checks"]["ready"] is True
    client.indices.get.assert_called_once_with(
        index="*",
        allow_no_indices=True,
        expand_wildcards="all",
        features=["aliases", "settings"],
        flat_settings=True,
    )
