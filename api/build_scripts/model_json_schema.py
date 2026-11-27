"""Offline JSON Schema for Howler's public entities and published ODM field tables.

Pydantic supplies the types, constraints, aliases and local references. The public
profile describes Howler's ``as_primitives`` output and its UI projection contract,
not the fields required to validate a new document.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast, get_args, get_origin

from pydantic import BaseModel, create_model
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema

if TYPE_CHECKING:
    from howler.models.fields import HowlerFieldMetadata

PUBLIC_INDEXES = ("action", "analytic", "case", "dossier", "event", "hit", "overview", "template", "user", "view")
API_DIR = Path(__file__).resolve().parents[1]
Profile = Literal["entities", "documentation"]


def _without_null(node: JsonSchemaValue) -> JsonSchemaValue:
    """A null property or mapping value is omitted; null array elements are retained."""
    if "anyOf" in node:
        branches = [_without_null(branch) for branch in node["anyOf"] if branch.get("type") != "null"]
        rest = {k: v for k, v in node.items() if k != "anyOf"}
        if not branches:
            return {**rest, "enum": []}  # A null-only property is never present.
        return {**branches[0], **rest} if len(branches) == 1 else {**rest, "anyOf": branches}
    if node.get("type") == "null":
        return {**node, "not": {"type": "null"}}
    if "enum" in node and None in node["enum"]:
        return {**node, "enum": [value for value in node["enum"] if value is not None]}
    return node


def _describe_kind(node: JsonSchemaValue, metadata: HowlerFieldMetadata) -> None:
    if metadata.kind is not None:
        node["x-howler-kind"] = metadata.kind
    if metadata.kind == "Enum" and node.get("type") == "string":
        # enum() returns strings. Iterable declarations may be unordered sets.
        node["enum"] = sorted({str(v) for v in dict(metadata.options)["values"] if v})
    if metadata.kind in {"Integer", "Long"}:
        # Pydantic's after-coercion constraints can be emitted as ge/le.
        for key, standard in (("ge", "minimum"), ("le", "maximum")):
            if key in node:
                node[standard] = node.pop(key)
    if metadata.reference:
        node["x-howler-reference"] = metadata.reference
    if metadata.deprecated:
        node["deprecated"] = True
        node["x-howler-deprecation"] = metadata.deprecated_description


def _describe_type(node: JsonSchemaValue, annotation: Any, metadata: HowlerFieldMetadata | None) -> None:
    """Attach ODM vocabulary and validator-backed constraints at their actual container depth."""
    from howler.models.registry import field_metadata, unwrap_annotation

    if metadata is not None:
        _describe_kind(node, metadata)
    unwrapped = unwrap_annotation(annotation)
    args = get_args(unwrapped)
    if get_origin(unwrapped) is list and "items" in node:
        child = node["items"]
        # A nullable list item still occupies a position in the serialized array.
        for branch in child.get("anyOf", [child]):
            if branch.get("type") != "null":
                _describe_type(branch, args[0], field_metadata(args[0]))
    elif unwrapped is dict or get_origin(unwrapped) in (dict, Mapping):
        if isinstance(child := node.get("additionalProperties"), dict):
            value_type = args[1] if len(args) == 2 else Any
            _describe_type(child, value_type, field_metadata(value_type))


class _PrimitiveSchema(GenerateJsonSchema):
    """Adjust Pydantic's serialization schema for Howler's public primitive serializer."""

    def any_schema(self, schema: core_schema.AnySchema) -> JsonSchemaValue:
        # Use a named recursive value so Pydantic manages its local $ref just
        # like model references. Only array elements may be null at any depth.
        name = f"{__name__}.HowlerJsonValue"
        value = core_schema.definition_reference_schema(name)
        non_null = core_schema.union_schema(
            [
                core_schema.bool_schema(),
                core_schema.float_schema(),  # JSON number includes integers.
                core_schema.str_schema(),
                core_schema.list_schema(core_schema.nullable_schema(value)),
                core_schema.dict_schema(core_schema.str_schema(), value),
            ],
            ref=name,
        )
        return self.generate_inner(core_schema.nullable_schema(non_null))

    def dict_schema(self, schema: core_schema.DictSchema) -> JsonSchemaValue:
        node = super().dict_schema({"values_schema": core_schema.any_schema(), **schema})
        if isinstance(value := node.get("additionalProperties"), dict):
            node["additionalProperties"] = _without_null(value)
        for pattern, value in node.get("patternProperties", {}).items():
            node["patternProperties"][pattern] = _without_null(value)
        return node

    def is_instance_schema(self, schema: core_schema.IsInstanceSchema) -> JsonSchemaValue:
        from howler.models.fields import ClassificationValue

        if schema["cls"] is ClassificationValue:
            return {"type": "string"}
        return super().is_instance_schema(schema)

    def model_fields_schema(self, schema: core_schema.ModelFieldsSchema) -> JsonSchemaValue:
        # BaseESModel.meta is private DSL state (and is not JSON serializable).
        fields = {k: v for k, v in schema["fields"].items() if k != "meta"}
        return super().model_fields_schema({**schema, "fields": fields})

    def model_schema(self, schema: core_schema.ModelSchema) -> JsonSchemaValue:
        from howler.models.registry import model_registry

        node = super().model_schema(schema)
        model = cast(type[BaseModel], schema["cls"])
        props = node["properties"]
        definitions = model_registry.fields(model)
        for python_name, info in model.model_fields.items():
            key = info.serialization_alias or info.alias or python_name
            if key not in props:
                continue
            name = info.serialization_alias or info.alias or python_name.rstrip("_")
            definition = definitions[name]
            prop = _without_null(props[key] if key == name else props.pop(key))
            _describe_type(prop, definition.annotation, definition.metadata)
            if definition.description:
                prop["description"] = definition.description
            # Input defaults such as NOW, {}, or None are not serialized default values.
            if "default" in prop:
                prop["x-howler-default"] = prop.pop("default")
            if (
                definition.metadata
                and definition.metadata.optional
                or (not definition.required and definition.default is None and definition.default_factory is None)
            ):
                prop["x-howler-optional"] = True
            props[name] = prop
        node.pop("required", None)
        return node


def _belongs_to(model: type[BaseModel], module: str, name: str) -> bool:
    # A reachable model's module is necessarily loaded. Compare the actual class
    # (including finalized subclasses) without importing unrelated deployment models.
    return getattr(sys.modules.get(f"howler.models.{module}"), name, None) in model.__mro__


class _EntitySchema(_PrimitiveSchema):
    def model_schema(self, schema: core_schema.ModelSchema) -> JsonSchemaValue:
        node = super().model_schema(schema)
        model = cast(type[BaseModel], schema["cls"])
        if _belongs_to(model, "user", "User"):
            # Credential-bearing objects are private even when embedded by a plugin.
            node["properties"].pop("apikeys", None)
            node["properties"].pop("password", None)
        if getattr(model, "_include_index", False) is True:
            node["properties"]["__index"] = {"type": "string", "const": model.__name__.lower()}
            node["required"] = ["__index"]
            if _belongs_to(model, "hit", "Hit") or _belongs_to(model, "event", "Event"):
                node["required"] += ["timestamp", "howler"]
        # The UI's identity fields survive its usual projection; other fields may
        # be absent, even when required for ingestion. Apply this to nested records too.
        if _belongs_to(model, "howler_data", "HowlerData"):
            node["required"] = ["id", "hash", "analytic", "assignment"]
        elif _belongs_to(model, "event", "EventData"):
            node["required"] = ["id", "hash"]
        return node


class _DocumentationSchema(_PrimitiveSchema):
    def model_schema(self, schema: core_schema.ModelSchema) -> JsonSchemaValue:
        from howler.models.registry import model_registry

        node = super().model_schema(schema)
        if description := model_registry.metadata(cast(type[BaseModel], schema["cls"])).description:
            node["description"] = description
        return node


def _bundle(models: Mapping[str, type[BaseModel]], *, documentation: bool = False) -> JsonSchemaValue:
    # A single schema lets Pydantic disambiguate identically named models (including
    # plugin types), share references, and prune unreachable/private definitions.
    roots: dict[str, Any] = {name: (model, ...) for name, model in sorted(models.items())}
    bundle = create_model("HowlerSchema", **roots)

    generator = _DocumentationSchema if documentation else _EntitySchema
    result = bundle.model_json_schema(mode="serialization", schema_generator=generator)
    result["$schema"] = generator.schema_dialect
    result["additionalProperties"] = False
    result.setdefault("$defs", {})
    return result


def _fixture_environment() -> dict[str, str]:
    # Pydantic Settings reads environment variables case-insensitively. Strip those
    # overrides before importing Howler, including during interpreter startup.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("HWL_") and k.upper() != "AZURE_TEST_CONFIG"}
    fixture = API_DIR / "build_scripts"
    env.update(
        # Config also probes Path('/etc') / APP_NAME / 'conf' before HWL_CONF_FOLDER.
        APP_NAME=str(fixture),
        HWL_CONF_FOLDER=str(fixture),  # classification field validators
        HWL_CLASSIFICATION_PATH=str(fixture / "classification.yml"),  # model defaults
    )
    return env


def _fixture_schema(profile: Profile) -> JsonSchemaValue:
    # Models capture the classification engine and default marking *at import*;
    # extension finalization also registers derived classes. Isolate both from a
    # caller that may already be running Howler with a different configuration.
    raw = subprocess.check_output(
        [sys.executable, "-m", "build_scripts.model_json_schema", profile],
        cwd=API_DIR,
        env=_fixture_environment(),
    )
    return json.loads(raw)


def entity_schema(models: Mapping[str, type[BaseModel] | None] | None = None) -> JsonSchemaValue:
    """Return the ten built-in UI roots, or the public subset of supplied finalized models.

    ``properties[index]`` always holds a local ``$ref`` into ``$defs``. Supplying a
    mapping (e.g. from runtime finalization) uses those exact classes: this function
    never discovers plugins, declares extensions, or changes the caller's registries.
    """
    if models is None:
        return _fixture_schema("entities")
    return _bundle({index: model for index, model in models.items() if index in PUBLIC_INDEXES and model is not None})


def documentation_schema() -> JsonSchemaValue:
    """Return the historical pre-extension ODM documentation scope with repository defaults."""
    return _fixture_schema("documentation")


def _builtins() -> dict[str, type[BaseModel]]:
    from howler.models import model_extensions
    from howler.models.clue import declare_hit_extension

    # This interpreter owns its registry. Reuse the real declaration, without
    # depending on deployment feature flags or importing datastore startup.
    declare_hit_extension()
    return {
        index: model_extensions.finalize(getattr(importlib.import_module(f"howler.models.{index}"), index.title()))
        for index in PUBLIC_INDEXES
    }


if __name__ == "__main__":
    # Direct CLI use has the same isolated profile as the subprocess API.
    fixture_env = _fixture_environment()
    for key in os.environ.keys() - fixture_env.keys():
        del os.environ[key]
    os.environ.update(fixture_env)
    if sys.argv[1:] == ["entities"]:
        json.dump(entity_schema(_builtins()), sys.stdout)
    elif sys.argv[1:] == ["documentation"]:
        from build_scripts.generate_md_docs import documentation_models

        json.dump(_bundle(documentation_models(), documentation=True), sys.stdout)
    else:
        raise SystemExit("Expected profile: entities or documentation")
