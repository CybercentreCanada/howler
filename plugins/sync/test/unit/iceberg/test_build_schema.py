from pathlib import Path
from types import SimpleNamespace
from typing import Annotated

import pytest
from howler import models as m
from howler.common.exceptions import HowlerValueError
from howler.models import clue
from howler.models.hit import Hit
from pyspark.sql import types as s

from sync.iceberg.build import build_schema
from sync.services import sync_service


@m.register_model(embedded=True)
class Nested(m.HowlerEmbeddedModel):
    value: m.Keyword
    mapping: m.mapping(m.Text)


@m.register_model(embedded=True)
class Probe(m.HowlerEmbeddedModel):
    keyword: m.Keyword
    boolean: m.Boolean
    integer: m.Integer
    floating: m.Float
    text: m.Text
    date: m.Date
    compound: Nested
    described: Annotated[m.Keyword, m.metadata(description="parent")]
    items: list[Annotated[m.Integer, m.metadata(description="child")]]
    mapped: m.mapping(m.Text, description="parent")
    optional_items: list[Annotated[m.Integer | None, m.metadata(description="optional", optional=True)]]
    optional: m.Integer | None = None
    default_date: m.Date = "NOW"
    optional_default: Annotated[m.Text | None, m.metadata(optional=True)] = "value"
    optional_list: list[m.Text] | None = None
    nullable_items: list[Annotated[m.Text | None, m.metadata(optional=True, default="value")]] = []
    default_items: list[Annotated[m.Integer, m.metadata(default=0)]]
    optional_map: m.mapping(m.Text, optional=True)
    nullable_values: m.mapping(m.Text | None, default={})
    generated_values: m.mapping(m.UUID)
    lists: m.mapping(list[Annotated[m.Date, m.metadata(default="NOW")]])
    optional_compound: Nested | None = None
    excluded: Annotated[m.Keyword, m.metadata(sync=False)]


@m.register_model(embedded=True)
class AnyField(m.HowlerEmbeddedModel):
    raw: object


def test_schema_types_and_nullability():
    for model in (Probe, Probe.model_construct()):
        fields = build_schema(model)
        assert fields.fieldNames() == [name for name in Probe.model_fields if name != "excluded"]
        for name, kind in {
            "keyword": s.StringType,
            "boolean": s.BooleanType,
            "integer": s.IntegerType,
            "floating": s.DoubleType,
            "text": s.StringType,
            "date": s.TimestampType,
        }.items():
            assert fields[name].dataType == kind()
        assert fields["compound"].dataType["mapping"].dataType == s.MapType(s.StringType(), s.StringType())
        assert fields["items"].dataType == s.ArrayType(s.IntegerType(), containsNull=True)
        assert fields["mapped"].dataType == s.MapType(s.StringType(), s.StringType())
        for name, description in {
            "described": "parent",
            "items": "child",
            "mapped": "parent",
            "optional_items": "optional",
        }.items():
            assert fields[name].metadata == {"description": description}
        for name in ("keyword", "optional", "optional_default", "optional_list", "optional_map", "optional_compound"):
            assert fields[name].nullable
        for name in ("default_date", "nullable_items", "nullable_values"):
            assert not fields[name].nullable
        assert fields["nullable_items"].dataType.containsNull
        assert not fields["default_items"].dataType.containsNull
        assert fields["nullable_values"].dataType.valueContainsNull
        assert not fields["generated_values"].dataType.valueContainsNull
        assert fields["lists"].dataType == s.MapType(s.StringType(), s.ArrayType(s.TimestampType(), containsNull=False))
        assert isinstance(fields["optional_compound"].dataType, s.StructType)
    with pytest.raises(HowlerValueError, match="``Any`` type is not supported"):
        build_schema(AnyField)
    assert build_schema(AnyField, allow_any_as_string=True)["raw"].dataType == s.StringType()


def test_public_hit_schema_matches_legacy_fields():
    fields = build_schema(Hit)
    assert {name: fields[name].jsonValue() for name in ("tags", "labels", "timestamp")} | {
        "related.ip": fields["related"].dataType["ip"].jsonValue()
    } == {
        "tags": {
            "name": "tags",
            "type": {"type": "array", "elementType": "string", "containsNull": True},
            "nullable": False,
            "metadata": {"description": "List of keywords used to tag each event."},
        },
        "labels": {
            "name": "labels",
            "type": {"type": "map", "keyType": "string", "valueType": "string", "valueContainsNull": True},
            "nullable": False,
            "metadata": {"description": "Custom key/value pairs."},
        },
        "timestamp": {
            "name": "timestamp",
            "type": "timestamp",
            "nullable": False,
            "metadata": {"description": "Date/time when the event originated."},
        },
        "related.ip": {
            "name": "ip",
            "type": {"type": "array", "elementType": "binary", "containsNull": True},
            "nullable": False,
            "metadata": {"description": "All of the IPs seen on your event."},
        },
    }
    assert fields["howler"].dataType["labels"].nullable


def test_hit_plugin_schema_and_null_batches(monkeypatch):
    plugins = Path(__file__).resolve().parents[4]
    monkeypatch.syspath_prepend(plugins / "evidence")
    monkeypatch.syspath_prepend(plugins / "sentinel")
    from evidence.models import hit as evidence
    from sentinel.models import hit as sentinel

    registry = m.ModelExtensionRegistry()
    for module in (clue, evidence, sentinel):
        monkeypatch.setattr(module, "model_extensions", registry)
        module.declare_hit_extension()
    registry.declare(
        Hit, "batch", Annotated[list[m.Keyword] | None, m.metadata(optional=True, default=[])], plugin="test"
    )
    registry.declare(Hit, "batches", Annotated[list[list[m.Keyword] | None], m.metadata(default=[])], plugin="test")
    model = registry.finalize(Hit)
    fields = build_schema(model)
    evidence_field = fields["evidence"]
    assert not evidence_field.nullable and evidence_field.dataType.containsNull
    assert fields["clue"].nullable and fields["clue"].dataType["types"].dataType.containsNull
    assert fields["sentinel"].nullable and fields["sentinel"].dataType["alert_id"].nullable
    row = model.model_validate(
        {"howler": {"analytic": "Test", "hash": "ab"}, "batch": None, "batches": [None, ["abc"]]}
    ).as_primitives(strip_null=False)
    assert row["batch"] is None and row["batches"] == [None, ["abc"]]
    s._make_type_verifier(s.StructType([fields["batches"], fields["batch"]]))(row)
    assert not fields["batches"].nullable
    for selected in (model, None):
        monkeypatch.setattr(
            sync_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=selected))
        )
        assert sync_service.get_model_struct_schema(Hit) == build_schema(selected or Hit)
