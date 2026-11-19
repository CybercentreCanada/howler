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
from decimal import Decimal, InvalidOperation
from math import ceil
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pydantic import BaseModel, ValidationError

from howler.common.exceptions import HowlerAttributeError, HowlerRuntimeError
from howler.datastore.ilm_contract import ilm_policy, shadowed_dynamic_templates
from howler.external.elasticsearch_rest import (
    NO_MIGRATION_NEEDED,
    SOURCE_STACK_VERSION,
    ElasticsearchRestClient,
    ElasticsearchRestError,
    add_connection_arguments,
    canonical_ilm_generation,
    client_from_args,
    collect_index_inventory,
    index_setting,
    is_closed_index,
    load_configured_plugins,
    primary_shard_sync_issues,
    strict_int,
    walk_deprecations,
    write_json_report,
)

TARGET_VERSION = "9.5.2"
DEFAULT_TOTAL_FIELDS_LIMIT = 1000
_COLLECTION_MODELS: tuple[tuple[str, type[BaseModel] | None], ...] = ()


def _issue(target: list[dict[str, Any]], check: str, message: str, **fields: Any) -> None:
    target.append({"check": check, "message": message, **fields})


def _collection_models() -> tuple[tuple[str, type[BaseModel] | None], ...]:
    """Use application schema finalization without constructing a datastore or reconciling Elasticsearch."""
    global _COLLECTION_MODELS
    if _COLLECTION_MODELS:
        return _COLLECTION_MODELS

    plugins = load_configured_plugins()
    from howler.datastore.howler_store import finalize_models

    _COLLECTION_MODELS = tuple(finalize_models(plugins).items())
    return _COLLECTION_MODELS


def _prefix() -> str:
    """Return the same configured index prefix as Howler's datastore."""
    from howler.common.loader import DATASTORE_INDEX_PREFIX

    return DATASTORE_INDEX_PREFIX


def _configured_ilm_policy(collection: str) -> dict[str, Any] | None:
    """Resolve the managed policy using the same configuration as Howler startup."""
    from howler.config_models import ILMIndexConfig, config
    from howler.datastore.howler_store import ILM_ENABLED_INDEXES

    global_config = config.datastore.ilm
    index_config = global_config.indices.get(collection)
    if index_config is None:
        index_config = ILMIndexConfig(enabled=collection in ILM_ENABLED_INDEXES)
    return ilm_policy(index_config, global_config) if global_config.enabled and index_config.enabled else None


def _expectations() -> dict[str, dict[str, Any]]:
    from howler.models import schema

    prefix = _prefix()
    contracts: dict[str, dict[str, Any]] = {}
    for collection, model in _collection_models():
        alias = f"{prefix}-{collection}"
        policy = _configured_ilm_policy(collection)
        contract: dict[str, Any] = {
            "alias": alias,
            "ilm": policy is not None,
            "mapping": schema.document_mapping(model),
            "model": model,
            "total_fields_limit": schema.total_fields_limit(model),
        }
        if policy is not None:
            contract["ilm_policy"] = policy
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


