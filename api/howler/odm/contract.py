"""Generate deterministic compatibility contracts for the legacy ODM."""

from __future__ import annotations

import ast
import hashlib
import importlib
import inspect
import json
import pkgutil
import re
from datetime import date, datetime
from enum import Enum as PyEnum
from ipaddress import IPv4Address, IPv6Address
from pathlib import Path
from typing import Any

import howler.odm.base as odm_base
import howler.odm.models as model_package
from howler.common.exceptions import HowlerException
from howler.datastore.support.build import build_mapping
from howler.odm.base import Compound, Enum, List, Mapping, Model, Optional, _Field

CONTRACT_VERSION = 1
REPOSITORY_ROOT = Path(__file__).parents[3]
GENERATED_ARTIFACT_GLOBS = (
    "documentation/docs/odm/**/*.md",
    "ui/src/models/entities/generated/*.d.ts",
)
VALIDATION_INPUTS = (
    None,
    "",
    "Example",
    "127.0.0.1",
    "2024-01-02T03:04:05.000000Z",
    "0123456789abcdef0123456789abcdef",
    0,
    1,
    1.5,
    True,
    [],
    ["Example"],
    {},
    {"key": "Example"},
)


def _qualified_name(value: type[Any]) -> str:
    return f"{value.__module__}.{value.__qualname__}"


def _normalize(value: Any) -> Any:  # noqa: C901
    if isinstance(value, PyEnum):
        return _normalize(value.value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (IPv4Address, IPv6Address)):
        return str(value)
    if isinstance(value, odm_base.ClassificationObject):
        return str(value)
    if isinstance(value, Model):
        return _normalize(value.as_primitives())
    if isinstance(value, re.Pattern):
        return value.pattern
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [_normalize(item) for item in value]
        return sorted(normalized, key=lambda item: json.dumps(item, sort_keys=True))
    if value is None or isinstance(value, (bool, float, int, str)):
        return value

    raise TypeError(f"Unsupported ODM contract value: {value!r}")


def _field_classes() -> list[type[_Field]]:
    return sorted(
        (
            field_class
            for _, field_class in inspect.getmembers(odm_base, inspect.isclass)
            if field_class.__module__ == odm_base.__name__
            and issubclass(field_class, _Field)
            and field_class is not _Field
        ),
        key=_qualified_name,
    )


def _parameter_contract(parameter: inspect.Parameter) -> dict[str, Any]:
    contract: dict[str, Any] = {
        "kind": parameter.kind.name,
        "required": parameter.default is inspect.Parameter.empty,
    }
    if parameter.default is not inspect.Parameter.empty:
        contract["default"] = _normalize(parameter.default)
    if parameter.annotation is not inspect.Parameter.empty:
        contract["annotation"] = inspect.formatannotation(parameter.annotation)
    return contract


def _field_type_contract(field_class: type[_Field]) -> dict[str, Any]:
    return {
        "bases": [
            _qualified_name(base)
            for base in field_class.__bases__
            if inspect.isclass(base) and issubclass(base, _Field)
        ],
        "constructor": {
            name: _parameter_contract(parameter)
            for name, parameter in inspect.signature(field_class).parameters.items()
        },
        "description": inspect.getdoc(field_class),
    }


def _field_contract(field: _Field) -> dict[str, Any]:
    contract = {
        "type": _qualified_name(type(field)),
        "index": field.index,
        "store": field.store,
        "copy_to": list(field.copyto),
        "default_set": field.default_set,
        "default": _normalize(field.default),
        "description": field.description,
        "reference": field.reference,
        "optional": field.optional,
        "deprecated": field.deprecated,
        "deprecated_description": field.deprecated_description,
        "sync": field.sync,
    }

    for attribute in ("min", "max", "strict", "is_uc"):
        if hasattr(field, attribute):
            contract[attribute] = _normalize(getattr(field, attribute))

    if hasattr(field, "validation_regex"):
        contract["validation_regex"] = field.validation_regex.pattern

    if isinstance(field, Enum):
        contract["values"] = _normalize(field.values)

    if isinstance(field, (List, Mapping, Optional)):
        contract["child"] = _field_contract(field.child_type)

    if isinstance(field, Compound):
        contract["model"] = _qualified_name(field.child_type)

    return contract


