"""Offline coverage for the frozen application-v1 cutover corpus and seed-plan API.

These tests validate fixtures with the current Pydantic models and compare collection contracts
to the independent frozen inventory. They do not import the legacy ODM or claim a live ES/API
application verification.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import bcrypt
import pytest

import howler.datastore.collection as collection_module
from build_scripts.step9_application import (
    ACCESS_FIELDS,
    APPLICATION_FIXTURE_SHA256,
    APPLICATION_FIXTURE_VERSION,
    COLLECTION_NAMES,
    DOCUMENT_COUNTS,
    FIXTURE_NAMESPACE,
    FixtureContractError,
    application_environment,
    build_seed_plan,
    load_application_fixture,
    validate_application_fixture_data,
)
from howler.config_models import Config
from howler.datastore.collection import ESCollection
from howler.datastore.howler_store import ILM_ENABLED_INDEXES, INDEXES
from howler.models.case import Case
from howler.models.hit import Hit
from howler.models.schema import build_index_contract, ilm_template_body
from howler.models.user import User

API_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = API_ROOT / "test" / "unit" / "odm" / "fixtures" / "odm_contract_inventory.json"
EXPECTED_INVENTORY_SHA256 = "6a85a3df82c548ad9d398e6af18c07927e957b2b771ac21c40faea40821add35"
MODEL_BY_COLLECTION = {"hit": Hit, "case": Case, "user": User}


def _model_input(source: dict[str, Any]) -> dict[str, Any]:
    """Remove stored-only helpers that the document model regenerates on serialization."""
    return {key: value for key, value in source.items() if key not in ACCESS_FIELDS and key != "__index"}


def test_fixture_is_versioned_from_the_unchanged_independent_inventory() -> None:
    fixture = load_application_fixture()
    inventory_bytes = INVENTORY_PATH.read_bytes()
    inventory_hash = hashlib.sha256(inventory_bytes).hexdigest()

    assert APPLICATION_FIXTURE_VERSION == "application-v1"
    assert inventory_hash == EXPECTED_INVENTORY_SHA256
    assert fixture["metadata"]["source_inventory_sha256"] == inventory_hash
    assert fixture["metadata"]["captured_from_commit"] == "3071fc4ea45d4b2dd44a7ee1646095426097d061"
    assert fixture["metadata"]["stored_document_capture"]["runtime_legacy_imports"] is False
    canonical = json.dumps(fixture, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == APPLICATION_FIXTURE_SHA256


def test_fixture_carries_all_legacy_mappings_settings_dynamic_templates_and_namespaced_aliases() -> None:
    fixture = load_application_fixture()
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))

    assert tuple(fixture["collections"]) == COLLECTION_NAMES
    for name in COLLECTION_NAMES:
        frozen = fixture["collections"][name]
        legacy = inventory["collections"][name]
        alias = f"{FIXTURE_NAMESPACE}-howler-{name}"

        assert frozen["settings"] == legacy["legacy_index"]["settings"]
        assert frozen["mappings"] == legacy["legacy_index"]["mappings"]
        assert frozen["mappings"]["dynamic_templates"] == legacy["legacy_index"]["mappings"]["dynamic_templates"]
        assert frozen["ilm_enabled_by_default"] is legacy["ilm_enabled_by_default"]
        assert frozen["alias"] == alias
        assert frozen["index_name"] == f"{alias}_hot"
        legacy_alias_body = next(iter(legacy["legacy_index"]["aliases"].values()))
        assert frozen["aliases"] == {alias: legacy_alias_body}
        assert not any(key.startswith("howler-") for key in frozen["aliases"])

        if "ilm_template" in legacy:
            expected_template = deepcopy(legacy["ilm_template"])
            expected_template["index_patterns"] = [f"{alias}-*"]
            lifecycle = expected_template["template"]["settings"]["index"]
            if "lifecycle.name" in lifecycle:
                lifecycle["lifecycle.name"] = f"{FIXTURE_NAMESPACE}-howler-{name}_policy"
            if "lifecycle.rollover_alias" in lifecycle:
                lifecycle["lifecycle.rollover_alias"] = alias
            assert frozen["historical_ilm_template"] == expected_template
        else:
            assert "historical_ilm_template" not in frozen


def test_current_pydantic_schemas_pass_full_legacy_mapping_settings_and_ilm_parity() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))

    assert set(INDEXES) == set(COLLECTION_NAMES)
    for name, model_type in INDEXES.items():
        legacy = inventory["collections"][name]
        legacy_index = legacy["legacy_index"]
        contract = build_index_contract(model_type, shards=1, replicas=0)

        assert contract.settings == legacy_index["settings"]
        assert contract.mappings == legacy_index["mappings"]
        if name in ILM_ENABLED_INDEXES:
            expected_template = ilm_template_body(
                model_type,
                shards=1,
                replicas=0,
                policy_name=f"howler-{name}_policy",
                rollover_alias=f"howler-{name}",
            )
            assert expected_template == legacy["ilm_template"]["template"]


def test_pydantic_models_validate_and_roundtrip_all_frozen_legacy_stored_outputs() -> None:
    fixture = load_application_fixture()
    for collection, model_type in MODEL_BY_COLLECTION.items():
        assert len(fixture["documents"][collection]) == DOCUMENT_COUNTS[collection]
        for entry in fixture["documents"][collection]:
            model_primitives = entry["model_primitives"]
            source = entry["source"]
            assert "__index" not in model_primitives
            assert set(ACCESS_FIELDS).issubset(model_primitives)
            assert source["id"] == entry["id"]
            model = model_type.model_validate(_model_input(model_primitives))
            serialized = model.as_primitives(hidden_fields=True)
            # Hit/Case keep the historical in-memory __index annotation; datastore source omits it.
            serialized.pop("__index", None)
            assert serialized == model_primitives
            stored_expected = deepcopy(serialized)
            stored_expected["id"] = entry["id"]
            assert source == stored_expected


def test_frozen_documents_are_deterministic_linked_and_have_real_read_only_identities() -> None:
    fixture = load_application_fixture()
    hits = fixture["documents"]["hit"]
    case = fixture["documents"]["case"][0]
    users = fixture["documents"]["user"]
    ids = {hit["id"] for hit in hits}

    assert len(ids) == 8
    assert case["model_primitives"]["items"][0]["value"] in ids
    for collection_entries in fixture["documents"].values():
        for entry in collection_entries:
            _assert_no_now_or_runtime_date(entry["model_primitives"])
            assert all(
                isinstance(entry["model_primitives"][field], list)
                for field in ACCESS_FIELDS
                if field != "__access_lvl__"
            )
            assert isinstance(entry["model_primitives"]["__access_lvl__"], int)

    assert len(users) == 2
    assert set(fixture["test_credentials"]) == {entry["id"] for entry in users}
    for entry in users:
        source = entry["source"]
        identity = fixture["test_credentials"][entry["id"]]
        assert source["uname"] == entry["id"]
        assert "admin" not in source["type"]
        api_key = source["apikeys"][identity["api_key_name"]]
        assert api_key["acl"] == ["R"]
        assert api_key["agents"] == []
        assert bcrypt.checkpw(identity["api_key_secret"].encode(), api_key["password"].encode())
        assert source["password"] != api_key["password"]
        assert all(source["password"] != other["api_key_secret"] for other in fixture["test_credentials"].values())
        assert source["password"].startswith("$2b$")
        assert "__access_lvl__:[0 TO " in source["access_control"]

    assert fixture["application_environment"]["HWL_AUTH__INTERNAL__ENABLED"] == "false"


def test_seed_plan_is_pure_and_rebinds_every_index_alias_template_and_query() -> None:
    plan = build_seed_plan("step9-unit-run-42")

    assert plan.fixture_version == APPLICATION_FIXTURE_VERSION
    assert plan.namespace == "step9-unit-run-42"
    assert plan.compatibility_validation_required is True
    assert plan.application_verification_status == "NOT_RUN"
    assert plan.environment == {
        "HWL_DATASTORE_INDEX_PREFIX": "step9-unit-run-42-howler",
        "HWL_DATASTORE__ILM__ENABLED": "false",
        "HWL_AUTH__INTERNAL__ENABLED": "false",
    }
    assert len(plan.indexes) == len(COLLECTION_NAMES) == 11
    assert len(plan.documents) == sum(DOCUMENT_COUNTS.values()) == 11
    aliases = {index.alias for index in plan.indexes}
    assert len(aliases) == 11
    assert all(alias.startswith("step9-unit-run-42-howler-") for alias in aliases)
    assert all(not alias.startswith("howler-") for alias in aliases)

    for index in plan.indexes:
        assert index.index_name == f"{index.alias}_hot"
        body = index.create_body()
        assert body["aliases"] == {index.alias: {}}
        assert set(body) == {"settings", "mappings", "aliases"}
        if index.historical_ilm_template is not None:
            assert index.historical_ilm_template["index_patterns"] == [f"{index.alias}-*"]
            assert (
                index.historical_ilm_template["template"]["settings"]["index"]["lifecycle.rollover_alias"]
                == index.alias
            )

    for document in plan.documents:
        action = document.bulk_action()
        assert action["_index"] == document.index_alias
        assert action["_source"] == document.source
        assert action["_id"] == document.document_id
        assert action["_source"]["id"] == action["_id"]
        assert not document.index_alias.startswith("howler-")
    requests = plan.query_contracts["requests"]
    assert {request["index"] for request in requests.values()} == {"step9-unit-run-42-howler-hit"}

    # Actions are fresh copies and cannot mutate the frozen source held by the plan.
    first = plan.documents[0]
    action = first.bulk_action()
    action["_source"]["test_mutation"] = True
    assert "test_mutation" not in first.source


def test_application_startup_prefix_and_ilm_contract_is_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    namespace = "step9-startup-no-net"
    expected_environment = application_environment(namespace)
    for key, value in expected_environment.items():
        monkeypatch.setenv(key, value)

    config = Config()
    assert config.datastore.ilm.enabled is False
    assert config.auth.internal.enabled is False

    # The application loader resolves this import-time variable before datastore startup. Simulate
    # that fresh-process resolution, then prohibit collection creation/network calls explicitly.
    prefix = expected_environment["HWL_DATASTORE_INDEX_PREFIX"]
    monkeypatch.setattr(collection_module, "DATASTORE_INDEX_PREFIX", prefix)
    monkeypatch.setattr(ESCollection, "IGNORE_ENSURE_COLLECTION", True)
    for collection_name, model_type in INDEXES.items():
        datastore = Mock()
        collection = ESCollection(datastore, collection_name, model_class=model_type, ilm_config=None)
        assert collection.name == f"{prefix}-{collection_name}"
        assert collection.index_name == f"{prefix}-{collection_name}_hot"
        assert collection.ilm_config is None
        datastore.assert_not_called()


@pytest.mark.parametrize("namespace", ["", "howler-danger", "step9-prod", "step9-test-*", "step9--bad", "step9-UPPER"])
def test_seed_plan_rejects_default_or_unsafe_namespaces(namespace: str) -> None:
    with pytest.raises(ValueError, match="namespace"):
        build_seed_plan(namespace)


def test_fixture_structure_rejects_default_alias_and_unverified_app_status() -> None:
    fixture = load_application_fixture()
    fixture["collections"]["hit"]["aliases"] = {"howler-hit": {}}
    with pytest.raises(FixtureContractError, match="default howler"):
        validate_application_fixture_data(fixture)

    fixture = load_application_fixture()
    fixture["application_verification"]["status"] = "PASS"
    with pytest.raises(FixtureContractError, match="NOT_RUN"):
        validate_application_fixture_data(fixture)

    fixture = load_application_fixture()
    fixture["query_contracts"]["requests"]["exact_hit_lookup"]["index"] = "howler-hit"
    with pytest.raises(FixtureContractError, match="raw query targets"):
        validate_application_fixture_data(fixture)

    fixture = load_application_fixture()
    fixture["collections"]["hit"]["historical_ilm_template"]["index_patterns"] = ["howler-hit-*"]
    with pytest.raises(FixtureContractError, match="ILM pattern"):
        validate_application_fixture_data(fixture)


@pytest.mark.parametrize("section", ["source", "credentials", "mappings", "queries"])
def test_code_pinned_artifact_hash_rejects_tampering(tmp_path: Path, section: str) -> None:
    fixture = load_application_fixture()
    if section == "source":
        fixture["documents"]["hit"][0]["source"]["message"] += " tampered"
    elif section == "credentials":
        fixture["test_credentials"]["step9-reader"]["api_key_secret"] += "-tampered"
    elif section == "mappings":
        fixture["collections"]["hit"]["mappings"]["properties"]["message"]["type"] = "text"
    else:
        fixture["query_contracts"]["requests"]["relevance"]["body"]["size"] += 1

    tampered_path = tmp_path / f"tampered-{section}.json"
    tampered_path.write_text(json.dumps(fixture), encoding="utf-8")
    with pytest.raises(FixtureContractError, match="canonical SHA-256"):
        load_application_fixture(tampered_path)


def test_fixture_rejects_unknown_keys_and_query_counts_not_derived_from_documents() -> None:
    fixture = load_application_fixture()
    fixture["unexpected_contract"] = True
    with pytest.raises(FixtureContractError, match="unknown=.*unexpected_contract"):
        validate_application_fixture_data(fixture)

    fixture = load_application_fixture()
    first_hit = fixture["documents"]["hit"][0]
    first_hit["model_primitives"]["howler"]["status"] = "on-hold"
    first_hit["source"]["howler"]["status"] = "on-hold"
    with pytest.raises(FixtureContractError, match="aggregation expectations must be derived"):
        validate_application_fixture_data(fixture)


def test_raw_es_contracts_are_frozen_but_relevance_and_application_gates_are_not_claimed() -> None:
    fixture = load_application_fixture()
    contracts = fixture["query_contracts"]
    requests = contracts["requests"]

    assert contracts["server_versions"] == {"baseline": "8.19.11", "target": "9.5.2"}
    assert set(requests) == {"default_id_search", "exact_hit_lookup", "status_aggregation", "relevance"}
    assert requests["default_id_search"]["body"]["query"] == {"query_string": {"query": "id:*"}}
    assert requests["exact_hit_lookup"]["body"]["query"] == {
        "term": {"howler.id": fixture["documents"]["hit"][0]["id"]}
    }
    assert "aggs" in requests["status_aggregation"]["body"]
    assert requests["relevance"]["body"]["track_scores"] is True
    relevance_terms = requests["relevance"]["body"]["query"]["bool"]["should"]
    assert len(relevance_terms) == 4
    assert [term["term"]["howler.analytic"]["boost"] for term in relevance_terms] == [5.0, 3.0, 2.0, 1.0]
    expected = contracts["source_derived_expectations"]
    hit_statuses = [entry["model_primitives"]["howler"]["status"] for entry in fixture["documents"]["hit"]]
    expected_buckets = [{"key": key, "doc_count": count} for key, count in sorted(Counter(hit_statuses).items())]
    assert expected["status_aggregation_buckets"] == expected_buckets
    assert expected["default_id_search_ids"] == [entry["id"] for entry in fixture["documents"]["hit"]]
    assert expected["relevance"]["capture_status"] == "NOT_CAPTURED"
    assert expected["relevance"]["baseline_es_8_19_11"] is None
    assert expected["relevance"]["target_es_9_5_2"] is None
    assert fixture["application_verification"]["status"] == "NOT_RUN"
    assert fixture["application_verification"]["must_not_be_reported_as_passed"] is True


def _assert_no_now_or_runtime_date(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            assert item != "NOW"
            if key in {"timestamp", "ingested", "created", "modified", "created_at"}:
                assert isinstance(item, str)
                assert item.startswith("2025-09-15T")
            _assert_no_now_or_runtime_date(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_now_or_runtime_date(item)