def _collection_indices(alias: str, ilm: bool, indices: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return configured-layout backing indices and all indices attached to the alias."""
    attached = sorted(name for name, data in indices.items() if alias in data.get("aliases", {}))
    if ilm:
        expected_layout = [name for name in indices if canonical_ilm_generation(alias, name) is not None]
    else:
        hot = f"{alias}_hot"
        expected_layout = [hot] if hot in indices else []
    backers = sorted(set(expected_layout) | set(attached))
    return backers, attached


def _configured_backing_index_names(expectations: dict[str, dict[str, Any]], indices: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for expectation in expectations.values():
        backers, attached = _collection_indices(expectation["alias"], expectation["ilm"], indices)
        names.update(backers)
        names.update(attached)
    return names


def _effective_write_indices(alias: str, attached: list[str], indices: dict[str, Any], *, ilm: bool) -> list[str]:
    # A legacy _hot alias can write implicitly. ILM needs an explicit write flag so rollover
    # keeps the old generation on the read alias instead of moving the alias to the new index.
    if not ilm and len(attached) == 1 and "is_write_index" not in indices[attached[0]]["aliases"][alias]:
        return attached
    return [name for name in attached if indices[name]["aliases"][alias].get("is_write_index") is True]


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


def _root_dynamic(mapping: dict[str, Any]) -> str:
    # ES defaults to true and can render the dynamic mode as either a boolean or a string.
    return str(mapping.get("dynamic", True)).lower()


def _source_enabled(mapping: dict[str, Any], index_data: dict[str, Any]) -> bool:
    source = mapping.get("_source", {})
    return (
        isinstance(source, dict)
        and str(source.get("enabled", True)).lower() == "true"
        and str(source.get("mode")).lower() != "disabled"
        and str(index_setting(index_data, "index.mapping.source.mode")).lower() != "disabled"
    )


def _mapping_differences(
    expected_mapping: dict[str, Any], actual_mapping: dict[str, Any]
) -> list[tuple[str, dict[str, Any], dict[str, Any] | None]]:
    expected_properties = _flatten_properties(expected_mapping.get("properties", {}))
    actual_properties = _flatten_properties(actual_mapping.get("properties", {}))
    return [
        (field, expected, actual_properties.get(field))
        for field, expected in expected_properties.items()
        if actual_properties.get(field) is None or not _mapping_matches(expected, actual_properties[field])
    ]


def _template_key(template: Any) -> str | None:
    if isinstance(template, dict) and len(template) == 1:
        name, body = next(iter(template.items()))
        if isinstance(body, dict):
            return name
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
    index: str,
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    *,
    schema_less: bool = False,
) -> None:
    definitions: dict[str, list[Any]] = {}
    for template in expected:
        name = _template_key(template)
        if name is not None:
            definitions.setdefault(name, []).append(template[name])
    duplicate_names = sorted(name for name, values in definitions.items() if len(values) > 1)
    expected = _merge_dynamic_templates(expected)
    actual = _merge_dynamic_templates(actual)
    expected_names = [_template_key(template) for template in expected]
    actual_names = [_template_key(template) for template in actual]
    expected_name_set = {name for name in expected_names if name is not None}
    invalid_templates = [name for name in (*expected_names, *actual_names) if name is None]
    expected_active_order = [name for name in expected_names if name is not None]
    actual_active_order = [name for name in actual_names if name in expected_name_set]
    expected_by_name = {name: template for template in expected if (name := _template_key(template)) is not None}
    actual_by_name = {
        name: template
        for template in actual
        if (name := _template_key(template)) is not None and name in expected_name_set
    }
    missing = sorted(name for name in expected_name_set if name not in actual_by_name)
    changed = sorted(
        name for name in expected_name_set & set(actual_by_name) if expected_by_name[name] != actual_by_name[name]
    )
    extra = {name for name in actual_names if name is not None and name not in expected_name_set}
    conflicts = shadowed_dynamic_templates(expected, actual) if extra and not invalid_templates else []
    if missing or changed or invalid_templates or actual_active_order != expected_active_order or conflicts:
        finding = {
            "check": "schema_less_dynamic_templates" if schema_less else "dynamic_templates",
            "collection": collection,
            "index": index,
            "message": "Dynamic templates are missing, changed, malformed, reordered, or shadowed.",
            "missing": missing,
            "changed": changed,
            "shadowed": [{"obsolete": obsolete, "active": active} for obsolete, active in conflicts],
            "actual_active_order": actual_active_order,
            "expected_active_order": expected_active_order,
        }
        (warnings if schema_less else blockers).append(finding)
    if duplicate_names:
        shadowed = {
            name: {
                "shadowed": definitions[name][:-1],
                "effective": definitions[name][-1],
            }
            for name in duplicate_names
        }
        _issue(
            warnings,
            "shadowed_dynamic_template_name",
            "The source contract declares duplicate dynamic-template names; Elasticsearch keeps the last "
            "definition at the first position.",
            collection=collection,
            index=index,
            names=duplicate_names,
            shadowed_definitions=shadowed,
        )
    retained = sorted(extra - {obsolete for obsolete, _ in conflicts})
    if retained:
        _issue(
            warnings,
            "obsolete_dynamic_templates",
            "Extra dynamic templates are retained; verify they belong to disabled extensions.",
            collection=collection,
            index=index,
            templates=retained,
        )


def _critical_deprecations(value: Any) -> list[dict[str, Any]]:
    return [
        {
            "path": ".".join(path),
            "message": str(issue.get("message", "Critical deprecation")),
            "details": issue.get("details"),
            "_meta": issue.get("_meta", issue.get("meta")),
        }
        for path, issue in walk_deprecations(value)
        if issue.get("level") == "critical"
    ]


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


def _empty_unwritten_index(data: dict[str, Any]) -> bool:
    return (
        data.get("doc_count") == 0
        and not primary_shard_sync_issues(data)
        and all(shard["max_seq_no"] == -1 for shard in data["primary_shards"].values())
    )


def _shard_sequence_contract(data: dict[str, Any]) -> dict[str, tuple[int, int]] | None:
    shards = data.get("primary_shards")
    if not isinstance(shards, dict) or not shards:
        return None
    result: dict[str, tuple[int, int]] = {}
    for shard_id, shard in shards.items():
        if not isinstance(shard, dict):
            return None
        doc_count = strict_int(shard.get("doc_count"))
        max_seq_no = strict_int(shard.get("max_seq_no"))
        if doc_count is None or max_seq_no is None:
            return None
        result[str(shard_id)] = (doc_count, max_seq_no)
    return result


def _ilm_age(value: Any) -> Any:
    """Compare phase and rollover ages in nanoseconds, independent of their wire units."""
    if not isinstance(value, str):
        return value
    if value == "0":
        return "0nanos"
    units = {
        "nanos": 1,
        "micros": 1000,
        "ms": 10**6,
        "s": 10**9,
        "m": 60 * 10**9,
        "h": 3600 * 10**9,
        "d": 86400 * 10**9,
    }
    match = re.fullmatch(r"(\d+)\s*(nanos|micros|ms|s|m|h|d)", value.strip(), re.IGNORECASE)
    if match is None or match[2] == "M":
        return value
    return f"{int(match[1]) * units[match[2].lower()]}nanos"


def _ilm_size(value: Any) -> int | None:
    """Read an ES ByteSizeValue: integral bytes, or up to two decimals in a larger unit, rounded up."""
    if not isinstance(value, str):
        return None
    if value in {"0", "-1"}:
        return int(value)
    match = re.fullmatch(r"([0-9.e+-]+)\s*(b|[kmgtp]b?)", value.strip().lower())
    if match is None:
        return None
    number, unit = match.groups()
    if unit == "b" and not re.fullmatch(r"[+-]?[0-9]+", number):
        return None  # ES parses bytes as a long, not a decimal.
    try:
        amount = Decimal(number)
    except InvalidOperation:
        return None
    max_bytes = 2**63 - 1
    if amount > max_bytes or amount < (-1 if unit == "b" else 0) or int(amount.as_tuple().exponent) < -2:
        return None
    size = ceil(amount * 1024 ** "bkmgtp".index(unit[0]))
    return size if size <= max_bytes else None


def _managed_policy_phases(policy: Any) -> dict[str, Any] | None:
    """Normalize the managed behavior; policy metadata and GET response bookkeeping are not actions."""
    phases = deepcopy(policy.get("phases")) if isinstance(policy, dict) else None
    if not isinstance(phases, dict):
        return None
    for phase in phases.values():
        if not isinstance(phase, dict):
            return None
        phase["min_age"] = _ilm_age(phase.get("min_age", "0ms"))
        actions = phase.get("actions")
        rollover = actions.get("rollover") if isinstance(actions, dict) else None
        if isinstance(rollover, dict):
            if "max_age" in rollover:
                rollover["max_age"] = _ilm_age(rollover["max_age"])
            if "max_primary_shard_size" in rollover:
                size = _ilm_size(rollover["max_primary_shard_size"])
                if size is None:
                    return None
                rollover["max_primary_shard_size"] = size
    return phases


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
        _issue(
            blockers,
            "ilm_template_missing",
            "The configured ILM composable index template is missing.",
            collection=collection,
            template=template_name,
        )
    else:
        actual_patterns = live_template.get("index_patterns", [])
        if actual_patterns != [f"{alias}-*"]:
            _issue(
                blockers,
                "ilm_template_patterns",
                "ILM template index_patterns do not match the configured collection.",
                collection=collection,
                expected=[f"{alias}-*"],
                actual=actual_patterns,
            )
        actual_template = live_template.get("template", {})
        actual_settings = {"settings": actual_template.get("settings", {})}
        expected_policy = f"{alias}_policy"
        for setting_name in (
            "index.lifecycle.name",
            "index.lifecycle.rollover_alias",
            "index.mapping.total_fields.limit",
        ):
            actual_value = index_setting(actual_settings, setting_name)
            wanted = expected_policy if setting_name == "index.lifecycle.name" else alias
            if setting_name == "index.mapping.total_fields.limit":
                wanted = expectation["total_fields_limit"]
                try:
                    actual_value = int(actual_value)
                except (TypeError, ValueError):
                    actual_value = None
            if actual_value != wanted:
                _issue(
                    blockers,
                    "ilm_template_setting",
                    "ILM template settings do not match the finalized Howler contract.",
                    collection=collection,
                    setting=setting_name,
                    expected=wanted,
                    actual=actual_value,
                )

        actual_mapping = actual_template.get("mappings", {})
        expected_mapping = expected_template.get("mappings", {})
        if not _source_enabled(actual_mapping, actual_settings):
            _issue(
                blockers,
                "ilm_template_source_disabled",
                "The ILM template must keep _source enabled for future generations.",
                collection=collection,
                template=template_name,
            )
        if _root_dynamic(actual_mapping) != _root_dynamic(expected_mapping):
            _issue(
                blockers,
                "ilm_template_mapping",
                "ILM template mapping-level dynamic behavior differs from the schema.",
                collection=collection,
            )
        for field, expected_definition, actual_definition in _mapping_differences(expected_mapping, actual_mapping):
            _issue(
                blockers,
                "ilm_template_property",
                "ILM template does not contain the expected property definition.",
                collection=collection,
                property=field,
                expected=expected_definition,
                actual=actual_definition,
            )
        _template_checks(
            collection,
            template_name,
            expected_mapping.get("dynamic_templates", []),
            actual_mapping.get("dynamic_templates", []),
            blockers,
            warnings,
            schema_less=expectation["model"] is None,
        )

    policy = inventory.get("ilm_policies", {}).get(collection)
    expected_policy_body = expectation["ilm_policy"]
    expected_phases = _managed_policy_phases(expected_policy_body)
    if expected_phases is None or _managed_policy_phases(policy) != expected_phases:
        _issue(
            blockers,
            "ilm_policy_phases",
            "ILM policy phases, actions or thresholds differ from the configured Howler policy.",
            collection=collection,
            policy=f"{alias}_policy",
            expected=expected_policy_body["phases"],
            actual=policy.get("phases") if isinstance(policy, dict) else None,
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
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
) -> dict[str, dict[str, dict[str, int]]] | None:
    """Return per-shard document/sequence drift, or None when shard layouts differ."""
    if before.keys() != after.keys():
        return None

    changes: dict[str, dict[str, dict[str, int]]] = {}
    for shard_id in sorted(before):
        before_count, before_max_seq_no = before[shard_id]
        after_count, after_max_seq_no = after[shard_id]
        if before_count != after_count or before_max_seq_no != after_max_seq_no:
            changes[shard_id] = {
                "baseline": {"doc_count": before_count, "max_seq_no": before_max_seq_no},
                "current": {"doc_count": after_count, "max_seq_no": after_max_seq_no},
            }
    return changes


def _post_baseline_index_contract(
    collection: str,
    alias: str,
    kind: str,
    index: str,
    candidates: list[str],
    attached: list[str],
    indices: dict[str, Any],
    blockers: list[dict[str, Any]],
    *,
    ilm: bool,
) -> bool:
    """Validate the common empty, single-alias, single-write-index post-baseline contract."""
    is_new_collection = kind == "new_collection"

    def check_empty() -> bool:
        if all(_empty_unwritten_index(indices[name]) for name in candidates):
            return True
        fields = {"indices": candidates} if is_new_collection else {"index": index}
        _issue(
            blockers,
            f"baseline_{kind}_nonempty",
            "A collection initialized after the baseline must still be empty and unwritten."
            if is_new_collection
            else "A rollover index created after the baseline must be empty and unwritten.",
            collection=collection,
            **fields,
        )
        return False

    if not is_new_collection and not check_empty():
        return False

    aliases = _alias_contract(indices[index])
    if set(aliases) != {alias}:
        _issue(
            blockers,
            f"baseline_{kind}_aliases",
            "A newly initialized index may carry only its configured Howler alias."
            if is_new_collection
            else "A rollover generation may carry only its configured Howler alias.",
            collection=collection,
            index=index,
            aliases=aliases,
        )
        return False

    write_indices = _effective_write_indices(alias, attached, indices, ilm=ilm)
    if write_indices != [index]:
        _issue(
            blockers,
            f"baseline_{kind}_write_index",
            "Newly initialized collection must have one configured write index."
            if is_new_collection
            else "The new rollover generation must be the only write index.",
            collection=collection,
            expected=index if is_new_collection else [index],
            actual=write_indices,
        )
        return False
    return check_empty() if is_new_collection else True


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
        _issue(
            blockers,
            "baseline_index_prefix",
            "Baseline index_prefix must exactly match the deployed datastore prefix.",
            expected=prefix,
            actual=baseline_prefix,
        )
        return

    old_indices = _baseline_indices(baseline, prefix)
    new_indices = _baseline_indices({"inventory": current}, prefix)
    if not old_indices:
        _issue(
            blockers,
            "baseline_no_prefix_indices",
            f"Baseline contains no Howler indices using configured prefix {prefix!r}.",
        )
    old_names, new_names = set(old_indices), set(new_indices)
    missing_names = old_names - new_names
    if missing_names:
        _issue(
            blockers,
            "baseline_index_missing",
            "Every baseline Howler index must remain present; a missing index may indicate data loss.",
            indices=sorted(missing_names),
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
                canonical = [name for name in current_new if canonical_ilm_generation(alias, name) is not None]
                expected_write = canonical[0] if len(canonical) == 1 else None
                valid_layout = len(canonical) == 1 and len(current_new) == len(canonical) == len(current_backers)
            else:
                hot = f"{alias}_hot"
                expected_write = hot if len(current_backers) == 1 and current_backers[0] == hot else None
                valid_layout = current_new == [hot] and current_backers == [hot]
            if not valid_layout or expected_write is None or current_attached != [expected_write]:
                _issue(
                    blockers,
                    "baseline_new_collection_layout",
                    "A collection initialized after the baseline must have exactly its configured empty "
                    "layout and alias.",
                    collection=collection,
                    indices=current_new,
                )
                continue
            if not _post_baseline_index_contract(
                collection,
                alias,
                "new_collection",
                expected_write,
                current_new,
                current_attached,
                new_indices,
                blockers,
                ilm=ilm,
            ):
                continue
            permitted_new.update(current_new)
            _issue(
                warnings,
                "baseline_new_empty_collection",
                "A configured collection absent from the baseline was initialized empty after it.",
                collection=collection,
                indices=current_new,
            )
            continue

        if ilm and old_collection_present:
            new_generations = [name for name in current_new if canonical_ilm_generation(alias, name) is not None]
            baseline_write_indices = _effective_write_indices(alias, old_attached, old_indices, ilm=True)
            baseline_generation = (
                canonical_ilm_generation(alias, baseline_write_indices[0]) if len(baseline_write_indices) == 1 else None
            )
            if new_generations:
                new_generation_number = canonical_ilm_generation(alias, new_generations[0])
                if (
                    len(new_generations) != 1
                    or baseline_generation is None
                    or new_generation_number is None
                    or new_generation_number <= baseline_generation
                ):
                    _issue(
                        blockers,
                        "baseline_rollover_generation",
                        "At most one new canonical ILM generation above the baseline write index is allowed.",
                        collection=collection,
                        indices=new_generations,
                    )
                    continue
                new_generation = new_generations[0]
                if not _post_baseline_index_contract(
                    collection,
                    alias,
                    "rollover",
                    new_generation,
                    [new_generation],
                    current_attached,
                    new_indices,
                    blockers,
                    ilm=True,
                ):
                    continue
                permitted_new.add(new_generation)
                rollover_old_writes[baseline_write_indices[0]] = alias
                _issue(
                    warnings,
                    "baseline_ilm_rollover",
                    "One empty ILM generation rolled over during the quiesced baseline window.",
                    collection=collection,
                    index=new_generation,
                )

    unexplained_new = new_names - old_names - permitted_new
    unexplained_new -= {name for name, data in new_indices.items() if is_closed_index(data)}
    if unexplained_new:
        _issue(
            blockers,
            "baseline_unexpected_indices",
            "New Howler-prefixed indices are not an allowed empty initialization or single-generation rollover.",
            indices=sorted(unexplained_new),
        )

    common_names = old_names & new_names
    unknown_acceptances = accepted_sequence_drift - common_names
    for index in sorted(unknown_acceptances):
        _issue(
            warnings,
            "unknown_sequence_drift_acceptance",
            "No baseline/current index pair matched this acceptance; no drift was accepted.",
            index=index,
        )

    for name in sorted(common_names):
        before, after = old_indices[name], new_indices[name]
        if before.get("uuid") is None or after.get("uuid") is None:
            _issue(blockers, "baseline_uuid", "Baseline or current index UUID is missing.", index=name)
        elif before["uuid"] != after["uuid"]:
            _issue(
                blockers,
                "baseline_uuid",
                "Index UUID changed; this may indicate reindexing or index replacement.",
                index=name,
                baseline=before["uuid"],
                current=after["uuid"],
            )
        aliases_match = (
            _allowed_alias_flip(before, after, rollover_old_writes[name])
            if name in rollover_old_writes
            else _alias_contract(before) == _alias_contract(after)
        )
        if not aliases_match:
            _issue(
                blockers,
                "baseline_aliases",
                "Alias membership or is_write_index changed after the baseline.",
                index=name,
                baseline=_alias_contract(before),
                current=_alias_contract(after),
            )
        if is_closed_index(before) or is_closed_index(after):
            continue
        accepted = name in accepted_sequence_drift
        before_count, after_count = before.get("doc_count"), after.get("doc_count")
        if (
            isinstance(before_count, bool)
            or not isinstance(before_count, int)
            or isinstance(after_count, bool)
            or not isinstance(after_count, int)
        ):
            _issue(blockers, "baseline_doc_count", "Baseline or current primary document count is missing.", index=name)
        elif before_count != after_count and not accepted:
            _issue(
                blockers,
                "baseline_doc_count",
                "Primary document count changed after the quiesced baseline.",
                index=name,
                baseline=before_count,
                current=after_count,
            )
        before_shards = _shard_sequence_contract(before)
        after_shards = _shard_sequence_contract(after)
        if before_shards is None or after_shards is None:
            _issue(
                blockers,
                "baseline_sequence_numbers",
                "Baseline or current primary-shard stats are incomplete.",
                index=name,
            )
        else:
            baseline_sync = primary_shard_sync_issues(before)
            if baseline_sync:
                _issue(
                    blockers,
                    "sequence_checkpoint_unsynced",
                    "Baseline primary sequence stats are incomplete or unsynced; after quiescing writes, "
                    "flush, wait for the global checkpoint to catch up, and capture a new baseline.",
                    index=name,
                    baseline_issues=baseline_sync,
                )
                continue

            if primary_shard_sync_issues(after):
                continue  # Already reported for the current inventory; drift acceptance requires complete evidence.
            drift = _sequence_drift(before_shards, after_shards)
            if drift is None:
                _issue(
                    blockers,
                    "baseline_sequence_numbers",
                    "Primary shard layout changed after the quiesced baseline.",
                    index=name,
                    baseline=before_shards,
                    current=after_shards,
                )
                continue

            decreases = sorted(
                shard_id for shard_id in before_shards if after_shards[shard_id][1] < before_shards[shard_id][1]
            )
            if decreases:
                _issue(
                    blockers,
                    "baseline_sequence_decrease",
                    "Primary max_seq_no decreased after the baseline; this may indicate rolled-back writes.",
                    index=name,
                    shards=decreases,
                )
            elif drift and accepted:
                _issue(
                    warnings,
                    "baseline_sequence_drift_accepted",
                    "The cutover lead explicitly accepted primary document-count/max_seq_no drift for this "
                    "index; record the decision in the change record.",
                    index=name,
                    shards=drift,
                )
            elif drift:
                _issue(
                    blockers,
                    "baseline_sequence_numbers",
                    "Per-shard document counts or max_seq_no changed after the quiesced baseline.",
                    index=name,
                    shards=drift,
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
        _issue(warnings, "cluster_health_override", "Yellow health was explicitly accepted using --allow-yellow.")
    elif health == "yellow":
        _issue(
            blockers,
            "cluster_health",
            "Cluster health is yellow; rerun with --allow-yellow only after operator review.",
        )
    else:
        _issue(
            blockers,
            "cluster_health",
            "Cluster health must be green"
            f"{' or explicitly allowed yellow' if allow_yellow else ''}; found {health or 'unknown'}.",
        )
    if health_data.get("timed_out") is True:
        _issue(blockers, "cluster_health_timeout", "Cluster health request timed out; its result is incomplete.")

    root_version = inventory.get("version", {}).get("version", {}).get("number")
    node_data = inventory.get("nodes", {}).get("nodes", {})
    node_versions = {node.get("name", node_id): node.get("version") for node_id, node in node_data.items()}
    if not node_versions:
        _issue(blockers, "node_versions", "No Elasticsearch nodes or node versions were returned.")
    for node, version in sorted(node_versions.items()):
        if version != TARGET_VERSION:
            _issue(
                blockers,
                "node_version",
                f"Every node must report {TARGET_VERSION}; found {version or 'unknown'}.",
                node=node,
            )
    if root_version != TARGET_VERSION:
        _issue(
            blockers,
            "cluster_version",
            f"Cluster info must report {TARGET_VERSION}; found {root_version or 'unknown'}.",
        )

    feature_status = inventory.get("feature_upgrade_status", {}).get("migration_status")
    if feature_status in {"IN_PROGRESS", "ERROR"}:
        _issue(
            blockers,
            "system_features",
            f"System feature migration is {feature_status}; resolve or stop the migration before cutover.",
        )
    elif feature_status == "MIGRATION_NEEDED":
        _issue(
            warnings,
            "es10_readiness_system_features",
            "System-feature migration is Elasticsearch 10 preparation; schedule and rehearse it separately.",
        )
    elif feature_status != NO_MIGRATION_NEEDED:
        _issue(
            warnings,
            "es10_readiness_system_features",
            f"Unrecognized system-feature status {feature_status or 'missing'}; "
            "confirm future-major readiness separately.",
        )
    critical = _critical_deprecations(inventory.get("deprecations", {}))
    es10_readiness = [issue for issue in critical if _is_es10_readiness(issue)]
    cutover_critical = [issue for issue in critical if not _is_es10_readiness(issue)]
    if es10_readiness:
        _issue(
            warnings,
            "es10_readiness",
            "These next-major reindex/readiness deprecations are expected after an 8.x-to-9.x upgrade.",
            resources=es10_readiness,
        )
    if cutover_critical:
        _issue(
            blockers,
            "critical_deprecations",
            f"Resolve {len(cutover_critical)} critical deprecation(s) that affect 9.x operation.",
            resources=cutover_critical,
        )

    indices = inventory.get("indices", {})
    mappings = inventory.get("mappings", {})
    current_prefix = inventory.get("index_prefix", _prefix())
    baseline_indices = _baseline_indices(baseline, current_prefix) if baseline is not None else {}
    configured_backers = _configured_backing_index_names(expectations, indices)
    configured_backers.update(_configured_backing_index_names(expectations, baseline_indices))
    closed_current = {name for name, data in indices.items() if is_closed_index(data)}
    closed_baseline = {name for name, data in baseline_indices.items() if is_closed_index(data)}
    for index in sorted(closed_current | closed_baseline):
        if index in configured_backers or index in baseline_indices:
            _issue(
                blockers,
                "closed_howler_index",
                "A closed index backs a configured collection or is present in the baseline; reopen or archive "
                "it before cutover.",
                index=index,
            )
        else:
            _issue(
                warnings,
                "closed_howler_index",
                "Closed Howler-prefixed index is not configured and is absent from the baseline; review it.",
                index=index,
            )

    for index, data in sorted(indices.items()):
        if not index.startswith(f"{current_prefix}-") or is_closed_index(data):
            continue
        sync_issues = primary_shard_sync_issues(data)
        if sync_issues:
            _issue(
                blockers,
                "sequence_checkpoint_unsynced",
                "Primary sequence stats are incomplete or unsynced; wait for cluster health to be green, "
                "then rerun the verifier.",
                index=index,
                shards=sync_issues,
            )
    if integrity_only:
        if baseline is None:
            _issue(blockers, "baseline_required", "--integrity-only requires --baseline.")
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
                _issue(
                    blockers,
                    "collection_missing_after_baseline",
                    "A configured collection present at baseline is now missing.",
                    collection=collection,
                    alias=alias,
                )
            else:
                _issue(
                    blockers,
                    "collection_not_initialized",
                    "Collection is not initialized; run the separate collection initializer before full verification.",
                    collection=collection,
                    alias=alias,
                )
            continue
        if ilm:
            _check_ilm_template_and_policy(collection, expectation, inventory, blockers, warnings)
        if not attached:
            _issue(
                blockers,
                "alias_missing",
                "Collection alias has no backing indices.",
                collection=collection,
                alias=alias,
            )
        write_indices = _effective_write_indices(alias, attached, indices, ilm=ilm)
        if len(write_indices) != 1:
            _issue(
                blockers,
                "alias_write_index",
                f"Alias must resolve to exactly one write index; found {len(write_indices)}.",
                collection=collection,
                alias=alias,
                attached_indices=attached,
                write_indices=write_indices,
            )
        if ilm:
            canonical_backers = [name for name in backers if canonical_ilm_generation(alias, name) is not None]
            if not canonical_backers:
                _issue(
                    blockers,
                    "ilm_backing_indices",
                    "ILM collection has no canonical six-digit backing index.",
                    collection=collection,
                    alias=alias,
                )
            if attached != canonical_backers:
                _issue(
                    blockers,
                    "ilm_alias_members",
                    "The read alias must include every canonical ILM generation and no other indices.",
                    collection=collection,
                    alias=alias,
                    missing=sorted(set(canonical_backers) - set(attached)),
                    unexpected=sorted(set(attached) - set(canonical_backers)),
                )
            expected_write = canonical_backers[-1] if canonical_backers else None
            if expected_write is not None and write_indices != [expected_write]:
                _issue(
                    blockers,
                    "ilm_write_index",
                    "The latest canonical ILM generation must have is_write_index explicitly set to true.",
                    collection=collection,
                    alias=alias,
                    expected=expected_write,
                    actual=write_indices,
                )
        else:
            hot = f"{alias}_hot"
            if hot not in indices:
                _issue(
                    blockers,
                    "legacy_hot_index",
                    "Configured legacy _hot index is missing.",
                    collection=collection,
                    index=hot,
                )
            if attached != [hot] or write_indices != [hot]:
                _issue(
                    blockers,
                    "legacy_write_index",
                    "The legacy alias must write to its _hot index.",
                    collection=collection,
                    alias=alias,
                    expected=[hot],
                    actual=write_indices,
                )

        schema_less = expectation["model"] is None
        expected_mapping = expectation["mapping"]
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
                blockers.append(finding)  # Even schema-less backers must have a verifiable _source.
                continue
            live_mapping = mappings[index].get("mappings", mappings[index])
            if not _source_enabled(live_mapping, index_data):
                _issue(
                    blockers,
                    "mapping_source_disabled",
                    "Backing index must keep _source enabled to retrieve stored documents.",
                    collection=collection,
                    index=index,
                )
            if _root_dynamic(live_mapping) != _root_dynamic(expected_mapping):
                _issue(
                    blockers,
                    "mapping_dynamic",
                    "Backing index root dynamic behavior differs from the finalized Howler schema.",
                    collection=collection,
                    index=index,
                    expected=_root_dynamic(expected_mapping),
                    actual=_root_dynamic(live_mapping),
                )
            for path, expected_definition, actual_definition in _mapping_differences(expected_mapping, live_mapping):
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
                index,
                expected_templates,
                live_mapping.get("dynamic_templates", []),
                blockers,
                warnings,
                schema_less=schema_less,
            )
            limit = index_setting(index_data, "index.mapping.total_fields.limit")
            expected_limit = expectation["total_fields_limit"]
            try:
                actual_limit = int(limit) if limit is not None else DEFAULT_TOTAL_FIELDS_LIMIT
            except (TypeError, ValueError):
                actual_limit = 0
            actual_mapping_fields = _mapped_field_count(live_mapping)
            is_write_index = index in write_indices
            if is_write_index and actual_limit < expected_limit:
                _issue(
                    blockers,
                    "total_fields_limit",
                    f"Mapping field limit must be at least {expected_limit}.",
                    collection=collection,
                    index=index,
                    expected_minimum=expected_limit,
                    actual=limit,
                )

            elif actual_limit < actual_mapping_fields:
                _issue(
                    blockers,
                    "total_fields_limit_below_mapped_fields",
                    "Index field limit is below its actual mapped field count.",
                    collection=collection,
                    index=index,
                    actual_limit=actual_limit,
                    mapped_fields=actual_mapping_fields,
                )
            elif actual_limit < expected_limit:
                _issue(
                    warnings,
                    "total_fields_limit_legacy_lower",
                    "Existing backing index has a lower-than-current schema limit but can hold its current mapping.",
                    collection=collection,
                    index=index,
                    actual_limit=actual_limit,
                    expected_minimum=expected_limit,
                    mapped_fields=actual_mapping_fields,
                )

            if ilm:
                lifecycle_name = index_setting(index_data, "index.lifecycle.name")
                rollover_alias = index_setting(index_data, "index.lifecycle.rollover_alias")
                if lifecycle_name != policy_name or rollover_alias != alias:
                    _issue(
                        blockers,
                        "ilm_settings",
                        "Backing index lifecycle policy or rollover alias settings are incorrect.",
                        collection=collection,
                        index=index,
                        expected_policy=policy_name,
                        actual_policy=lifecycle_name,
                        expected_rollover_alias=alias,
                        actual_rollover_alias=rollover_alias,
                    )
                explain = inventory.get("ilm_explain", {}).get(index, {})
                if explain.get("managed") is not True:
                    _issue(
                        blockers,
                        "ilm_managed",
                        "ILM-backed collection index is not managed by ILM.",
                        collection=collection,
                        index=index,
                    )
                if explain.get("policy") != policy_name:
                    _issue(
                        blockers,
                        "ilm_policy",
                        "ILM explain reports an unexpected or missing policy.",
                        collection=collection,
                        index=index,
                        expected=policy_name,
                        actual=explain.get("policy"),
                    )
                step_info = explain.get("step_info")
                has_step_error = isinstance(step_info, dict) and bool(step_info.get("type") or step_info.get("reason"))
                if str(explain.get("step", "")).upper() == "ERROR" or has_step_error:
                    _issue(
                        blockers,
                        "ilm_step",
                        "ILM explain reports an ERROR step or step information.",
                        collection=collection,
                        index=index,
                        step=explain.get("step"),
                        step_info=explain.get("step_info"),
                    )

        caps_result = inventory.get("field_caps", {}).get(collection, {})
        has_caps = isinstance(caps_result, dict) and isinstance(caps_result.get("fields"), dict)
        caps = caps_result["fields"] if has_caps else {}
        schema_paths = set(_flatten_properties(expected_mapping.get("properties", {})))
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
        has_closed_backer = any(is_closed_index(indices.get(index, {})) for index in backers)
        if backers and not has_caps and not has_closed_backer:
            _issue(
                blockers,
                "field_caps_missing",
                "No field_caps result was collected for this collection.",
                collection=collection,
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
        _issue(
            blockers,
            "sequence_drift_acceptance_requires_baseline",
            "--accept-sequence-drift requires a validated --baseline report.",
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
    indices = collect_index_inventory(client, prefix, scoped=True)
    health = client.get("/_cluster/health")

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
            explain = client.get_optional(
                f"/{quote(alias, safe='-_.')}-*/_ilm/explain",
                {"only_managed": "false"},
            )
            if explain is not None:
                ilm_explain.update(explain.get("indices", explain))
            template_name = f"{alias}_template"
            policy_name = f"{alias}_policy"
            response = client.get_optional(f"/_index_template/{quote(template_name, safe='-_.')}")
            if response is None:
                ilm_templates[collection] = None
            else:
                template_list = response.get("index_templates", [])
                ilm_templates[collection] = next(
                    (
                        item.get("index_template")
                        for item in template_list
                        if item.get("name") == template_name and isinstance(item.get("index_template"), dict)
                    ),
                    None,
                )
            response = client.get_optional(f"/_ilm/policy/{quote(policy_name, safe='-_.')}")
            ilm_policies[collection] = response.get(policy_name, {}).get("policy") if response is not None else None
        if attached and not any(is_closed_index(indices.get(name, {})) for name in attached):
            field_caps[collection] = client.get(f"/{quote(alias, safe='-_.')}/_field_caps", {"fields": "*"})

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


def _read_baseline(  # noqa: C901
    path: Path | None, parser: argparse.ArgumentParser
) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        parser.error(f"Cannot read baseline JSON: {error}")
    if not isinstance(value, dict):
        parser.error("Baseline must be a preflight report containing inventory.indices.")
    inventory = value.get("inventory")
    checks = value.get("checks")
    if not isinstance(inventory, dict) or not isinstance(inventory.get("indices"), dict):
        parser.error("Baseline must be a preflight report containing inventory.indices.")
    version_data = inventory.get("version")
    if not isinstance(version_data, dict) or not isinstance(checks, dict):
        parser.error("Baseline must include inventory.version and checks.ready.")
    if value.get("source_stack_version") != SOURCE_STACK_VERSION:
        parser.error(f"Baseline source_stack_version must be exactly {SOURCE_STACK_VERSION}.")
    if value.get("baseline_capture") is not True:
        parser.error("Baseline must be produced by preflight with --baseline-capture.")
    cluster_version = version_data.get("version")
    baseline_version = cluster_version.get("number") if isinstance(cluster_version, dict) else None
    if baseline_version != SOURCE_STACK_VERSION:
        parser.error(f"Baseline inventory.version.number must be exactly {SOURCE_STACK_VERSION}.")
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
    add_connection_arguments(parser)
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
    args = parser.parse_args()
    if args.integrity_only and args.baseline is None:
        parser.error("--integrity-only requires --baseline.")
    if args.accept_sequence_drift and args.baseline is None:
        parser.error("--accept-sequence-drift requires --baseline.")
    baseline = _read_baseline(args.baseline, parser)
    client = client_from_args(args, parser)
    report: dict[str, Any]
    try:
        report = build_report(
            client,
            baseline=baseline,
            allow_yellow=args.allow_yellow,
            integrity_only=args.integrity_only,
            accepted_sequence_drift=set(args.accept_sequence_drift),
        )
    except Exception as error:  # noqa: BLE001 - a failed schema/config check must produce a blocking JSON report
        if isinstance(error, ElasticsearchRestError):
            message = str(error)
        else:
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
    write_json_report(report, args.output)
    return 0 if report["checks"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
