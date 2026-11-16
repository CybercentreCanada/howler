"""Read-only verification of the Elasticsearch 9.5.2 production cutover.

Run this module from the deployed API image with the API ConfigMap, environment,
classification files, plugin mounts, and configured Redis endpoints available.
Importing the deployed plugin/config registry initializes Howler's Redis clients;
it does not construct the Elasticsearch datastore or write Elasticsearch state.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ValidationError

from howler.common.exceptions import HowlerAttributeError, HowlerRuntimeError
from howler.external.elasticsearch_rest import (
    ElasticsearchRestClient,
    ElasticsearchRestError,
    collect_primary_shard_stats,
    credentials_from_environment,
    load_configured_plugins,
    primary_shard_sync_issues,
)

TARGET_VERSION = "9.5.2"
NO_MIGRATION_NEEDED = "NO_MIGRATION_NEEDED"
DEFAULT_TOTAL_FIELDS_LIMIT = 1000
_ILM_COLLECTIONS = frozenset({"hit", "event", "case"})
_COLLECTION_MODELS: tuple[tuple[str, type[BaseModel] | None], ...] = ()


def _collection_models() -> tuple[tuple[str, type[BaseModel] | None], ...]:  # noqa: C901
    """Load Howler's model registry and finalize enabled typed plugin extensions.

    This deliberately reproduces the pure schema-finalization portion of
    ``HowlerDatastore.__init__``. It does not construct a datastore or collection,
    create clients, or perform index/template/policy reconciliation.
    """
    global _COLLECTION_MODELS
    plugins = load_configured_plugins()
    if _COLLECTION_MODELS:
        return _COLLECTION_MODELS

    from howler.config_models import config
    from howler.models import model_extensions
    from howler.models.action import Action
    from howler.models.analytic import Analytic
    from howler.models.case import Case
    from howler.models.clue import declare_hit_extension
    from howler.models.dossier import Dossier
    from howler.models.event import Event
    from howler.models.hit import Hit
    from howler.models.migration import MigrationRecord
    from howler.models.overview import Overview
    from howler.models.template import Template
    from howler.models.user import User
    from howler.models.view import View

    model_extensions.clear()
    models: dict[str, type[BaseModel] | None] = {
        "hit": Hit,
        "event": Event,
        "case": Case,
        "template": Template,
        "overview": Overview,
        "analytic": Analytic,
        "action": Action,
        "migration": MigrationRecord,
        "user": User,
        "view": View,
        "dossier": Dossier,
        "user_avatar": None,
    }
    for plugin in plugins:
        legacy_only = {
            target
            for target in plugin.modules.odm.modify_odm
            if models.get(target) is not None and target not in plugin.modules.models.declare_extensions
        }
        if legacy_only:
            targets = ", ".join(sorted(legacy_only))
            raise ValueError(
                f"Plugin {plugin.name} uses legacy modify_odm for {targets}; add typed model extensions before cutover."
            )

    if config.core.clue.enabled:
        declare_hit_extension()
    for plugin in plugins:
        for target in models:
            if declare_extension := plugin.modules.models.declare_extensions.get(target):
                declare_extension()

    from howler.models import schema

    finalized: list[tuple[str, type[BaseModel] | None]] = []
    for name, model in models.items():
        final_model = model_extensions.finalize(model) if model is not None else None
        # Building the mapping validates extension fields without touching Elasticsearch.
        schema.document_mapping(final_model)
        finalized.append((name, final_model))

    _COLLECTION_MODELS = tuple(finalized)
    return _COLLECTION_MODELS


def _prefix() -> str:
    """Return the same configured index prefix as Howler's datastore."""
    from howler.common.loader import DATASTORE_INDEX_PREFIX

    return DATASTORE_INDEX_PREFIX


def _configured_ilm(collection: str) -> bool:
    """Resolve ILM using the same global/per-collection defaults as Howler startup."""
    from howler.config_models import ILMIndexConfig, config

    index_config = config.datastore.ilm.indices.get(collection)
    if index_config is None:
        index_config = ILMIndexConfig(enabled=collection in _ILM_COLLECTIONS)
    return bool(config.datastore.ilm.enabled and index_config.enabled)


def _expectations() -> dict[str, dict[str, Any]]:
    from howler.models import schema

    prefix = _prefix()
    contracts: dict[str, dict[str, Any]] = {}
    for collection, model in _collection_models():
        alias = f"{prefix}-{collection}"
        ilm = _configured_ilm(collection)
        contract: dict[str, Any] = {
            "alias": alias,
            "ilm": ilm,
            "mapping": schema.document_mapping(model),
            "model": model,
            "total_fields_limit": schema.total_fields_limit(model),
        }
        if ilm:
            shards, replicas = _collection_shards_replicas(collection)
            contract["ilm_template"] = schema.ilm_template_body(
                model,
                shards=shards,
                replicas=replicas,
                policy_name=f"{alias}_policy",
                rollover_alias=alias,
            )
        contracts[collection] = contract
    return contracts


def _collection_shards_replicas(collection: str) -> tuple[int, int]:
    """Resolve index sizing environment variables exactly as ESCollection does."""
    replicas = int(
        os.environ.get(f"ELASTIC_{collection.upper()}_REPLICAS", os.environ.get("ELASTIC_DEFAULT_REPLICAS", 0))
    )
    shards = int(os.environ.get(f"ELASTIC_{collection.upper()}_SHARDS", os.environ.get("ELASTIC_DEFAULT_SHARDS", 1)))
    return shards, replicas


def _index_settings(data: dict[str, Any]) -> dict[str, Any]:
    settings = data.get("settings", {})
    if isinstance(settings.get("index"), dict):
        return settings["index"]
    return settings


def _setting(data: dict[str, Any], flat_name: str, nested: tuple[str, ...]) -> Any:
    settings = data.get("settings", {})
    if flat_name in settings:
        return settings[flat_name]
    value: Any = settings
    for position, part in enumerate(nested):
        if not isinstance(value, dict):
            return None
        remaining = ".".join(nested[position:])
        if remaining in value:
            return value[remaining]
        value = value.get(part)
    return value


