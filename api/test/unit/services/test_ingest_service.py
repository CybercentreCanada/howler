import json
from types import SimpleNamespace
from typing import Annotated

import pytest
from pydantic import Field

from howler.common.exceptions import HowlerValueError
from howler.models import (
    HowlerEmbeddedModel,
    HowlerModelValidationError,
    Integer,
    Json,
    Keyword,
    mapping,
    metadata,
    model_extensions,
)
from howler.models.event import Event
from howler.models.hit import Hit
from howler.services import event_service, hit_service, ingest_service


class Entry(HowlerEmbeddedModel):
    value: Keyword | None = None
    count: Integer | None = None
    payload: Json | None = None
    legacy: Annotated[Keyword | None, metadata(default=None, deprecated=True)]


@pytest.fixture(params=["event", "hit"])
def convert(request, monkeypatch):
    index = request.param
    target, service = (Event, event_service) if index == "event" else (Hit, hit_service)
    with model_extensions.isolated():
        for name, field in {
            "plugin": Entry,
            "grouped": mapping(Entry, default={}, index=False),
            "grouped_lists": mapping(list[Entry], default={}, index=False),
            "scalar_map": mapping(Keyword, default={}),
            "payload": Annotated[Json | None, metadata(default=None)],
            "json_list": Annotated[list[Json], Field(default=[])],
            "json_map": mapping(Json, default={}),
            "json_map_list": mapping(list[Json], default={}),
        }.items():
            model_extensions.declare(target, name, field, plugin="example")
        collection = SimpleNamespace(model_class=model_extensions.finalize(target))
        monkeypatch.setattr(service, "datastore", lambda: SimpleNamespace(**{index: collection}))
        base = {"howler.analytic": "Example"} if index == "hit" else {}
        yield lambda data, **kwargs: getattr(service, f"convert_{index}")({**base, **data}, unique=False, **kwargs)


@pytest.mark.parametrize("ignore_extra_values", [False, True])
@pytest.mark.parametrize("payload", [{"nested": {}}, {"nested": {"items": [1, {}, {"deep": "value"}]}}])
def test_ingest_extensions_and_opaque_json(convert, ignore_extra_values, payload):
    record, warnings = convert(
        {
            "plugin": {"payload": payload},
            "plugin.legacy": "keep",
            "grouped": {"team": {"value": "keep"}},
            "grouped.other.value": "also keep",
            "payload": payload,
            "json_list": [payload],
            "json_map": {"team": payload},
            "json_map_list": {"team": [payload]},
        },
        ignore_extra_values=ignore_extra_values,
    )
    result = record.as_primitives()
    assert result["plugin"]["legacy"] == "keep"
    assert result["grouped"] == {"team": {"value": "keep"}, "other": {"value": "also keep"}}
    for value in (
        result["plugin"]["payload"],
        result["payload"],
        result["json_list"][0],
        result["json_map"]["team"],
        result["json_map_list"]["team"][0],
    ):
        assert json.loads(value) == payload
    assert warnings == ["plugin.legacy is deprecated."]
    assert convert({"plugin": {}}, ignore_extra_values=ignore_extra_values)[0].as_primitives()["plugin"] == {}


@pytest.mark.parametrize("permissive", [False, True])
def test_ingest_unknown_mapping_children(convert, permissive):
    data = {
        "plugin": {"value": {"invalid": "value"}, "payload": {"nested": {}}},
        "grouped": {"team": {"value": "keep", "unknown": "drop"}},
        "grouped.other.value.deeper": "invalid",
        "grouped_lists": {"team": [{"value": "keep", "unknown": "drop"}]},
        "scalar_map": {"team": {"invalid": "value"}},
    }
    paths = (
        "plugin.value.invalid",
        "grouped.team.unknown",
        "grouped.other.value.deeper",
        "grouped_lists.team.unknown",
        "scalar_map.team.invalid",
    )
    if not permissive:
        with pytest.raises(HowlerValueError, match="invalid parameters") as error:
            convert(data)
        assert all(path in str(error.value) for path in paths)
        assert "payload.nested" not in str(error.value)
        return
    record, warnings = convert(data, ignore_extra_values=True)
    result = record.as_primitives()
    assert result["grouped"]["team"] == {"value": "keep"}
    assert result["grouped_lists"] == {"team": [{"value": "keep"}]}
    assert json.loads(result["plugin"]["payload"]) == {"nested": {}}
    assert set(warnings) == {f"{path} is not currently used by howler." for path in paths}
    with pytest.raises(HowlerValueError, match="grouped.team.count"):
        convert({"grouped": {"team": {"count": "invalid", "unknown": "drop"}}}, ignore_extra_values=True)


@pytest.mark.parametrize("ignore_extra_values", [False, True])
@pytest.mark.parametrize("field,value", [("json_list", {"nested": {}}), ("json_map", {"bad key": {"nested": {}}})])
def test_ingest_json_containers_are_validated(convert, ignore_extra_values, field, value):
    with pytest.raises(HowlerModelValidationError, match=field):
        convert({field: value}, ignore_extra_values=ignore_extra_values)


class ExtendedHit(Hit):
    stored_plugin: Entry | None = None
    new_plugin: Entry | None = None
    absent_list: list[Entry] | None = None
    populated: Entry
    groups: mapping(list[Keyword])
    scalar_map: mapping(Keyword)
    compounds: mapping(Entry, index=False)
    count: Integer
    raw: Json


@pytest.mark.parametrize("flatten", [True, False], ids=["v1", "v2"])
@pytest.mark.parametrize("replace", [False, True])
def test_overwrite_empty_values(flatten, replace):
    stored = ExtendedHit.model_validate(
        {
            "howler.analytic": "Old",
            "howler.hash": "ab",
            "stored_plugin": {},
            "populated.value": "keep",
            "groups": {"team": ["old"]},
            "scalar_map": {"team": "old"},
            "compounds": {"team": {"value": "keep"}},
            "count": 2,
            "raw": {"old": True},
        }
    ).as_primitives()

    def update(data):
        return ingest_service.prepare_overwrite(
            stored, data, ExtendedHit, user=None, replace=replace, flatten_patch_mappings=flatten
        )

    result = update(
        {
            "howler.analytic": "Updated",
            "new_plugin": {},
            "populated": {},
            "absent_list": {},
            "groups": {},
            "compounds": {"team": {}, "new": {}},
            "raw": {},
        }
    ).as_primitives()
    assert result["howler"]["analytic"] == "Updated"
    assert result["stored_plugin"] == result["new_plugin"] == {}
    assert "absent_list" not in result
    assert result["populated"] == {"value": "keep"}
    assert result["groups"] == {"team": ["old"]}
    assert result["compounds"] == ({"team": {"value": "keep"}} if flatten else {"team": {"value": "keep"}, "new": {}})
    assert result["raw"] == ('{"old": true}' if flatten else "{}")
    if flatten:
        result = update({"groups": {"team": {}}, "scalar_map": {"team": {}}, "count": {}})
        assert result.groups == {"team": ["old"]} and result.scalar_map == {"team": "old"} and result.count == 2
    else:
        with pytest.raises(HowlerValueError, match="groups.team"):
            update({"groups": {"team": {}}})
        with pytest.raises(HowlerValueError, match="count"):
            update({"count": {}})
        assert update({"scalar_map": {"team": {}}}).scalar_map == {"team": "{}"}
    for data in ({"unknown": {}}, {"howler": {"unknown": {}}}):
        if flatten:
            assert update(data).howler.analytic == "Old"
        else:
            with pytest.raises(HowlerValueError, match="unknown"):
                update(data)
