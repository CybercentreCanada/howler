"""Focused offline tests for lazy raw-row to Howler hit mapping."""

from __future__ import annotations

import copy
import hashlib
import inspect
import itertools
import json
import sys
from collections.abc import Generator, Mapping
from pathlib import Path
from typing import Any

import pytest

from howler_client.module.mapping import HowlerMapping, MappingError, RowMapping, RowMappingResult

EXAMPLE_URL = "https://example.invalid/mcp"
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


def _fingerprint(fields: Mapping[str, Any]) -> str:
    canonical = json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _snapshot(fields: Mapping[str, Any] | None = None, url: str = EXAMPLE_URL) -> dict[str, Any]:
    selected = dict(fields or EXAMPLE_FIELDS)
    return {
        "version": 1,
        "mcp_url": url,
        "fields_sha256": _fingerprint(selected),
        "fields": selected,
    }


def _base_mapping() -> dict[str, Any]:
    return {
        "version": 1,
        "source": {
            "table": "synthetic.identity.users",
            "columns": ["id", "name", "roles_a", "roles_b", "created", "nested", "maybe"],
        },
        "target": {
            "index": "hit",
            "mcp_url": EXAMPLE_URL,
            "fields_sha256": _fingerprint(EXAMPLE_FIELDS),
        },
        "policy": {"missing": "error", "on_null": "error"},
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
        "maybe": "present",
    }


def _single_value_mapping(
    expression: dict[str, Any],
    *,
    target: str = "result.value",
    value_key: str = "value",
    on_null: str = "error",
) -> dict[str, Any]:
    return {
        "version": 1,
        "source": {"table": "synthetic.values", "columns": [value_key]},
        "target": {"index": "hit", "mcp_url": EXAMPLE_URL, "fields_sha256": "0" * 64},
        "policy": {"missing": "error", "on_null": on_null},
        "mappings": {target: expression},
    }


def _single_row(expression: dict[str, Any], value: Any, **kwargs: Any) -> Any:
    mapping = _single_value_mapping(expression, **kwargs)
    return RowMapping(mapping).map_row({kwargs.get("value_key", "value"): value})["result"]["value"]


def _assert_detached_error(error: MappingError | None) -> None:
    assert isinstance(error, MappingError)
    assert error.__traceback__ is None
    assert error.__cause__ is None
    assert error.__context__ is None
    assert error.__suppress_context__ is True


def test_public_api_is_generator_and_consumes_one_shot_infinite_input_on_demand() -> None:
    assert inspect.isgeneratorfunction(HowlerMapping().map_rows)
    assert inspect.isgeneratorfunction(RowMapping.map_rows)

    started: list[int] = []

    def endless_rows() -> Generator[Mapping[str, Any], None, None]:
        for number in itertools.count():
            started.append(number)
            yield {"id": f"synthetic-{number}"}

    source = endless_rows()
    generated = HowlerMapping().map_rows(
        source, _single_value_mapping({"column": "id"}, target="user.id", value_key="id")
    )
    assert inspect.isgenerator(generated)
    assert started == []
    assert next(generated) == ({"user": {"id": "synthetic-0"}}, None)
    assert started == [0]
    assert next(generated) == ({"user": {"id": "synthetic-1"}}, None)
    assert started == [0, 1]


def test_row_mapping_method_is_lazy_and_preserves_source_order() -> None:
    calls: list[int] = []

    def one_shot() -> Generator[Mapping[str, Any], None, None]:
        for number in range(3):
            calls.append(number)
            yield {"id": str(number)}

    mapping = RowMapping(_single_value_mapping({"column": "id"}, target="user.id", value_key="id"))
    rows = mapping.map_rows(one_shot())
    assert calls == []
    assert next(rows) == ({"user": {"id": "0"}}, None)
    assert calls == [0]
    assert list(rows) == [({"user": {"id": "1"}}, None), ({"user": {"id": "2"}}, None)]
    assert calls == [0, 1, 2]


def test_valid_invalid_valid_rows_yield_results_and_continue_without_leaking_values() -> None:
    mapping = RowMapping(_single_value_mapping({"column": "id"}, target="user.id", value_key="id"))
    results: list[RowMappingResult] = list(
        HowlerMapping().map_rows(
            [
                {"id": "first"},
                {"private_payload": "DO_NOT_INCLUDE_THIS_SOURCE_VALUE"},
                {"id": "third"},
            ],
            mapping,
        )
    )
    assert results[0] == ({"user": {"id": "first"}}, None)
    assert results[1][0] is None
    _assert_detached_error(results[1][1])
    assert "row 2" in str(results[1][1])
    assert "user.id" in str(results[1][1])
    assert "DO_NOT_INCLUDE_THIS_SOURCE_VALUE" not in str(results[1][1])
    assert results[2] == ({"user": {"id": "third"}}, None)


