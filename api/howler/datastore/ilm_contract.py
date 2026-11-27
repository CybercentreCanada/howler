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
