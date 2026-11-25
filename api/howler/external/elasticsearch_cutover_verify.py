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
from howler.datastore.ilm_contract import ilm_policy, normalized_field_mapping, shadowed_dynamic_templates
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
    load_configured_plugins,
    primary_shard_sync_issues,
    strict_int,
    walk_deprecations,
    write_json_report,
)

TARGET_VERSION = "9.5.2"
DEFAULT_TOTAL_FIELDS_LIMIT = 1000
_COLLECTION_MODELS: tuple[tuple[str, type[BaseModel] | None], ...] = ()


def _collection_models() -> tuple[tuple[str, type[BaseModel] | None], ...]:
    global _COLLECTION_MODELS
    if not _COLLECTION_MODELS:
        plugins = load_configured_plugins()
        from howler.datastore.howler_store import finalize_models

        _COLLECTION_MODELS = tuple(finalize_models(plugins).items())
    return _COLLECTION_MODELS


def _prefix() -> str:
    from howler.common.loader import DATASTORE_INDEX_PREFIX

    return DATASTORE_INDEX_PREFIX


def _configured_ilm_policy(collection: str) -> dict[str, Any] | None:
    from howler.config_models import ILMIndexConfig, config
    from howler.datastore.howler_store import ILM_ENABLED_INDEXES

    global_cfg = config.datastore.ilm
    index_cfg = global_cfg.indices.get(collection) or ILMIndexConfig(enabled=collection in ILM_ENABLED_INDEXES)
    return ilm_policy(index_cfg, global_cfg) if global_cfg.enabled and index_cfg.enabled else None


def _collection_shards_replicas(collection: str) -> tuple[int, int]:
    replicas = int(
        os.environ.get(f"ELASTIC_{collection.upper()}_REPLICAS", os.environ.get("ELASTIC_DEFAULT_REPLICAS", 0))
    )
    shards = int(os.environ.get(f"ELASTIC_{collection.upper()}_SHARDS", os.environ.get("ELASTIC_DEFAULT_SHARDS", 1)))
    return shards, replicas


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
            shards, replicas = _collection_shards_replicas(collection)
            contract["ilm_policy"] = policy
            contract["ilm_template"] = schema.ilm_template_body(
                model, shards=shards, replicas=replicas, policy_name=f"{alias}_policy", rollover_alias=alias
            )
        contracts[collection] = contract
    return contracts


def _collection_indices(alias: str, ilm: bool, indices: dict[str, Any]) -> tuple[list[str], list[str]]:
    attached = sorted(name for name, data in indices.items() if alias in data.get("aliases", {}))
    if ilm:
        expected = [name for name in indices if canonical_ilm_generation(alias, name) is not None]
    else:
        hot = f"{alias}_hot"
        expected = [hot] if hot in indices else []
    return sorted(set(expected) | set(attached)), attached