def test_repeated_failures_and_non_mapping_rows_are_returned_independently() -> None:
    mapper = RowMapping(_single_value_mapping({"column": "id"}, target="user.id", value_key="id"))
    repeated = list(mapper.map_rows([{}, {}, {"id": "valid"}, {}]))
    assert [hit for hit, _error in repeated] == [None, None, {"user": {"id": "valid"}}, None]
    errors = [error for _hit, error in repeated if error is not None]
    assert [str(error).split(",", 1)[0] for error in errors] == ["row 1", "row 2", "row 4"]
    assert len({id(error) for error in errors}) == 3
    for error in errors:
        _assert_detached_error(error)

    mixed_rows: list[Any] = [None, 42, ["not", "a", "row"], {"id": "valid"}]
    mixed_results = list(mapper.map_rows(mixed_rows))  # type: ignore[arg-type]
    assert [hit for hit, _error in mixed_results] == [None, None, None, {"user": {"id": "valid"}}]
    for row_number, (_hit, error) in enumerate(mixed_results[:3], start=1):
        _assert_detached_error(error)
        assert f"row {row_number}" in str(error)
        assert "target <row>" in str(error)


def test_null_path_and_transform_row_failures_return_errors_then_continue() -> None:
    null_mapping = RowMapping(_single_value_mapping({"column": "value"}))
    null_results = list(null_mapping.map_rows([{"value": None}, {"value": "good"}]))
    assert null_results[0][0] is None
    _assert_detached_error(null_results[0][1])
    assert "row 1, target result.value" in str(null_results[0][1])
    assert null_results[1] == ({"result": {"value": "good"}}, None)

    path_document = _single_value_mapping({"column": "value", "path": ["child"]}, on_null="omit")
    path_mapping = RowMapping(path_document)
    path_results = list(path_mapping.map_rows([{"value": {}}, {"value": {"child": "good"}}]))
    assert path_results[0][0] is None
    _assert_detached_error(path_results[0][1])
    assert "row 1, target result.value" in str(path_results[0][1])
    assert path_results[1] == ({"result": {"value": "good"}}, None)

    transform_document = _single_value_mapping({"column": "value", "transforms": ["integer"]})
    transform_mapping = RowMapping(transform_document)
    transform_results = list(transform_mapping.map_rows([{"value": "not-an-integer"}, {"value": "7"}]))
    assert transform_results[0][0] is None
    _assert_detached_error(transform_results[0][1])
    assert "row 1, target result.value" in str(transform_results[0][1])
    assert transform_results[1] == ({"result": {"value": 7}}, None)


def test_failed_row_never_returns_a_partially_built_hit() -> None:
    document = _single_value_mapping({"value": "already-computed"}, value_key="missing")
    document["source"]["columns"].append("other")
    document["mappings"] = {"result.first": {"value": "already-computed"}}
    document["mappings"]["user.id"] = {"column": "missing"}
    mapper = RowMapping(document)

    hit, error = next(mapper.map_rows([{"other": "synthetic"}]))
    assert hit is None
    _assert_detached_error(error)
    assert "row 1, target user.id" in str(error)


def test_invalid_configuration_raises_before_source_iteration_even_when_empty() -> None:
    consumed: list[str] = []

    class TrackedRows:
        def __iter__(self) -> Generator[Mapping[str, Any], None, None]:
            consumed.append("iterated")
            yield {"value": "should-not-be-read"}

    invalid_mapping = _single_value_mapping({"value": "constant"})
    invalid_mapping["mappings"].clear()
    generated = HowlerMapping().map_rows(TrackedRows(), invalid_mapping)  # type: ignore[arg-type]
    with pytest.raises(MappingError, match="at least one target"):
        next(generated)
    assert consumed == []

    with pytest.raises(MappingError, match="at least one target"):
        list(HowlerMapping().map_rows([], invalid_mapping))


