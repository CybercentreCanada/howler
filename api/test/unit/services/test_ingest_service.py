import json
from types import SimpleNamespace

import pytest

from howler.common.exceptions import HowlerValueError
from howler.models import (
    HowlerEmbeddedModel,
    HowlerModelValidationError,
    compound,
    integer,
    json_field,
    keyword,
    list_field,
    mapping,
    model_extensions,
    optional,
)
from howler.models.event import Event
from howler.models.hit import Hit
from howler.services import event_service, hit_service, ingest_service


class Entry(HowlerEmbeddedModel):
    value: optional(keyword())
    count: optional(integer())
    payload: optional(json_field())


@pytest.fixture(params=["event", "hit"])
def convert(request, monkeypatch):
    index = request.param
    target, service = (Event, event_service) if index == "event" else (Hit, hit_service)
    with model_extensions.isolated():
        model_extensions.declare(target, "plugin", compound(Entry), plugin="example")
        model_extensions.declare(target, "grouped", mapping(compound(Entry), default={}, index=False), plugin="example")
        model_extensions.declare(
            target, "grouped_lists", mapping(list_field(compound(Entry)), default={}, index=False), plugin="example"
        )
        model_extensions.declare(target, "scalar_map", mapping(keyword(), default={}), plugin="example")
        model_extensions.declare(target, "payload", optional(json_field()), plugin="example")
        model_extensions.declare(target, "json_list", list_field(json_field(), default=[]), plugin="example")
        model_extensions.declare(target, "json_map", mapping(json_field(), default={}), plugin="example")
        model_extensions.declare(
            target, "json_map_list", mapping(list_field(json_field()), default={}), plugin="example"
        )
        collection = SimpleNamespace(model_class=model_extensions.finalize(target))
        monkeypatch.setattr(service, "datastore", lambda: SimpleNamespace(**{index: collection}))
        convert_record = getattr(service, f"convert_{index}")
        base = {"howler.analytic": "Example"} if index == "hit" else {}
        yield lambda data, **kwargs: convert_record({**base, **data}, unique=False, **kwargs)


@pytest.mark.parametrize("ignore_extra_values", [False, True])
def test_ingest_preserves_explicit_empty_required_compound(convert, ignore_extra_values):
    record, warnings = convert({"plugin": {}}, ignore_extra_values=ignore_extra_values)
    assert record.as_primitives()["plugin"] == {}
    assert warnings == []


@pytest.mark.parametrize("ignore_extra_values", [False, True])
def test_ingest_accepts_declared_children_of_typed_mapping(convert, ignore_extra_values):
    record, warnings = convert(
        {"plugin.value": "present", "grouped": {"team": {"value": "keep"}}, "grouped.other.value": "also keep"},
        ignore_extra_values=ignore_extra_values,
    )
    assert record.as_primitives()["grouped"] == {"team": {"value": "keep"}, "other": {"value": "also keep"}}
    assert warnings == []


def test_strict_ingest_rejects_unknown_and_scalar_mapping_descendants(convert):
    with pytest.raises(HowlerValueError, match="invalid parameters") as error:
        convert(
            {
                "plugin.value": "present",
                "grouped": {"team": {"unknown": "invalid"}},
                "grouped.other.value.deeper": "invalid",
                "scalar_map.team.deeper": "invalid",
            }
        )
    for path in ("grouped.team.unknown", "grouped.other.value.deeper", "scalar_map.team.deeper"):
        assert path in str(error.value)


def test_permissive_ingest_prunes_unknown_typed_mapping_children(convert):
    record, warnings = convert(
        {"plugin": {}, "grouped": {"team": {"value": "keep", "unknown": "drop"}}}, ignore_extra_values=True
    )
    assert record.as_primitives()["grouped"] == {"team": {"value": "keep"}}
    assert "grouped.team.unknown is not currently used by howler." in warnings


def test_permissive_ingest_still_rejects_invalid_typed_mapping_values(convert):
    with pytest.raises(HowlerValueError, match="grouped.team.count"):
        convert(
            {"plugin": {}, "grouped": {"team": {"count": "invalid", "unknown": "drop"}}},
            ignore_extra_values=True,
        )


def test_permissive_ingest_prunes_mapping_of_compound_lists(convert):
    record, warnings = convert(
        {"plugin": {}, "grouped_lists": {"team": [{"value": "keep", "unknown": "drop"}]}},
        ignore_extra_values=True,
    )
    assert record.as_primitives()["grouped_lists"] == {"team": [{"value": "keep"}]}
    assert "grouped_lists.team.unknown is not currently used by howler." in warnings