def discover_models() -> list[type[Model]]:
    """Import and return every decorated model in the core ODM package."""
    models: list[type[Model]] = []

    for module_info in pkgutil.walk_packages(model_package.__path__, f"{model_package.__name__}."):
        module = importlib.import_module(module_info.name)
        for _, model_class in inspect.getmembers(module, inspect.isclass):
            if (
                model_class.__module__ == module.__name__
                and issubclass(model_class, Model)
                and "_Model__id_field" in model_class.__dict__
            ):
                models.append(model_class)

    return sorted(models, key=_qualified_name)


def _model_contract(model_class: type[Model]) -> dict[str, Any]:
    properties, dynamic_templates = build_mapping(model_class.fields().values())
    return {
        "name": model_class.__name__,
        "description": model_class._Model__description,  # type: ignore[attr-defined]
        "id_field": model_class._Model__id_field,  # type: ignore[attr-defined]
        "fields": {name: _field_contract(field) for name, field in sorted(model_class.fields(no_cache=True).items())},
        "flat_fields": {
            path: _field_contract(field) for path, field in sorted(model_class.flat_fields(show_compound=True).items())
        },
        "elasticsearch": {
            "properties": properties,
            "dynamic_templates": dynamic_templates,
        },
    }


def _collection_contract(name: str, model_class: type[Model] | None, ilm_enabled: bool) -> dict[str, Any]:
    from howler.datastore.collection import ESCollection

    collection = object.__new__(ESCollection)
    collection.model_class = model_class
    collection.name = f"howler-{name}"
    collection.shards = 1
    collection.replicas = 0

    settings = collection._get_index_settings()
    mappings = collection._get_index_mappings()
    contract = {
        "model": _qualified_name(model_class) if model_class else None,
        "ilm_enabled_by_default": ilm_enabled,
        "legacy_index": {
            "aliases": {collection.name: {}},
            "mappings": mappings,
            "settings": settings,
        },
    }
    if ilm_enabled:
        ilm_settings = json.loads(json.dumps(settings))
        ilm_settings["index"]["lifecycle.name"] = f"{collection.name}_policy"
        ilm_settings["index"]["lifecycle.rollover_alias"] = collection.name
        contract["ilm_template"] = {
            "index_patterns": [f"{collection.name}-*"],
            "template": {
                "mappings": mappings,
                "settings": ilm_settings,
            },
        }

    return contract


def _field_instance(field_class: type[_Field]) -> _Field:
    if field_class is Enum:
        return field_class(["one", "two"])
    if field_class is Compound:
        return field_class(_ContractChild)
    if field_class in {List, Mapping, Optional}:
        return field_class(odm_base.Keyword())
    if field_class is odm_base.ValidatedKeyword:
        return field_class(re.compile(r"^[A-Za-z]+$"))
    return field_class()


@odm_base.model()
class _ContractChild(Model):
    value = odm_base.Keyword()


def _field_validation_contract(field_class: type[_Field]) -> list[dict[str, Any]]:
    field = _field_instance(field_class)
    outcomes = []
    for value in VALIDATION_INPUTS:
        try:
            normalized = field.check(value)
        except (AttributeError, HowlerException, KeyError, TypeError, ValueError) as error:
            outcomes.append(
                {
                    "accepted": False,
                    "error": _qualified_name(type(error)),
                    "input": _normalize(value),
                }
            )
        else:
            if field_class is odm_base.UUID and value is None:
                normalized = "<generated UUID>"
            outcomes.append(
                {
                    "accepted": True,
                    "input": _normalize(value),
                    "normalized": _normalize(normalized),
                }
            )
    return outcomes


def _generated_artifact_contract() -> dict[str, dict[str, Any]]:
    artifacts = {}
    for pattern in GENERATED_ARTIFACT_GLOBS:
        for path in REPOSITORY_ROOT.glob(pattern):
            if not path.is_file():
                continue
            content = path.read_bytes()
            artifacts[path.relative_to(REPOSITORY_ROOT).as_posix()] = {
                "sha256": hashlib.sha256(content).hexdigest(),
                "size": len(content),
            }
    return dict(sorted(artifacts.items()))


