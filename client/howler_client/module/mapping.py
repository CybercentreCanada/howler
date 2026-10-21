"""Offline, deterministic mapping of raw table rows to Howler hit records.

The mapping format is deliberately declarative. It never evaluates code, talks to
Howler, or creates server-owned identifiers. See the client README for examples.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import math
import os
import re
import sys
from collections.abc import Generator, Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeAlias, cast

import yaml

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

_FIELD_TYPES = {
    "keyword",
    "text",
    "integer",
    "long",
    "float",
    "boolean",
    "ip",
    "date",
    "object",
}
_TRANSFORMS = {
    "string",
    "integer",
    "number",
    "boolean",
    "trim",
    "lower",
    "upper",
    "list",
    "json",
}
_OMIT = object()
_MAX_JSON_NESTING = 128


class MappingError(ValueError):
    """A mapping document, source row, or optional field snapshot is invalid."""


RowMappingResult: TypeAlias = tuple[dict[str, Any] | None, MappingError | None]


def _clone_json(
    value: Any,
    context: str,
    seen: set[int] | None = None,
    depth: int = 0,
) -> Any:
    """Copy JSON values, rejecting unsupported values and nesting beyond 128."""
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise MappingError(f"{context} contains a non-finite number")
        return value

    active = seen if seen is not None else set()
    if isinstance(value, (Mapping, list)):
        if depth >= _MAX_JSON_NESTING:
            raise MappingError(f"{context} exceeds the maximum JSON nesting depth of {_MAX_JSON_NESTING}")
        identity = id(value)
        if identity in active:
            raise MappingError(f"{context} contains a cyclic value")
        active.add(identity)
        try:
            if isinstance(value, Mapping):
                result: dict[str, Any] = {}
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise MappingError(f"{context} object keys must be strings")
                    result[key] = _clone_json(item, context, active, depth + 1)
                return result
            return [_clone_json(item, context, active, depth + 1) for item in value]
        finally:
            active.remove(identity)

    raise MappingError(f"{context} contains a non-JSON value")


def _canonical_json(value: Any) -> str:
    normalized = _clone_json(value, "JSON value")
    try:
        serialized = json.dumps(
            normalized,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError, RecursionError):
        serialized = None
    if serialized is None:
        raise MappingError("JSON value cannot be serialized safely")
    return serialized


class _StrictLoader(yaml.SafeLoader):
    """Safe YAML loader with duplicate-key and scalar-resolution safeguards."""

    yaml_implicit_resolvers = {
        key: list(resolvers) for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
    }


for _character, _resolvers in tuple(_StrictLoader.yaml_implicit_resolvers.items()):
    _StrictLoader.yaml_implicit_resolvers[_character] = [
        (tag, resolver)
        for tag, resolver in _resolvers
        if tag not in {"tag:yaml.org,2002:timestamp", "tag:yaml.org,2002:bool"}
    ]
_StrictLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(true|false)$"), list("tf"))


def _construct_yaml_mapping(loader: Any, node: Any, deep: bool = False) -> dict[str, Any]:
    if any(getattr(key_node, "tag", None) == "tag:yaml.org,2002:merge" for key_node, _value_node in node.value):
        raise MappingError("YAML merge keys are not supported")

    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise MappingError("YAML object keys must be strings")
        if key in result:
            raise MappingError("duplicate YAML object key")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_StrictLoader.add_constructor("tag:yaml.org,2002:map", _construct_yaml_mapping)


def _load_yaml(text: str) -> Any:
    if not isinstance(text, str):
        raise TypeError("YAML input must be text")

    try:
        tokens = list(yaml.scan(text))
    except yaml.YAMLError:
        raise MappingError("invalid YAML mapping document") from None
    if any(isinstance(token, (yaml.tokens.AnchorToken, yaml.tokens.AliasToken)) for token in tokens):
        raise MappingError("YAML anchors and aliases are not supported")

    try:
        loaded = yaml.load(text, Loader=_StrictLoader)  # noqa: S506 - _StrictLoader subclasses SafeLoader.
        return _clone_json(loaded, "mapping document")
    except MappingError:
        raise  # Preserve intentional safe parser and schema messages before ValueError normalization.
    except (yaml.YAMLError, TypeError, ValueError, KeyError, OverflowError, RecursionError):
        # Parser errors can include source snippets; never echo mapping text.
        raise MappingError("invalid YAML mapping document") from None


def _is_howler_id_target(target: str) -> bool:
    return target == "howler.id" or target.startswith("howler.id.")


def _reject_howler_id(record: Mapping[str, Any]) -> None:
    if any(_is_howler_id_target(target) for target in record if isinstance(target, str)):
        raise MappingError("howler.id is server-generated and must not be set")

    howler = record.get("howler")
    if isinstance(howler, Mapping) and any(
        isinstance(key, str) and (key == "id" or key.startswith("id.")) for key in howler
    ):
        raise MappingError("howler.id is server-generated and must not be set")


def _validate_path(path: Any, *, target: str) -> None:
    if not isinstance(path, list) or not path:
        raise MappingError(f"invalid source path for target: {target}")
    for segment in path:
        if isinstance(segment, str):
            continue
        if type(segment) is int and segment >= 0:
            continue
        raise MappingError(f"invalid source path for target: {target}")


def _validate_column_expression(target: str, spec: dict[str, Any], columns: set[str]) -> None:
    column = spec["column"]
    if not isinstance(column, str) or not column:
        raise MappingError(f"invalid source column for target: {target}")
    if column not in columns:
        raise MappingError(f"undeclared source column for target: {target}")
    if "path" in spec:
        _validate_path(spec["path"], target=target)


def _validate_concat_expression(target: str, spec: dict[str, Any], columns: set[str]) -> None:
    concat = spec["concat"]
    if (
        not isinstance(concat, list)
        or len(concat) < 2
        or any(not isinstance(column, str) or not column for column in concat)
        or len(set(concat)) != len(concat)
    ):
        raise MappingError(f"invalid concatenation for target: {target}")
    if any(column not in columns for column in concat):
        raise MappingError(f"undeclared source column for target: {target}")


def _validate_transforms(target: str, transforms: Any) -> None:
    if not isinstance(transforms, list):
        raise MappingError(f"invalid transforms for target: {target}")
    for operation in transforms:
        if isinstance(operation, str) and operation in _TRANSFORMS:
            continue
        if isinstance(operation, dict) and set(operation) <= {"op", "assume_timezone"}:
            if operation.get("op") != "timestamp":
                raise MappingError(f"unsupported transform for target: {target}")
            if "assume_timezone" in operation and operation["assume_timezone"] != "UTC":
                raise MappingError(f"invalid timestamp timezone for target: {target}")
            continue
        raise MappingError(f"unsupported transform for target: {target}")


def _validate_expression(target: str, spec: Any, columns: set[str]) -> None:
    if not isinstance(spec, dict):
        raise MappingError(f"invalid mapping expression for target: {target}")
    if set(spec) - {"column", "path", "concat", "value", "on_null", "transforms"}:
        raise MappingError(f"unsupported mapping key for target: {target}")
    expressions = sum(key in spec for key in ("column", "concat", "value"))
    if expressions != 1:
        raise MappingError(f"target requires exactly one expression: {target}")
    if "on_null" in spec and (not isinstance(spec["on_null"], str) or spec["on_null"] not in {"error", "omit"}):
        raise MappingError(f"invalid null policy for target: {target}")

    if "column" in spec:
        _validate_column_expression(target, spec, columns)
    elif "path" in spec:
        raise MappingError(f"path requires a column expression for target: {target}")
    if "concat" in spec:
        _validate_concat_expression(target, spec, columns)
    if "transforms" in spec:
        _validate_transforms(target, spec["transforms"])


def _validate_source(source: Any) -> set[str]:
    if not isinstance(source, dict) or set(source) != {"table", "columns"}:
        raise MappingError("source must contain only table and columns")
    if not isinstance(source["table"], str) or not source["table"]:
        raise MappingError("source.table must be a non-empty string")
    columns = source["columns"]
    if (
        not isinstance(columns, list)
        or not columns
        or any(not isinstance(column, str) or not column for column in columns)
        or len(set(columns)) != len(columns)
    ):
        raise MappingError("source.columns must contain unique non-empty strings")
    return set(columns)


def _validate_target_metadata(target: Any) -> None:
    if not isinstance(target, dict) or set(target) != {"index", "mcp_url", "fields_sha256"}:
        raise MappingError("target must contain only index, mcp_url, and fields_sha256")
    if target["index"] != "hit":
        raise MappingError("mapping version 1 supports only the hit index")
    if not isinstance(target["mcp_url"], str) or not target["mcp_url"].startswith("https://"):
        raise MappingError("target.mcp_url must be an HTTPS URL")
    fingerprint = target["fields_sha256"]
    if not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        raise MappingError("target.fields_sha256 must be a lowercase SHA-256 digest")


def _validate_policy(policy: Any) -> None:
    if not isinstance(policy, dict) or set(policy) != {"missing", "on_null"}:
        raise MappingError("policy must contain only missing and on_null")
    if policy["missing"] != "error":
        raise MappingError("policy.missing must be error")
    if not isinstance(policy["on_null"], str) or policy["on_null"] not in {"error", "omit"}:
        raise MappingError("policy.on_null must be error or omit")


def _validate_targets(mappings: Any, columns: set[str]) -> None:
    if not isinstance(mappings, dict) or not mappings:
        raise MappingError("mapping must define at least one target")
    target_names: list[str] = []
    for name, expression in mappings.items():
        if not isinstance(name, str) or not name or any(part == "" for part in name.split(".")):
            raise MappingError("mapping targets must be non-empty dotted field names")
        if _is_howler_id_target(name):
            raise MappingError("howler.id is server-generated and must not be set")
        _validate_expression(name, expression, columns)
        if name == "howler" and "value" in expression:
            _reject_howler_id({"howler": expression["value"]})
        target_names.append(name)

    ordered_targets = sorted(target_names)
    for index, name in enumerate(ordered_targets):
        if any(other.startswith(name + ".") for other in ordered_targets[index + 1 :]):
            raise MappingError(f"conflicting parent/child target: {name}")


def _validate_constant_expressions(mappings: dict[str, Any], null_policy: str) -> None:
    for target, expression in mappings.items():
        if "value" not in expression:
            continue
        error_message: str | None = None
        try:
            value = _evaluate(expression, {}, null_policy)
            if value is not _OMIT:
                _canonical_json(value)
        except MappingError as exc:
            error_message = str(exc)
        if error_message is not None:
            raise MappingError(f"invalid constant for target {target}: {error_message}")


def _validate_mapping_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise MappingError("mapping document must be an object")
    if set(document) != {"version", "source", "target", "policy", "mappings"}:
        raise MappingError("mapping document has missing or unsupported keys")
    if type(document["version"]) is not int or document["version"] != 1:
        raise MappingError("only mapping version 1 is supported")

    columns = _validate_source(document["source"])
    _validate_target_metadata(document["target"])
    _validate_policy(document["policy"])
    _validate_targets(document["mappings"], columns)
    _validate_constant_expressions(document["mappings"], document["policy"]["on_null"])
    return document


def _valid_regex(pattern: str) -> bool:
    try:
        re.compile(pattern)
    except re.error:
        return False
    return True


def _validate_field_metadata(name: Any, metadata: Any) -> None:
    if not isinstance(name, str) or not isinstance(metadata, dict):
        raise MappingError("fields_snapshot contains invalid field metadata")
    field_type = metadata.get("type")
    if not isinstance(field_type, str) or field_type not in _FIELD_TYPES or type(metadata.get("list")) is not bool:
        raise MappingError("fields_snapshot contains unsupported field metadata")
    if "deprecated" in metadata and type(metadata["deprecated"]) is not bool:
        raise MappingError("fields_snapshot contains unsupported field metadata")
    if "values" in metadata and metadata["values"] is not None and not isinstance(metadata["values"], list):
        raise MappingError("fields_snapshot contains unsupported field metadata")
    pattern = metadata.get("regex")
    if pattern is not None and (not isinstance(pattern, str) or not _valid_regex(pattern)):
        raise MappingError("fields_snapshot contains unsupported field metadata")


def _validate_fields_snapshot(snapshot: Any) -> dict[str, Any]:
    required = {"version", "mcp_url", "fields_sha256", "fields"}
    if not isinstance(snapshot, dict) or set(snapshot) != required:
        raise MappingError("fields_snapshot must be a saved version-1 fields snapshot")
    if type(snapshot["version"]) is not int or snapshot["version"] != 1:
        raise MappingError("fields_snapshot has an unsupported version")
    if not isinstance(snapshot["mcp_url"], str) or not snapshot["mcp_url"].startswith("https://"):
        raise MappingError("fields_snapshot endpoint must be an HTTPS URL")

    fields = snapshot["fields"]
    if not isinstance(fields, dict) or not fields:
        raise MappingError("fields_snapshot must contain field metadata")
    for name, metadata in fields.items():
        _validate_field_metadata(name, metadata)

    fingerprint = snapshot["fields_sha256"]
    if not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        raise MappingError("fields_snapshot has an invalid fingerprint")
    expected = hashlib.sha256(_canonical_json(fields).encode("utf-8")).hexdigest()
    if fingerprint != expected:
        raise MappingError("fields_snapshot fingerprint does not match its fields")
    return snapshot


def _timestamp(value: Any, assume_timezone: Any = None) -> str:
    if not isinstance(value, str):
        raise MappingError("timestamp requires an ISO-8601 string")
    timestamp_text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(timestamp_text)
    except ValueError:
        raise MappingError("invalid ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        if assume_timezone != "UTC":
            raise MappingError("timestamp has no timezone; explicitly set assume_timezone: UTC")
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        normalized = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise MappingError("invalid ISO-8601 timestamp") from None
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _transform_text(value: Any, operation: str) -> str:
    if not isinstance(value, str):
        raise MappingError("text transform requires a string")
    if operation == "trim":
        return value.strip()
    if operation == "lower":
        return value.lower()
    return value.upper()


def _transform_string(value: Any) -> str:
    if isinstance(value, (dict, list)):
        raise MappingError("use the json transform for structured values")
    return _canonical_json(value) if not isinstance(value, str) else value


def _transform_boolean(value: Any) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str) and value in {"true", "false"}:
        return value == "true"
    raise MappingError("boolean accepts only booleans or the strings true/false")


def _transform_numeric(value: Any, operation: str) -> int | float:
    if type(value) not in {str, int, float}:
        raise MappingError("numeric conversion requires a number or numeric string")
    if operation == "integer":
        if type(value) is float and not value.is_integer():
            raise MappingError("invalid numeric conversion")
        try:
            return int(value)
        except (ValueError, OverflowError):
            raise MappingError("invalid numeric conversion") from None
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise MappingError("invalid numeric conversion") from None
    if not math.isfinite(result):
        raise MappingError("invalid numeric conversion")
    return result


def _transform(value: Any, operation: str | dict[str, Any]) -> Any:
    if isinstance(operation, dict):
        return _timestamp(value, operation.get("assume_timezone"))
    if operation == "string":
        return _transform_string(value)
    if operation in {"trim", "lower", "upper"}:
        return _transform_text(value, operation)
    if operation == "list":
        return value if isinstance(value, list) else [value]
    if operation == "json":
        return _canonical_json(value)
    if operation == "boolean":
        return _transform_boolean(value)
    if operation in {"integer", "number"}:
        return _transform_numeric(value, operation)
    raise MappingError("unsupported transform")


def _evaluate_column(spec: dict[str, Any], row: Mapping[str, Any]) -> Any:
    column = spec["column"]
    if column not in row:
        raise MappingError("source column is missing")
    value = row[column]
    for segment in spec.get("path", []):
        if value is None:
            break
        if isinstance(segment, str) and isinstance(value, Mapping) and segment in value:
            value = value[segment]
        elif type(segment) is int and isinstance(value, list) and segment < len(value):
            value = value[segment]
        else:
            raise MappingError("source path is missing or has the wrong container type")
    return value


def _evaluate_concat(spec: dict[str, Any], row: Mapping[str, Any], null_policy: str) -> Any:
    parts: list[Any] = []
    # Check every reference first, so a null/omitted earlier input cannot hide
    # a missing later source column.
    for column in spec["concat"]:
        if column not in row:
            raise MappingError("source column is missing")
        parts.append(row[column])

    has_null = any(part is None for part in parts)
    cloned_parts: list[list[Any]] = []
    for part in parts:
        if part is None:
            continue
        if not isinstance(part, list):
            raise MappingError("source list concatenation requires list-valued columns")
        cloned_parts.append(_clone_json(part, "source value"))
    if has_null:
        if null_policy == "omit":
            return _OMIT
        raise MappingError("null source value is not permitted")
    result: list[Any] = []
    for part in cloned_parts:
        result.extend(part)
    return result


def _evaluate(spec: dict[str, Any], row: Mapping[str, Any], null_policy: str) -> Any:
    mapping_null_policy = spec.get("on_null", null_policy)
    if "column" in spec:
        value = _evaluate_column(spec, row)
    elif "concat" in spec:
        value = _evaluate_concat(spec, row, mapping_null_policy)
        if value is _OMIT:
            return _OMIT
    else:
        value = _clone_json(spec["value"], "mapping constant")

    if value is None:
        if mapping_null_policy == "omit":
            return _OMIT
        raise MappingError("null source value is not permitted")

    value = _clone_json(value, "source value") if "value" not in spec else value
    for operation in spec.get("transforms", []):
        value = _transform(value, operation)
    return value


def _valid_finite_number(value: Any) -> bool:
    if type(value) not in {int, float}:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _valid_ip(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _valid_field_item(value: Any, field_type: str) -> bool:
    if field_type in {"keyword", "text"}:
        return isinstance(value, str)
    if field_type in {"integer", "long"}:
        bits = 32 if field_type == "integer" else 64
        return type(value) is int and -(2 ** (bits - 1)) <= value < 2 ** (bits - 1)
    if field_type == "float":
        return _valid_finite_number(value)
    if field_type == "boolean":
        return type(value) is bool
    if field_type == "object":
        return isinstance(value, dict)
    if field_type == "ip":
        return _valid_ip(value)
    if field_type == "date":
        _timestamp(value)
        return True
    return False


def _validate_field_value(value: Any, metadata: dict[str, Any]) -> None:
    is_list = metadata["list"]
    if is_list:
        if not isinstance(value, list):
            raise MappingError("target requires a list; explicitly use the list transform")
        values = value
    else:
        if isinstance(value, list):
            raise MappingError("target is scalar but the mapped value is a list")
        values = [value]

    field_type = metadata["type"]
    for item in values:
        if not _valid_field_item(item, field_type):
            raise MappingError(f"target requires {field_type}{' list elements' if is_list else ''}")
        allowed_values = metadata.get("values")
        if allowed_values is not None and item not in allowed_values:
            raise MappingError("value is not in the target enum")
        pattern = metadata.get("regex")
        if pattern and (not isinstance(item, str) or re.fullmatch(pattern, item) is None):
            raise MappingError("value does not match the target regex")


class RowMapping:
    """Validated, offline mapping from one raw table row to one hit dictionary.

    ``fields_snapshot`` is optional. Without it, mapping structure and each
    rendered row are checked for safety, but backend field existence/types are
    not asserted.
    """

    def __init__(self, mapping: Mapping[str, Any], fields_snapshot: Mapping[str, Any] | None = None):
        """Create a mapping from an already loaded version-1 document."""
        if not isinstance(mapping, Mapping):
            raise TypeError("mapping must be a mapping document")
        self._mapping = _validate_mapping_document(_clone_json(mapping, "mapping document"))
        self._fields_snapshot: dict[str, Any] | None = None
        if fields_snapshot is not None:
            self._fields_snapshot = _validate_fields_snapshot(_clone_json(fields_snapshot, "fields_snapshot"))
            self._validate_against_snapshot()

    @classmethod
    def from_file(
        cls,
        path: str | os.PathLike[str],
        fields_snapshot: Mapping[str, Any] | None = None,
    ) -> RowMapping:
        """Load a mapping from a YAML file, optionally pinning a field snapshot."""
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, TypeError, ValueError):
            raise MappingError("unable to read mapping file") from None
        return cls.from_yaml(text, fields_snapshot=fields_snapshot)

    @classmethod
    def from_yaml(cls, text: str, fields_snapshot: Mapping[str, Any] | None = None) -> RowMapping:
        """Parse a YAML mapping document without unsafe tags, aliases, or coercions."""
        loaded = _load_yaml(text)
        if not isinstance(loaded, Mapping):
            raise MappingError("mapping document must be an object")
        return cls(loaded, fields_snapshot=fields_snapshot)

    @property
    def mapping(self) -> dict[str, Any]:
        """Return a detached copy of the mapping document."""
        return cast(dict[str, Any], _clone_json(self._mapping, "mapping document"))

    def _validate_against_snapshot(self) -> None:
        if self._fields_snapshot is None:
            raise MappingError("fields_snapshot was not supplied")
        target = self._mapping["target"]
        snapshot = self._fields_snapshot
        if target["mcp_url"] != snapshot["mcp_url"] or target["fields_sha256"] != snapshot["fields_sha256"]:
            raise MappingError("mapping and fields_snapshot endpoints or fingerprints differ")

        fields = snapshot["fields"]
        for name, expression in self._mapping["mappings"].items():
            if name not in fields:
                raise MappingError(f"unknown Howler field: {name}")
            metadata = fields[name]
            if metadata.get("deprecated"):
                raise MappingError(f"deprecated Howler field: {name}")
            if "concat" in expression and not metadata["list"]:
                raise MappingError("source list concatenation requires a list target")
            if "value" in expression:
                value = _evaluate(expression, {}, self._mapping["policy"]["on_null"])
                if value is not _OMIT:
                    _validate_field_value(value, metadata)
                    if name == "howler":
                        _reject_howler_id({"howler": value})

    def map_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        """Map one row and return a new nested hit dictionary."""
        return _map_one(self._mapping, self._fields_snapshot, row, 1)

    def map_rows(self, rows: Iterable[Mapping[str, Any]]) -> Generator[RowMappingResult, None, None]:
        """Lazily yield ``(hit, None)`` or ``(None, error)`` for each source row.

        Row-level failures are returned and do not stop processing later rows.
        Configuration failures have already been raised during construction.
        """
        for row_number, row in enumerate(rows, start=1):
            result = _map_one_result(self._mapping, self._fields_snapshot, row, row_number)
            del row
            yield result
            del result


def _map_one(
    mapping: dict[str, Any],
    fields_snapshot: dict[str, Any] | None,
    row: Mapping[str, Any],
    row_number: int,
) -> dict[str, Any]:
    if not isinstance(row, Mapping):
        raise MappingError(f"row {row_number}, target <row>: expected a mapping object")  # noqa: TRY004 - include row context in the public mapping error.
    if any(not isinstance(key, str) for key in row):
        raise MappingError(f"row {row_number}, target <row>: source object keys must be strings")

    record: dict[str, Any] = {}
    for target in sorted(mapping["mappings"]):
        expression = mapping["mappings"][target]
        try:
            value = _map_target_value(mapping, fields_snapshot, row, target, expression)
            if value is not _OMIT:
                _insert_target(record, target, value)
        except MappingError as exc:
            raise MappingError(f"row {row_number}, target {target}: {exc}") from None

    if not record:
        raise MappingError(f"row {row_number}, target <row>: all fields were omitted")
    try:
        _reject_howler_id(record)
    except MappingError as exc:
        raise MappingError(f"row {row_number}, target <row>: {exc}") from None
    return record


def _new_detached_error(message: str) -> MappingError:
    """Build a traceback-free error suitable for handing back to a caller."""
    error = MappingError(message)
    error.__traceback__ = None
    error.__cause__ = None
    error.__context__ = None
    error.__suppress_context__ = True
    return error


def _map_one_result(
    mapping: dict[str, Any],
    fields_snapshot: dict[str, Any] | None,
    row: Mapping[str, Any],
    row_number: int,
) -> RowMappingResult:
    try:
        return _map_one(mapping, fields_snapshot, row, row_number), None
    except MappingError as exc:
        # Do not return the raised exception: its traceback can retain the source
        # row and any partially constructed record in this generator's frame.
        message = str(exc)
    return None, _new_detached_error(message)


def _map_target_value(
    mapping: dict[str, Any],
    fields_snapshot: dict[str, Any] | None,
    row: Mapping[str, Any],
    target: str,
    expression: dict[str, Any],
) -> Any:
    value = _evaluate(expression, row, mapping["policy"]["on_null"])
    if value is _OMIT:
        return _OMIT
    normalized = _clone_json(value, "mapped value")
    if fields_snapshot is not None:
        _validate_field_value(normalized, fields_snapshot["fields"][target])
    if target == "howler":
        _reject_howler_id({"howler": normalized})
    return normalized


def _insert_target(record: dict[str, Any], target: str, value: Any) -> None:
    current = record
    parts = target.split(".")
    for part in parts[:-1]:
        current = current.setdefault(part, {})
    current[parts[-1]] = value


class HowlerMapping(object):
    """Methods related to mapping data"""

    def map_rows(
        self: Self,
        rows: Iterable[Mapping[str, Any]],
        mapping: RowMapping | Mapping[str, Any] | str | os.PathLike[str],
        *,
        fields_snapshot: Mapping[str, Any] | None = None,
    ) -> Generator[RowMappingResult, None, None]:
        """Lazily yield a result tuple for each raw row, without persisting records.

        ``mapping`` may be a :class:`RowMapping`, a loaded version-1 mapping
        document, or a YAML filename. Pass YAML text to ``RowMapping.from_yaml`` to
        avoid ambiguity with paths. Each success is ``(hit, None)``; each row error
        is ``(None, MappingError)`` and iteration continues. Invalid configuration
        raises before the source iterable is consumed. Source iterator exceptions
        propagate unchanged. This function transforms only; it never stores or
        ingests records.
        """
        if isinstance(mapping, RowMapping):
            if fields_snapshot is not None:
                raise TypeError("fields_snapshot must be supplied when constructing RowMapping")
            row_mapping = mapping
        elif isinstance(mapping, Mapping):
            row_mapping = RowMapping(mapping, fields_snapshot=fields_snapshot)
        elif isinstance(mapping, (str, os.PathLike)):
            row_mapping = RowMapping.from_file(mapping, fields_snapshot=fields_snapshot)
        else:
            raise TypeError("mapping must be RowMapping, a mapping document, or a YAML file path")

        yield from row_mapping.map_rows(rows)


__all__ = ["MappingError", "RowMapping", "RowMappingResult", "HowlerMapping"]