def _configured_backing_index_names(expectations: dict[str, dict[str, Any]], indices: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for expectation in expectations.values():
        backers, attached = _collection_indices(expectation["alias"], expectation["ilm"], indices)
        names.update(backers, attached)
    return names


def _effective_write_indices(alias: str, attached: list[str], indices: dict[str, Any], *, ilm: bool) -> list[str]:
    # A legacy _hot alias can write implicitly; ILM requires an explicit is_write_index flag.
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
    def count_tree(properties: Any) -> int:
        if not isinstance(properties, dict):
            return 0
        return sum(
            1 + count_tree(body.get("properties")) + count_tree(body.get("fields"))
            for body in properties.values()
            if isinstance(body, dict)
        )

    return count_tree(mapping.get("properties")) + count_tree(mapping.get("runtime"))


def _root_dynamic(mapping: dict[str, Any]) -> str:
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
    expected_props = _flatten_properties(expected_mapping.get("properties", {}))
    actual_props = _flatten_properties(actual_mapping.get("properties", {}))
    return [
        (field, expected, actual_props.get(field))
        for field, expected in expected_props.items()
        if (actual := actual_props.get(field)) is None
        or normalized_field_mapping(expected) != normalized_field_mapping(actual)
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
        if (name := _template_key(template)) is not None:
            definitions.setdefault(name, []).append(template[name])
    duplicate_names = sorted(name for name, values in definitions.items() if len(values) > 1)

    expected = _merge_dynamic_templates(expected)
    actual = _merge_dynamic_templates(actual)
    expected_names = [_template_key(t) for t in expected]
    actual_names = [_template_key(t) for t in actual]
    expected_set = {name for name in expected_names if name is not None}
    invalid = [name for name in (*expected_names, *actual_names) if name is None]
    expected_order = [name for name in expected_names if name is not None]
    actual_order = [name for name in actual_names if name in expected_set]
    expected_by_name = {name: t for t in expected if (name := _template_key(t)) is not None}
    actual_by_name = {name: t for t in actual if (name := _template_key(t)) is not None and name in expected_set}
    missing = sorted(expected_set - set(actual_by_name))
    changed = sorted(
        name for name in expected_set & set(actual_by_name) if expected_by_name[name] != actual_by_name[name]
    )
    extra = {name for name in actual_names if name is not None and name not in expected_set}
    conflicts = shadowed_dynamic_templates(expected, actual) if extra and not invalid else []

    if missing or changed or invalid or actual_order != expected_order or conflicts:
        add_issue(
            warnings if schema_less else blockers,
            "schema_less_dynamic_templates" if schema_less else "dynamic_templates",
            "Dynamic templates are missing, changed, malformed, reordered, or shadowed.",
            collection=collection,
            index=index,
            missing=missing,
            changed=changed,
            shadowed=[{"obsolete": old, "active": active} for old, active in conflicts],
            actual_active_order=actual_order,
            expected_active_order=expected_order,
        )
    if duplicate_names:
        add_issue(
            warnings,
            "shadowed_dynamic_template_name",
            "The source contract declares duplicate dynamic-template names; Elasticsearch keeps the last "
            "definition at the first position.",
            collection=collection,
            index=index,
            names=duplicate_names,
            shadowed_definitions={
                name: {"shadowed": definitions[name][:-1], "effective": definitions[name][-1]}
                for name in duplicate_names
            },
        )
    retained = sorted(extra - {old for old, _ in conflicts})
    if retained:
        add_issue(
            warnings,
            "obsolete_dynamic_templates",
            "Extra dynamic templates are retained; verify they belong to disabled extensions.",
            collection=collection,
            index=index,
            templates=retained,
        )


def _check_mapping_contract(
    collection: str,
    target: str,
    expected_mapping: dict[str, Any],
    actual_mapping: dict[str, Any],
    actual_settings: dict[str, Any],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    *,
    schema_less: bool = False,
    is_template: bool = False,
) -> None:
    if not _source_enabled(actual_mapping, actual_settings):
        scope = {"template": target} if is_template else {"index": target}
        add_issue(
            blockers,
            "ilm_template_source_disabled" if is_template else "mapping_source_disabled",
            "The ILM template must keep _source enabled for future generations."
            if is_template
            else "Backing index must keep _source enabled to retrieve stored documents.",
            collection=collection,
            **scope,
        )
    if _root_dynamic(actual_mapping) != _root_dynamic(expected_mapping):
        extra = (
            {}
            if is_template
            else {
                "index": target,
                "expected": _root_dynamic(expected_mapping),
                "actual": _root_dynamic(actual_mapping),
            }
        )
        add_issue(
            blockers,
            "ilm_template_mapping" if is_template else "mapping_dynamic",
            "ILM template mapping-level dynamic behavior differs from the schema."
            if is_template
            else "Backing index root dynamic behavior differs from the finalized Howler schema.",
            collection=collection,
            **extra,
        )
    for field, expected_def, actual_def in _mapping_differences(expected_mapping, actual_mapping):
        if is_template:
            add_issue(
                blockers,
                "ilm_template_property",
                "ILM template does not contain the expected property definition.",
                collection=collection,
                property=field,
                expected=expected_def,
                actual=actual_def,
            )
            continue
        prefix = "schema_less_" if schema_less else ""
        kind = "missing" if actual_def is None else "mismatch"
        prop_extra: dict[str, Any] = {} if actual_def is None else {"expected": expected_def, "actual": actual_def}
        add_issue(
            warnings if schema_less else blockers,
            f"{prefix}mapping_property_{kind}",
            "Expected mapping property is missing."
            if actual_def is None
            else "Live property mapping differs from the finalized Howler schema.",
            collection=collection,
            index=target,
            property=field,
            **prop_extra,
        )
    _template_checks(
        collection,
        target,
        expected_mapping.get("dynamic_templates", []),
        actual_mapping.get("dynamic_templates", []),
        blockers,
        warnings,
        schema_less=schema_less,
    )


def _contains_reindex_required(value: Any) -> bool:
    if isinstance(value, dict):
        return value.get("reindex_required") is True or any(_contains_reindex_required(v) for v in value.values())
    if isinstance(value, list):
        return any(_contains_reindex_required(item) for item in value)
    return False


def _is_es10_readiness(issue: dict[str, Any]) -> bool:
    message = issue.get("message", "").lower()
    return (
        _contains_reindex_required(issue.get("details"))
        or _contains_reindex_required(issue.get("_meta"))
        or message.startswith(("old index with a compatibility version", "old data stream"))
    )


def _baseline_indices(report: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {
        name: data
        for name, data in report.get("inventory", {}).get("indices", {}).items()
        if name.startswith(f"{prefix}-")
    }


def _alias_contract(data: dict[str, Any]) -> dict[str, Any]:
    aliases = data.get("aliases", {})
    return {name: deepcopy(val) for name, val in sorted(aliases.items())} if isinstance(aliases, dict) else {}


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
        doc_count, max_seq_no = strict_int(shard.get("doc_count")), strict_int(shard.get("max_seq_no"))
        if doc_count is None or max_seq_no is None:
            return None
        result[str(shard_id)] = (doc_count, max_seq_no)
    return result


def _ilm_age(value: Any) -> Any:
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
    return value if match is None or match[2] == "M" else f"{int(match[1]) * units[match[2].lower()]}nanos"


def _ilm_size(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    if value in {"0", "-1"}:
        return int(value)
    match = re.fullmatch(r"([0-9.e+-]+)\s*(b|[kmgtp]b?)", value.strip().lower())
    if match is None or (match[2] == "b" and not re.fullmatch(r"[+-]?[0-9]+", match[1])):
        return None
    try:
        amount = Decimal(match[1])
    except InvalidOperation:
        return None
    max_bytes = 2**63 - 1
    if amount > max_bytes or amount < (-1 if match[2] == "b" else 0) or int(amount.as_tuple().exponent) < -2:
        return None
    size = ceil(amount * 1024 ** "bkmgtp".index(match[2][0]))
    return size if size <= max_bytes else None


def _managed_policy_phases(policy: Any) -> dict[str, Any] | None:
    phases = deepcopy(policy.get("phases")) if isinstance(policy, dict) else None
    if not isinstance(phases, dict):
        return None
    for phase in phases.values():
        if not isinstance(phase, dict):
            return None
        phase["min_age"] = _ilm_age(phase.get("min_age", "0ms"))
        rollover = phase.get("actions", {}).get("rollover") if isinstance(phase.get("actions"), dict) else None
        if isinstance(rollover, dict):
            if "max_age" in rollover:
                rollover["max_age"] = _ilm_age(rollover["max_age"])
            if "max_primary_shard_size" in rollover:
                if (size := _ilm_size(rollover["max_primary_shard_size"])) is None:
                    return None
                rollover["max_primary_shard_size"] = size
    return phases


def _check_ilm_template_and_policy(
    collection: str,
    expectation: dict[str, Any],
    inventory: dict[str, Any],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    alias = expectation["alias"]
    template_name, policy_name = f"{alias}_template", f"{alias}_policy"
    live_template = inventory.get("ilm_templates", {}).get(collection)
    if not isinstance(live_template, dict):
        add_issue(
            blockers,
            "ilm_template_missing",
            "The configured ILM composable index template is missing.",
            collection=collection,
            template=template_name,
        )
    else:
        if (actual_patterns := live_template.get("index_patterns", [])) != [f"{alias}-*"]:
            add_issue(
                blockers,
                "ilm_template_patterns",
                "ILM template index_patterns do not match the configured collection.",
                collection=collection,
                expected=[f"{alias}-*"],
                actual=actual_patterns,
            )
        actual_template = live_template.get("template", {})
        actual_settings = {"settings": actual_template.get("settings", {})}
        expected_settings = {
            "index.lifecycle.name": policy_name,
            "index.lifecycle.rollover_alias": alias,
            "index.mapping.total_fields.limit": expectation["total_fields_limit"],
        }
        for setting_name, wanted in expected_settings.items():
            actual_val = index_setting(actual_settings, setting_name)
            if setting_name == "index.mapping.total_fields.limit":
                try:
                    actual_val = int(actual_val)
                except (TypeError, ValueError):
                    actual_val = None
            if actual_val != wanted:
                add_issue(
                    blockers,
                    "ilm_template_setting",
                    "ILM template settings do not match the finalized Howler contract.",
                    collection=collection,
                    setting=setting_name,
                    expected=wanted,
                    actual=actual_val,
                )
        _check_mapping_contract(
            collection,
            template_name,
            expectation["ilm_template"].get("mappings", {}),
            actual_template.get("mappings", {}),
            actual_settings,
            blockers,
            warnings,
            schema_less=expectation["model"] is None,
            is_template=True,
        )

    policy = inventory.get("ilm_policies", {}).get(collection)
    expected_policy_body = expectation["ilm_policy"]
    expected_phases = _managed_policy_phases(expected_policy_body)
    if expected_phases is None or _managed_policy_phases(policy) != expected_phases:
        add_issue(
            blockers,
            "ilm_policy_phases",
            "ILM policy phases, actions or thresholds differ from the configured Howler policy.",
            collection=collection,
            policy=policy_name,
            expected=expected_policy_body["phases"],
            actual=policy.get("phases") if isinstance(policy, dict) else None,
        )


def _allowed_alias_flip(before: dict[str, Any], after: dict[str, Any], alias: str) -> bool:
    old_aliases, new_aliases = _alias_contract(before), _alias_contract(after)
    old_def, new_def = old_aliases.get(alias), new_aliases.get(alias)
    if not isinstance(old_def, dict) or not isinstance(new_def, dict):
        return False
    if old_def.get("is_write_index") is not True or new_def.get("is_write_index") is not False:
        return False
    old_def["is_write_index"] = False
    return old_aliases == new_aliases


def _sequence_drift(
    before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]
) -> dict[str, dict[str, dict[str, int]]] | None:
    if before.keys() != after.keys():
        return None
    return {
        shard_id: {
            "baseline": {"doc_count": before[shard_id][0], "max_seq_no": before[shard_id][1]},
            "current": {"doc_count": after[shard_id][0], "max_seq_no": after[shard_id][1]},
        }
        for shard_id in sorted(before)
        if before[shard_id] != after[shard_id]
    }


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
    is_new = kind == "new_collection"
    if not is_new and not all(_empty_unwritten_index(indices[name]) for name in candidates):
        add_issue(
            blockers,
            f"baseline_{kind}_nonempty",
            "A rollover index created after the baseline must be empty and unwritten.",
            collection=collection,
            index=index,
        )
        return False
    if set(aliases := _alias_contract(indices[index])) != {alias}:
        add_issue(
            blockers,
            f"baseline_{kind}_aliases",
            f"A {'newly initialized index' if is_new else 'rollover generation'} may carry only its configured "
            "Howler alias.",
            collection=collection,
            index=index,
            aliases=aliases,
        )
        return False
    if (write_indices := _effective_write_indices(alias, attached, indices, ilm=ilm)) != [index]:
        add_issue(
            blockers,
            f"baseline_{kind}_write_index",
            "Newly initialized collection must have one configured write index."
            if is_new
            else "The new rollover generation must be the only write index.",
            collection=collection,
            expected=index if is_new else [index],
            actual=write_indices,
        )
        return False
    if is_new and not all(_empty_unwritten_index(indices[name]) for name in candidates):
        add_issue(
            blockers,
            f"baseline_{kind}_nonempty",
            "A collection initialized after the baseline must still be empty and unwritten.",
            collection=collection,
            indices=candidates,
        )
        return False
    return True


def _check_baseline_new_and_rollover(
    expectations: dict[str, dict[str, Any]],
    old_indices: dict[str, Any],
    new_indices: dict[str, Any],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> tuple[set[str], dict[str, str]]:
    old_names, new_names = set(old_indices), set(new_indices)
    permitted_new: set[str] = set()
    rollover_old_writes: dict[str, str] = {}
    for collection, expectation in sorted(expectations.items()):
        alias, ilm = expectation["alias"], expectation["ilm"]
        old_backers, old_attached = _collection_indices(alias, ilm, old_indices)
        cur_backers, cur_attached = _collection_indices(alias, ilm, new_indices)
        old_present = bool(old_backers or old_attached)
        cur_new = sorted(set(cur_backers) & (new_names - old_names))

        if not old_present and cur_new:
            if ilm:
                canonical = [n for n in cur_new if canonical_ilm_generation(alias, n) is not None]
                expected_write = canonical[0] if len(canonical) == 1 else None
                valid = len(canonical) == 1 and len(cur_new) == 1 == len(cur_backers)
            else:
                hot = f"{alias}_hot"
                expected_write = hot if cur_backers == [hot] else None
                valid = cur_new == [hot] and cur_backers == [hot]
            if not valid or expected_write is None or cur_attached != [expected_write]:
                add_issue(
                    blockers,
                    "baseline_new_collection_layout",
                    "A collection initialized after the baseline must have exactly its configured empty layout "
                    "and alias.",
                    collection=collection,
                    indices=cur_new,
                )
            elif _post_baseline_index_contract(
                collection,
                alias,
                "new_collection",
                expected_write,
                cur_new,
                cur_attached,
                new_indices,
                blockers,
                ilm=ilm,
            ):
                permitted_new.update(cur_new)
                add_issue(
                    warnings,
                    "baseline_new_empty_collection",
                    "A configured collection absent from the baseline was initialized empty after it.",
                    collection=collection,
                    indices=cur_new,
                )
        elif (
            ilm and old_present and (new_gens := [n for n in cur_new if canonical_ilm_generation(alias, n) is not None])
        ):
            old_writes = _effective_write_indices(alias, old_attached, old_indices, ilm=True)
            base_gen = canonical_ilm_generation(alias, old_writes[0]) if len(old_writes) == 1 else None
            new_gen_num = canonical_ilm_generation(alias, new_gens[0])
            if len(new_gens) != 1 or base_gen is None or new_gen_num is None or new_gen_num <= base_gen:
                add_issue(
                    blockers,
                    "baseline_rollover_generation",
                    "At most one new canonical ILM generation above the baseline write index is allowed.",
                    collection=collection,
                    indices=new_gens,
                )
            elif _post_baseline_index_contract(
                collection, alias, "rollover", new_gens[0], [new_gens[0]], cur_attached, new_indices, blockers, ilm=True
            ):
                permitted_new.add(new_gens[0])
                rollover_old_writes[old_writes[0]] = alias
                add_issue(
                    warnings,
                    "baseline_ilm_rollover",
                    "One empty ILM generation rolled over during the quiesced baseline window.",
                    collection=collection,
                    index=new_gens[0],
                )
    return permitted_new, rollover_old_writes


def _check_baseline_shard_sequences(
    name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    accepted: bool,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    before_shards, after_shards = _shard_sequence_contract(before), _shard_sequence_contract(after)
    if before_shards is None or after_shards is None:
        add_issue(
            blockers, "baseline_sequence_numbers", "Baseline or current primary-shard stats are incomplete.", index=name
        )
        return
    if baseline_sync := primary_shard_sync_issues(before):
        add_issue(
            blockers,
            "sequence_checkpoint_unsynced",
            "Baseline primary sequence stats are incomplete or unsynced; after quiescing writes, "
            "flush, wait for the global checkpoint to catch up, and capture a new baseline.",
            index=name,
            baseline_issues=baseline_sync,
        )
        return
    if primary_shard_sync_issues(after):
        return
    if (drift := _sequence_drift(before_shards, after_shards)) is None:
        add_issue(
            blockers,
            "baseline_sequence_numbers",
            "Primary shard layout changed after the quiesced baseline.",
            index=name,
            baseline=before_shards,
            current=after_shards,
        )
        return
    if decreases := sorted(sid for sid in before_shards if after_shards[sid][1] < before_shards[sid][1]):
        add_issue(
            blockers,
            "baseline_sequence_decrease",
            "Primary max_seq_no decreased after the baseline; this may indicate rolled-back writes.",
            index=name,
            shards=decreases,
        )
    elif drift and accepted:
        add_issue(
            warnings,
            "baseline_sequence_drift_accepted",
            "The cutover lead explicitly accepted primary document-count/max_seq_no drift for this index; "
            "record the decision in the change record.",
            index=name,
            shards=drift,
        )
    elif drift:
        add_issue(
            blockers,
            "baseline_sequence_numbers",
            "Per-shard document counts or max_seq_no changed after the quiesced baseline.",
            index=name,
            shards=drift,
        )


def _check_baseline_common_index(
    name: str,
    before: dict[str, Any],
    after: dict[str, Any],
    rollover_alias: str | None,
    accepted: bool,
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    if before.get("uuid") is None or after.get("uuid") is None:
        add_issue(blockers, "baseline_uuid", "Baseline or current index UUID is missing.", index=name)
    elif before["uuid"] != after["uuid"]:
        add_issue(
            blockers,
            "baseline_uuid",
            "Index UUID changed; this may indicate reindexing or index replacement.",
            index=name,
            baseline=before["uuid"],
            current=after["uuid"],
        )
    aliases_match = (
        _allowed_alias_flip(before, after, rollover_alias)
        if rollover_alias is not None
        else _alias_contract(before) == _alias_contract(after)
    )
    if not aliases_match:
        add_issue(
            blockers,
            "baseline_aliases",
            "Alias membership or is_write_index changed after the baseline.",
            index=name,
            baseline=_alias_contract(before),
            current=_alias_contract(after),
        )
    if is_closed_index(before) or is_closed_index(after):
        return

    before_count, after_count = before.get("doc_count"), after.get("doc_count")
    if strict_int(before_count) is None or strict_int(after_count) is None:
        add_issue(blockers, "baseline_doc_count", "Baseline or current primary document count is missing.", index=name)
    elif before_count != after_count and not accepted:
        add_issue(
            blockers,
            "baseline_doc_count",
            "Primary document count changed after the quiesced baseline.",
            index=name,
            baseline=before_count,
            current=after_count,
        )
    _check_baseline_shard_sequences(name, before, after, accepted, blockers, warnings)


def _compare_baseline(
    current: dict[str, Any],
    baseline: dict[str, Any],
    prefix: str,
    expectations: dict[str, dict[str, Any]],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    accepted_sequence_drift: set[str] | None = None,
) -> None:
    accepted_drift = accepted_sequence_drift or set()
    if (baseline_prefix := baseline.get("index_prefix")) != prefix:
        add_issue(
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
        add_issue(
            blockers,
            "baseline_no_prefix_indices",
            f"Baseline contains no Howler indices using configured prefix {prefix!r}.",
        )
    old_names, new_names = set(old_indices), set(new_indices)
    if missing_names := old_names - new_names:
        add_issue(
            blockers,
            "baseline_index_missing",
            "Every baseline Howler index must remain present; a missing index may indicate data loss.",
            indices=sorted(missing_names),
        )

    permitted_new, rollover_old_writes = _check_baseline_new_and_rollover(
        expectations, old_indices, new_indices, blockers, warnings
    )
    unexplained = (new_names - old_names - permitted_new) - {n for n, d in new_indices.items() if is_closed_index(d)}
    if unexplained:
        add_issue(
            blockers,
            "baseline_unexpected_indices",
            "New Howler-prefixed indices are not an allowed empty initialization or single-generation rollover.",
            indices=sorted(unexplained),
        )

    common_names = old_names & new_names
    for index in sorted(accepted_drift - common_names):
        add_issue(
            warnings,
            "unknown_sequence_drift_acceptance",
            "No baseline/current index pair matched this acceptance; no drift was accepted.",
            index=index,
        )
    for name in sorted(common_names):
        _check_baseline_common_index(
            name,
            old_indices[name],
            new_indices[name],
            rollover_old_writes.get(name),
            name in accepted_drift,
            blockers,
            warnings,
        )


def _check_health_and_versions(
    inventory: dict[str, Any], allow_yellow: bool, blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]
) -> None:
    health_data = inventory.get("cluster_health", {})
    health = health_data.get("status")
    if health == "yellow" and allow_yellow:
        add_issue(warnings, "cluster_health_override", "Yellow health was explicitly accepted using --allow-yellow.")
    elif health == "yellow":
        add_issue(
            blockers,
            "cluster_health",
            "Cluster health is yellow; rerun with --allow-yellow only after operator review.",
        )
    elif health != "green":
        allowed = " or explicitly allowed yellow" if allow_yellow else ""
        add_issue(blockers, "cluster_health", f"Cluster health must be green{allowed}; found {health or 'unknown'}.")
    if health_data.get("timed_out") is True:
        add_issue(blockers, "cluster_health_timeout", "Cluster health request timed out; its result is incomplete.")

    node_data = inventory.get("nodes", {}).get("nodes", {})
    node_versions = {node.get("name", node_id): node.get("version") for node_id, node in node_data.items()}
    if not node_versions:
        add_issue(blockers, "node_versions", "No Elasticsearch nodes or node versions were returned.")
    for node, version in sorted(node_versions.items()):
        if version != TARGET_VERSION:
            add_issue(
                blockers,
                "node_version",
                f"Every node must report {TARGET_VERSION}; found {version or 'unknown'}.",
                node=node,
            )
    if (root_version := inventory.get("version", {}).get("version", {}).get("number")) != TARGET_VERSION:
        add_issue(
            blockers,
            "cluster_version",
            f"Cluster info must report {TARGET_VERSION}; found {root_version or 'unknown'}.",
        )


def _check_cluster_gates(
    inventory: dict[str, Any], allow_yellow: bool, blockers: list[dict[str, Any]], warnings: list[dict[str, Any]]
) -> None:
    _check_health_and_versions(inventory, allow_yellow, blockers, warnings)

    feature_status = inventory.get("feature_upgrade_status", {}).get("migration_status")
    if feature_status in {"IN_PROGRESS", "ERROR"}:
        add_issue(
            blockers,
            "system_features",
            f"System feature migration is {feature_status}; resolve or stop the migration before cutover.",
        )
    elif feature_status == "MIGRATION_NEEDED":
        add_issue(
            warnings,
            "es10_readiness_system_features",
            "System-feature migration is Elasticsearch 10 preparation; schedule and rehearse it separately.",
        )
    elif feature_status != NO_MIGRATION_NEEDED:
        add_issue(
            warnings,
            "es10_readiness_system_features",
            f"Unrecognized system-feature status {feature_status or 'missing'}; confirm future-major readiness "
            "separately.",
        )

    critical = [
        {
            "path": ".".join(path),
            "message": str(issue.get("message", "Critical deprecation")),
            "details": issue.get("details"),
            "_meta": issue.get("_meta", issue.get("meta")),
        }
        for path, issue in walk_deprecations(inventory.get("deprecations", {}))
        if issue.get("level") == "critical"
    ]
    if es10 := [item for item in critical if _is_es10_readiness(item)]:
        add_issue(
            warnings,
            "es10_readiness",
            "These next-major reindex/readiness deprecations are expected after an 8.x-to-9.x upgrade.",
            resources=es10,
        )
    if cutover := [item for item in critical if not _is_es10_readiness(item)]:
        add_issue(
            blockers,
            "critical_deprecations",
            f"Resolve {len(cutover)} critical deprecation(s) that affect 9.x operation.",
            resources=cutover,
        )


def _check_index_ilm(
    collection: str,
    index: str,
    alias: str,
    index_data: dict[str, Any],
    inventory: dict[str, Any],
    blockers: list[dict[str, Any]],
) -> None:
    policy_name = f"{alias}_policy"
    lifecycle_name = index_setting(index_data, "index.lifecycle.name")
    rollover_alias = index_setting(index_data, "index.lifecycle.rollover_alias")
    if lifecycle_name != policy_name or rollover_alias != alias:
        add_issue(
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
        add_issue(
            blockers,
            "ilm_managed",
            "ILM-backed collection index is not managed by ILM.",
            collection=collection,
            index=index,
        )
    if explain.get("policy") != policy_name:
        add_issue(
            blockers,
            "ilm_policy",
            "ILM explain reports an unexpected or missing policy.",
            collection=collection,
            index=index,
            expected=policy_name,
            actual=explain.get("policy"),
        )
    step_info = explain.get("step_info")
    if str(explain.get("step", "")).upper() == "ERROR" or (
        isinstance(step_info, dict) and bool(step_info.get("type") or step_info.get("reason"))
    ):
        add_issue(
            blockers,
            "ilm_step",
            "ILM explain reports an ERROR step or step information.",
            collection=collection,
            index=index,
            step=explain.get("step"),
            step_info=step_info,
        )


def _check_backing_index(
    collection: str,
    index: str,
    expectation: dict[str, Any],
    inventory: dict[str, Any],
    write_indices: list[str],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    indices, mappings = inventory.get("indices", {}), inventory.get("mappings", {})
    index_data = indices.get(index, {})
    if index not in mappings:
        add_issue(
            blockers,
            "mapping_missing",
            "No live mapping was returned for a backing index.",
            collection=collection,
            index=index,
        )
        return

    live_mapping = mappings[index].get("mappings", mappings[index])
    _check_mapping_contract(
        collection,
        index,
        expectation["mapping"],
        live_mapping,
        index_data,
        blockers,
        warnings,
        schema_less=expectation["model"] is None,
    )

    limit = index_setting(index_data, "index.mapping.total_fields.limit")
    expected_limit = expectation["total_fields_limit"]
    try:
        actual_limit = int(limit) if limit is not None else DEFAULT_TOTAL_FIELDS_LIMIT
    except (TypeError, ValueError):
        actual_limit = 0
    mapped_fields = _mapped_field_count(live_mapping)
    if index in write_indices and actual_limit < expected_limit:
        add_issue(
            blockers,
            "total_fields_limit",
            f"Mapping field limit must be at least {expected_limit}.",
            collection=collection,
            index=index,
            expected_minimum=expected_limit,
            actual=limit,
        )
    elif actual_limit < mapped_fields:
        add_issue(
            blockers,
            "total_fields_limit_below_mapped_fields",
            "Index field limit is below its actual mapped field count.",
            collection=collection,
            index=index,
            actual_limit=actual_limit,
            mapped_fields=mapped_fields,
        )
    elif actual_limit < expected_limit:
        add_issue(
            warnings,
            "total_fields_limit_legacy_lower",
            "Existing backing index has a lower-than-current schema limit but can hold its current mapping.",
            collection=collection,
            index=index,
            actual_limit=actual_limit,
            expected_minimum=expected_limit,
            mapped_fields=mapped_fields,
        )

    if expectation["ilm"]:
        _check_index_ilm(collection, index, expectation["alias"], index_data, inventory, blockers)


def _check_collection_layout(
    collection: str,
    alias: str,
    ilm: bool,
    backers: list[str],
    attached: list[str],
    indices: dict[str, Any],
    write_indices: list[str],
    blockers: list[dict[str, Any]],
) -> None:
    if ilm:
        canonical = [name for name in backers if canonical_ilm_generation(alias, name) is not None]
        if not canonical:
            add_issue(
                blockers,
                "ilm_backing_indices",
                "ILM collection has no canonical six-digit backing index.",
                collection=collection,
                alias=alias,
            )
        if attached != canonical:
            add_issue(
                blockers,
                "ilm_alias_members",
                "The read alias must include every canonical ILM generation and no other indices.",
                collection=collection,
                alias=alias,
                missing=sorted(set(canonical) - set(attached)),
                unexpected=sorted(set(attached) - set(canonical)),
            )
        if canonical and write_indices != [canonical[-1]]:
            add_issue(
                blockers,
                "ilm_write_index",
                "The latest canonical ILM generation must have is_write_index explicitly set to true.",
                collection=collection,
                alias=alias,
                expected=canonical[-1],
                actual=write_indices,
            )
        return

    hot = f"{alias}_hot"
    if hot not in indices:
        add_issue(
            blockers, "legacy_hot_index", "Configured legacy _hot index is missing.", collection=collection, index=hot
        )
    if attached != [hot] or write_indices != [hot]:
        add_issue(
            blockers,
            "legacy_write_index",
            "The legacy alias must write to its _hot index.",
            collection=collection,
            alias=alias,
            expected=[hot],
            actual=write_indices,
        )


def _check_collection(
    collection: str,
    expectation: dict[str, Any],
    inventory: dict[str, Any],
    baseline_indices: dict[str, Any],
    blockers: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    indices = inventory.get("indices", {})
    alias, ilm = expectation["alias"], expectation["ilm"]
    backers, attached = _collection_indices(alias, ilm, indices)
    if not backers and not attached:
        base_backers, base_attached = _collection_indices(alias, ilm, baseline_indices)
        if base_backers or base_attached:
            add_issue(
                blockers,
                "collection_missing_after_baseline",
                "A configured collection present at baseline is now missing.",
                collection=collection,
                alias=alias,
            )
        else:
            add_issue(
                blockers,
                "collection_not_initialized",
                "Collection is not initialized; run the separate collection initializer before full verification.",
                collection=collection,
                alias=alias,
            )
        return

    if ilm:
        _check_ilm_template_and_policy(collection, expectation, inventory, blockers, warnings)
    if not attached:
        add_issue(
            blockers, "alias_missing", "Collection alias has no backing indices.", collection=collection, alias=alias
        )
    write_indices = _effective_write_indices(alias, attached, indices, ilm=ilm)
    if len(write_indices) != 1:
        add_issue(
            blockers,
            "alias_write_index",
            f"Alias must resolve to exactly one write index; found {len(write_indices)}.",
            collection=collection,
            alias=alias,
            attached_indices=attached,
            write_indices=write_indices,
        )
    _check_collection_layout(collection, alias, ilm, backers, attached, indices, write_indices, blockers)

    for index in backers:
        _check_backing_index(collection, index, expectation, inventory, write_indices, blockers, warnings)

    caps_result = inventory.get("field_caps", {}).get(collection, {})
    has_caps = isinstance(caps_result, dict) and isinstance(caps_result.get("fields"), dict)
    caps = caps_result["fields"] if has_caps else {}
    schema_paths = set(_flatten_properties(expectation["mapping"].get("properties", {})))
    for field, types in sorted(caps.items()):
        if len(types) > 1:
            add_issue(
                blockers if field in schema_paths else warnings,
                "field_caps_conflict" if field in schema_paths else "field_caps_non_schema_conflict",
                "field_caps reports more than one field type across backing indices.",
                collection=collection,
                field=field,
                types=sorted(types),
            )
    if backers and not has_caps and not any(is_closed_index(indices.get(idx, {})) for idx in backers):
        add_issue(
            blockers,
            "field_caps_missing",
            "No field_caps result was collected for this collection.",
            collection=collection,
        )


def evaluate_inventory(
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
    accepted_drift = accepted_sequence_drift or set()
    _check_cluster_gates(inventory, allow_yellow, blockers, warnings)

    indices = inventory.get("indices", {})
    prefix = inventory.get("index_prefix", _prefix())
    baseline_indices = _baseline_indices(baseline, prefix) if baseline is not None else {}
    configured_backers = _configured_backing_index_names(expectations, indices) | _configured_backing_index_names(
        expectations, baseline_indices
    )
    for index in sorted(
        {n for n, d in indices.items() if is_closed_index(d)}
        | {n for n, d in baseline_indices.items() if is_closed_index(d)}
    ):
        if index in configured_backers or index in baseline_indices:
            add_issue(
                blockers,
                "closed_howler_index",
                "A closed index backs a configured collection or is present in the baseline; "
                "reopen or archive it before cutover.",
                index=index,
            )
        else:
            add_issue(
                warnings,
                "closed_howler_index",
                "Closed Howler-prefixed index is not configured and is absent from the baseline; review it.",
                index=index,
            )

    for index, data in sorted(indices.items()):
        if index.startswith(f"{prefix}-") and not is_closed_index(data) and (sync := primary_shard_sync_issues(data)):
            add_issue(
                blockers,
                "sequence_checkpoint_unsynced",
                "Primary sequence stats are incomplete or unsynced; wait for cluster health to be green, "
                "then rerun the verifier.",
                index=index,
                shards=sync,
            )

    if integrity_only:
        if baseline is None:
            add_issue(blockers, "baseline_required", "--integrity-only requires --baseline.")
        else:
            _compare_baseline(inventory, baseline, prefix, expectations, blockers, warnings, accepted_drift)
        return {
            "allow_yellow": allow_yellow,
            "integrity_only": True,
            "blockers": blockers,
            "ready": not blockers,
            "warnings": warnings,
        }

    for collection, expectation in sorted(expectations.items()):
        _check_collection(collection, expectation, inventory, baseline_indices, blockers, warnings)

    if baseline is not None:
        _compare_baseline(inventory, baseline, prefix, expectations, blockers, warnings, accepted_drift)
    elif accepted_drift:
        add_issue(
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


def collect_inventory(
    client: ElasticsearchRestClient, expectations: dict[str, dict[str, Any]], *, integrity_only: bool = False
) -> dict[str, Any]:
    """Read configured Howler indices and cluster gates using GET requests only."""
    prefix = _prefix()
    indices = collect_index_inventory(client, prefix, scoped=True)
    mappings = (
        client.get(f"/{quote(prefix, safe='-_.')}-*/_mapping", {"expand_wildcards": "all", "allow_no_indices": "true"})
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
            if (
                explain := client.get_optional(f"/{quote(alias, safe='-_.')}-*/_ilm/explain", {"only_managed": "false"})
            ) is not None:
                ilm_explain.update(explain.get("indices", explain))
            template_name, policy_name = f"{alias}_template", f"{alias}_policy"
            tpl_resp = client.get_optional(f"/_index_template/{quote(template_name, safe='-_.')}")
            ilm_templates[collection] = (
                next(
                    (
                        item.get("index_template")
                        for item in tpl_resp.get("index_templates", [])
                        if item.get("name") == template_name and isinstance(item.get("index_template"), dict)
                    ),
                    None,
                )
                if tpl_resp is not None
                else None
            )
            pol_resp = client.get_optional(f"/_ilm/policy/{quote(policy_name, safe='-_.')}")
            ilm_policies[collection] = pol_resp.get(policy_name, {}).get("policy") if pol_resp is not None else None
        if attached and not any(is_closed_index(indices.get(name, {})) for name in attached):
            field_caps[collection] = client.get(f"/{quote(alias, safe='-_.')}/_field_caps", {"fields": "*"})

    return {
        "cluster_health": client.get("/_cluster/health"),
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
    return {
        "checks": evaluate_inventory(
            inventory,
            expectations,
            baseline=baseline,
            allow_yellow=allow_yellow,
            integrity_only=integrity_only,
            accepted_sequence_drift=accepted_sequence_drift,
        ),
        "expected_collections": {
            name: {"alias": c["alias"], "ilm": c["ilm"], "total_fields_limit": c["total_fields_limit"]}
            for name, c in sorted(expectations.items())
        },
        "index_prefix": inventory["index_prefix"],
        "inventory": inventory,
        "target_version": TARGET_VERSION,
    }


def _read_baseline(path: Path | None, parser: argparse.ArgumentParser) -> dict[str, Any] | None:
    if path is None:
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        parser.error(f"Cannot read baseline JSON: {error}")
    inv = value.get("inventory") if isinstance(value, dict) else None
    checks = value.get("checks") if isinstance(value, dict) else None
    version_data = inv.get("version") if isinstance(inv, dict) else None
    cluster_ver = version_data.get("version") if isinstance(version_data, dict) else None
    prefix = _prefix()
    found_prefix = value.get("index_prefix") if isinstance(value, dict) else None
    for invalid, msg in (
        (
            not isinstance(value, dict) or not isinstance(inv, dict) or not isinstance(inv.get("indices"), dict),
            "Baseline must be a preflight report containing inventory.indices.",
        ),
        (
            not isinstance(version_data, dict) or not isinstance(checks, dict),
            "Baseline must include inventory.version and checks.ready.",
        ),
        (
            isinstance(value, dict) and value.get("source_stack_version") != SOURCE_STACK_VERSION,
            f"Baseline source_stack_version must be {SOURCE_STACK_VERSION}.",
        ),
        (
            isinstance(value, dict) and value.get("baseline_capture") is not True,
            "Baseline must be produced with --baseline-capture.",
        ),
        (
            (cluster_ver.get("number") if isinstance(cluster_ver, dict) else None) != SOURCE_STACK_VERSION,
            f"Baseline inventory.version.number must be {SOURCE_STACK_VERSION}.",
        ),
        (isinstance(checks, dict) and checks.get("ready") is not True, "Baseline preflight checks.ready must be true."),
        (found_prefix != prefix, f"Baseline index_prefix must match {prefix!r}; found {found_prefix!r}."),
    ):
        if invalid:
            parser.error(msg)
    return value  # type: ignore[return-value]


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
            "Explicitly accept doc_count/max_seq_no drift for this baseline index (repeatable). "
            "Decreases are never accepted."
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
    except Exception as error:  # noqa: BLE001 - failed schema/config checks must emit a blocking JSON report
        if isinstance(error, (ElasticsearchRestError, HowlerAttributeError, HowlerRuntimeError)) or (
            isinstance(error, ValueError) and not isinstance(error, ValidationError)
        ):
            message = str(error)
        else:
            message = (
                "Unable to load deployed Howler configuration/schema or complete verification "
                f"({type(error).__name__}); details were omitted to avoid exposing configuration values."
            )
        report = {
            "checks": {
                "allow_yellow": args.allow_yellow,
                "blockers": [{"check": "collection_or_connection", "message": message}],
                "ready": False,
                "warnings": [],
            },
            "target_version": TARGET_VERSION,
        }
    write_json_report(report, args.output)
    return 0 if report["checks"]["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
