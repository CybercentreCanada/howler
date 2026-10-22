"""Offline mapping of raw table rows to Howler hit records.

The mapping format is declarative. It never evaluates code, talks to Howler, or
creates server-owned identifiers. See the client README for examples.
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
from collections.abc import Callable, Generator, Iterable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypeAlias, cast

import yaml

from howler_client.common.dict_utils import unflatten

_NULL_POLICIES = ("error", "omit")
_EXPRESSION_KEYS = {"column", "path", "concat", "value", "on_null", "transforms"}
_ID_ERROR = "howler.id is server-generated and must not be set"
_OMIT = object()


class MappingError(ValueError):
    """A mapping document, field definition, or source row is invalid."""


RowMappingResult: TypeAlias = tuple[dict[str, Any] | None, MappingError | None]


def _dumps(value: Any, what: str = "value", **kwargs: Any) -> str:
    try:
        return json.dumps(value, allow_nan=False, **kwargs)
    except (TypeError, ValueError, RecursionError):
        # Serializer messages can include source values; never echo them.
        raise MappingError(f"{what} is not valid JSON") from None


def _normalize(value: Any, what: str = "value") -> Any:
    """Return a detached JSON copy of ``value``, rejecting non-JSON and non-finite values."""
    return json.loads(_dumps(value, what))


def _canonical_json(value: Any) -> str:
    return _dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _timestamp(value: Any, assume_utc: bool = False) -> str:
    if not isinstance(value, str):
        raise MappingError("timestamp requires an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        raise MappingError("invalid ISO-8601 timestamp") from None
    if parsed.tzinfo is None:
        if not assume_utc:
            raise MappingError("timestamp has no timezone; explicitly set assume_timezone: UTC")
        parsed = parsed.replace(tzinfo=timezone.utc)
    try:
        normalized = parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise MappingError("invalid ISO-8601 timestamp") from None
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _text(value: Any) -> str:
    if not isinstance(value, str):
        raise MappingError("text transform requires a string")
    return value


def _to_string(value: Any) -> str:
    if isinstance(value, (Mapping, list)):
        raise MappingError("use the json transform for structured values")
    return value if isinstance(value, str) else _canonical_json(value)


def _to_integer(value: Any) -> int:
    if type(value) is float and value.is_integer():
        return int(value)
    if type(value) in (int, str):
        try:
            return int(value)
        except ValueError:
            pass
    raise MappingError("invalid integer conversion")


def _to_number(value: Any) -> float:
    try:
        result = float(value) if type(value) in (int, float, str) else math.nan
    except (ValueError, OverflowError):
        result = math.nan
    if not math.isfinite(result):
        raise MappingError("invalid numeric conversion")
    return result


def _to_boolean(value: Any) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str) and value in ("true", "false"):
        return value == "true"
    raise MappingError("boolean accepts only booleans or the strings true/false")


_TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "string": _to_string,
    "integer": _to_integer,
    "number": _to_number,
    "boolean": _to_boolean,
    "trim": lambda value: _text(value).strip(),
    "lower": lambda value: _text(value).lower(),
    "upper": lambda value: _text(value).upper(),
    "list": lambda value: value if isinstance(value, list) else [value],
    "json": _canonical_json,
}


def _apply_transform(value: Any, operation: str | Mapping[str, Any]) -> Any:
    if isinstance(operation, Mapping):
        return _timestamp(value, assume_utc=operation.get("assume_timezone") == "UTC")
    return _TRANSFORMS[operation](value)


def _is_ip(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


def _is_timestamp(value: Any) -> bool:
    try:
        _timestamp(value)
    except MappingError:
        return False
    return True


_FIELD_TYPE_CHECKS: dict[str, Callable[[Any], bool]] = {
    "keyword": lambda value: isinstance(value, str),
    "text": lambda value: isinstance(value, str),
    "integer": lambda value: type(value) is int,
    "long": lambda value: type(value) is int,
    "float": lambda value: type(value) in (int, float),
    "boolean": lambda value: type(value) is bool,
    "object": lambda value: isinstance(value, dict),
    "ip": _is_ip,
    "date": _is_timestamp,
}


def _check_field_value(value: Any, field: Mapping[str, Any]) -> None:
    """Check list shape and basic type against Howler field metadata; unknown types are not checked."""
    is_list = bool(field.get("list"))
    if is_list and not isinstance(value, list):
        raise MappingError("target requires a list; explicitly use the list transform")
    if not is_list and isinstance(value, list):
        raise MappingError("target is scalar but the mapped value is a list")
    check = _FIELD_TYPE_CHECKS.get(str(field.get("type")))
    if check and not all(check(item) for item in (value if is_list else [value])):
        raise MappingError(f"target requires {field['type']}")


def _validate_transform(target: str, operation: Any) -> None:
    if isinstance(operation, str) and operation in _TRANSFORMS:
        return
    if (
        isinstance(operation, Mapping)
        and operation.get("op") == "timestamp"
        and set(operation) <= {"op", "assume_timezone"}
        and operation.get("assume_timezone", "UTC") == "UTC"
    ):
        return
    raise MappingError(f"unsupported transform for target: {target}")


def _validate_expression(target: str, spec: Any) -> None:  # noqa: C901
    if not isinstance(spec, Mapping) or set(spec) - _EXPRESSION_KEYS:
        raise MappingError(f"invalid mapping expression for target: {target}")
    if sum(key in spec for key in ("column", "concat", "value")) != 1:
        raise MappingError(f"target requires exactly one of column, concat, or value: {target}")
    if spec.get("on_null", "error") not in _NULL_POLICIES:
        raise MappingError(f"invalid null policy for target: {target}")
    if "column" in spec and (not isinstance(spec["column"], str) or not spec["column"]):
        raise MappingError(f"invalid source column for target: {target}")
    if "path" in spec:
        path = spec["path"]
        if (
            "column" not in spec
            or not isinstance(path, list)
            or not path
            or any(not isinstance(segment, str) and not (type(segment) is int and segment >= 0) for segment in path)
        ):
            raise MappingError(f"invalid source path for target: {target}")
    if "concat" in spec:
        concat = spec["concat"]
        if not isinstance(concat, list) or len(concat) < 2 or any(not isinstance(c, str) or not c for c in concat):
            raise MappingError(f"invalid concatenation for target: {target}")
    transforms = spec.get("transforms", [])
    if not isinstance(transforms, list):
        raise MappingError(f"invalid transforms for target: {target}")
    for operation in transforms:
        _validate_transform(target, operation)


def _validate_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise MappingError("mapping document must be an object")
    if set(document) - {"version", "on_null", "mappings"}:
        raise MappingError("mapping document has unsupported keys")
    if type(document.get("version")) is not int or document["version"] != 1:
        raise MappingError("only mapping version 1 is supported")
    if document.get("on_null", "error") not in _NULL_POLICIES:
        raise MappingError("on_null must be error or omit")

    mappings = document.get("mappings")
    if not isinstance(mappings, Mapping) or not mappings:
        raise MappingError("mapping must define at least one target")
    for target, spec in mappings.items():
        if not isinstance(target, str) or "" in target.split("."):
            raise MappingError("mapping targets must be non-empty dotted field names")
        if target == "howler.id" or target.startswith("howler.id."):
            raise MappingError(_ID_ERROR)
        parts = target.split(".")
        if any(".".join(parts[:index]) in mappings for index in range(1, len(parts))):
            raise MappingError(f"conflicting parent/child target: {target}")
        _validate_expression(target, spec)
    return cast(dict[str, Any], _normalize(document, "mapping document"))


def _lookup(row: Mapping[str, Any], column: str, path: Iterable[str | int] = ()) -> Any:
    """Read a column and optional nested path; a missing nested key or index yields None."""
    if column not in row:
        raise MappingError("source column is missing")
    value = row[column]
    for segment in path:
        if isinstance(value, Mapping) and isinstance(segment, str):
            value = value.get(segment)
        elif isinstance(value, list) and isinstance(segment, int):
            value = value[segment] if segment < len(value) else None
        elif value is not None:
            raise MappingError("source path has the wrong container type")
    return value


def _evaluate(spec: Mapping[str, Any], row: Mapping[str, Any], on_null: str) -> Any:
    if "value" in spec:
        value = spec["value"]
    elif "column" in spec:
        value = _lookup(row, spec["column"], spec.get("path", ()))
    else:
        parts = [_lookup(row, column) for column in spec["concat"]]
        if any(part is None for part in parts):
            value = None
        elif not all(isinstance(part, list) for part in parts):
            raise MappingError("concat requires list-valued columns")
        else:
            value = [item for part in parts for item in part]

    if value is None:
        if spec.get("on_null", on_null) == "omit":
            return _OMIT
        raise MappingError("null source value is not permitted")
    for operation in spec.get("transforms", []):
        value = _apply_transform(value, operation)
    return value


class RowMapping:
    """Validated, offline mapping from one raw table row to one hit dictionary.

    ``fields`` is optional Howler field metadata keyed by dotted field name, as
    returned by ``client.search.fields.hit()`` or the MCP ``get_hit_fields`` tool.
    When supplied, targets must exist and not be deprecated, and mapped values are
    checked for list shape and basic type. Without it, backend field existence and
    types are not asserted.
    """

    def __init__(self, mapping: Mapping[str, Any], fields: Mapping[str, Any] | None = None):
        """Create a mapping from an already loaded version-1 document."""
        self._document = _validate_document(mapping)
        self._on_null: str = self._document.get("on_null", "error")
        self._fields: dict[str, Any] | None = None
        if fields is not None:
            self._fields = _validate_fields(_normalize(fields, "fields"), self._document["mappings"])

        self._targets: dict[str, dict[str, Any]] = {}
        self._constants: dict[str, str] = {}
        for target, spec in sorted(self._document["mappings"].items()):
            if "value" not in spec:
                self._targets[target] = spec
                continue
            try:
                value = self._map_target(target, spec, {})
            except MappingError as exc:
                raise MappingError(f"invalid constant for target {target}: {exc}") from None
            if value is not _OMIT:
                self._targets[target] = spec
                self._constants[target] = json.dumps(value)

    @classmethod
    def from_file(cls, path: str | os.PathLike[str], fields: Mapping[str, Any] | None = None) -> RowMapping:
        """Load a mapping from a YAML file."""
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, ValueError):
            raise MappingError("unable to read mapping file") from None
        return cls.from_yaml(text, fields=fields)

    @classmethod
    def from_yaml(cls, text: str, fields: Mapping[str, Any] | None = None) -> RowMapping:
        """Parse a YAML mapping document with ``yaml.safe_load``."""
        try:
            document = yaml.safe_load(text)
        except Exception:
            # Parser errors can include source snippets; never echo mapping text.
            raise MappingError("invalid YAML mapping document") from None
        return cls(document, fields=fields)

    @property
    def mapping(self) -> dict[str, Any]:
        """Return a detached copy of the mapping document."""
        return cast(dict[str, Any], _normalize(self._document))

    def map_row(self, row: Mapping[str, Any]) -> dict[str, Any]:
        """Map one row and return a new nested hit dictionary."""
        return self._map_row(row, 1)

    def map_rows(self, rows: Iterable[Mapping[str, Any]]) -> Generator[RowMappingResult, None, None]:
        """Lazily yield ``(hit, None)`` or ``(None, error)`` for each source row.

        Row-level failures are returned and do not stop processing later rows.
        """
        for number, row in enumerate(rows, start=1):
            try:
                result: RowMappingResult = (self._map_row(row, number), None)
            except MappingError as exc:
                # A fresh error has no traceback, so it cannot retain the source row.
                result = (None, MappingError(str(exc)))
            yield result

    def _map_target(self, target: str, spec: Mapping[str, Any], row: Mapping[str, Any]) -> Any:
        value = _evaluate(spec, row, self._on_null)
        if value is _OMIT:
            return _OMIT
        value = _normalize(value)
        if self._fields is not None:
            _check_field_value(value, self._fields[target])
        if target == "howler" and isinstance(value, dict) and any(k == "id" or k.startswith("id.") for k in value):
            raise MappingError(_ID_ERROR)
        return value

    def _map_row(self, row: Mapping[str, Any], number: int) -> dict[str, Any]:
        if not isinstance(row, Mapping):
            raise MappingError(f"row {number}, target <row>: expected a mapping object")  # noqa: TRY004
        values: dict[str, Any] = {}
        for target, spec in self._targets.items():
            try:
                if target in self._constants:
                    value = json.loads(self._constants[target])
                else:
                    value = self._map_target(target, spec, row)
            except MappingError as exc:
                raise MappingError(f"row {number}, target {target}: {exc}") from None
            if value is not _OMIT:
                values[target] = value
        if not values:
            raise MappingError(f"row {number}, target <row>: all fields were omitted")
        return cast(dict[str, Any], unflatten(values))


def _validate_fields(fields: Any, mappings: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(fields, dict):
        raise MappingError("fields must map field names to field metadata")
    for target, spec in mappings.items():
        field = fields.get(target)
        if not isinstance(field, dict):
            raise MappingError(f"unknown Howler field: {target}")
        if field.get("deprecated"):
            raise MappingError(f"deprecated Howler field: {target}")
        if "concat" in spec and not field.get("list"):
            raise MappingError(f"concat requires a list target: {target}")
    return fields


def map_rows(
    rows: Iterable[Mapping[str, Any]],
    mapping: RowMapping | Mapping[str, Any] | str | os.PathLike[str],
    *,
    fields: Mapping[str, Any] | None = None,
) -> Generator[RowMappingResult, None, None]:
    """Return a lazy generator of result tuples for each raw row, without persisting records.

    ``mapping`` may be a :class:`RowMapping`, a loaded version-1 mapping document,
    or a YAML file path. Pass YAML text to ``RowMapping.from_yaml``. Each success is
    ``(hit, None)``; each row error is ``(None, MappingError)`` and iteration
    continues. Invalid configuration raises immediately, before any row is read.
    """
    if isinstance(mapping, RowMapping):
        if fields is not None:
            raise TypeError("fields must be supplied when constructing RowMapping")
        row_mapping = mapping
    elif isinstance(mapping, Mapping):
        row_mapping = RowMapping(mapping, fields=fields)
    elif isinstance(mapping, (str, os.PathLike)):
        row_mapping = RowMapping.from_file(mapping, fields=fields)
    else:
        raise TypeError("mapping must be RowMapping, a mapping document, or a YAML file path")
    return row_mapping.map_rows(rows)


class HowlerMapping(object):
    """Methods related to mapping data"""

    def map_rows(
        self,
        rows: Iterable[Mapping[str, Any]],
        mapping: RowMapping | Mapping[str, Any] | str | os.PathLike[str],
        *,
        fields: Mapping[str, Any] | None = None,
    ) -> Generator[RowMappingResult, None, None]:
        """Map raw rows to hit dictionaries; see :func:`howler_client.map_rows`."""
        return map_rows(rows, mapping, fields=fields)


__all__ = ["HowlerMapping", "MappingError", "RowMapping", "RowMappingResult", "map_rows"]