def _collection_indices(alias: str, ilm: bool, indices: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return configured-layout backing indices and all indices attached to the alias."""
    attached = sorted(name for name, data in indices.items() if alias in data.get("aliases", {}))
    if ilm:
        generation = re.compile(rf"^{re.escape(alias)}-(\d{{6}})$")
        expected_layout = sorted(name for name in indices if generation.fullmatch(name))
    else:
        hot = f"{alias}_hot"
        expected_layout = [hot] if hot in indices else []
    backers = sorted(set(expected_layout) | set(attached))
    return backers, attached


def _is_closed(index_data: dict[str, Any]) -> bool:
    return str(index_data.get("status", "")).lower() in {"close", "closed"}


def _configured_backing_index_names(expectations: dict[str, dict[str, Any]], indices: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for expectation in expectations.values():
        backers, attached = _collection_indices(expectation["alias"], expectation["ilm"], indices)
        names.update(backers)
        names.update(attached)
    return names


def _effective_write_indices(alias: str, attached: list[str], indices: dict[str, Any]) -> list[str]:
    explicit = []
    implicit = []
    for name in attached:
        alias_data = indices[name].get("aliases", {}).get(alias, {})
        if alias_data.get("is_write_index") is True:
            explicit.append(name)
        elif alias_data.get("is_write_index") is None and "is_write_index" not in alias_data:
            implicit.append(name)
    if explicit:
        return explicit
    # Elasticsearch treats a single-index alias with no flag as its write index;
    # legacy Howler _hot aliases have historically used exactly this representation.
    return implicit if len(attached) == 1 else []


def _flatten_properties(properties: dict[str, Any], prefix: str = "") -> dict[str, dict[str, Any]]:
    flattened: dict[str, dict[str, Any]] = {}
    for name, value in properties.items():
        path = f"{prefix}.{name}" if prefix else name
        if isinstance(value, dict) and isinstance(value.get("properties"), dict):
            flattened.update(_flatten_properties(value["properties"], path))
        elif isinstance(value, dict):
            flattened[path] = value
    return flattened


def _mapped_field_count(mapping: dict[str, Any]) -> int:
    """Count currently mapped property, multi-field, and runtime field names."""

    def count_tree(properties: Any) -> int:
        if not isinstance(properties, dict):
            return 0
        return sum(
            1 + count_tree(body.get("properties")) + count_tree(body.get("fields"))
            for body in properties.values()
            if isinstance(body, dict)
        )

    return count_tree(mapping.get("properties")) + count_tree(mapping.get("runtime"))


def _mapping_defaults(field_type: str | None) -> dict[str, Any]:
    defaults: dict[str, Any] = {"store": False, "enabled": True, "dynamic": True}
    if field_type in {"object", "nested", "text"}:
        defaults["doc_values"] = False
    else:
        defaults["doc_values"] = True
    if field_type in {"object", "nested"}:
        defaults["index"] = True
    else:
        defaults["index"] = True
    if field_type == "text":
        defaults.update({"norms": True, "index_options": "positions", "fielddata": False})
    elif field_type == "keyword":
        defaults.update({"norms": False, "eager_global_ordinals": False})
    if field_type in {"integer", "long", "short", "byte", "float", "double", "scaled_float"}:
        defaults.update({"coerce": True, "ignore_malformed": False})
    return defaults


def _normalized_mapping(body: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(body)
    field_type = normalized.get("type")
    defaults = _mapping_defaults(field_type)
    for key, default in defaults.items():
        if normalized.get(key, default) == default:
            normalized.pop(key, None)
    if "copy_to" in normalized:
        targets = normalized["copy_to"]
        normalized["copy_to"] = [targets] if isinstance(targets, str) else targets
    for nested_key in ("fields", "properties"):
        nested = normalized.get(nested_key)
        if isinstance(nested, dict):
            normalized[nested_key] = {key: _normalized_mapping(value) for key, value in nested.items()}
    return normalized


def _mapping_matches(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    return _normalized_mapping(expected) == _normalized_mapping(actual)


def _template_key(template: Any) -> str | None:
    if isinstance(template, dict) and len(template) == 1:
        return next(iter(template))
    return None


def _merge_dynamic_templates(templates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply Elasticsearch name-merge semantics without sorting template order."""
    merged: list[dict[str, Any]] = []
    positions: dict[str, int] = {}
    for template in templates:
        name = _template_key(template)
        if name is None:
            merged.append(template)
        elif name in positions:
            merged[positions[name]] = template
        else:
            positions[name] = len(merged)
            merged.append(template)
    return merged


def _template_checks(
    collection: str,
    alias: str,
    index: str,
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    *,
    schema_less: bool = False,
) -> None:
    source_expected = expected
    raw_names = [_template_key(template) for template in source_expected]
    duplicate_names = sorted({name for name in raw_names if name is not None and raw_names.count(name) > 1})
    expected = _merge_dynamic_templates(expected)
    actual = _merge_dynamic_templates(actual)
    expected_names = [_template_key(template) for template in expected]
    actual_names = [_template_key(template) for template in actual]
    expected_name_set = {name for name in expected_names if name is not None}
    invalid_templates = [name for name in (*expected_names, *actual_names) if name is None]
    expected_active_order = [name for name in expected_names if name is not None]
    actual_active = [template for template in actual if _template_key(template) in expected_name_set]
    actual_active_order = [name for name in actual_names if name in expected_name_set]
    expected_by_name = {
        _template_key(template): template for template in expected if _template_key(template) is not None
    }
    actual_by_name = {
        _template_key(template): template for template in actual_active if _template_key(template) is not None
    }
    missing = sorted(name for name in expected_name_set if name not in actual_by_name)
    changed = sorted(
        name for name in expected_name_set & set(actual_by_name) if expected_by_name[name] != actual_by_name[name]
    )
    if missing or changed or invalid_templates or actual_active_order != expected_active_order:
        finding = {
            "check": "schema_less_dynamic_templates" if schema_less else "dynamic_templates",
            "collection": collection,
            "index": index,
            "message": "Dynamic templates are missing, changed, malformed, or reordered.",
            "missing": missing,
            "changed": changed,
            "actual_active_order": actual_active_order,
            "expected_active_order": expected_active_order,
        }
        (warnings if schema_less else blockers).append(finding)
    if duplicate_names:
        shadowed = {
            name: {
                "shadowed": [template[name] for template in source_expected if _template_key(template) == name][:-1],
                "effective": [template[name] for template in source_expected if _template_key(template) == name][-1],
            }
            for name in duplicate_names
        }
        warnings.append(
            {
                "check": "shadowed_dynamic_template_name",
                "collection": collection,
                "index": index,
                "message": (
                    "The source contract declares duplicate dynamic-template names; Elasticsearch keeps the last "
                    "definition at the first position."
                ),
                "names": duplicate_names,
                "shadowed_definitions": shadowed,
            }
        )
    extra = sorted(name for name in actual_names if name is not None and name not in expected_name_set)
    if extra:
        warnings.append(
            {
                "check": "obsolete_dynamic_templates",
                "collection": collection,
                "index": index,
                "message": "Extra dynamic templates are retained; verify they belong to disabled extensions.",
                "templates": extra,
            }
        )


def _critical_deprecations(value: Any, path: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("level") == "critical":
            found.append(
                {
                    "path": ".".join(path),
                    "message": str(value.get("message", "Critical deprecation")),
                    "details": value.get("details"),
                    "_meta": value.get("_meta", value.get("meta")),
                }
            )
        for key, child in value.items():
            found.extend(_critical_deprecations(child, (*path, str(key))))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_critical_deprecations(child, (*path, str(index))))
    return found


def _contains_reindex_required(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("reindex_required") is True:
            return True
        return any(_contains_reindex_required(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_reindex_required(child) for child in value)
    return False


def _is_es10_readiness(issue: dict[str, Any]) -> bool:
    message = issue.get("message", "").lower()
    return (
        _contains_reindex_required(issue.get("details"))
        or _contains_reindex_required(issue.get("_meta"))
        or message.startswith(("old index with a compatibility version", "old data stream"))
    )


def _baseline_indices(report: dict[str, Any], prefix: str) -> dict[str, Any]:
    inventory = report.get("inventory", {})
    indices = inventory.get("indices", {})
    return {name: data for name, data in indices.items() if name.startswith(f"{prefix}-")}


def _alias_contract(data: dict[str, Any]) -> dict[str, Any]:
    """Return complete alias metadata so baseline checks catch routing/filter drift too."""
    aliases = data.get("aliases", {})
    if not isinstance(aliases, dict):
        return {}
    return {name: deepcopy(alias_data) for name, alias_data in sorted(aliases.items())}


def _canonical_generation(alias: str, index: str) -> int | None:
    match = re.fullmatch(rf"{re.escape(alias)}-(\d{{6}})", index)
    return int(match.group(1)) if match else None


def _empty_unwritten_index(data: dict[str, Any]) -> bool:
    shards = data.get("primary_shards")
    return (
        data.get("doc_count") == 0
        and isinstance(shards, dict)
        and bool(shards)
        and all(shard.get("max_seq_no") == -1 for shard in shards.values())
    )


def _shard_sequence_contract(data: dict[str, Any]) -> dict[str, tuple[int, int, int]] | None:
    shards = data.get("primary_shards")
    if not isinstance(shards, dict) or not shards:
        return None
    result: dict[str, tuple[int, int, int]] = {}
    for shard_id, shard in shards.items():
        if not isinstance(shard, dict):
            return None
        doc_count = shard.get("doc_count")
        max_seq_no = shard.get("max_seq_no")
        global_checkpoint = shard.get("global_checkpoint")
        if (
            isinstance(doc_count, bool)
            or not isinstance(doc_count, int)
            or isinstance(max_seq_no, bool)
            or not isinstance(max_seq_no, int)
            or isinstance(global_checkpoint, bool)
            or not isinstance(global_checkpoint, int)
        ):
            return None
        result[str(shard_id)] = (doc_count, max_seq_no, global_checkpoint)
    return result


def _check_ilm_template_and_policy(  # noqa: C901
    collection: str,
    expectation: dict[str, Any],
    inventory: dict[str, Any],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    alias = expectation["alias"]
    template_name = f"{alias}_template"
    expected_template = expectation["ilm_template"]
    live_template = inventory.get("ilm_templates", {}).get(collection)
    if not isinstance(live_template, dict):
        blockers.append(
            {
                "check": "ilm_template_missing",
                "collection": collection,
                "template": template_name,
                "message": "The configured ILM composable index template is missing.",
            }
        )
    else:
        actual_patterns = live_template.get("index_patterns", [])
        if actual_patterns != [f"{alias}-*"]:
            blockers.append(
                {
                    "check": "ilm_template_patterns",
                    "collection": collection,
                    "expected": [f"{alias}-*"],
                    "actual": actual_patterns,
                    "message": "ILM template index_patterns do not match the configured collection.",
                }
            )
        actual_template = live_template.get("template", {})
        actual_settings = {"settings": actual_template.get("settings", {})}
        expected_settings = expected_template.get("settings", {})
        expected_policy = f"{alias}_policy"
        for setting_name, nested in (
            ("index.lifecycle.name", ("index", "lifecycle", "name")),
            ("index.lifecycle.rollover_alias", ("index", "lifecycle", "rollover_alias")),
            ("index.mapping.total_fields.limit", ("index", "mapping", "total_fields", "limit")),
        ):
            expected_value = _setting({"settings": expected_settings}, setting_name, nested)
            actual_value = _setting(actual_settings, setting_name, nested)
            wanted = expected_policy if setting_name == "index.lifecycle.name" else alias
            if setting_name == "index.mapping.total_fields.limit":
                wanted = expectation["total_fields_limit"]
                try:
                    actual_value = int(actual_value)
                except (TypeError, ValueError):
                    actual_value = None
            if actual_value != wanted or expected_value != wanted:
                blockers.append(
                    {
                        "check": "ilm_template_setting",
                        "collection": collection,
                        "setting": setting_name,
                        "expected": wanted,
                        "actual": actual_value,
                        "message": "ILM template settings do not match the finalized Howler contract.",
                    }
                )

        actual_mapping = actual_template.get("mappings", {})
        expected_mapping = expected_template.get("mappings", {})
        if actual_mapping.get("dynamic", True) != expected_mapping.get("dynamic", True):
            blockers.append(
                {
                    "check": "ilm_template_mapping",
                    "collection": collection,
                    "message": "ILM template mapping-level dynamic behavior differs from the schema.",
                }
            )
        expected_properties = _flatten_properties(expected_mapping.get("properties", {}))
        actual_properties = _flatten_properties(actual_mapping.get("properties", {}))
        for field, expected_definition in expected_properties.items():
            actual_definition = actual_properties.get(field)
            if actual_definition is None or not _mapping_matches(expected_definition, actual_definition):
                blockers.append(
                    {
                        "check": "ilm_template_property",
                        "collection": collection,
                        "property": field,
                        "message": "ILM template does not contain the expected property definition.",
                        "expected": expected_definition,
                        "actual": actual_definition,
                    }
                )
        _template_checks(
            collection,
            alias,
            template_name,
            expected_mapping.get("dynamic_templates", []),
            actual_mapping.get("dynamic_templates", []),
            blockers,
            warnings,
            schema_less=expectation["model"] is None,
        )

    policy = inventory.get("ilm_policies", {}).get(collection)
    phases = policy.get("phases", {}) if isinstance(policy, dict) else {}
    hot_actions = phases.get("hot", {}).get("actions", {}) if isinstance(phases, dict) else {}
    rollover = hot_actions.get("rollover") if isinstance(hot_actions, dict) else None
    if not isinstance(rollover, dict):
        blockers.append(
            {
                "check": "ilm_policy_rollover",
                "collection": collection,
                "policy": f"{alias}_policy",
                "message": "ILM policy is missing or has no hot-phase rollover action.",
            }
        )


def _allowed_alias_flip(before: dict[str, Any], after: dict[str, Any], alias: str) -> bool:
    old_aliases = _alias_contract(before)
    new_aliases = _alias_contract(after)
    old_definition = old_aliases.get(alias)
    new_definition = new_aliases.get(alias)
    if not isinstance(old_definition, dict) or not isinstance(new_definition, dict):
        return False
    if old_definition.get("is_write_index") is not True or new_definition.get("is_write_index") is not False:
        return False
    old_definition["is_write_index"] = False
    return old_aliases == new_aliases


def _sequence_drift(
    before: dict[str, tuple[int, int, int]],
    after: dict[str, tuple[int, int, int]],
) -> dict[str, dict[str, dict[str, int]]] | None:
    """Return per-shard document/sequence drift, or None when shard layouts differ."""
    if before.keys() != after.keys():
        return None

    changes: dict[str, dict[str, dict[str, int]]] = {}
    for shard_id in sorted(before):
        before_count, before_max_seq_no, before_checkpoint = before[shard_id]
        after_count, after_max_seq_no, _ = after[shard_id]
        if before_count != after_count or before_max_seq_no != after_max_seq_no:
            changes[shard_id] = {
                "baseline": {"doc_count": before_count, "max_seq_no": before_max_seq_no},
                "current": {"doc_count": after_count, "max_seq_no": after_max_seq_no},
            }
    return changes


def _compare_baseline(  # noqa: C901
    current: dict[str, Any],
    baseline: dict[str, Any],
    prefix: str,
    expectations: dict[str, dict[str, Any]],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    accepted_sequence_drift: set[str] | None = None,
) -> None:
    accepted_sequence_drift = accepted_sequence_drift or set()
    baseline_prefix = baseline.get("index_prefix")
    if baseline_prefix != prefix:
        blockers.append(
            {
                "check": "baseline_index_prefix",
                "expected": prefix,
                "actual": baseline_prefix,
                "message": "Baseline index_prefix must exactly match the deployed datastore prefix.",
            }
        )
        return

    old_indices = _baseline_indices(baseline, prefix)
    new_indices = _baseline_indices({"inventory": current}, prefix)
    if not old_indices:
        blockers.append(
            {
                "check": "baseline_no_prefix_indices",
                "message": f"Baseline contains no Howler indices using configured prefix {prefix!r}.",
            }
        )
    old_names, new_names = set(old_indices), set(new_indices)
    missing_names = old_names - new_names
    if missing_names:
        blockers.append(
            {
                "check": "baseline_index_missing",
                "message": "Every baseline Howler index must remain present; a missing index may indicate data loss.",
                "indices": sorted(missing_names),
            }
        )

    permitted_new: set[str] = set()
    rollover_old_writes: dict[str, str] = {}
    for collection, expectation in sorted(expectations.items()):
        alias = expectation["alias"]
        ilm = expectation["ilm"]
        old_backers, old_attached = _collection_indices(alias, ilm, old_indices)
        current_backers, current_attached = _collection_indices(alias, ilm, new_indices)
        old_collection_present = bool(old_backers or old_attached)
        current_new = sorted(set(current_backers) & (new_names - old_names))

        if not old_collection_present and current_new:
            if ilm:
                canonical = [name for name in current_new if _canonical_generation(alias, name) is not None]
                expected_write = (
                    max(canonical, key=lambda name: _canonical_generation(alias, name) or -1) if canonical else None
                )
                valid_layout = len(canonical) == 1 and len(current_new) == len(canonical) == len(current_backers)
            else:
                hot = f"{alias}_hot"
                canonical = [name for name in current_new if name == hot]
                expected_write = hot if len(current_backers) == 1 and current_backers[0] == hot else None
                valid_layout = current_new == [hot] and current_backers == [hot]
            if not valid_layout or expected_write is None or current_attached != [expected_write]:
                blockers.append(
                    {
                        "check": "baseline_new_collection_layout",
                        "collection": collection,
                        "indices": current_new,
                        "message": (
                            "A collection initialized after the baseline must have exactly its configured empty "
                            "layout and alias."
                        ),
                    }
                )
                continue
            alias_contract = _alias_contract(new_indices[expected_write])
            if set(alias_contract) != {alias}:
                blockers.append(
                    {
                        "check": "baseline_new_collection_aliases",
                        "collection": collection,
                        "index": expected_write,
                        "aliases": alias_contract,
                        "message": "A newly initialized index may carry only its configured Howler alias.",
                    }
                )
                continue
            write_indices = _effective_write_indices(alias, current_attached, new_indices)
            if write_indices != [expected_write]:
                blockers.append(
                    {
                        "check": "baseline_new_collection_write_index",
                        "collection": collection,
                        "expected": expected_write,
                        "actual": write_indices,
                        "message": "Newly initialized collection must have one configured write index.",
                    }
                )
                continue
            if not all(_empty_unwritten_index(new_indices[name]) for name in current_new):
                blockers.append(
                    {
                        "check": "baseline_new_collection_nonempty",
                        "collection": collection,
                        "indices": current_new,
                        "message": "A collection initialized after the baseline must still be empty and unwritten.",
                    }
                )
                continue
            permitted_new.update(current_new)
            warnings.append(
                {
                    "check": "baseline_new_empty_collection",
                    "collection": collection,
                    "indices": current_new,
                    "message": "A configured collection absent from the baseline was initialized empty after it.",
                }
            )
            continue

        if ilm and old_collection_present:
            new_generations = [name for name in current_new if _canonical_generation(alias, name) is not None]
            baseline_write_indices = _effective_write_indices(alias, old_attached, old_indices)
            baseline_generation = (
                _canonical_generation(alias, baseline_write_indices[0]) if len(baseline_write_indices) == 1 else None
            )
            if new_generations:
                new_generation_number = _canonical_generation(alias, new_generations[0])
                if (
                    len(new_generations) != 1
                    or baseline_generation is None
                    or new_generation_number is None
                    or new_generation_number <= baseline_generation
                ):
                    blockers.append(
                        {
                            "check": "baseline_rollover_generation",
                            "collection": collection,
                            "indices": new_generations,
                            "message": (
                                "At most one new canonical ILM generation above the baseline write index is allowed."
                            ),
                        }
                    )
                    continue
                new_generation = new_generations[0]
                if not _empty_unwritten_index(new_indices[new_generation]):
                    blockers.append(
                        {
                            "check": "baseline_rollover_nonempty",
                            "collection": collection,
                            "index": new_generation,
                            "message": "A rollover index created after the baseline must be empty and unwritten.",
                        }
                    )
                    continue
                if set(_alias_contract(new_indices[new_generation])) != {alias}:
                    blockers.append(
                        {
                            "check": "baseline_rollover_aliases",
                            "collection": collection,
                            "index": new_generation,
                            "aliases": _alias_contract(new_indices[new_generation]),
                            "message": "A rollover generation may carry only its configured Howler alias.",
                        }
                    )
                    continue
                current_write_indices = _effective_write_indices(alias, current_attached, new_indices)
                if current_write_indices != [new_generation]:
                    blockers.append(
                        {
                            "check": "baseline_rollover_write_index",
                            "collection": collection,
                            "expected": [new_generation],
                            "actual": current_write_indices,
                            "message": "The new rollover generation must be the only write index.",
                        }
                    )
                    continue
                permitted_new.add(new_generation)
                rollover_old_writes[baseline_write_indices[0]] = alias
                warnings.append(
                    {
                        "check": "baseline_ilm_rollover",
                        "collection": collection,
                        "index": new_generation,
                        "message": "One empty ILM generation rolled over during the quiesced baseline window.",
                    }
                )

    unexplained_new = new_names - old_names - permitted_new
    unexplained_new -= {name for name, data in new_indices.items() if _is_closed(data)}
    if unexplained_new:
        blockers.append(
            {
                "check": "baseline_unexpected_indices",
                "message": (
                    "New Howler-prefixed indices are not an allowed empty initialization or single-generation rollover."
                ),
                "indices": sorted(unexplained_new),
            }
        )

    common_names = old_names & new_names
    unknown_acceptances = accepted_sequence_drift - common_names
    for index in sorted(unknown_acceptances):
        warnings.append(
            {
                "check": "unknown_sequence_drift_acceptance",
                "index": index,
                "message": "No baseline/current index pair matched this acceptance; no drift was accepted.",
            }
        )

    for name in sorted(common_names):
        before, after = old_indices[name], new_indices[name]
        if before.get("uuid") is None or after.get("uuid") is None:
            blockers.append(
                {"check": "baseline_uuid", "index": name, "message": "Baseline or current index UUID is missing."}
            )
        elif before["uuid"] != after["uuid"]:
            blockers.append(
                {
                    "check": "baseline_uuid",
                    "index": name,
                    "message": "Index UUID changed; this may indicate reindexing or index replacement.",
                    "baseline": before["uuid"],
                    "current": after["uuid"],
                }
            )
        aliases_match = (
            _allowed_alias_flip(before, after, rollover_old_writes[name])
            if name in rollover_old_writes
            else _alias_contract(before) == _alias_contract(after)
        )
        if not aliases_match:
            blockers.append(
                {
                    "check": "baseline_aliases",
                    "index": name,
                    "message": "Alias membership or is_write_index changed after the baseline.",
                    "baseline": _alias_contract(before),
                    "current": _alias_contract(after),
                }
            )
        if _is_closed(before) or _is_closed(after):
            continue
        accepted = name in accepted_sequence_drift and name in common_names
        before_count, after_count = before.get("doc_count"), after.get("doc_count")
        if (
            isinstance(before_count, bool)
            or not isinstance(before_count, int)
            or isinstance(after_count, bool)
            or not isinstance(after_count, int)
        ):
            blockers.append(
                {
                    "check": "baseline_doc_count",
                    "index": name,
                    "message": "Baseline or current primary document count is missing.",
                }
            )
        elif before_count != after_count and not accepted:
            blockers.append(
                {
                    "check": "baseline_doc_count",
                    "index": name,
                    "baseline": before_count,
                    "current": after_count,
                    "message": "Primary document count changed after the quiesced baseline.",
                }
            )
        before_shards = _shard_sequence_contract(before)
        after_shards = _shard_sequence_contract(after)
        if before_shards is None or after_shards is None:
            blockers.append(
                {
                    "check": "baseline_sequence_numbers",
                    "index": name,
                    "message": "Baseline or current primary-shard stats are incomplete.",
                }
            )
        else:
            baseline_sync = primary_shard_sync_issues(before.get("primary_shards"))
            if baseline_sync:
                blockers.append(
                    {
                        "check": "sequence_checkpoint_unsynced",
                        "index": name,
                        "message": (
                            "Baseline primary sequence stats are incomplete or unsynced; after quiescing writes, "
                            "flush, wait for the global checkpoint to catch up, and capture a new baseline."
                        ),
                        "baseline_issues": baseline_sync,
                    }
                )
                continue

            drift = _sequence_drift(before_shards, after_shards)
            if drift is None:
                blockers.append(
                    {
                        "check": "baseline_sequence_numbers",
                        "index": name,
                        "message": "Primary shard layout changed after the quiesced baseline.",
                        "baseline": before_shards,
                        "current": after_shards,
                    }
                )
                continue

            decreases = sorted(
                shard_id for shard_id in before_shards if after_shards[shard_id][1] < before_shards[shard_id][1]
            )
            if decreases:
                blockers.append(
                    {
                        "check": "baseline_sequence_decrease",
                        "index": name,
                        "shards": decreases,
                        "message": (
                            "Primary max_seq_no decreased after the baseline; this may indicate rolled-back writes."
                        ),
                    }
                )
            elif drift and accepted:
                warnings.append(
                    {
                        "check": "baseline_sequence_drift_accepted",
                        "index": name,
                        "shards": drift,
                        "message": (
                            "The cutover lead explicitly accepted primary document-count/max_seq_no drift for this "
                            "index; record the decision in the change record."
                        ),
                    }
                )
            elif drift:
                blockers.append(
                    {
                        "check": "baseline_sequence_numbers",
                        "index": name,
                        "message": "Per-shard document counts or max_seq_no changed after the quiesced baseline.",
                        "shards": drift,
                    }
                )


def evaluate_inventory(  # noqa: C901
    inventory: dict[str, Any],
    expectations: dict[str, dict[str, Any]],
    *,
    baseline: dict[str, Any] | None = None,
    allow_yellow: bool = False,
    integrity_only: bool = False,
    accepted_sequence_drift: set[str] | None = None,
) -> dict[str, Any]:
    """Evaluate cluster, baseline, layout, ILM, mapping, and field-cap contracts."""
    blockers: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    accepted_sequence_drift = accepted_sequence_drift or set()
    health_data = inventory.get("cluster_health", {})
    health = health_data.get("status")
    if health == "green":
        pass
    elif health == "yellow" and allow_yellow:
        warnings.append(
            {
                "check": "cluster_health_override",
                "message": "Yellow health was explicitly accepted using --allow-yellow.",
            }
        )
    elif health == "yellow":
        blockers.append(
            {
                "check": "cluster_health",
                "message": "Cluster health is yellow; rerun with --allow-yellow only after operator review.",
            }
        )
    else:
        blockers.append(
            {
                "check": "cluster_health",
                "message": (
                    "Cluster health must be green"
                    f"{' or explicitly allowed yellow' if allow_yellow else ''}; found {health or 'unknown'}."
                ),
            }
        )
    if health_data.get("timed_out") is True:
        blockers.append(
            {
                "check": "cluster_health_timeout",
                "message": "Cluster health request timed out; its result is incomplete.",
            }
        )

    root_version = inventory.get("version", {}).get("version", {}).get("number")
    node_data = inventory.get("nodes", {}).get("nodes", {})
    node_versions = {node.get("name", node_id): node.get("version") for node_id, node in node_data.items()}
    if not node_versions:
        blockers.append({"check": "node_versions", "message": "No Elasticsearch nodes or node versions were returned."})
    for node, version in sorted(node_versions.items()):
        if version != TARGET_VERSION:
            blockers.append(
                {
                    "check": "node_version",
                    "node": node,
                    "message": f"Every node must report {TARGET_VERSION}; found {version or 'unknown'}.",
                }
            )
    if root_version != TARGET_VERSION:
        blockers.append(
            {
                "check": "cluster_version",
                "message": f"Cluster info must report {TARGET_VERSION}; found {root_version or 'unknown'}.",
            }
        )

    feature_status = inventory.get("feature_upgrade_status", {}).get("migration_status")
    if feature_status in {"IN_PROGRESS", "ERROR"}:
        blockers.append(
            {
                "check": "system_features",
                "message": (
                    f"System feature migration is {feature_status}; resolve or stop the migration before cutover."
                ),
            }
        )
    elif feature_status == "MIGRATION_NEEDED":
        warnings.append(
            {
                "check": "es10_readiness_system_features",
                "message": (
                    "System-feature migration is Elasticsearch 10 preparation; schedule and rehearse it separately."
                ),
            }
        )
    elif feature_status != NO_MIGRATION_NEEDED:
        warnings.append(
            {
                "check": "es10_readiness_system_features",
                "message": (
                    f"Unrecognized system-feature status {feature_status or 'missing'}; "
                    "confirm future-major readiness separately."
                ),
            }
        )
    critical = _critical_deprecations(inventory.get("deprecations", {}))
    es10_readiness = [issue for issue in critical if _is_es10_readiness(issue)]
    cutover_critical = [issue for issue in critical if not _is_es10_readiness(issue)]
    if es10_readiness:
        warnings.append(
            {
                "check": "es10_readiness",
                "message": "These next-major reindex/readiness deprecations are expected after an 8.x-to-9.x upgrade.",
                "resources": es10_readiness,
            }
        )
    if cutover_critical:
        blockers.append(
            {
                "check": "critical_deprecations",
                "message": f"Resolve {len(cutover_critical)} critical deprecation(s) that affect 9.x operation.",
                "resources": cutover_critical,
            }
        )

    indices = inventory.get("indices", {})
    mappings = inventory.get("mappings", {})
    current_prefix = inventory.get("index_prefix", _prefix())
    baseline_indices = _baseline_indices(baseline, current_prefix) if baseline is not None else {}
    configured_backers = _configured_backing_index_names(expectations, indices)
    configured_backers.update(_configured_backing_index_names(expectations, baseline_indices))
    closed_current = {name for name, data in indices.items() if _is_closed(data)}
    closed_baseline = {name for name, data in baseline_indices.items() if _is_closed(data)}
    for index in sorted(closed_current | closed_baseline):
        finding = {
            "check": "closed_howler_index",
            "index": index,
            "message": "Closed Howler-prefixed indices are not covered by open-index statistics.",
        }
        if index in configured_backers or index in baseline_indices:
            finding["message"] = (
                "A closed index backs a configured collection or is present in the baseline; reopen or archive it "
                "before cutover."
            )
            blockers.append(finding)
        else:
            finding["message"] = (
                "Closed Howler-prefixed index is not configured and is absent from the baseline; review it."
            )
            warnings.append(finding)

    for index, data in sorted(indices.items()):
        if not index.startswith(f"{current_prefix}-") or _is_closed(data):
            continue
        sync_issues = primary_shard_sync_issues(data.get("primary_shards"))
        if sync_issues:
            blockers.append(
                {
                    "check": "sequence_checkpoint_unsynced",
                    "index": index,
                    "message": (
                        "Primary sequence stats are incomplete or unsynced; wait for cluster health to be green, "
                        "then rerun the verifier."
                    ),
                    "shards": sync_issues,
                }
            )
    if integrity_only:
        if baseline is None:
            blockers.append({"check": "baseline_required", "message": "--integrity-only requires --baseline."})
        else:
            _compare_baseline(
                inventory,
                baseline,
                current_prefix,
                expectations,
                blockers,
                warnings,
                accepted_sequence_drift,
            )
        return {
            "allow_yellow": allow_yellow,
            "integrity_only": True,
            "blockers": blockers,
            "ready": not blockers,
            "warnings": warnings,
        }

    for collection, expectation in sorted(expectations.items()):
        alias = expectation["alias"]
        ilm = expectation["ilm"]
        backers, attached = _collection_indices(alias, ilm, indices)
        baseline_backers, baseline_attached = _collection_indices(alias, ilm, baseline_indices)
        baseline_present = bool(baseline_backers or baseline_attached)
        if not backers and not attached:
            if baseline_present:
                blockers.append(
                    {
                        "check": "collection_missing_after_baseline",
                        "collection": collection,
                        "alias": alias,
                        "message": "A configured collection present at baseline is now missing.",
                    }
                )
            else:
                blockers.append(
                    {
                        "check": "collection_not_initialized",
                        "collection": collection,
                        "alias": alias,
                        "message": (
                            "Collection is not initialized; run the separate collection initializer before full "
                            "verification."
                        ),
                    }
                )
            continue
        if ilm:
            _check_ilm_template_and_policy(collection, expectation, inventory, blockers, warnings)
        if not attached:
            blockers.append(
                {
                    "check": "alias_missing",
                    "collection": collection,
                    "alias": alias,
                    "message": "Collection alias has no backing indices.",
                }
            )
        write_indices = _effective_write_indices(alias, attached, indices)
        if len(write_indices) != 1:
            blockers.append(
                {
                    "check": "alias_write_index",
                    "collection": collection,
                    "alias": alias,
                    "message": f"Alias must resolve to exactly one write index; found {len(write_indices)}.",
                    "attached_indices": attached,
                    "write_indices": write_indices,
                }
            )
        if ilm:
            canonical_generation = re.compile(rf"^{re.escape(alias)}-(\d{{6}})$")
            canonical_backers = [name for name in backers if canonical_generation.fullmatch(name)]
            if not canonical_backers:
                blockers.append(
                    {
                        "check": "ilm_backing_indices",
                        "collection": collection,
                        "alias": alias,
                        "message": "ILM collection has no canonical six-digit backing index.",
                    }
                )
            expected_write = (
                max(canonical_backers, key=lambda name: int(name.rsplit("-", 1)[-1])) if canonical_backers else None
            )
            if expected_write is not None and write_indices != [expected_write]:
                blockers.append(
                    {
                        "check": "ilm_write_index",
                        "collection": collection,
                        "alias": alias,
                        "message": "ILM alias write index must be the latest canonical six-digit backing index.",
                        "expected": expected_write,
                        "actual": write_indices,
                    }
                )
        else:
            hot = f"{alias}_hot"
            if hot not in indices:
                blockers.append(
                    {
                        "check": "legacy_hot_index",
                        "collection": collection,
                        "index": hot,
                        "message": "Configured legacy _hot index is missing.",
                    }
                )
            if attached != [hot] or write_indices != [hot]:
                blockers.append(
                    {
                        "check": "legacy_write_index",
                        "collection": collection,
                        "alias": alias,
                        "message": "The legacy alias must write to its _hot index.",
                        "expected": [hot],
                        "actual": write_indices,
                    }
                )

        schema_less = expectation["model"] is None
        expected_mapping = expectation["mapping"]
        expected_properties = _flatten_properties(expected_mapping.get("properties", {}))
        expected_templates = expected_mapping.get("dynamic_templates", [])
        policy_name = f"{alias}_policy"
        for index in backers:
            index_data = indices.get(index, {})
            if index not in mappings:
                finding: dict[str, Any] = {
                    "check": "mapping_missing",
                    "collection": collection,
                    "index": index,
                    "message": "No live mapping was returned for a backing index.",
                }
                (warnings if schema_less else blockers).append(finding)
                continue
            live_mapping = mappings[index].get("mappings", mappings[index])
            live_properties = _flatten_properties(live_mapping.get("properties", {}))
            for path, expected_definition in expected_properties.items():
                actual_definition = live_properties.get(path)
                if actual_definition is None:
                    finding = {
                        "check": "schema_less_mapping_property_missing" if schema_less else "mapping_property_missing",
                        "collection": collection,
                        "index": index,
                        "property": path,
                        "message": "Expected mapping property is missing.",
                    }
                    (warnings if schema_less else blockers).append(finding)
                elif not _mapping_matches(expected_definition, actual_definition):
                    finding = {
                        "check": "schema_less_mapping_property_mismatch"
                        if schema_less
                        else "mapping_property_mismatch",
                        "collection": collection,
                        "index": index,
                        "property": path,
                        "message": "Live property mapping differs from the finalized Howler schema.",
                        "expected": expected_definition,
                        "actual": actual_definition,
                    }
                    (warnings if schema_less else blockers).append(finding)
            _template_checks(
                collection,
                alias,
                index,
                expected_templates,
                live_mapping.get("dynamic_templates", []),
                blockers,
                warnings,
                schema_less=schema_less,
            )
            limit = _setting(
                index_data,
                "index.mapping.total_fields.limit",
                ("index", "mapping", "total_fields", "limit"),
            )
            expected_limit = expectation["total_fields_limit"]
            try:
                actual_limit = int(limit) if limit is not None else DEFAULT_TOTAL_FIELDS_LIMIT
            except (TypeError, ValueError):
                actual_limit = 0
            actual_mapping_fields = _mapped_field_count(live_mapping)
            is_write_index = index in write_indices
            if is_write_index and actual_limit < expected_limit:
                blockers.append(
                    {
                        "check": "total_fields_limit",
                        "collection": collection,
                        "index": index,
                        "expected_minimum": expected_limit,
                        "actual": limit,
                        "message": f"Mapping field limit must be at least {expected_limit}.",
                    }
                )

            elif actual_limit < actual_mapping_fields:
                blockers.append(
                    {
                        "check": "total_fields_limit_below_mapped_fields",
                        "collection": collection,
                        "index": index,
                        "actual_limit": actual_limit,
                        "mapped_fields": actual_mapping_fields,
                        "message": "Index field limit is below its actual mapped field count.",
                    }
                )
            elif actual_limit < expected_limit:
                warnings.append(
                    {
                        "check": "total_fields_limit_legacy_lower",
                        "collection": collection,
                        "index": index,
                        "actual_limit": actual_limit,
                        "expected_minimum": expected_limit,
                        "mapped_fields": actual_mapping_fields,
                        "message": (
                            "Existing backing index has a lower-than-current schema limit but can hold its current "
                            "mapping."
                        ),
                    }
                )

            if ilm:
                lifecycle_name = _setting(index_data, "index.lifecycle.name", ("index", "lifecycle", "name"))
                rollover_alias = _setting(
                    index_data, "index.lifecycle.rollover_alias", ("index", "lifecycle", "rollover_alias")
                )
                if lifecycle_name != policy_name or rollover_alias != alias:
                    blockers.append(
                        {
                            "check": "ilm_settings",
                            "collection": collection,
                            "index": index,
                            "expected_policy": policy_name,
                            "actual_policy": lifecycle_name,
                            "expected_rollover_alias": alias,
                            "actual_rollover_alias": rollover_alias,
                            "message": "Backing index lifecycle policy or rollover alias settings are incorrect.",
                        }
                    )
                explain = inventory.get("ilm_explain", {}).get(index, {})
                if explain.get("managed") is not True:
                    blockers.append(
                        {
                            "check": "ilm_managed",
                            "collection": collection,
                            "index": index,
                            "message": "ILM-backed collection index is not managed by ILM.",
                        }
                    )
                if explain.get("policy") != policy_name:
                    blockers.append(
                        {
                            "check": "ilm_policy",
                            "collection": collection,
                            "index": index,
                            "expected": policy_name,
                            "actual": explain.get("policy"),
                            "message": "ILM explain reports an unexpected or missing policy.",
                        }
                    )
                step_info = explain.get("step_info")
                has_step_error = isinstance(step_info, dict) and bool(step_info.get("type") or step_info.get("reason"))
                if str(explain.get("step", "")).upper() == "ERROR" or has_step_error:
                    blockers.append(
                        {
                            "check": "ilm_step",
                            "collection": collection,
                            "index": index,
                            "step": explain.get("step"),
                            "step_info": explain.get("step_info"),
                            "message": "ILM explain reports an ERROR step or step information.",
                        }
                    )

        caps_result = inventory.get("field_caps", {}).get(collection, {})
        has_caps = isinstance(caps_result, dict) and isinstance(caps_result.get("fields"), dict)
        caps = caps_result["fields"] if has_caps else {}
        schema_paths = set(expected_properties)
        for field, types in sorted(caps.items()):
            if len(types) > 1:
                finding = {
                    "check": "field_caps_conflict" if field in schema_paths else "field_caps_non_schema_conflict",
                    "collection": collection,
                    "field": field,
                    "types": sorted(types),
                    "message": "field_caps reports more than one field type across backing indices.",
                }
                (blockers if field in schema_paths else warnings).append(finding)
        has_closed_backer = any(_is_closed(indices.get(index, {})) for index in backers)
        if backers and not has_caps and not has_closed_backer:
            blockers.append(
                {
                    "check": "field_caps_missing",
                    "collection": collection,
                    "message": "No field_caps result was collected for this collection.",
                }
            )

    if baseline is not None:
        _compare_baseline(
            inventory,
            baseline,
            current_prefix,
            expectations,
            blockers,
            warnings,
            accepted_sequence_drift,
        )
    elif accepted_sequence_drift:
        blockers.append(
            {
                "check": "sequence_drift_acceptance_requires_baseline",
                "message": "--accept-sequence-drift requires a validated --baseline report.",
            }
        )

    return {
        "allow_yellow": allow_yellow,
        "integrity_only": False,
        "blockers": blockers,
        "ready": not blockers,
        "warnings": warnings,
    }


def collect_inventory(  # noqa: C901
    client: ElasticsearchRestClient,
    expectations: dict[str, dict[str, Any]],
    *,
    integrity_only: bool = False,
) -> dict[str, Any]:
    """Read configured Howler indices and cluster gates using GET requests only."""
    prefix = _prefix()
    index_pattern = f"/{quote(prefix, safe='-_.')}-*"
    indices = client.get(
        index_pattern,
        {
            "features": "aliases,settings",
            "flat_settings": "true",
            "expand_wildcards": "all",
            "allow_no_indices": "true",
        },
    )
    catalog_rows = client.get(
        f"/_cat/indices/{quote(prefix, safe='-_.')}-*",
        {"format": "json", "h": "index,health,status", "expand_wildcards": "all"},
    )
    catalog = {row.get("index"): row for row in catalog_rows if row.get("index")}
    stats = collect_primary_shard_stats(client, prefix)
    health = client.get("/_cluster/health")
    for name, data in indices.items():
        settings = _index_settings(data)
        row = catalog.get(name, {})
        shard_stats = stats.get(name, {})
        data["uuid"] = settings.get("index.uuid") or settings.get("uuid") or data.get("uuid")
        data["doc_count"] = shard_stats.get("doc_count")
        data["primary_shards"] = shard_stats.get("primary_shards", {})
        data["health"] = row.get("health")
        data["status"] = row.get("status")

    mappings = (
        client.get(
            f"{index_pattern}/_mapping",
            {"expand_wildcards": "all", "allow_no_indices": "true"},
        )
        if not integrity_only
        else {}
    )
    ilm_explain: dict[str, Any] = {}
    field_caps: dict[str, Any] = {}
    ilm_templates: dict[str, Any] = {}
    ilm_policies: dict[str, Any] = {}
    for collection, expectation in expectations.items() if not integrity_only else ():
        alias = expectation["alias"]
        backers, attached = _collection_indices(alias, expectation["ilm"], indices)
        if expectation["ilm"] and backers:
            try:
                explain = client.get(
                    f"/{quote(alias, safe='-_.')}-*/_ilm/explain",
                    {"only_managed": "false"},
                )
                ilm_explain.update(explain.get("indices", explain))
            except ElasticsearchRestError as error:
                if error.status != 404:
                    raise
        if attached and not any(_is_closed(indices.get(name, {})) for name in attached):
            field_caps[collection] = client.get(f"/{quote(alias, safe='-_.')}/_field_caps", {"fields": "*"})
        if expectation["ilm"] and backers:
            template_name = f"{alias}_template"
            policy_name = f"{alias}_policy"
            try:
                response = client.get(f"/_index_template/{quote(template_name, safe='-_.')}")
                template_list = response.get("index_templates", [])
                ilm_templates[collection] = next(
                    (
                        item.get("index_template")
                        for item in template_list
                        if item.get("name") == template_name and isinstance(item.get("index_template"), dict)
                    ),
                    None,
                )
            except ElasticsearchRestError as error:
                if error.status != 404:
                    raise
                ilm_templates[collection] = None
            try:
                response = client.get(f"/_ilm/policy/{quote(policy_name, safe='-_.')}")
                ilm_policies[collection] = response.get(policy_name, {}).get("policy")
            except ElasticsearchRestError as error:
                if error.status != 404:
                    raise
                ilm_policies[collection] = None

    return {
        "cluster_health": health,
        "deprecations": client.get("/_migration/deprecations"),
        "feature_upgrade_status": client.get("/_migration/system_features"),
        "field_caps": field_caps,
        "ilm_explain": ilm_explain,
        "ilm_policies": ilm_policies,
        "ilm_templates": ilm_templates,
        "index_prefix": prefix,
        "indices": indices,
        "mappings": mappings,
        "nodes": client.get("/_nodes", {"filter_path": "nodes.*.name,nodes.*.version"}),
        "version": client.get("/"),
    }


def build_report(
    client: ElasticsearchRestClient,
    *,
    baseline: dict[str, Any] | None = None,
    allow_yellow: bool = False,
    integrity_only: bool = False,
    accepted_sequence_drift: set[str] | None = None,
) -> dict[str, Any]:
    """Build the post-cutover JSON report from the deployed model/config contract."""
    expectations = _expectations()
    inventory = collect_inventory(client, expectations, integrity_only=integrity_only)
    evaluation = evaluate_inventory(
        inventory,
        expectations,
        baseline=baseline,
        allow_yellow=allow_yellow,
        integrity_only=integrity_only,
        accepted_sequence_drift=accepted_sequence_drift,
    )
    return {
        "checks": evaluation,
        "expected_collections": {
            name: {
                "alias": contract["alias"],
                "ilm": contract["ilm"],
                "total_fields_limit": contract["total_fields_limit"],
            }
            for name, contract in sorted(expectations.items())
        },
        "index_prefix": inventory["index_prefix"],
        "inventory": inventory,
        "target_version": TARGET_VERSION,
    }


def _client_from_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> ElasticsearchRestClient:
    try:
        return ElasticsearchRestClient(
            args.url,
            **credentials_from_environment(),
            ca_certs=args.ca_certs,
            insecure=args.insecure,
            timeout=args.timeout,
            allow_insecure_http_auth=args.allow_insecure_http_auth,
        )
    except ValueError as error:
        parser.error(str(error))
        raise AssertionError("argparse parser.error must exit")  # pragma: no cover


def _read_baseline(  # noqa: C901
    path: Path | None, parser: argparse.ArgumentParser
) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        parser.error(f"Cannot read baseline JSON: {error}")
        raise AssertionError("argparse parser.error must exit")  # pragma: no cover
    if not isinstance(value, dict):
        parser.error("Baseline must be a preflight report containing inventory.indices.")
    inventory = value.get("inventory")
    checks = value.get("checks")
    if not isinstance(inventory, dict) or not isinstance(inventory.get("indices"), dict):
        parser.error("Baseline must be a preflight report containing inventory.indices.")
    version_data = inventory.get("version")
    if not isinstance(version_data, dict) or not isinstance(checks, dict):
        parser.error("Baseline must include inventory.version and checks.ready.")
    if value.get("source_stack_version") != "8.19.11":
        parser.error("Baseline source_stack_version must be exactly 8.19.11.")
    if value.get("baseline_capture") is not True:
        parser.error("Baseline must be produced by preflight with --baseline-capture.")
    cluster_version = version_data.get("version")
    baseline_version = cluster_version.get("number") if isinstance(cluster_version, dict) else None
    if baseline_version != "8.19.11":
        parser.error("Baseline inventory.version.number must be exactly 8.19.11.")
    if checks.get("ready") is not True:
        parser.error("Baseline preflight checks.ready must be true.")
    if value.get("index_prefix") != _prefix():
        parser.error(
            f"Baseline index_prefix must exactly match the deployed datastore prefix {_prefix()!r}; "
            f"found {value.get('index_prefix')!r}."
        )
    return value


def main() -> int:
    """Run the read-only post-cutover verification."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"),
        help="Elasticsearch URL. Defaults to ELASTICSEARCH_URL or http://localhost:9200.",
    )
    parser.add_argument("--output", type=Path, help="Write the JSON report to this path instead of stdout.")
    parser.add_argument("--baseline", type=Path, help="Quiesced Elasticsearch 8.19 preflight report JSON.")
    parser.add_argument("--allow-yellow", action="store_true", help="Explicitly accept yellow cluster health.")
    parser.add_argument(
        "--integrity-only",
        action="store_true",
        help="Check cluster and quiesced baseline integrity only; requires --baseline.",
    )
    parser.add_argument(
        "--accept-sequence-drift",
        action="append",
        default=[],
        metavar="INDEX",
        help=(
            "Explicitly accept doc_count/max_seq_no drift for this exact baseline index; repeat for each index. "
            "Decreases are never accepted. Record the decision in the change record."
        ),
    )
    parser.add_argument(
        "--allow-insecure-http-auth",
        action="store_true",
        help="Explicitly allow sending credentials over plain HTTP (not recommended).",
    )
    tls = parser.add_mutually_exclusive_group()
    tls.add_argument("--ca-certs", type=Path, help="Certificate authority bundle for TLS verification.")
    tls.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification.")
    parser.add_argument("--timeout", type=int, default=60, help="Request timeout in seconds.")
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be a positive number of seconds.")
    if args.integrity_only and args.baseline is None:
        parser.error("--integrity-only requires --baseline.")
    if args.accept_sequence_drift and args.baseline is None:
        parser.error("--accept-sequence-drift requires --baseline.")
    baseline = _read_baseline(args.baseline, parser)
    client = _client_from_args(args, parser)
    report: dict[str, Any]
    try:
        report = build_report(
            client,
            baseline=baseline,
            allow_yellow=args.allow_yellow,
            integrity_only=args.integrity_only,
            accepted_sequence_drift=set(args.accept_sequence_drift),
        )
    except ElasticsearchRestError as error:
        report = {
            "checks": {
                "allow_yellow": args.allow_yellow,
                "blockers": [{"check": "collection_or_connection", "message": str(error)}],
                "ready": False,
                "warnings": [],
            },
            "target_version": TARGET_VERSION,
        }
    except Exception as error:  # noqa: BLE001 - a failed schema/config check must produce a blocking JSON report
        safe_detail = None
        if isinstance(error, (HowlerAttributeError, HowlerRuntimeError)) or (
            isinstance(error, ValueError) and not isinstance(error, ValidationError)
        ):
            safe_detail = str(error)
        message = safe_detail or (
            "Unable to load deployed Howler configuration/schema or complete verification "
            f"({type(error).__name__}); details were omitted to avoid exposing configuration values."
        )
        report = {
            "checks": {
                "allow_yellow": args.allow_yellow,
                "blockers": [
                    {
                        "check": "collection_or_connection",
                        "message": message,
                    }
                ],
                "ready": False,
                "warnings": [],
            },
            "target_version": TARGET_VERSION,
        }
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")  # noqa: T201
    return 0 if report["checks"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