def test_source_iterator_exception_propagates_unchanged_without_retry() -> None:
    failure = RuntimeError("synthetic source iterator failure")
    attempts: list[str] = []

    def rows() -> Generator[Mapping[str, Any], None, None]:
        yield {"id": "first"}
        attempts.append("raised")
        raise failure

    mapper = RowMapping(_single_value_mapping({"column": "id"}, target="user.id", value_key="id"))
    generated = mapper.map_rows(rows())
    assert next(generated) == ({"user": {"id": "first"}}, None)
    with pytest.raises(RuntimeError) as error:
        next(generated)
    assert error.value is failure
    assert attempts == ["raised"]


def test_from_yaml_yaml_path_and_mapping_document_factories(tmp_path: Path) -> None:
    document = _single_value_mapping({"value": "synthetic"})
    yaml_text = """version: 1
source:
  table: synthetic.values
  columns: [value]
target:
  index: hit
  mcp_url: https://example.invalid/mcp
  fields_sha256: "0000000000000000000000000000000000000000000000000000000000000000"
policy:
  missing: error
  on_null: error
mappings:
  result.value:
    value: synthetic
"""
    from_yaml = RowMapping.from_yaml(yaml_text)
    assert from_yaml.mapping == document
    path = tmp_path / "mapping.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    from_file = RowMapping.from_file(path)
    assert next(HowlerMapping().map_rows([{}], path)) == ({"result": {"value": "synthetic"}}, None)
    assert from_file.map_row({}) == {"result": {"value": "synthetic"}}
    assert next(HowlerMapping().map_rows([{}], document)) == ({"result": {"value": "synthetic"}}, None)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda doc: doc.update({"unknown": True}),
        lambda doc: doc.update({"version": True}),
        lambda doc: doc.update({"version": 2}),
        lambda doc: doc["source"].update({"extra": "not allowed"}),
        lambda doc: doc["source"].update({"columns": []}),
        lambda doc: doc["source"].update({"columns": ["id", "id"]}),
        lambda doc: doc["target"].update({"index": "event"}),
        lambda doc: doc["target"].update({"mcp_url": "http://example.invalid/mcp"}),
        lambda doc: doc["policy"].update({"missing": "omit"}),
        lambda doc: doc["mappings"].clear(),
        lambda doc: doc["mappings"].update({"user.id": {"column": "not_declared"}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "value": "x"}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "transforms": ["eval"]}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "path": [-1]}}),
        lambda doc: doc["mappings"].update({"user.id": {"concat": ["id", "id"]}}),
        lambda doc: doc["mappings"].update({"user.id": {"concat": ["id", "missing"]}}),
        lambda doc: doc["mappings"].update({"user.id": {"column": "id", "on_null": ["omit"]}}),
        lambda doc: doc["mappings"].update({"user.id": {"value": "x", "path": ["id"]}}),
        lambda doc: doc["mappings"].update({"user.id": {"value": "x"}, "user.id.child": {"value": "y"}}),
        lambda doc: doc["mappings"].update({"howler.id": {"value": None, "on_null": "omit"}}),
        lambda doc: doc["mappings"].update({"howler.id.child": {"value": "x"}}),
    ],
)
def test_static_malformed_mapping_is_rejected(mutate: Any) -> None:
    document = _single_value_mapping({"column": "value"})
    mutate(document)
    with pytest.raises(MappingError):
        RowMapping(document)


def test_null_missing_and_path_semantics_are_distinct() -> None:
    omit_mapping = _single_value_mapping({"column": "value", "on_null": "omit"}, on_null="omit")
    with pytest.raises(MappingError, match="all fields were omitted"):
        RowMapping(omit_mapping).map_row({"value": None})
    with pytest.raises(MappingError, match="row 1, target result.value: source column is missing"):
        RowMapping(omit_mapping).map_row({})

    path_mapping = _single_value_mapping({"column": "value", "path": ["missing"], "on_null": "omit"}, on_null="omit")
    with pytest.raises(MappingError, match="row 1, target result.value: source path is missing"):
        RowMapping(path_mapping).map_row({"value": {}})

    concat_mapping = _single_value_mapping(
        {"concat": ["left", "right"], "on_null": "omit"},
        value_key="left",
        on_null="omit",
    )
    concat_mapping["source"]["columns"] = ["left", "right"]
    with pytest.raises(MappingError, match="row 1, target result.value: source column is missing"):
        RowMapping(concat_mapping).map_row({"left": None})