@pytest.mark.parametrize("ignore_extra_values", [False, True], ids=["strict", "permissive"])
@pytest.mark.parametrize("payload", [{"nested": {}}, {"nested": {"items": [1, {}, {"deep": "value"}]}}])
def test_ingest_opaque_json_fields(convert, ignore_extra_values, payload):
    record, warnings = convert(
        {
            "plugin": {"payload": payload},
            "payload": payload,
            "json_list": [payload],
            "json_map": {"team": payload},
            "json_map_list": {"team": [payload]},
        },
        ignore_extra_values=ignore_extra_values,
    )
    result = record.as_primitives()
    assert json.loads(result["plugin"]["payload"]) == payload
    assert json.loads(result["payload"]) == payload
    assert json.loads(result["json_list"][0]) == payload
    assert json.loads(result["json_map"]["team"]) == payload
    assert json.loads(result["json_map_list"]["team"][0]) == payload
    assert warnings == []


@pytest.mark.parametrize("ignore_extra_values", [False, True], ids=["strict", "permissive"])
def test_ingest_opaque_json_does_not_hide_scalar_descendants(convert, ignore_extra_values):
    data = {
        "plugin": {"payload": {"nested": {}}, "value": {"invalid": "value"}},
        "payload": {"nested": {}},
        "scalar_map": {"team": {"invalid": "value"}},
    }
    if not ignore_extra_values:
        with pytest.raises(HowlerValueError, match="invalid parameters") as error:
            convert(data)
        assert "scalar_map.team.invalid" in str(error.value)
        assert "plugin.value.invalid" in str(error.value)
        assert "payload.nested" not in str(error.value)
    else:
        record, warnings = convert(data, ignore_extra_values=True)
        assert json.loads(record.as_primitives()["payload"]) == {"nested": {}}
        assert set(warnings) == {
            "scalar_map.team.invalid is not currently used by howler.",
            "plugin.value.invalid is not currently used by howler.",
        }


@pytest.mark.parametrize("ignore_extra_values", [False, True], ids=["strict", "permissive"])
@pytest.mark.parametrize("field", ["payload", "json_list", "json_map", "json_map_list"])
def test_ingest_opaque_json_still_validates_values(convert, ignore_extra_values, field):
    invalid = {"nested": {"not JSON serializable"}}
    values = {
        "payload": invalid,
        "json_list": [invalid],
        "json_map": {"team": invalid},
        "json_map_list": {"team": [invalid]},
    }
    with pytest.raises(HowlerModelValidationError, match=field) as error:
        convert({"plugin": {}, field: values[field]}, ignore_extra_values=ignore_extra_values)
    assert any(item["type"] == "value_error" for item in error.value.errors)


@pytest.mark.parametrize("ignore_extra_values", [False, True], ids=["strict", "permissive"])
@pytest.mark.parametrize("field,value", [("json_list", {"nested": {}}), ("json_map", {"bad key": {"nested": {}}})])
def test_ingest_opaque_json_still_validates_containers(convert, ignore_extra_values, field, value):
    with pytest.raises(HowlerModelValidationError, match=field):
        convert({"plugin": {}, field: value}, ignore_extra_values=ignore_extra_values)


@pytest.mark.parametrize("flatten_patch_mappings", [True, False], ids=["v1", "v2"])
@pytest.mark.parametrize("replace", [False, True])
def test_overwrite_retains_stored_and_supplied_empty_compounds(flatten_patch_mappings, replace):
    class ExtendedHit(Hit):
        stored_plugin: optional(compound(Entry))
        new_plugin: optional(compound(Entry))
        absent_list: optional(list_field(compound(Entry)))
        populated: compound(Entry)

    stored = ExtendedHit.validate_howler(
        {"howler.analytic": "Old", "howler.hash": "ab", "stored_plugin": {}, "populated.value": "keep"}
    )
    updated = ingest_service.prepare_overwrite(
        stored.as_primitives(),
        {"howler.analytic": "Updated", "new_plugin": {}, "populated": {}, "absent_list": {}},
        ExtendedHit,
        user=None,
        replace=replace,
        flatten_patch_mappings=flatten_patch_mappings,
    )
    result = updated.as_primitives()
    assert result["howler"]["analytic"] == "Updated"
    assert result["stored_plugin"] == result["new_plugin"] == {}
    assert "absent_list" not in result
    assert result["populated"] == {"value": "keep"}


