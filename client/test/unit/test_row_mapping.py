"""Focused offline tests for lazy raw-row to Howler hit mapping."""

from __future__ import annotations

import copy
import inspect
import itertools
import json
import sys
from collections.abc import Generator, Mapping
from importlib import resources
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator

import howler_client
from howler_client.module.mapping import (
    _TRANSFORMS,
    HowlerMapping,
    MappingError,
    RowMapping,
    RowMappingResult,
    map_rows,
)

EXAMPLE_FIELDS: dict[str, dict[str, Any]] = {
    "howler.analytic": {"type": "keyword", "list": False},
    "classification": {"type": "keyword", "list": False},
    "user.id": {"type": "keyword", "list": False},
    "user.name": {"type": "keyword", "list": False},
    "user.full_name": {"type": "keyword", "list": False},
    "user.email": {"type": "keyword", "list": False},
    "user.roles": {"type": "keyword", "list": True},
    "organization.name": {"type": "keyword", "list": False},
}


def _base_mapping() -> dict[str, Any]:
    return {
        "version": 1,
        "mappings": {
            "howler.analytic": {"value": "Synthetic identity inventory"},
            "user.id": {"column": "id"},
            "user.name": {"column": "name", "transforms": ["trim", "lower"]},
            "user.roles": {"concat": ["roles_a", "roles_b"]},
            "event.created": {"column": "created", "transforms": [{"op": "timestamp"}]},
            "custom.object": {"column": "nested"},
            "custom.constant": {"value": {"members": ["fixed"]}},
        },
    }


def _row(identifier: str = "synthetic-1") -> dict[str, Any]:
    return {
        "id": identifier,
        "name": " Alice Example ",
        "roles_a": ["admin", "reader"],
        "roles_b": ["reader", "operator"],
        "created": "2026-04-01T10:00:00+02:00",
        "nested": {"enabled": True, "tags": ["one"]},
    }


def _single_value_mapping(
    expression: dict[str, Any],
    *,
    target: str = "result.value",
    on_null: str = "error",
) -> dict[str, Any]:
    return {"version": 1, "on_null": on_null, "mappings": {target: expression}}


def _single_row(expression: dict[str, Any], value: Any) -> Any:
    return RowMapping(_single_value_mapping(expression)).map_row({"value": value})["result"]["value"]


def _with_raw_data(hit: dict[str, Any], row: Mapping[str, Any]) -> dict[str, Any]:
    expected = copy.deepcopy(hit)
    howler = expected.setdefault("howler", {})
    howler_data = howler.get("data", [])
    if not isinstance(howler_data, list):
        howler_data = [howler_data]
    howler["data"] = [copy.deepcopy(dict(row)), *howler_data]
    return expected


def _id_mapping() -> RowMapping:
    return RowMapping(_single_value_mapping({"column": "id"}, target="user.id"))


def _assert_detached_error(error: MappingError | None) -> None:
    assert isinstance(error, MappingError)
    assert error.__traceback__ is None
    assert error.__cause__ is None
    assert error.__context__ is None


class _TrackedRows:
    def __init__(self) -> None:
        self.iterations = 0

    def __iter__(self) -> Generator[Mapping[str, Any], None, None]:
        self.iterations += 1
        yield {"value": "must-not-be-read"}


def test_package_exports_offline_mapping_api() -> None:
    assert howler_client.RowMapping is RowMapping
    assert howler_client.MappingError is MappingError
    assert howler_client.map_rows is map_rows
    assert howler_client.RowMappingResult is RowMappingResult


def test_public_api_consumes_one_shot_infinite_input_on_demand() -> None:
    started: list[int] = []

    def endless_rows() -> Generator[Mapping[str, Any], None, None]:
        for number in itertools.count():
            started.append(number)
            yield {"id": f"synthetic-{number}"}

    for mapper in (map_rows, HowlerMapping().map_rows):
        started.clear()
        generated = mapper(endless_rows(), _single_value_mapping({"column": "id"}, target="user.id"))
        assert inspect.isgenerator(generated)
        assert started == []
        assert next(generated) == (_with_raw_data({"user": {"id": "synthetic-0"}}, {"id": "synthetic-0"}), None)
        assert started == [0]
        assert next(generated) == (_with_raw_data({"user": {"id": "synthetic-1"}}, {"id": "synthetic-1"}), None)
        assert started == [0, 1]