def test_concat_null_policy_omits_target_only_after_checking_all_inputs() -> None:
    document = _single_value_mapping({"concat": ["left", "right"], "on_null": "omit"}, on_null="omit")
    document["source"]["columns"] = ["left", "right"]
    document["mappings"]["user.id"] = {"value": "still-present"}
    mapper = RowMapping(document)
    assert mapper.map_row({"left": None, "right": []}) == {"user": {"id": "still-present"}}

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
    for invalid in (True, 3.1, "3.0", "not-a-number"):
        with pytest.raises(MappingError):
            _single_row({"column": "value", "transforms": ["integer"]}, invalid)

    assert _single_row({"column": "value", "transforms": ["number"]}, "2.5") == 2.5
    for invalid in (True, "nan", "inf", float("inf"), float("nan")):
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
    assert _single_row({"column": "value", "transforms": ["json"]}, {"z": 2, "a": 1}) == '{"a":1,"z":2}'


@pytest.mark.parametrize("operation", ["json", "string"])
@pytest.mark.parametrize("use_public_api", [False, True])
def test_large_integer_serialization_errors_are_row_results_and_later_rows_continue(
    operation: str, use_public_api: bool
) -> None:
    digit_limit = getattr(sys, "get_int_max_str_digits", lambda: 0)()
    if digit_limit <= 0:
        pytest.skip("this Python runtime does not enforce an integer-to-string digit limit")
    large_integer = 10**digit_limit

    document = _single_value_mapping({"column": "value", "transforms": [operation]})
    mapper = RowMapping(document)
    rows = [{"value": "first"}, {"value": large_integer}, {"value": "third"}]
    generated = HowlerMapping().map_rows(rows, document) if use_public_api else mapper.map_rows(rows)
    results = list(generated)

    assert results[0][0] is not None and results[0][1] is None
    assert results[1][0] is None
    _assert_detached_error(results[1][1])
    assert str(results[1][1]) == "row 2, target result.value: JSON value cannot be serialized safely"
    assert results[2][0] is not None and results[2][1] is None

    with pytest.raises(MappingError, match="JSON value cannot be serialized safely"):
        mapper.map_row({"value": large_integer})

    constant_document = _single_value_mapping({"value": large_integer, "transforms": [operation]})
    with pytest.raises(MappingError, match="invalid constant for target result.value") as config_error:
        RowMapping(constant_document)
    assert str(config_error.value) == (
        "invalid constant for target result.value: JSON value cannot be serialized safely"
    )

    source_iterations: list[str] = []

    class TrackedRows:
        def __iter__(self) -> Generator[Mapping[str, Any], None, None]:
            source_iterations.append("iterated")
            yield {"value": "must-not-be-read"}

    with pytest.raises(MappingError, match="invalid constant for target result.value"):
        next(HowlerMapping().map_rows(TrackedRows(), constant_document))  # type: ignore[arg-type]
    assert source_iterations == []


@pytest.mark.parametrize("use_public_api", [False, True])
def test_oversized_integer_for_float_field_returns_error_and_continues(use_public_api: bool) -> None:
    snapshot = _snapshot({"result.value": {"type": "float", "list": False}})
    document = _single_value_mapping({"column": "value"})
    document["target"]["fields_sha256"] = snapshot["fields_sha256"]
    mapper = RowMapping(document, fields_snapshot=snapshot)
    rows = [{"value": 1.25}, {"value": 10**400}, {"value": 2.5}]
    generated = (
        HowlerMapping().map_rows(rows, document, fields_snapshot=snapshot) if use_public_api else mapper.map_rows(rows)
    )
    results = list(generated)

    assert results[0] == ({"result": {"value": 1.25}}, None)
    assert results[1][0] is None
    _assert_detached_error(results[1][1])
    assert str(results[1][1]) == "row 2, target result.value: target requires float"
    assert results[2] == ({"result": {"value": 2.5}}, None)
    with pytest.raises(MappingError, match="target requires float"):
        mapper.map_row({"value": 10**400})