@pytest.mark.parametrize("flatten_patch_mappings", [True, False], ids=["v1", "v2"])
@pytest.mark.parametrize("replace", [False, True])
def test_overwrite_empty_dynamic_mappings_follow_original_route_behavior(flatten_patch_mappings, replace):
    class ExtendedHit(Hit):
        groups: mapping(list_field(keyword()))
        scalar_map: mapping(keyword())
        compounds: mapping(compound(Entry), index=False)

    stored = ExtendedHit.validate_howler(
        {
            "howler.analytic": "Original",
            "howler.hash": "ab",
            "groups": {"team": ["old"]},
            "scalar_map": {"team": "old"},
            "compounds": {"team": {"value": "keep"}},
        }
    ).as_primitives()
    empty_map = ingest_service.prepare_overwrite(
        stored, {"groups": {}}, ExtendedHit, user=None, replace=replace, flatten_patch_mappings=flatten_patch_mappings
    )
    assert empty_map.groups == {"team": ["old"]}
    compound_entries = ingest_service.prepare_overwrite(
        stored,
        {"compounds": {"team": {}, "new": {}}},
        ExtendedHit,
        user=None,
        replace=replace,
        flatten_patch_mappings=flatten_patch_mappings,
    )
    assert compound_entries.as_primitives()["compounds"] == (
        {"team": {"value": "keep"}} if flatten_patch_mappings else {"team": {"value": "keep"}, "new": {}}
    )

    if flatten_patch_mappings:
        updated = ingest_service.prepare_overwrite(
            stored,
            {"groups": {"team": {}}, "scalar_map": {"team": {}}},
            ExtendedHit,
            user=None,
            replace=replace,
            flatten_patch_mappings=True,
        )
        assert updated.groups == {"team": ["old"]}
        assert updated.scalar_map == {"team": "old"}
    else:
        with pytest.raises(HowlerValueError, match="groups.team"):
            ingest_service.prepare_overwrite(stored, {"groups": {"team": {}}}, ExtendedHit, user=None, replace=replace)
        updated = ingest_service.prepare_overwrite(
            stored, {"scalar_map": {"team": {}}}, ExtendedHit, user=None, replace=replace
        )
        assert updated.scalar_map == {"team": "{}"}


@pytest.mark.parametrize("flatten_patch_mappings", [True, False], ids=["v1", "v2"])
@pytest.mark.parametrize("replace", [False, True])
@pytest.mark.parametrize("updates", [{"unknown": {}}, {"howler": {"unknown": {}}}])
def test_overwrite_empty_unknowns_follow_original_route_behavior(flatten_patch_mappings, replace, updates):
    stored = Hit.validate_howler({"howler.analytic": "Original", "howler.hash": "ab"}).as_primitives()
    if flatten_patch_mappings:
        updated = ingest_service.prepare_overwrite(
            stored, updates, Hit, user=None, replace=replace, flatten_patch_mappings=True
        )
        assert updated.howler.analytic == "Original"
    else:
        with pytest.raises(HowlerValueError, match="unknown"):
            ingest_service.prepare_overwrite(stored, updates, Hit, user=None, replace=replace)


@pytest.mark.parametrize("flatten_patch_mappings", [True, False], ids=["v1", "v2"])
@pytest.mark.parametrize("replace", [False, True])
def test_overwrite_other_empty_scalars_follow_original_route_behavior(flatten_patch_mappings, replace):
    class ExtendedHit(Hit):
        count: integer()
        raw: json_field()

    stored = ExtendedHit.validate_howler(
        {"howler.analytic": "Original", "howler.hash": "ab", "count": 2, "raw": {"old": True}}
    ).as_primitives()
    if flatten_patch_mappings:
        updated = ingest_service.prepare_overwrite(
            stored, {"count": {}, "raw": {}}, ExtendedHit, user=None, replace=replace, flatten_patch_mappings=True
        )
        assert updated.count == 2
        assert updated.raw == '{"old": true}'
    else:
        with pytest.raises(HowlerValueError, match="count"):
            ingest_service.prepare_overwrite(stored, {"count": {}}, ExtendedHit, user=None, replace=replace)
        updated = ingest_service.prepare_overwrite(stored, {"raw": {}}, ExtendedHit, user=None, replace=replace)
        assert updated.raw == "{}"