def test_row_mapping_method_is_lazy_and_preserves_source_order() -> None:
    calls: list[int] = []

    def one_shot() -> Generator[Mapping[str, Any], None, None]:
        for number in range(3):
            calls.append(number)
            yield {"id": str(number)}

    rows = _id_mapping().map_rows(one_shot())
    assert calls == []
    assert next(rows) == (_with_raw_data({"user": {"id": "0"}}, {"id": "0"}), None)
    assert calls == [0]
    assert list(rows) == [
        (_with_raw_data({"user": {"id": "1"}}, {"id": "1"}), None),
        (_with_raw_data({"user": {"id": "2"}}, {"id": "2"}), None),
    ]
    assert calls == [0, 1, 2]


def test_valid_invalid_valid_rows_yield_results_and_continue_without_leaking_values() -> None:
    results: list[RowMappingResult] = list(
        map_rows(
            [{"id": "first"}, {"private_payload": "DO_NOT_INCLUDE_THIS_SOURCE_VALUE"}, {"id": "third"}],
            _id_mapping(),
        )
    )
    assert results[0] == (_with_raw_data({"user": {"id": "first"}}, {"id": "first"}), None)
    assert results[1][0] is None
    _assert_detached_error(results[1][1])
    assert str(results[1][1]) == "row 2, target user.id: source column is missing"
    assert results[2] == (_with_raw_data({"user": {"id": "third"}}, {"id": "third"}), None)


def test_repeated_failures_and_non_mapping_rows_are_returned_independently() -> None:
    mapper = _id_mapping()
    repeated = list(mapper.map_rows([{}, {}, {"id": "valid"}, {}]))
    assert [hit for hit, _error in repeated] == [
        None,
        None,
        _with_raw_data({"user": {"id": "valid"}}, {"id": "valid"}),
        None,
    ]
    errors = [error for _hit, error in repeated if error is not None]
    assert [str(error).split(",", 1)[0] for error in errors] == ["row 1", "row 2", "row 4"]
    assert len({id(error) for error in errors}) == 3
    for error in errors:
        _assert_detached_error(error)

    mixed_rows: list[Any] = [None, 42, ["not", "a", "row"], {"id": "valid"}]
    mixed_results = list(mapper.map_rows(mixed_rows))
    assert [hit for hit, _error in mixed_results] == [
        None,
        None,
        None,
        _with_raw_data({"user": {"id": "valid"}}, {"id": "valid"}),
    ]
    for row_number, (_hit, error) in enumerate(mixed_results[:3], start=1):
        _assert_detached_error(error)
        assert str(error) == f"row {row_number}, target <row>: expected a mapping object"


def test_null_and_transform_row_failures_return_errors_then_continue() -> None:
    null_results = list(
        RowMapping(_single_value_mapping({"column": "value"})).map_rows([{"value": None}, {"value": "a"}])
    )
    assert null_results[0][0] is None
    assert str(null_results[0][1]) == "row 1, target result.value: null source value is not permitted"
    assert null_results[1] == (_with_raw_data({"result": {"value": "a"}}, {"value": "a"}), None)

    transform = RowMapping(_single_value_mapping({"column": "value", "transforms": ["integer"]}))
    transform_results = list(transform.map_rows([{"value": "not-an-integer"}, {"value": "7"}]))
    assert transform_results[0][0] is None
    assert "row 1, target result.value" in str(transform_results[0][1])
    assert transform_results[1] == (_with_raw_data({"result": {"value": 7}}, {"value": "7"}), None)


def test_failed_row_never_returns_a_partially_built_hit() -> None:
    document = {
        "version": 1,
        "mappings": {"result.first": {"value": "already-computed"}, "user.id": {"column": "missing"}},
    }
    hit, error = next(RowMapping(document).map_rows([{"other": "synthetic"}]))
    assert hit is None
    assert "row 1, target user.id" in str(error)


def test_invalid_configuration_raises_on_call_before_source_iteration() -> None:
    invalid = _single_value_mapping({"value": "constant"})
    invalid["mappings"].clear()
    rows = _TrackedRows()
    for mapper in (map_rows, HowlerMapping().map_rows):
        with pytest.raises(MappingError, match="at least one target"):
            mapper(rows, invalid)
    with pytest.raises(TypeError, match="mapping must be RowMapping"):
        map_rows(rows, 42)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="fields must be supplied"):
        map_rows(rows, _id_mapping(), fields={})
    assert rows.iterations == 0