@pytest.mark.parametrize("shape", ["list", "dict"])
@pytest.mark.parametrize("use_public_api", [False, True])
def test_deep_selected_row_values_return_detached_errors_and_continue(shape: str, use_public_api: bool) -> None:
    deep_value: Any = "synthetic leaf"
    for _ in range(2_000):
        deep_value = [deep_value] if shape == "list" else {"child": deep_value}

    document = _single_value_mapping({"column": "value"})
    mapper = RowMapping(document)
    rows = [{"value": "first"}, {"value": deep_value}, {"value": "third"}]
    generated = HowlerMapping().map_rows(rows, document) if use_public_api else mapper.map_rows(rows)
    results = list(generated)

    assert results[0] == ({"result": {"value": "first"}}, None)
    assert results[1][0] is None
    _assert_detached_error(results[1][1])
    assert "row 2, target result.value" in str(results[1][1])
    assert "maximum JSON nesting depth of 128" in str(results[1][1])
    assert "synthetic leaf" not in str(results[1][1])
    assert results[2] == ({"result": {"value": "third"}}, None)

    with pytest.raises(MappingError, match="maximum JSON nesting depth of 128"):
        mapper.map_row({"value": deep_value})


def test_deep_unmapped_source_columns_are_not_traversed_or_copied() -> None:
    deep_value: Any = "synthetic leaf"
    for _ in range(2_000):
        deep_value = {"child": deep_value}
    document = _single_value_mapping({"column": "value"})
    document["source"]["columns"].append("unused")

    results = list(
        HowlerMapping().map_rows(
            [
                {"value": "first", "unused": deep_value},
                {"value": "second", "unused": deep_value},
            ],
            document,
        )
    )
    assert results == [
        ({"result": {"value": "first"}}, None),
        ({"result": {"value": "second"}}, None),
    ]


def test_deep_mapping_and_snapshot_configuration_fail_before_source_iteration() -> None:
    deep_value: Any = "synthetic leaf"
    for _ in range(2_000):
        deep_value = [deep_value]

    class TrackedRows:
        def __init__(self) -> None:
            self.iterations = 0

        def __iter__(self) -> Generator[Mapping[str, Any], None, None]:
            self.iterations += 1
            yield {"value": "must-not-be-read"}

    deep_constant = _single_value_mapping({"value": deep_value})
    mapping_rows = TrackedRows()
    with pytest.raises(MappingError, match="maximum JSON nesting depth of 128"):
        next(HowlerMapping().map_rows(mapping_rows, deep_constant))  # type: ignore[arg-type]
    assert mapping_rows.iterations == 0

    valid_document = _single_value_mapping({"column": "value"})
    fields = {
        "result.value": {
            "type": "keyword",
            "list": False,
            "description": {"deep": deep_value},
        }
    }
    snapshot = {
        "version": 1,
        "mcp_url": EXAMPLE_URL,
        "fields_sha256": "0" * 64,
        "fields": fields,
    }
    snapshot_rows = TrackedRows()
    with pytest.raises(MappingError, match="maximum JSON nesting depth of 128"):
        next(HowlerMapping().map_rows(snapshot_rows, valid_document, fields_snapshot=snapshot))
    assert snapshot_rows.iterations == 0


def test_unserializable_snapshot_metadata_fails_safely_before_source_iteration() -> None:
    digit_limit = getattr(sys, "get_int_max_str_digits", lambda: 0)()
    if digit_limit <= 0:
        pytest.skip("this Python runtime does not enforce an integer-to-string digit limit")
    fields = {
        "result.value": {
            "type": "keyword",
            "list": False,
            "description": 10**digit_limit,
        }
    }
    snapshot = {
        "version": 1,
        "mcp_url": EXAMPLE_URL,
        "fields_sha256": "0" * 64,
        "fields": fields,
    }
    document = _single_value_mapping({"column": "value"})
    consumed: list[bool] = []

    class TrackedRows:
        def __iter__(self) -> Generator[Mapping[str, Any], None, None]:
            consumed.append(True)
            yield {"value": "must-not-be-read"}

    with pytest.raises(MappingError) as error:
        next(HowlerMapping().map_rows(TrackedRows(), document, fields_snapshot=snapshot))
    assert str(error.value) == "JSON value cannot be serialized safely"
    assert consumed == []


def test_timestamp_timezone_normalization_and_explicit_utc_assumption() -> None:
    aware = _single_row({"column": "value", "transforms": [{"op": "timestamp"}]}, "2026-01-01T01:02:03.123456+01:00")
    assert aware == "2026-01-01T00:02:03.123456Z"
    utc = _single_row(
        {"column": "value", "transforms": [{"op": "timestamp", "assume_timezone": "UTC"}]},
        "2026-01-01T01:02:03",
    )
    assert utc == "2026-01-01T01:02:03.000000Z"
    date_only = _single_row(
        {"column": "value", "transforms": [{"op": "timestamp", "assume_timezone": "UTC"}]},
        "2026-01-01",
    )
    assert date_only == "2026-01-01T00:00:00.000000Z"
    with pytest.raises(MappingError, match="no timezone"):
        _single_row({"column": "value", "transforms": [{"op": "timestamp"}]}, "2026-01-01T00:00:00")
    with pytest.raises(MappingError, match="invalid ISO-8601"):
        _single_row({"column": "value", "transforms": [{"op": "timestamp"}]}, "not-a-date")


