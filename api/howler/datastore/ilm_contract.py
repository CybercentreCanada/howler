"""Pure Elasticsearch contract comparisons shared by startup and cutover checks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from howler.config_models import ILMConfig, ILMIndexConfig


def normalized_field_mapping(body: dict[str, Any]) -> dict[str, Any]:
    """Compare explicit field mappings with Elasticsearch's equivalent implicit defaults."""
    kind = body.get("type")
    defaults: dict[str, Any] = {
        "index": True,
        "store": False,
        "enabled": True,
        "dynamic": True,
    }
    if kind is not None:
        defaults["doc_values"] = kind not in {"object", "nested", "text"}
    if kind == "keyword":
        defaults.update(norms=False, eager_global_ordinals=False, index_options="docs")
    elif kind == "text":
        defaults.update(norms=True, fielddata=False, index_options="positions")
    elif kind in {"integer", "long", "short", "byte", "double", "float", "scaled_float"}:
        defaults.update(coerce=True, ignore_malformed=False)
    normalized = {key: value for key, value in body.items() if key not in defaults or value != defaults[key]}
    if isinstance(target := normalized.get("copy_to"), str):
        normalized["copy_to"] = [target]
    for key in ("properties", "fields"):
        if key in normalized:
            normalized[key] = {name: normalized_field_mapping(field) for name, field in normalized[key].items()}
    return normalized


def _patterns(value: str | list[str]) -> list[str]:
    return value if isinstance(value, list) else [value]


def _covers_selector(broader: dict[str, Any], narrower: dict[str, Any]) -> bool:
    """Prove name/path coverage without treating a plugin-specific path as a global catch-all."""
    mode = broader.get("match_pattern", "simple")
    same_mode = mode == narrower.get("match_pattern", "simple")
    for key, value in broader.items():
        if key == "match_pattern" or (same_mode and value == narrower.get(key)):
            continue
        if key not in {"match", "path_match"}:
            return False
        patterns = _patterns(value)
        if (mode == "simple" and "*" in patterns) or (mode == "regex" and ".*" in patterns):
            continue
        if not same_mode or not all(
            any(
                pattern == item
                or (
                    mode == "simple"
                    and pattern.endswith("*")
                    and "*" not in pattern[:-1]
                    and item.startswith(pattern[:-1])
                )
                for pattern in patterns
            )
            for item in _patterns(narrower.get(key, "*"))
        ):
            return False
    return True


def _template_rules(templates: list[dict[str, Any]], kind: str) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Return the ordered name/path selectors that apply to this detected JSON type."""
    rules = []
    for template in templates:
        name, body = next(iter(template.items()))
        if not body.keys() & {"match_mapping_type", "match", "path_match"}:
            continue  # Named-only templates are selected explicitly in bulk requests.
        if not {kind, "*"}.intersection(_patterns(body.get("match_mapping_type", "*"))):
            continue
        if {kind, "*"}.intersection(_patterns(body.get("unmatch_mapping_type", []))):
            continue
        effect = {k: normalized_field_mapping(v) for k, v in body.items() if k in {"mapping", "runtime"}}
        selector = {
            k: v for k, v in body.items() if k not in effect and k not in {"match_mapping_type", "unmatch_mapping_type"}
        }
        rules.append((name, selector, effect))
    return rules


def shadowed_dynamic_templates(expected: list[dict[str, Any]], live: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """Report first-match conflicts by obsolete live position, then by active declaration position."""

    def declaration_order(templates: list[dict[str, Any]]) -> dict[str, int]:
        order: dict[str, int] = {}
        for position, template in enumerate(templates):
            for name in template:
                order.setdefault(name, position)
        return order

    active = declaration_order(expected)
    if all(next(iter(template)) in active for template in live):
        return []
    conflicts = set()
    for kind in ("boolean", "date", "double", "long", "object", "string"):
        wanted = _template_rules(expected, kind)
        current = _template_rules(live, kind)
        scopes = [scope for _, scope, _ in wanted]
        # A global rule alone does not declare every disabled plugin's namespace active.
        # But within an explicitly declared namespace, an obsolete narrower rule can
        # steal only part of that namespace. Use that narrower selector as a witness
        # and resolve both sides in their actual first-match order.
        for _, namespace, _ in wanted:
            if not any(
                key in namespace
                and bool(_patterns(namespace[key]))
                and not {"*", ".*"}.intersection(_patterns(namespace[key]))
                for key in ("match", "path_match")
            ):
                continue
            scopes.extend(
                selector
                for name, selector, _ in current
                if name not in active and _covers_selector(namespace, selector)
            )
        for scope in scopes:
            first = next((rule for rule in current if _covers_selector(rule[1], scope)), None)
            if first is not None and first[0] not in active:
                winner = next(rule for rule in wanted if _covers_selector(rule[1], scope))
                if first[2] != winner[2]:
                    conflicts.add((first[0], winner[0]))
    live_order = declaration_order(live)
    return sorted(conflicts, key=lambda pair: (live_order[pair[0]], active[pair[1]]))


def ilm_policy(index_config: ILMIndexConfig | None, global_config: ILMConfig) -> dict[str, Any]:
    """Build the managed policy; the retention job, not ILM, handles deletion."""
    phases: dict[str, Any] = {
        "hot": {
            "min_age": "0ms",
            "actions": {
                "rollover": {
                    "max_age": global_config.rollover_max_age,
                    "max_primary_shard_size": global_config.rollover_max_size,
                }
            },
        }
    }
    if index_config and index_config.warm:
        actions = {}
        if index_config.warm_forcemerge_segments is not None:
            actions["forcemerge"] = {"max_num_segments": index_config.warm_forcemerge_segments}
        phases["warm"] = {"min_age": index_config.warm, "actions": actions}
    if index_config and index_config.cold:
        phases["cold"] = {"min_age": index_config.cold, "actions": {}}
    return {"phases": phases}