def test_source_iterator_exception_propagates_unchanged_without_retry() -> None:
    failure = RuntimeError("synthetic source iterator failure")

    def rows() -> Generator[Mapping[str, Any], None, None]:
        yield {"id": "first"}
        raise failure

    generated = _id_mapping().map_rows(rows())
    assert next(generated) == (_with_raw_data({"user": {"id": "first"}}, {"id": "first"}), None)
    with pytest.raises(RuntimeError) as error:
        next(generated)
    assert error.value is failure


def test_from_yaml_yaml_path_and_mapping_document_factories(tmp_path: Path) -> None:
    document = _single_value_mapping({"value": "synthetic"})
    yaml_text = "version: 1\non_null: error\nmappings:\n  result.value:\n    value: synthetic\n"
    assert RowMapping.from_yaml(yaml_text).mapping == document
    path = tmp_path / "mapping.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    assert RowMapping.from_file(path).map_row({}) == _with_raw_data({"result": {"value": "synthetic"}}, {})
    assert next(map_rows([{}], path)) == (_with_raw_data({"result": {"value": "synthetic"}}, {}), None)
    assert next(map_rows([{}], document)) == (_with_raw_data({"result": {"value": "synthetic"}}, {}), None)
    with pytest.raises(MappingError, match="unable to read mapping file"):
        RowMapping.from_file(tmp_path / "missing.yaml")


@pytest.mark.parametrize(
    "mutate",
    [
        lambda doc: doc.update({"unknown": True}),
        lambda doc: doc.update({"version": True}),
        lambda doc: doc.update({"version": 2}),
        lambda doc: doc.update({"on_null": "skip"}),
        lambda doc: doc.update({"on_null": ["omit"]}),
        lambda doc: doc.update({"include_raw_data": "false"}),
        lambda doc: doc.update({"include_raw_data": []}),
        lambda doc: doc["mappings"].clear(),
        lambda doc: doc["mappings"].update({"": {"value": "x"}}),
        lambda doc: doc["mappings"].update({"user..id": {"value": "x"}}),
        lambda doc: doc["mappings"].update({"user.id": "id"}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "value": "x"}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "extra": 1}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": ""}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "transforms": ["eval"]}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "transforms": "trim"}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "transforms": [{"op": "eval"}]}}),
        lambda doc: doc["mappings"].update(
            {"user.id": {"column": "id", "transforms": [{"op": "timestamp", "assume_timezone": "EST"}]}}
        ),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "path": [-1]}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "path": [True]}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "path": []}}),
        lambda doc: doc["mappings"].update({"user.id": {"concat": ["id"]}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "on_null": ["omit"]}}),
        lambda doc: doc["mappings"].update({"user.id": {"value": "x", "path": ["id"]}}),
        lambda doc: doc["mappings"].update({"user.id": {"value": "x"}, "user.id.child": {"value": "y"}}),
        lambda doc: doc["mappings"].update({"user": {"value": {}}, "user.id.child": {"value": "y"}}),
        lambda doc: doc["mappings"].update({"howler.id": {"value": None, "on_null": "omit"}}),
        lambda doc: doc["mappings"].update({"howler.id.child": {"value": "x"}}),
    ],
)
def test_static_malformed_mapping_is_rejected(mutate: Any) -> None:
    document = _single_value_mapping({"column": "value"})
    mutate(document)
    with pytest.raises(MappingError):
        RowMapping(document)


def test_non_mapping_documents_are_rejected() -> None:
    for document in (None, [], "text"):
        with pytest.raises(MappingError, match="mapping document must be an object"):
            RowMapping(document)  # type: ignore[arg-type]