def test_yaml_parser_rejects_unsafe_ambiguous_and_duplicate_documents() -> None:
    bad_documents = [
        "version: 1\nversion: 1\n",
        "value: &anchor [1]\n",
        "value: *alias\n",
        "value: !!python/object/apply:os.system ['echo unsafe']\n",
        "value: .nan\n",
        "value: .inf\n",
        "1: non-string-key\n",
        "<<: {x: 1}\n",
        "value: {nested: 1, nested: 2}\n",
        "first: document\n---\nsecond: document\n",
    ]
    for text in bad_documents:
        with pytest.raises(MappingError):
            RowMapping.from_yaml(text)


@pytest.mark.parametrize("tag", ["int", "bool"])
def test_invalid_explicit_native_scalars_have_generic_sanitized_errors(tag: str) -> None:
    with pytest.raises(MappingError) as error:
        RowMapping.from_yaml(f"value: !!{tag} private_marker")
    assert str(error.value) == "invalid YAML mapping document"
    assert "private_marker" not in str(error.value)


def test_intentional_yaml_and_mapping_validation_errors_keep_details() -> None:
    with pytest.raises(MappingError, match="duplicate YAML object key"):
        RowMapping.from_yaml("value: first\nvalue: second\n")

    invalid_mapping = _single_value_mapping({"value": "constant"})
    invalid_mapping["version"] = 2
    with pytest.raises(MappingError, match="only mapping version 1 is supported"):
        RowMapping(invalid_mapping)


def test_yaml_keeps_legacy_boolean_words_and_dates_as_strings() -> None:
    text = """version: 1
source: {table: synthetic.values, columns: [value]}
target:
  index: hit
  mcp_url: https://example.invalid/mcp
  fields_sha256: "0000000000000000000000000000000000000000000000000000000000000000"
policy: {missing: error, on_null: error}
mappings:
  result.yes: {value: yes}
  result.no: {value: no}
  result.on: {value: on}
  result.off: {value: off}
  result.date: {value: 2026-01-01}
  result.true: {value: true}
  result.false: {value: false}
"""
    result = RowMapping.from_yaml(text).map_row({})
    assert result == {
        "result": {
            "yes": "yes",
            "no": "no",
            "on": "on",
            "off": "off",
            "date": "2026-01-01",
            "true": True,
            "false": False,
        }
    }


def test_every_row_gets_fresh_nested_output_and_no_server_generated_id() -> None:
    source = _row()
    source_before = copy.deepcopy(source)
    mapper = RowMapping(_base_mapping())
    (first, first_error), (second, second_error) = list(mapper.map_rows([source, source]))

    assert first_error is None
    assert second_error is None
    assert first is not None
    assert second is not None
    assert first == second
    assert "id" not in first["howler"]
    assert first is not second
    assert first["user"] is not second["user"]
    assert first["user"]["roles"] is not second["user"]["roles"]
    assert first["custom"]["object"] is not second["custom"]["object"]
    assert first["custom"]["constant"] is not second["custom"]["constant"]
    assert first["custom"]["constant"]["members"] is not second["custom"]["constant"]["members"]

    first["user"]["roles"].append("mutated")
    first["custom"]["object"]["tags"].append("mutated")
    first["custom"]["constant"]["members"].append("mutated")
    assert "mutated" not in second["user"]["roles"]
    assert "mutated" not in second["custom"]["object"]["tags"]
    assert "mutated" not in second["custom"]["constant"]["members"]
    assert source == source_before


def test_server_owned_ids_are_rejected_in_parent_values_and_dynamic_rows() -> None:
    document = _single_value_mapping({"value": {"id": None}}, target="howler")
    with pytest.raises(MappingError, match="howler.id is server-generated"):
        RowMapping(document)

    document = _single_value_mapping({"column": "value"}, target="howler")
    document["source"]["columns"] = ["value"]
    mapper = RowMapping(document)
    with pytest.raises(MappingError, match="row 1, target howler: howler.id is server-generated"):
        mapper.map_row({"value": {"id": {"child": "not allowed"}}})


