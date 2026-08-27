"""Elasticsearch index-contract builder for the new Pydantic/DSL model registry.

Generates settings, mappings (properties + dynamic templates), aliases, and ILM composable
template payloads directly from ``howler.models.registry.model_registry`` metadata. This module
is structurally faithful to the legacy ``howler.datastore.support.build.build_mapping``/
``build_templates`` algorithm (same disabled-object rules, same dynamic template shapes, same
``refuse_all_implicit_mappings``/``strings_as_keywords`` behavior) so the generated contract is
normalized-compatible with the deterministic legacy contract fixture.

Only the *schema* (index settings/mappings/templates) is generated here. Document persistence,
deserialization, search, and update continue to use the legacy ODM models until Step 7/8; callers
must not use this module for document read/write conversion.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Annotated, Any, get_args, get_origin

from pydantic import BaseModel

from howler.common.exceptions import HowlerNotImplementedError
from howler.common.logging import get_logger
from howler.models.registry import (
    FieldDefinition,
    field_metadata,
    model_registry,
    unwrap_annotation,
)
from howler.models.schema_defaults import (
    default_dynamic_strings,
    default_dynamic_templates,
    default_index,
    default_mapping,
)

logger = get_logger(__name__)

# Kinds whose dotted-key value is a nested dynamic-key structure rather than a single leaf value.
DYNAMIC_KEY_KINDS = frozenset({"Mapping", "FlattenedObject", "FlattenedListObject"})

# Elasticsearch type per Howler field "kind", extending the legacy datastore type table with the
# new-model field kinds that map to the same underlying ES types.
KIND_TYPE_MAPPING: dict[str, str] = {
    "Any": "keyword",
    "Boolean": "boolean",
    "CaseInsensitiveKeyword": "keyword",
    "Classification": "keyword",
    "ClassificationString": "keyword",
    "Date": "date",
    "Domain": "keyword",
    "Email": "keyword",
    "EmptyableKeyword": "keyword",
    "Enum": "keyword",
    "Float": "float",
    "HowlerHash": "keyword",
    "IP": "ip",
    "IndexText": "text",
    "Integer": "integer",
    "Json": "keyword",
    "Keyword": "keyword",
    "Long": "long",
    "LowerKeyword": "keyword",
    "MAC": "keyword",
    "MD5": "keyword",
    "PhoneNumber": "keyword",
    "Platform": "keyword",
    "Processor": "keyword",
    "SHA1": "keyword",
    "SHA256": "keyword",
    "SSDeepHash": "text",
    "Text": "text",
    "URI": "keyword",
    "URIPath": "keyword",
    "UUID": "keyword",
    "UpperKeyword": "keyword",
    "ValidatedKeyword": "keyword",
}

DISABLED_OBJECT_MAPPING: dict[str, Any] = {"type": "object", "enabled": False}
ID_PROPERTY_MAPPING: dict[str, Any] = {"store": True, "doc_values": True, "type": "keyword"}
TEXT_PROPERTY_MAPPING: dict[str, Any] = {"store": False, "type": "text"}


@dataclass(frozen=True)
class IndexContract:
    """A complete generated index contract for one collection."""

    settings: dict[str, Any]
    mappings: dict[str, Any]


def analysis_settings() -> dict[str, Any]:
    """Return the shared analyzer/normalizer/filter settings block."""
    return deepcopy(default_index["settings"])


def flat_field_count(model_type: type[BaseModel] | None) -> int:
    """Return the number of flat (dotted-path) fields for a schema model."""
    if model_type is None:
        return 0
    return len(model_registry.flat_fields(model_type))


def total_fields_limit(model_type: type[BaseModel] | None) -> int:
    """Return ``max(1500, flat field count + 500)``, matching the legacy field-cap heuristic."""
    limit = flat_field_count(model_type) + 500
    if limit < 1500:
        return 1500
    if limit > 1500:
        logger.warning("Schema field size is larger than 1500 - set to %s", limit)
    return limit


def index_settings(model_type: type[BaseModel] | None, *, shards: int, replicas: int) -> dict[str, Any]:
    """Build the ``settings`` block: shared analysis settings, shards/replicas, field limit."""
    settings = analysis_settings()
    settings.setdefault("index", {})
    settings["index"]["number_of_shards"] = shards
    settings["index"]["number_of_replicas"] = replicas
    settings["index"].setdefault("mapping", {}).setdefault("total_fields", {})
    settings["index"]["mapping"]["total_fields"]["limit"] = total_fields_limit(model_type)
    return settings


def mapping_value_annotation(definition: FieldDefinition) -> Any:
    """Return the value-type annotation of a ``dict[str, X]`` Mapping/FlattenedObject field."""
    unwrapped = unwrap_annotation(definition.annotation)
    args = get_args(unwrapped)
    return args[1] if len(args) > 1 else args[0]


def _is_any_kind(annotation: Any) -> bool:
    metadata = field_metadata(annotation)
    return metadata is not None and metadata.kind == "Any"


def _document_properties_tree(model_type: type[BaseModel]) -> dict[str, Any]:
    return deepcopy(model_registry.mapping(model_type)).get("properties", {})


def build_properties(model_type: type[BaseModel]) -> tuple[dict[str, Any], dict[str, FieldDefinition]]:  # noqa: C901
    """Flatten the DSL-generated nested mapping into legacy-compatible dotted properties.

    Object/nested sub-schemas produced for ``Compound`` fields (which the DSL always represents
    with a ``properties`` key, whether or not the field is a list) are recursively flattened into
    dotted leaf keys and the parent wrapper is dropped entirely, matching the legacy contract's
    representation. Enabled ``Mapping``/``FlattenedObject``/``FlattenedListObject`` fields (whose
    dynamic keys cannot be statically declared) are omitted from ``properties`` and returned
    separately for dynamic template generation; disabled ones (``index=False`` or a child kind of
    ``Any``) are retained as ``{"type": "object", "enabled": False}``.
    """
    tree = _document_properties_tree(model_type)
    flat_defs = model_registry.flat_fields(model_type)
    raw_properties: dict[str, Any] = {}
    properties: dict[str, Any] = {}
    dynamic_sources: dict[str, FieldDefinition] = {}

    def walk(node_properties: dict[str, Any], prefix: str) -> None:
        for key, node in node_properties.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(node, dict) and "properties" in node:
                # Compound object (or list of compound): always inlined as dotted leaves.
                walk(node["properties"], path)
                continue
            raw_properties[path] = deepcopy(node)

    walk(tree, "")

    # The DSL mapping tree does not guarantee stable property iteration order across processes.
    # Follow the canonical registry order so dynamic-template order is deterministic and matches
    # the legacy declaration traversal.
    for path, definition in flat_defs.items():
        kind = definition.metadata.kind if definition.metadata else None
        if kind in DYNAMIC_KEY_KINDS:
            assert definition.metadata is not None  # noqa: S101 - kind came from this metadata
            resolved_index = definition.metadata.index if definition.metadata.index is not None else True
            value_annotation = mapping_value_annotation(definition)
            if not resolved_index or _is_any_kind(value_annotation):
                properties[path] = dict(DISABLED_OBJECT_MAPPING)
            else:
                dynamic_sources[path] = definition
            continue

        if path in raw_properties:
            properties[path] = raw_properties[path]

    # Classification access fields are generated mapping properties, not declared model fields.
    for path in ("__access_lvl__", "__access_req__", "__access_grp1__", "__access_grp2__"):
        if path in raw_properties:
            properties[path] = raw_properties[path]

    for path in sorted(raw_properties.keys() - properties.keys() - dynamic_sources.keys()):
        properties[path] = raw_properties[path]

    return properties, dynamic_sources


def _resolve_index(local_index: bool | None, inherited: bool) -> bool:
    return local_index if local_index is not None else inherited


def _leaf_template(name: str, kind: str, index: bool, copy_to: tuple[str, ...]) -> dict[str, Any]:
    es_type = KIND_TYPE_MAPPING.get(kind)
    if es_type is None:
        raise HowlerNotImplementedError(f"Unknown type for elasticsearch dynamic mapping: {kind}")
    mapping_body: dict[str, Any] = {"type": es_type, "index": index}
    if copy_to:
        if len(copy_to) > 1:
            logger.warning("copyto field larger than 1, only using first entry")
        mapping_body["copy_to"] = copy_to[0]
    return {f"{name}_tpl": {"path_match": name, "mapping": mapping_body}}


def _dynamic_templates(  # noqa: C901
    name: str,
    annotation: Any,
    *,
    inherited_index: bool,
    nested_template: bool = False,
) -> list[dict[str, Any]]:
    """Recursively build dynamic templates for a raw (unflattened) annotation.

    Mirrors ``howler.datastore.support.build.build_templates`` exactly, including its legacy
    quirks: a nested ``Mapping``/``List``/``FlattenedObject`` always forces ``nested_template``
    on its own recursive call regardless of the incoming flag, while descending into a
    ``Compound`` model always resets it to ``False`` for each sub-field (matching the legacy
    Python-side recursion, which never forwards ``nested_template`` into ``Compound.fields()``).
    """
    unwrapped = unwrap_annotation(annotation)
    origin = get_origin(unwrapped)

    if origin is list:
        child_annotation = get_args(unwrapped)[0]
        return _dynamic_templates(name, child_annotation, inherited_index=inherited_index, nested_template=True)

    if isinstance(unwrapped, type) and issubclass(unwrapped, BaseModel):
        out: list[dict[str, Any]] = []
        for sub_name, sub_definition in model_registry.fields(unwrapped).items():
            sub_index = _resolve_index(
                sub_definition.metadata.index if sub_definition.metadata else None, inherited_index
            )
            # Pydantic's ``FieldInfo.annotation`` strips a field's own outermost Howler metadata
            # into ``FieldInfo.metadata`` (already resolved onto ``sub_definition.metadata``), so
            # a direct scalar sub-field's bare annotation (e.g. plain ``str``) would otherwise
            # lose its kind here. Re-attach the already-resolved metadata before recursing so
            # every sub-field (scalar, list, or nested compound) is inspected consistently.
            sub_annotation = (
                Annotated[sub_definition.annotation, sub_definition.metadata]
                if sub_definition.metadata is not None
                else sub_definition.annotation
            )
            out.extend(_dynamic_templates(f"{name}.{sub_name}", sub_annotation, inherited_index=sub_index))
        return out

    metadata = field_metadata(annotation)
    kind = metadata.kind if metadata else None
    local_index = metadata.index if metadata else None
    effective_index = _resolve_index(local_index, inherited_index)

    if kind in DYNAMIC_KEY_KINDS:
        value_annotation = get_args(unwrapped)[1] if len(get_args(unwrapped)) > 1 else get_args(unwrapped)[0]
        return _dynamic_templates(
            name,
            value_annotation,
            inherited_index=effective_index,
            nested_template=True,
        )

    if nested_template:
        return [{f"nested_{name}": {"match": name, "mapping": {"type": "nested"}}}]

    if kind == "Any" or effective_index is False:
        return [{f"{name}_tpl": {"path_match": name, "mapping": {"type": "keyword", "index": False}}}]

    copy_to = metadata.copy_to if metadata else ()
    if kind is None:
        raise HowlerNotImplementedError(f"Unknown type for elasticsearch dynamic mapping: {annotation!r}")
    return [_leaf_template(name, kind, effective_index if effective_index is not None else True, copy_to)]


def build_dynamic_templates(dynamic_sources: dict[str, FieldDefinition]) -> list[dict[str, Any]]:
    """Build the model-specific dynamic template list (excludes the shared/defaults templates)."""
    templates: list[dict[str, Any]] = []
    for path, definition in dynamic_sources.items():
        assert definition.metadata is not None  # noqa: S101
        resolved_index = definition.metadata.index if definition.metadata.index is not None else True
        value_annotation = mapping_value_annotation(definition)
        nested_template = definition.metadata.kind in {"FlattenedObject", "FlattenedListObject"}
        templates.extend(
            _dynamic_templates(
                f"{path}.*",
                value_annotation,
                inherited_index=resolved_index,
                nested_template=nested_template,
            )
        )
    return templates


def document_mapping(model_type: type[BaseModel] | None) -> dict[str, Any]:
    """Build the complete ``mappings`` block for a schema model (or a schema-less collection)."""
    mappings: dict[str, Any] = deepcopy(default_mapping)

    if model_type is not None:
        properties, dynamic_sources = build_properties(model_type)
        dynamic_templates = build_dynamic_templates(dynamic_sources)
        if not dynamic_templates:
            dynamic_templates.append(
                {
                    "refuse_all_implicit_mappings": {
                        "match": "*",
                        "mapping": {"index": False, "ignore_malformed": True},
                    }
                }
            )
        dynamic_templates.insert(0, default_dynamic_strings)
        mappings["properties"] = properties
        mappings["dynamic_templates"] = dynamic_templates
    else:
        mappings["dynamic_templates"] = deepcopy(default_dynamic_templates)

    if not mappings["dynamic_templates"]:
        mappings["dynamic"] = "strict"

    mappings["properties"]["id"] = dict(ID_PROPERTY_MAPPING)
    mappings["properties"]["__text__"] = dict(TEXT_PROPERTY_MAPPING)

    return mappings


def build_index_contract(model_type: type[BaseModel] | None, *, shards: int, replicas: int) -> IndexContract:
    """Build the complete settings + mappings contract for one collection."""
    return IndexContract(
        settings=index_settings(model_type, shards=shards, replicas=replicas),
        mappings=document_mapping(model_type),
    )


def ilm_template_body(
    model_type: type[BaseModel] | None,
    *,
    shards: int,
    replicas: int,
    policy_name: str,
    rollover_alias: str,
) -> dict[str, Any]:
    """Build the composable index template body (settings + mappings + ILM lifecycle settings)."""
    contract = build_index_contract(model_type, shards=shards, replicas=replicas)
    settings = deepcopy(contract.settings)
    settings["index"]["lifecycle.name"] = policy_name
    settings["index"]["lifecycle.rollover_alias"] = rollover_alias
    return {"settings": settings, "mappings": contract.mappings}