def test_bundled_mapping_schema_is_valid_local_and_matches_runtime_transform_registry() -> None:
    schema = json.loads(
        resources.files("howler_client.schemas").joinpath("row_mapping_v1.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)

    def refs(schema: Any) -> list[str]:
        if isinstance(schema, dict):
            return [
                *([schema["$ref"]] if "$ref" in schema else []),
                *(reference for value in schema.values() for reference in refs(value)),
            ]
        if isinstance(schema, list):
            return [reference for value in schema for reference in refs(value)]
        return []

    assert all(reference.startswith("#/") for reference in refs(schema))
    transform_enum = schema["$defs"]["transform"]["oneOf"][0]["enum"]
    assert set(transform_enum) == set(_TRANSFORMS)


def test_schema_accepts_unrestricted_target_characters_empty_path_parts_and_duplicate_concat_names() -> None:
    target = "  unusual/field #name"
    line_ending_target = "howler.id\n"
    mapping = RowMapping(
        {
            "version": 1,
            "mappings": {
                target: {"column": "nested", "path": ["", ""]},
                line_ending_target: {"value": "not-the-reserved-id"},
                "result.duplicated": {"concat": ["items", "items"]},
            },
        }
    )
    source = {"nested": {"": {"": "kept"}}, "items": ["one"]}
    assert mapping.map_row(source) == _with_raw_data(
        {
            target: "kept",
            "howler": {"id\n": "not-the-reserved-id"},
            "result": {"duplicated": ["one", "one"]},
        },
        source,
    )


@pytest.mark.parametrize("version", [1.0, True])
def test_schema_rejects_non_integer_or_boolean_versions(version: Any) -> None:
    with pytest.raises(MappingError):
        RowMapping({"version": version, "mappings": {"result.value": {"value": "x"}}})


@pytest.mark.parametrize("segment", [1.0, True])
def test_schema_rejects_float_and_boolean_path_indexes(segment: Any) -> None:
    with pytest.raises(MappingError):
        RowMapping(_single_value_mapping({"column": "value", "path": [segment]}))


def test_json_schema_diagnostics_do_not_expose_source_or_constant_values() -> None:
    source_marker = "SENSITIVE_SOURCE_COLUMN_MARKER"
    constant_marker = "SENSITIVE_CONSTANT_PAYLOAD_MARKER"
    document = _single_value_mapping(
        {"column": source_marker, "value": constant_marker, "unrecognized": "SENSITIVE_EXTRA_MARKER"}
    )
    with pytest.raises(MappingError) as error:
        RowMapping(document)

    for marker in (source_marker, constant_marker, "SENSITIVE_EXTRA_MARKER"):
        assert marker not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.parametrize(
    "yaml_text",
    [
        "version: 1\nmappings:\n  result.value: {value: 2026-01-01}\n",
        "version: 1\nmappings:\n  result.value: {value: !!set {member: null}}\n",
        "version: 1\nmappings:\n  result.value: {value: !!binary SGVsbG8=}\n",
        "version: 1\nmappings:\n  result.value: {value: .nan}\n",
        "1: private_root_key_marker\nversion: 1\nmappings:\n  result.value: {value: x}\n",
        "version: 1\nmappings:\n  result.value:\n    1: private_expression_key_marker\n",
        (
            "version: 1\nmappings:\n  result.value:\n    column: value\n"
            "    transforms: [{op: timestamp, 1: private_timestamp_key_marker}]\n"
        ),
    ],
)
def test_yaml_non_json_types_and_invalid_keys_are_rejected_without_echoing_input(yaml_text: str) -> None:
    with pytest.raises(MappingError) as error:
        RowMapping.from_yaml(yaml_text)
    assert "private_" not in str(error.value)


def test_mapping_defaults_are_not_applied_and_expression_null_policy_inherits() -> None:
    default_error_document = {"version": 1, "mappings": {"result.value": {"column": "value"}}}
    default_error_mapping = RowMapping(default_error_document)
    assert default_error_mapping.mapping == default_error_document
    with pytest.raises(MappingError, match="null source value"):
        default_error_mapping.map_row({"value": None})

    document = {"version": 1, "on_null": "omit", "mappings": {"result.value": {"column": "value"}}}
    original = copy.deepcopy(document)
    mapping = RowMapping(document)
    assert mapping.mapping == original
    assert document == original
    with pytest.raises(MappingError, match="all fields were omitted"):
        mapping.map_row({"value": None})

    timestamp_document = {
        "version": 1,
        "mappings": {"result.time": {"column": "value", "transforms": [{"op": "timestamp"}]}},
    }
    timestamp_mapping = RowMapping(timestamp_document)
    assert timestamp_mapping.mapping == timestamp_document
    with pytest.raises(MappingError):
        timestamp_mapping.map_row({"value": "2026-01-01T00:00:00"})


@pytest.mark.parametrize("targets", [["result", "result.value"], ["result.value", "result"]])
def test_semantic_parent_child_conflicts_are_rejected_in_either_order(targets: list[str]) -> None:
    document = {
        "version": 1,
        "mappings": {target: {"value": target} for target in targets},
    }
    with pytest.raises(MappingError, match="conflicting parent/child target"):
        RowMapping(document)


@pytest.mark.parametrize("target", ["howler.id", "howler.id.child"])
def test_schema_rejection_of_server_owned_targets_keeps_safe_diagnostic(target: str) -> None:
    with pytest.raises(MappingError, match="howler.id is server-generated"):
        RowMapping({"version": 1, "mappings": {target: {"value": "x"}}})


def test_null_missing_and_path_semantics() -> None:
    omit = RowMapping(_single_value_mapping({"column": "value"}, on_null="omit"))
    with pytest.raises(MappingError, match="all fields were omitted"):
        omit.map_row({"value": None})
    with pytest.raises(MappingError, match="row 1, target result.value: source column is missing"):
        omit.map_row({})

    path = RowMapping(_single_value_mapping({"column": "value", "path": ["child", 1]}, on_null="omit"))
    source = {"value": {"child": ["a", "b"]}}
    assert path.map_row(source) == _with_raw_data({"result": {"value": "b"}}, source)
    for missing in ({}, {"child": None}, {"child": ["a"]}, None):
        with pytest.raises(MappingError, match="all fields were omitted"):
            path.map_row({"value": missing})
    with pytest.raises(MappingError, match="wrong container type"):
        path.map_row({"value": {"child": "not-a-list"}})

    strict_path = RowMapping(_single_value_mapping({"column": "value", "path": ["child"]}))
    with pytest.raises(MappingError, match="null source value"):
        strict_path.map_row({"value": {}})

    concat = RowMapping(_single_value_mapping({"concat": ["left", "right"]}, on_null="omit"))
    with pytest.raises(MappingError, match="row 1, target result.value: source column is missing"):
        concat.map_row({"left": None})


def test_concat_joins_lists_and_applies_null_policy() -> None:
    document = _single_value_mapping({"concat": ["left", "right"], "on_null": "omit"})
    document["mappings"]["user.id"] = {"value": "still-present"}
    source = {"left": ["a"], "right": ["b", "a"]}
    assert RowMapping(document).map_row(source) == _with_raw_data(
        {"result": {"value": ["a", "b", "a"]}, "user": {"id": "still-present"}}, source
    )
    source = {"left": None, "right": []}
    assert RowMapping(document).map_row(source) == _with_raw_data({"user": {"id": "still-present"}}, source)
    with pytest.raises(MappingError, match="concat requires list-valued columns"):
        RowMapping(document).map_row({"left": "a", "right": []})

    document["mappings"]["result.value"]["on_null"] = "error"
    with pytest.raises(MappingError, match="row 1, target result.value: null source value"):
        RowMapping(document).map_row({"left": None, "right": []})


def test_transform_string_integer_number_and_boolean_boundaries() -> None:
    assert _single_row({"column": "value", "transforms": ["string"]}, True) == "true"
    assert _single_row({"column": "value", "transforms": ["string"]}, 3.0) == "3.0"
    with pytest.raises(MappingError, match="use the json transform"):
        _single_row({"column": "value", "transforms": ["string"]}, {"a": 1})

    assert _single_row({"column": "value", "transforms": ["integer"]}, "42") == 42
    assert _single_row({"column": "value", "transforms": ["integer"]}, 3.0) == 3
    for invalid in (True, 3.1, "3.0", "not-a-number", float("inf"), float("nan")):
        with pytest.raises(MappingError):
            _single_row({"column": "value", "transforms": ["integer"]}, invalid)

    assert _single_row({"column": "value", "transforms": ["number"]}, "2.5") == 2.5
    for invalid in (True, "nan", "inf", float("inf"), float("nan"), 10**400, [1]):
        with pytest.raises(MappingError):
            _single_row({"column": "value", "transforms": ["number"]}, invalid)

    assert _single_row({"column": "value", "transforms": ["boolean"]}, True) is True
    assert _single_row({"column": "value", "transforms": ["boolean"]}, "false") is False
    for invalid in (1, "yes", "True"):
        with pytest.raises(MappingError):
            _single_row({"column": "value", "transforms": ["boolean"]}, invalid)


def test_transform_text_list_and_canonical_json_boundaries() -> None:
    assert _single_row({"column": "value", "transforms": ["trim", "lower"]}, "  HELLO ") == "hello"
    assert _single_row({"column": "value", "transforms": ["upper"]}, "hi") == "HI"
    with pytest.raises(MappingError, match="text transform"):
        _single_row({"column": "value", "transforms": ["trim"]}, 1)

    assert _single_row({"column": "value", "transforms": ["list"]}, "one") == ["one"]
    assert _single_row({"column": "value", "transforms": ["list"]}, ["one", "one"]) == ["one", "one"]
    assert _single_row({"column": "value", "transforms": ["json"]}, {"z": 2, "é": 1}) == '{"z":2,"é":1}'


def test_timestamp_timezone_normalization_and_explicit_utc_assumption() -> None:
    timestamp = {"column": "value", "transforms": [{"op": "timestamp"}]}
    assume_utc = {"column": "value", "transforms": [{"op": "timestamp", "assume_timezone": "UTC"}]}
    assert _single_row(timestamp, "2026-01-01T01:02:03.123456+01:00") == "2026-01-01T00:02:03.123456Z"
    assert _single_row(timestamp, "2026-01-01T01:02:03Z") == "2026-01-01T01:02:03.000000Z"
    assert _single_row(assume_utc, "2026-01-01T01:02:03") == "2026-01-01T01:02:03.000000Z"
    assert _single_row(assume_utc, "2026-01-01") == "2026-01-01T00:00:00.000000Z"
    with pytest.raises(MappingError, match="no timezone"):
        _single_row(timestamp, "2026-01-01T00:00:00")
    for invalid in ("not-a-date", 20260101):
        with pytest.raises(MappingError, match="ISO-8601"):
            _single_row(timestamp, invalid)


def test_non_json_mapped_values_fail_without_echoing_values_and_later_rows_continue() -> None:
    deep_value: Any = "synthetic leaf"
    for _ in range(100_000):
        deep_value = {"child": deep_value}

    mapper = RowMapping(_single_value_mapping({"column": "value"}))
    invalid_values = [
        float("nan"),
        float("inf"),
        object(),
        {"secret": "not-json-source-value", "nested": float("nan")},
        deep_value,
    ]
    digit_limit = getattr(sys, "get_int_max_str_digits", lambda: 0)()
    rows = [{"value": "first"}, *({"value": value} for value in invalid_values), {"value": "last"}]
    results = list(mapper.map_rows(rows))

    assert results[0] == (_with_raw_data({"result": {"value": "first"}}, {"value": "first"}), None)
    assert results[-1] == (_with_raw_data({"result": {"value": "last"}}, {"value": "last"}), None)
    for row_number, (hit, error) in enumerate(results[1:-1], start=2):
        assert hit is None
        _assert_detached_error(error)
        assert str(error) == f"row {row_number}, target result.value: value is not valid JSON"

    if digit_limit > 0:
        json_mapper = RowMapping(_single_value_mapping({"column": "value", "transforms": ["json"]}))
        with pytest.raises(MappingError, match="value is not valid JSON"):
            json_mapper.map_row({"value": 10**digit_limit})


def test_unmapped_raw_source_columns_must_be_valid_json() -> None:
    deep_value: Any = "synthetic leaf"
    for _ in range(100_000):
        deep_value = {"child": deep_value}
    mapper = RowMapping(_single_value_mapping({"column": "value"}))
    hit, error = next(mapper.map_rows([{"value": "a", "unused": deep_value}]))
    assert hit is None
    assert str(error) == "row 1, target howler.data: raw row is not valid JSON"


def test_constants_are_validated_once_and_copied_per_row() -> None:
    with pytest.raises(MappingError, match="mapping document is not valid JSON"):
        RowMapping(_single_value_mapping({"value": float("nan")}))
    with pytest.raises(MappingError, match="invalid constant for target result.value: invalid integer"):
        RowMapping(_single_value_mapping({"value": "x", "transforms": ["integer"]}))

    omitted = _single_value_mapping({"value": None}, on_null="omit")
    omitted["mappings"]["user.id"] = {"column": "id"}
    source = {"id": "a"}
    assert RowMapping(omitted).map_row(source) == _with_raw_data({"user": {"id": "a"}}, source)


def test_yaml_parse_errors_are_sanitized() -> None:
    bad_documents = [
        "value: [unterminated\n",
        "value: !!python/object/apply:os.system ['echo private_marker']\n",
        "value: !!int private_marker\n",
        "value: !!bool private_marker\n",
        "first: document\n---\nsecond: document\n",
    ]
    for text in bad_documents:
        with pytest.raises(MappingError) as error:
            RowMapping.from_yaml(text)
        assert str(error.value) == "invalid YAML mapping document"


def test_yaml_documents_must_still_pass_mapping_validation() -> None:
    with pytest.raises(MappingError, match="mapping document must be an object"):
        RowMapping.from_yaml("- not\n- an object\n")
    with pytest.raises(MappingError, match="mapping document is not valid JSON"):
        RowMapping.from_yaml("version: 1\nmappings:\n  result.date: {value: 2026-01-01}\n")
    quoted = RowMapping.from_yaml('version: 1\nmappings:\n  result.date: {value: "2026-01-01"}\n')
    assert quoted.map_row({}) == _with_raw_data({"result": {"date": "2026-01-01"}}, {})


def test_every_row_gets_fresh_nested_output_and_no_server_generated_id() -> None:
    source = _row()
    source_before = copy.deepcopy(source)
    (first, first_error), (second, second_error) = list(RowMapping(_base_mapping()).map_rows([source, source]))

    assert first_error is None and second_error is None
    assert first is not None and second is not None
    assert first == second
    assert first["user"]["roles"] == ["admin", "reader", "reader", "operator"]
    assert first["event"]["created"] == "2026-04-01T08:00:00.000000Z"
    assert "id" not in first["howler"]
    assert first["howler"]["data"][0] == source

    first["user"]["roles"].append("mutated")
    first["custom"]["object"]["tags"].append("mutated")
    first["custom"]["constant"]["members"].append("mutated")
    first["howler"]["data"][0]["nested"]["tags"].append("mutated")
    assert "mutated" not in second["user"]["roles"]
    assert "mutated" not in second["custom"]["object"]["tags"]
    assert "mutated" not in second["custom"]["constant"]["members"]
    assert "mutated" not in second["howler"]["data"][0]["nested"]["tags"]
    assert source == source_before


def test_raw_record_is_first_data_entry_and_mapped_data_follows() -> None:
    source = {"id": "synthetic-1", "payload": "mapped raw value", "unused": {"keep": True}}
    mapping = RowMapping(
        {
            "version": 1,
            "mappings": {
                "user.id": {"column": "id"},
                "howler.data": {"column": "payload"},
            },
        }
    )

    hit = mapping.map_row(source)

    assert hit["howler"]["data"] == [source, "mapped raw value"]
    hit["howler"]["data"][0]["unused"]["keep"] = False
    assert source["unused"]["keep"] is True


def test_raw_record_inclusion_can_be_disabled_and_explicit_data_is_preserved() -> None:
    source = {"id": "synthetic-1", "payload": "mapped raw value"}
    mapping = RowMapping(
        {
            "version": 1,
            "include_raw_data": False,
            "mappings": {
                "user.id": {"column": "id"},
            },
        }
    )
    assert mapping.map_row(source) == {"user": {"id": "synthetic-1"}}
    assert mapping.map_row({"id": "synthetic-1", "unused": object()}) == {"user": {"id": "synthetic-1"}}

    mapping_with_data = RowMapping(
        {
            "version": 1,
            "include_raw_data": False,
            "mappings": {
                "user.id": {"column": "id"},
                "howler.data": {"column": "payload"},
            },
        }
    )
    assert mapping_with_data.map_row(source) == {
        "user": {"id": "synthetic-1"},
        "howler": {"data": "mapped raw value"},
    }


def test_mapping_document_is_detached_from_caller() -> None:
    document = _base_mapping()
    mapper = RowMapping(document)
    document["mappings"]["custom.constant"]["value"]["members"].append("mutated")
    mapper.mapping["mappings"]["custom.constant"]["value"]["members"].append("mutated")
    assert mapper.map_row(_row())["custom"]["constant"] == {"members": ["fixed"]}


def test_server_owned_ids_are_rejected_in_parent_values_and_dynamic_rows() -> None:
    with pytest.raises(MappingError, match="howler.id is server-generated"):
        RowMapping(_single_value_mapping({"value": {"id": None}}, target="howler"))

    mapper = RowMapping(_single_value_mapping({"column": "value"}, target="howler"))
    source = {"value": {"analytic": "a"}}
    assert mapper.map_row(source) == _with_raw_data({"howler": {"analytic": "a"}}, source)
    with pytest.raises(MappingError, match="row 1, target howler: howler.id is server-generated"):
        mapper.map_row({"value": {"id": {"child": "not allowed"}}})
    with pytest.raises(MappingError, match="howler.id is server-generated"):
        mapper.map_row({"value": {"id.child": "not allowed"}})


def test_fields_check_existence_deprecation_and_concat_targets() -> None:
    document = _base_mapping()
    fields = {
        "howler.analytic": {"type": "keyword", "list": False},
        "user.id": {"type": "keyword", "list": False},
        "user.name": {"type": "keyword", "list": False},
        "user.roles": {"type": "keyword", "list": True},
        "event.created": {"type": "date", "list": False},
        "custom.object": {"type": "object", "list": False},
        "custom.constant": {"type": "object", "list": False},
    }
    assert RowMapping(document, fields=fields).map_row(_row())["user"]["id"] == "synthetic-1"

    unknown = copy.deepcopy(document)
    unknown["mappings"]["unknown.field"] = {"value": "x"}
    with pytest.raises(MappingError, match="unknown Howler field: unknown.field"):
        RowMapping(unknown, fields=fields)

    deprecated = copy.deepcopy(fields)
    deprecated["user.id"]["deprecated"] = True
    with pytest.raises(MappingError, match="deprecated Howler field: user.id"):
        RowMapping(document, fields=deprecated)

    non_list = copy.deepcopy(fields)
    non_list["user.roles"]["list"] = False
    with pytest.raises(MappingError, match="concat requires a list target"):
        RowMapping(document, fields=non_list)

    with pytest.raises(MappingError, match="fields must map field names"):
        RowMapping(document, fields=[])  # type: ignore[arg-type]

    wrong_constant = _single_value_mapping({"value": 1}, target="user.id")
    assert RowMapping(wrong_constant, fields=fields).map_row({}) == _with_raw_data({"user": {"id": 1}}, {})


def test_fields_do_not_check_mapped_row_types_or_list_shape() -> None:
    fields = {
        "event.count": {"type": "integer", "list": False},
        "event.counts": {"type": "long", "list": True},
        "event.ratio": {"type": "float", "list": False},
        "event.flag": {"type": "boolean", "list": False},
        "event.created": {"type": "date", "list": False},
        "source.ip": {"type": "ip", "list": False},
        "event.other": {"type": "geo_point", "list": False},
    }

    def mapper(target: str) -> RowMapping:
        return RowMapping(_single_value_mapping({"column": "value"}, target=target), fields=fields)

    assert mapper("event.count").map_row({"value": 2}) == _with_raw_data({"event": {"count": 2}}, {"value": 2})
    assert mapper("event.counts").map_row({"value": [1, 2]}) == _with_raw_data(
        {"event": {"counts": [1, 2]}}, {"value": [1, 2]}
    )
    assert mapper("event.ratio").map_row({"value": 1}) == _with_raw_data({"event": {"ratio": 1}}, {"value": 1})
    assert mapper("source.ip").map_row({"value": "2001:db8::1"}) == _with_raw_data(
        {"source": {"ip": "2001:db8::1"}}, {"value": "2001:db8::1"}
    )
    assert mapper("event.other").map_row({"value": {"lat": 1}}) == _with_raw_data(
        {"event": {"other": {"lat": 1}}}, {"value": {"lat": 1}}
    )

    values = [
        ("event.count", True),
        ("event.count", 1.5),
        ("event.counts", 1),
        ("event.counts", [1, "2"]),
        ("event.flag", [True]),
        ("event.flag", "true"),
        ("event.created", "2026-01-01T00:00:00"),
        ("source.ip", "not-an-ip"),
        ("source.ip", 1),
    ]
    for target, value in values:
        hit = mapper(target).map_row({"value": value})
        nested_value: Any = hit
        parts = target.split(".")
        for part in parts[:-1]:
            nested_value = nested_value[part]
        assert nested_value[parts[-1]] == value


def test_without_fields_backend_field_catalog_is_not_checked() -> None:
    document = _single_value_mapping({"value": "synthetic"}, target="unknown.field")
    assert RowMapping(document).map_row({}) == _with_raw_data({"unknown": {"field": "synthetic"}}, {})


def test_sanitized_directory_example_with_and_without_fields() -> None:
    example_path = Path(__file__).parents[2] / "examples" / "row_mapping" / "example_mapping.yaml"
    mapper = RowMapping.from_file(example_path, fields=EXAMPLE_FIELDS)
    synthetic_row = {
        "classification_label": "UNCLASSIFIED",
        "user_identifier": "synthetic-principal-001",
        "account_name": " User@Example.Invalid ",
        "profile": {
            "display_name": " Synthetic Example User ",
            "organization": {"name": " Example Organization "},
        },
        "primary_email": None,
        "directory_role_names": ["Synthetic Reader", "Synthetic Analyst"],
        "elevated_role_names": ["Synthetic Operator"],
    }

    hit, error = next(mapper.map_rows([synthetic_row]))
    assert error is None
    assert hit == _with_raw_data(
        {
            "howler": {"analytic": "Directory User Inventory Snapshot"},
            "classification": "UNCLASSIFIED",
            "user": {
                "id": "synthetic-principal-001",
                "name": "user@example.invalid",
                "full_name": "Synthetic Example User",
                "roles": ["Synthetic Reader", "Synthetic Analyst", "Synthetic Operator"],
            },
            "organization": {"name": "Example Organization"},
        },
        synthetic_row,
    )
    assert RowMapping.from_file(example_path).map_row(synthetic_row) == hit