def test_empty_mapping_and_rows_with_only_omitted_targets_are_rejected() -> None:
    document = _single_value_mapping({"value": "constant"})
    document["mappings"].clear()
    with pytest.raises(MappingError, match="at least one target"):
        RowMapping(document)

    document = _single_value_mapping({"column": "value", "on_null": "omit"}, on_null="omit")
    hit, error = next(RowMapping(document).map_rows([{"value": None}]))
    assert hit is None
    _assert_detached_error(error)
    assert "row 1, target <row>: all fields were omitted" in str(error)


def test_snapshot_pins_endpoint_fingerprint_fields_types_and_list_shape() -> None:
    document = _base_mapping()
    snapshot = _snapshot(
        {
            "howler.analytic": {"type": "keyword", "list": False},
            "user.id": {"type": "keyword", "list": False},
            "user.name": {"type": "keyword", "list": False},
            "user.roles": {"type": "keyword", "list": True},
            "event.created": {"type": "date", "list": False},
            "custom.object": {"type": "object", "list": False},
            "custom.constant": {"type": "object", "list": False},
        }
    )
    document["target"]["fields_sha256"] = snapshot["fields_sha256"]
    assert RowMapping(document, fields_snapshot=snapshot).map_row(_row())["user"]["id"] == "synthetic-1"

    wrong_url = copy.deepcopy(snapshot)
    wrong_url["mcp_url"] = "https://other.example.invalid/mcp"
    wrong_url["fields_sha256"] = _fingerprint(wrong_url["fields"])
    with pytest.raises(MappingError, match="endpoints or fingerprints differ"):
        RowMapping(document, fields_snapshot=wrong_url)

    wrong_hash = copy.deepcopy(snapshot)
    wrong_hash["fields_sha256"] = "0" * 64
    with pytest.raises(MappingError, match="fingerprint"):
        RowMapping(document, fields_snapshot=wrong_hash)

    unknown = copy.deepcopy(document)
    unknown["mappings"]["unknown.field"] = {"value": "x"}
    with pytest.raises(MappingError, match="unknown Howler field"):
        RowMapping(unknown, fields_snapshot=snapshot)

    non_list = copy.deepcopy(snapshot)
    non_list["fields"]["user.roles"]["list"] = False
    non_list["fields_sha256"] = _fingerprint(non_list["fields"])
    document["target"]["fields_sha256"] = non_list["fields_sha256"]
    with pytest.raises(MappingError, match="list concatenation"):
        RowMapping(document, fields_snapshot=non_list)


def test_snapshot_row_type_ranges_deprecation_and_list_checks() -> None:
    fields = {
        "event.count": {"type": "integer", "list": False},
        "event.counts": {"type": "long", "list": True},
        "event.flag": {"type": "boolean", "list": False},
        "event.created": {"type": "date", "list": False},
    }
    snapshot = _snapshot(fields)

    def mapper(target: str, spec: dict[str, Any]) -> RowMapping:
        document = _single_value_mapping(spec, target=target, value_key="v")
        document["target"]["fields_sha256"] = snapshot["fields_sha256"]
        return RowMapping(document, fields_snapshot=snapshot)

    assert mapper("event.count", {"column": "v"}).map_row({"v": 2}) == {"event": {"count": 2}}
    for value in (True, 2**31, 1.5):
        with pytest.raises(MappingError, match="target requires integer"):
            mapper("event.count", {"column": "v"}).map_row({"v": value})
    with pytest.raises(MappingError, match="target requires a list"):
        mapper("event.counts", {"column": "v"}).map_row({"v": 1})
    with pytest.raises(MappingError, match="target is scalar"):
        mapper("event.flag", {"column": "v"}).map_row({"v": [True]})
    with pytest.raises(MappingError, match="no timezone"):
        mapper("event.created", {"column": "v"}).map_row({"v": "2026-01-01T00:00:00"})

    deprecated_fields = {"event.count": {"type": "integer", "list": False, "deprecated": True}}
    deprecated_snapshot = _snapshot(deprecated_fields)
    deprecated_mapping = _single_value_mapping({"column": "v"}, target="event.count", value_key="v")
    deprecated_mapping["target"]["fields_sha256"] = deprecated_snapshot["fields_sha256"]
    with pytest.raises(MappingError, match="deprecated Howler field"):
        RowMapping(deprecated_mapping, fields_snapshot=deprecated_snapshot)


