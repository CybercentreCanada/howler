"""Offline mapping of raw table rows to Howler hit records.

The mapping format is declarative. It never evaluates code, talks to Howler, or
creates server-owned identifiers. See the client README for examples.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Generator, Iterable, Mapping
from importlib import resources
from pathlib import Path
from typing import Any, TypeAlias, cast

import yaml
from jsonschema import Draft202012Validator, validators

from howler_client.common.dict_utils import unflatten
from howler_client.common.exceptions import MappingError
from howler_client.utils.transforms import (
    canonical_json,
    normalize,
    render_template,
    text,
    timestamp,
    to_boolean,
    to_integer,
    to_number,
    to_string,
    validate_template,
)

_ID_ERROR = "howler.id is server-generated and must not be set"
_OMIT = object()


RowMappingResult: TypeAlias = tuple[dict[str, Any] | None, MappingError | None]

_TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "string": to_string,
    "integer": to_integer,
    "number": to_number,
    "boolean": to_boolean,
    "trim": lambda value: text(value).strip(),
    "lower": lambda value: text(value).lower(),
    "upper": lambda value: text(value).upper(),
    "list": lambda value: value if isinstance(value, list) else [value],
    "json": canonical_json,
}


def _strict_integer(_checker: Any, instance: Any) -> bool:
    return isinstance(instance, int) and not isinstance(instance, bool)


VALIDATOR = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine("integer", _strict_integer),
)(
    json.loads(
        resources.files("howler_client.schemas").joinpath("row_mapping_v1.schema.json").read_text(encoding="utf-8")
    )
)


def _apply_transform(value: Any, operation: str | Mapping[str, Any]) -> Any:
    if isinstance(operation, Mapping):
        if operation.get("op") == "template":
            return render_template(value, operation["template"])
        return timestamp(value, assume_utc=operation.get("assume_timezone") == "UTC")
    return _TRANSFORMS[operation](value)


def _schema_error_message(error: Any, document: Mapping[str, Any]) -> str:
    """Map schema failures to fixed diagnostics without rendering instance data."""
    path = tuple(error.absolute_path)
    if error.validator == "minProperties" and path == ("mappings",):
        return "mapping must define at least one target"
    if error.validator in ("const", "type") and path == ("version",):
        return "only mapping version 1 is supported"
    if error.validator == "not" and tuple(error.schema_path) == (
        "properties",
        "mappings",
        "propertyNames",
        "allOf",
        1,
        "not",
    ):
        targets = document["mappings"]
        if any(target == "howler.id" or target.startswith("howler.id.") for target in targets):
            return _ID_ERROR

    return "mapping document is invalid"


def _validate_document(document: Mapping) -> dict[str, Any]:
    if not isinstance(document, Mapping):
        raise MappingError("mapping document must be an object")
    normalized = normalize(document, "mapping document")

    try:
        error = next(VALIDATOR.iter_errors(normalized), None)
    except Exception as err:
        raise MappingError("mapping document is invalid") from err

    if error is not None:
        raise MappingError(_schema_error_message(error, normalized)) from None

    mappings = normalized["mappings"]

    for spec in mappings.values():
        for operation in spec.get("transforms", []):
            if isinstance(operation, Mapping) and operation.get("op") == "template":
                validate_template(operation["template"])

    for target in mappings:
        parts = target.split(".")
        if any(".".join(parts[:index]) in mappings for index in range(1, len(parts))):
            raise MappingError(f"conflicting parent/child target: {target}")

    return cast(dict[str, Any], normalized)


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


def _prepend_raw_record(hit: dict[str, Any], row: Mapping[str, Any], number: int) -> dict[str, Any]:
    try:
        raw_record = normalize(dict(row), "raw row")
    except MappingError as exc:
        raise MappingError(f"row {number}, target howler.data: {exc}") from None

    howler = hit.get("howler")
    if howler is None:
        howler = {}
        hit["howler"] = howler
    elif not isinstance(howler, dict):
        raise MappingError(f"row {number}, target howler: expected an object")

    howler_data = howler.get("data", [])
    if not isinstance(howler_data, list):
        howler_data = [howler_data]
    howler["data"] = [raw_record, *howler_data]
    return hit


class RowMapping:
    """Validated, offline mapping from one raw table row to one hit dictionary.

    By default, each mapped hit includes a detached copy of the raw row as the
    first entry in ``howler.data``. Set ``include_raw_data: false`` in the mapping
    document to disable this. Any explicitly mapped ``howler.data`` value remains.

    ``fields`` is optional Howler field metadata keyed by dotted field name, as
    returned by ``client.search.fields.hit()``.
    When supplied, targets must exist and not be deprecated. Mapped values are not
    checked against target field types or list shape; validate them with Howler's
    validation API or during ingestion.
    """

    def __init__(self, mapping: Mapping[str, Any], fields: Mapping[str, Any] | None = None):
        """Create a mapping from an already loaded version-1 document."""
        self._document = _validate_document(mapping)
        self._on_null: str = self._document.get("on_null", "error")
        self._include_raw_data: bool = self._document.get("include_raw_data", True)
        if fields is not None:
            _validate_fields(normalize(fields, "fields"), self._document["mappings"])

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
        return cast(dict[str, Any], normalize(self._document))

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
            except (MappingError, OverflowError) as exc:
                # A fresh error has no traceback, so it cannot retain the source row.
                result = (None, MappingError(str(exc)))
            yield result

    def _map_target(self, target: str, spec: Mapping[str, Any], row: Mapping[str, Any]) -> Any:
        value = _evaluate(spec, row, self._on_null)
        if value is _OMIT:
            return _OMIT
        value = normalize(value)
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

        hit = cast(dict[str, Any], unflatten(values))
        return _prepend_raw_record(hit, row, number) if self._include_raw_data else hit


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