def _collect_source_usage(
    node: ast.AST,
    relative_path: str,
    collection_methods: set[str],
    imports: list[dict[str, Any]],
    datastore_calls: list[dict[str, Any]],
    extension_hooks: list[dict[str, Any]],
) -> None:
    if isinstance(node, ast.Import):
        modules = sorted(alias.name for alias in node.names if alias.name.startswith("howler.odm"))
        if modules:
            imports.append({"line": node.lineno, "modules": modules, "path": relative_path})
    elif isinstance(node, ast.ImportFrom):
        module = node.module or ""
        names = sorted(alias.name for alias in node.names)
        if module.startswith("howler.odm") or (module == "howler" and "odm" in names):
            imports.append(
                {
                    "line": node.lineno,
                    "module": module,
                    "names": names,
                    "path": relative_path,
                }
            )
    elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        receiver = ast.unparse(node.func.value)
        usage = {
            "line": node.lineno,
            "method": node.func.attr,
            "path": relative_path,
            "receiver": receiver,
        }
        if node.func.attr in {"add_namespace", "remove_namespace"}:
            extension_hooks.append(usage)
        receiver_tokens = set(re.findall(r"[A-Za-z_]+", receiver.lower()))
        is_collection_receiver = any(
            token in {"col", "collection", "datastore", "ds", "es_connection", "storage"}
            or token.endswith(("_collection", "_datastore"))
            or token.startswith("datastore")
            for token in receiver_tokens
        )
        if node.func.attr in collection_methods and is_collection_receiver:
            datastore_calls.append(usage)


def _source_usage_contract() -> dict[str, list[dict[str, Any]]]:
    from howler.datastore.collection import ESCollection

    collection_methods = {
        name for name, value in inspect.getmembers(ESCollection, inspect.isfunction) if not name.startswith("_")
    }
    imports: list[dict[str, Any]] = []
    datastore_calls: list[dict[str, Any]] = []
    extension_hooks: list[dict[str, Any]] = []
    source_roots = (
        REPOSITORY_ROOT / "api",
        REPOSITORY_ROOT / "client",
        REPOSITORY_ROOT / "plugins",
    )
    for source_root in source_roots:
        for path in source_root.rglob("*.py"):
            if {".tox", ".venv", "node_modules"} & set(path.parts):
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue

            relative_path = path.relative_to(REPOSITORY_ROOT).as_posix()
            for node in ast.walk(tree):
                _collect_source_usage(
                    node,
                    relative_path,
                    collection_methods,
                    imports,
                    datastore_calls,
                    extension_hooks,
                )

    def ordering(usage: dict[str, Any]) -> tuple[str, int, str]:
        return usage["path"], usage["line"], usage.get("method", "")

    return {
        "datastore_calls": sorted(datastore_calls, key=ordering),
        "extension_hooks": sorted(extension_hooks, key=ordering),
        "imports": sorted(imports, key=lambda usage: (usage["path"], usage["line"])),
    }


def build_contract_inventory() -> dict[str, Any]:
    """Build the complete core ODM compatibility inventory."""
    from howler.datastore.howler_store import ILM_ENABLED_INDEXES, INDEXES

    return {
        "contract_version": CONTRACT_VERSION,
        "collections": {
            name: _collection_contract(name, model_class, name in ILM_ENABLED_INDEXES)
            for name, model_class in sorted(INDEXES.items())
        },
        "field_types": {
            _qualified_name(field_class): _field_type_contract(field_class) for field_class in _field_classes()
        },
        "field_validation": {
            _qualified_name(field_class): _field_validation_contract(field_class) for field_class in _field_classes()
        },
        "generated_artifacts": _generated_artifact_contract(),
        "models": {_qualified_name(model_class): _model_contract(model_class) for model_class in discover_models()},
        "source_usage": _source_usage_contract(),
    }


def render_contract_inventory() -> str:
    """Render the current contract as stable, human-reviewable JSON."""
    return json.dumps(build_contract_inventory(), indent=2, sort_keys=True) + "\n"


def write_contract_inventory(path: Path) -> None:
    """Write the current contract inventory to *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_contract_inventory(), encoding="utf-8")