def test_snapshot_ip_regex_and_enum_metadata_validation() -> None:
    fields = {
        "source.ip": {"type": "ip", "list": False},
        "user.role": {"type": "keyword", "list": False, "values": ["reader", "admin"]},
        "user.email": {"type": "keyword", "list": False, "regex": r"[\w.+-]+@example\.invalid"},
    }
    snapshot = _snapshot(fields)

    def mapper(target: str) -> RowMapping:
        document = _single_value_mapping({"column": "v"}, target=target, value_key="v")
        document["target"]["fields_sha256"] = snapshot["fields_sha256"]
        return RowMapping(document, fields_snapshot=snapshot)

    assert mapper("source.ip").map_row({"v": "2001:db8::1"}) == {"source": {"ip": "2001:db8::1"}}
    with pytest.raises(MappingError, match="target requires ip"):
        mapper("source.ip").map_row({"v": "not-an-ip"})
    assert mapper("user.role").map_row({"v": "reader"}) == {"user": {"role": "reader"}}
    with pytest.raises(MappingError, match="target enum"):
        mapper("user.role").map_row({"v": "owner"})
    assert mapper("user.email").map_row({"v": "synthetic@example.invalid"}) == {
        "user": {"email": "synthetic@example.invalid"}
    }
    with pytest.raises(MappingError, match="target regex"):
        mapper("user.email").map_row({"v": "not-an-email"})


def test_snapshot_fingerprint_uses_canonical_unicode_json() -> None:
    fields = {
        "custom.label": {
            "type": "keyword",
            "list": False,
            "description": "données synthétiques",
        }
    }
    snapshot = _snapshot(fields)
    document = _single_value_mapping({"value": "résumé"}, target="custom.label")
    document["target"]["fields_sha256"] = snapshot["fields_sha256"]
    assert RowMapping(document, fields_snapshot=snapshot).map_row({}) == {"custom": {"label": "résumé"}}


def test_without_snapshot_checks_structure_and_rows_but_not_backend_field_catalog() -> None:
    document = _single_value_mapping({"value": "synthetic"}, target="unknown.field")
    assert RowMapping(document).map_row({}) == {"unknown": {"field": "synthetic"}}
    snapshot = _snapshot({"known.field": {"type": "keyword", "list": False}})
    document["target"]["fields_sha256"] = snapshot["fields_sha256"]
    with pytest.raises(MappingError, match="unknown Howler field"):
        RowMapping(document, fields_snapshot=snapshot)


def test_non_json_and_non_finite_mapped_values_fail_without_echoing_values() -> None:
    document = _single_value_mapping({"column": "value"})
    mapper = RowMapping(document)
    for value in (
        float("nan"),
        float("inf"),
        ("not", "JSON"),
        {"secret": "not-json-source-value", "nested": float("nan")},
    ):
        with pytest.raises(MappingError) as error:
            mapper.map_row({"value": value})
        assert "not-json-source-value" not in str(error.value)

    document["mappings"]["result.value"] = {"value": {"secret": "not-json-source-value", "nested": (1, 2)}}
    with pytest.raises(MappingError) as error:
        RowMapping(document)
    assert "not-json-source-value" not in str(error.value)


def test_sanitized_directory_example_exercises_mapping_expressions_with_optional_snapshot() -> None:
    example_path = Path(__file__).parents[2] / "examples" / "row_mapping" / "example_mapping.yaml"
    snapshot = _snapshot(EXAMPLE_FIELDS)
    mapper = RowMapping.from_file(example_path, fields_snapshot=snapshot)
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
    assert hit is not None
    assert hit["howler"]["analytic"] == "Directory User Inventory Snapshot"
    assert hit["classification"] == "UNCLASSIFIED"
    assert hit["user"]["id"] == "synthetic-principal-001"
    assert hit["user"]["name"] == "user@example.invalid"
    assert hit["user"]["full_name"] == "Synthetic Example User"
    assert "email" not in hit["user"]
    assert hit["user"]["roles"] == ["Synthetic Reader", "Synthetic Analyst", "Synthetic Operator"]
    assert hit["organization"]["name"] == "Example Organization"
    assert "id" not in hit["howler"]
    assert RowMapping.from_file(example_path).map_row(synthetic_row) == hit
