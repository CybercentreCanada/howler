"""Tests for the Howler Pydantic/DSL model foundation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import pytest
from pydantic import Field, ValidationError

from howler.common.exceptions import HowlerTypeError, HowlerValueError
from howler.models import (
    IP,
    UUID,
    AnyField,
    Date,
    FlattenedListObject,
    FlattenedObject,
    HowlerEmbeddedModel,
    HowlerESModel,
    HowlerModelValidationError,
    Integer,
    Json,
    Keyword,
    Text,
    classification,
    construct_partial,
    flat_to_nested,
    mapping,
    metadata,
    model_registry,
    partial_primitives,
    register_model,
    validate_field_value,
)
from howler.models.registry import ModelRegistry

CLASSIFICATION_CONFIG = str(Path(__file__).parents[2] / "classification.yml")
TIMESTAMP = "2024-01-02T03:04:05.000000Z"


@register_model(description="Embedded child", index=True, store=True, embedded=True)
class FoundationChild(HowlerEmbeddedModel):
    """Embedded model used by foundation tests."""

    name: Keyword
    count: Integer = 1
    address: IP
    created: Date


@register_model(description="Foundation document", id_field="document_id", index=True, store=True)
class FoundationDocument(HowlerESModel):
    """Top-level document used by foundation tests."""

    document_id: UUID
    from_: Annotated[Keyword, metadata(alias="from")]
    child: FoundationChild
    children: list[FoundationChild] = []
    tags: list[Keyword] = []
    counters: mapping(Integer, default={}, index=True, store=True)
    unindexed: mapping(Keyword, default={}, index=False, store=False)
    flattened: FlattenedObject = {}
    flattened_lists: FlattenedListObject = {}
    maybe: Keyword | None = None
    maybe_ip: IP | None = None
    maybe_unindexed: Annotated[Keyword | None, metadata(index=False, store=False)] = None
    class_: Annotated[Keyword | None, metadata(alias="class")] = None
    classification: classification(default="UNRESTRICTED", yml_config=CLASSIFICATION_CONFIG)


class FoundationBaseDocument(HowlerESModel):
    """Base document used to verify inherited mapping fields."""

    inherited: Keyword


class FoundationDerivedDocument(FoundationBaseDocument):
    """Derived document used to verify inherited mapping fields."""

    own: Integer


@register_model(index=False, store=False)
class FoundationUnindexedDocument(HowlerESModel):
    """Document used to verify model-wide field defaults."""

    value: Keyword
    body: Text


@register_model(embedded=True)
class IndexedChild(HowlerEmbeddedModel):
    """Embedded fields used to verify inherited mapping defaults."""

    inherited: Keyword
    explicitly_indexed: Annotated[Keyword, metadata(index=True)]
    explicitly_unindexed: Annotated[Keyword, metadata(index=False)]


@register_model(index=True, store=True)
class IndexedParent(HowlerESModel):
    """Document used to check compound-level mapping overrides."""

    child: IndexedChild
    unindexed_child: Annotated[IndexedChild, metadata(index=False)]


def _document_data() -> dict:
    return {
        "document_id": "document-1",
        "from": "source",
        "child": {
            "name": "first",
            "count": "2",
            "address": "127.0.0.1",
            "created": TIMESTAMP,
        },
        "tags": ["one", 2],
        "counters": {"one": "1"},
        "unindexed": {"Upper Key": "value"},
        "flattened": {"a.b": {"value": 1}},
        "flattened_lists": {"a.b": [{"value": 1}, "two"]},
    }


def test_model_validation_aliases_and_defaults() -> None:
    """Models validate aliases, assignments, containers, and defaults."""
    model = FoundationDocument.model_validate(_document_data())

    assert model.from_ == "source"
    assert model.child.count == 2
    assert model.tags == ["one", "2"]
    assert model.counters == {"one": 1}
    assert model.maybe is None
    assert model.children == []

    model.child.count = "3"
    assert model.child.count == 3
    with pytest.raises(HowlerModelValidationError):
        model.child.count = "invalid"
    with pytest.raises(HowlerModelValidationError):
        FoundationDocument.model_validate({**_document_data(), "unknown": True})

    model["from"] = "updated"  # pyright: ignore[reportIndexIssue]
    model["child.count"] = "4"  # pyright: ignore[reportIndexIssue]
    assert model.from_ == "updated"
    assert model.child.count == 4
    assert model["from"] == "updated"  # pyright: ignore[reportIndexIssue]
    assert model["child.count"] == 4  # pyright: ignore[reportIndexIssue]
    assert model.get("missing.field", "fallback") == "fallback"
    assert "from" in model
    assert "missing" not in model


def test_flattened_compound_list_input() -> None:
    """Dotted lists of compound fields reconstruct into aligned objects."""
    data = _document_data()
    data.update(
        {
            "children.name": ["one", "two"],
            "children.count": [1, 2],
            "children.address": ["127.0.0.1", "2001:db8::1"],
            "children.created": [TIMESTAMP, TIMESTAMP],
        }
    )
    model = FoundationDocument.model_validate(data)

    assert [item.name for item in model.children] == ["one", "two"]
    assert [item.count for item in model.children] == [1, 2]

    data["children.count"] = [1]
    with pytest.raises(HowlerModelValidationError):
        FoundationDocument.model_validate(data)


def test_primitive_serialization_modes_and_access_fields() -> None:
    """Stored primitives preserve aliases, timestamps, IP modes, and access fields."""
    model = FoundationDocument.model_validate(_document_data())

    primitives = model.as_primitives(hidden_fields=True)
    assert "from_" not in primitives
    assert primitives["from"] == "source"
    assert primitives["child"]["created"] == TIMESTAMP
    assert primitives["flattened"] == {"a.b": '{"value": 1}'}
    assert primitives["flattened_lists"] == {"a.b": ['{"value": 1}', "two"]}
    assert primitives["classification"] == "UNRESTRICTED"
    assert primitives["__access_lvl__"] == 100
    assert primitives["__access_grp1__"] == ["__EMPTY__"]


def test_partial_construction_validates_selected_fields_without_defaults() -> None:
    """Projected models validate present leaves without requiring unrelated fields."""
    partial = construct_partial(
        FoundationDocument,
        {
            "child": {"count": "2"},
            "tags": [1, "two"],
            "id": "stored-id",
            "__access_lvl__": 100,
        },
        meta={"id": "stored-id", "index": "howler-foundation"},
    )

    assert partial.child.count == 2
    assert partial.tags == ["1", "two"]
    assert "document_id" not in partial.__dict__
    assert partial.maybe is None
    assert partial.meta.id == "stored-id"
    assert partial.as_primitives() == {"child": {"count": 2}, "tags": ["1", "two"]}


def test_partial_primitives_rejects_unknown_fields() -> None:
    """Partial updates remain strict about registry field names."""
    with pytest.raises(ValueError, match="Unknown field"):
        partial_primitives(FoundationDocument, {"unknown": True})

    with pytest.raises(HowlerModelValidationError):
        construct_partial(FoundationDocument, {"child": None})


def test_partial_construction_does_not_evaluate_omitted_defaults() -> None:
    class ProjectedDocument(HowlerESModel):
        value: str = Field(alias="stored_value")
        omitted: str
        generated: str = Field(default_factory=lambda: pytest.fail("Omitted default factory ran"))
        defaulted: str = "unused"
        nullable: str | None = None

    partial = construct_partial(ProjectedDocument, {"stored_value": "selected"})

    assert partial.as_primitives(strip_null=False) == {"stored_value": "selected", "nullable": None}
    assert partial.model_fields_set == {"value", "meta"}


def test_partial_primitives_preserve_storage_serialization_and_access_fields() -> None:
    """Partial merges serialize dates, IPs, embedded values, and classification helpers."""
    primitives = partial_primitives(
        FoundationDocument,
        {
            "child": {
                "address": "127.0.0.1",
                "created": TIMESTAMP,
            },
            "classification": "UNRESTRICTED",
        },
    )

    assert primitives["child"] == {
        "address": "127.0.0.1",
        "created": TIMESTAMP,
    }
    assert primitives["classification"] == "UNRESTRICTED"
    assert primitives["__access_lvl__"] == 100
    assert primitives["__access_grp1__"] == ["__EMPTY__"]


def test_read_normalization_drops_unknown_fields_but_preserves_mapping_keys() -> None:
    """Removed plugin fields are ignored on reads without pruning dynamic mappings."""
    data = _document_data()
    data["removed_plugin_field"] = "unrecognized"
    data["child"]["removed_child_field"] = "unrecognized"
    data["counters"]["dynamic_key"] = "2"

    model = FoundationDocument.model_validate(data, extra="ignore")
    primitives = model.as_primitives()

    assert "removed_plugin_field" not in primitives
    assert "removed_child_field" not in primitives["child"]
    assert model.counters["dynamic_key"] == 2


def test_extra_ignore_traverses_typed_containers_without_pruning_loose_data() -> None:
    class Leaf(HowlerEmbeddedModel):
        value: Keyword | None = None
        count: Integer | None = None

    class Containers(HowlerEmbeddedModel):
        grouped: mapping(Leaf, index=False)
        listed: list[Leaf]
        nested: mapping(list[mapping(Leaf, index=False)], index=False)
        maybe_grouped: mapping(Leaf | None, index=False, optional=True)
        json_value: Json
        loose: dict[str, object]
        flat: FlattenedObject

    data = {
        "grouped": {"team": {"value": "keep", "unknown": "drop"}},
        "listed": [{"value": "keep", "unknown": "drop"}],
        "nested": {"team": [{"key": {"value": "keep", "unknown": "drop"}}]},
        "maybe_grouped": {"team": {"value": "keep", "unknown": "drop"}, "empty": None},
        "json_value": {"arbitrary": {"unknown": [1, {"other": True}]}},
        "loose": {"arbitrary": {"unknown": [1, {"other": True}]}},
        "flat": {"arbitrary": {"unknown": "keep"}},
    }
    model = Containers.model_validate(data, extra="ignore")
    clean = model.as_primitives()

    assert clean["grouped"] == {"team": {"value": "keep"}}
    assert clean["listed"] == [{"value": "keep"}]
    assert clean["nested"] == {"team": [{"key": {"value": "keep"}}]}
    assert clean["maybe_grouped"] == {"team": {"value": "keep"}}
    assert model.maybe_grouped == {"team": Leaf(value="keep", count=None), "empty": None}
    assert model.loose == data["loose"]
    assert data["grouped"]["team"]["unknown"] == "drop"


def test_extra_ignore_leaves_invalid_container_values_for_validation() -> None:
    class Leaf(HowlerEmbeddedModel):
        count: Integer

    class Containers(HowlerEmbeddedModel):
        grouped: mapping(Leaf, index=False)
        listed: list[Leaf]

    for data in (
        {"grouped": {"team": {"count": "invalid", "unknown": 1}}, "listed": []},
        {"grouped": {"team": "not an object"}, "listed": []},
        {"grouped": {}, "listed": ["not an object"]},
    ):
        with pytest.raises(HowlerModelValidationError):
            Containers.model_validate(data, extra="ignore")


def test_registry_fields_flattening_and_mapping() -> None:
    """The canonical registry exposes fields, dotted paths, and explicit DSL mappings."""
    metadata = model_registry.metadata(FoundationDocument)
    fields = model_registry.fields(FoundationDocument)
    flat = model_registry.flat_fields(FoundationDocument, show_compound=True)
    mapping_data = model_registry.mapping(FoundationDocument)
    properties = mapping_data["properties"]

    assert metadata.id_field == "document_id"
    assert metadata.description == "Foundation document"
    assert fields["from"].metadata is not None
    assert fields["from"].metadata.kind == "Keyword"
    assert flat["children"].multivalued
    assert flat["children"].compound_model is FoundationChild
    assert flat["children.address"].multivalued
    assert flat["children.address"].metadata is not None
    assert flat["children.address"].metadata.kind == "IP"
    assert "children" not in model_registry.flat_fields(FoundationDocument)

    assert properties["from"]["type"] == "keyword"
    assert properties["class"]["type"] == "keyword"
    assert properties["from"]["index"] is True
    assert properties["from"]["doc_values"] is True
    assert properties["child"]["type"] == "object"
    assert properties["children"]["type"] == "object"
    assert properties["tags"]["type"] == "keyword"
    assert properties["child"]["properties"]["address"]["type"] == "ip"
    assert properties["counters"]["type"] == "object"
    assert properties["unindexed"] == {"type": "object", "enabled": False}
    assert properties["maybe_unindexed"]["index"] is False
    assert properties["maybe_unindexed"]["doc_values"] is False
    assert properties["classification"]["type"] == "keyword"
    assert "ignore_above" not in properties["classification"]
    assert properties["__access_lvl__"] == {"type": "integer", "index": True}
    assert properties["__access_req__"] == {"type": "keyword", "index": True}
    assert "meta" not in properties

    properties["__access_lvl__"]["index"] = False
    assert model_registry.mapping(FoundationDocument)["properties"]["__access_lvl__"]["index"] is True


def test_inherited_document_fields_are_mapped() -> None:
    """The Howler metaclass fixes the preview DSL's inherited-field omission."""
    properties = model_registry.mapping(FoundationDerivedDocument)["properties"]
    assert properties["inherited"]["type"] == "keyword"
    assert properties["own"]["type"] == "integer"


def test_model_index_and_store_defaults_reach_registry_and_mapping() -> None:
    """Model-wide defaults govern both metadata consumers and physical mappings."""
    fields = model_registry.fields(FoundationUnindexedDocument)
    properties = model_registry.mapping(FoundationUnindexedDocument)["properties"]

    assert fields["value"].metadata is not None
    assert fields["value"].metadata.index is False
    assert fields["value"].metadata.store is False
    assert properties["value"]["index"] is False
    assert properties["value"]["doc_values"] is False
    assert properties["body"]["index"] is False


def test_mapping_key_validation() -> None:
    """Indexed mappings reject illegal keys while unindexed mappings retain them."""
    data = _document_data()
    data["counters"] = {"Bad Key": 1}
    with pytest.raises(HowlerModelValidationError):
        FoundationDocument.model_validate(data)

    data["counters"] = {"good": 1}
    data["unindexed"] = {"Bad Key": "value", "4key": "value"}
    model = FoundationDocument.model_validate(data)
    assert model.unindexed["Bad Key"] == "value"


def test_stable_validation_error_translation() -> None:
    """Pydantic validation errors translate to the Howler exception hierarchy across every validation entry point."""
    assert not FoundationDocument.__pydantic_custom_init__
    assert not FoundationChild.__pydantic_custom_init__

    with pytest.raises(HowlerModelValidationError) as raised:
        FoundationDocument.model_validate({"from": "missing required fields"})

    assert raised.value.errors
    assert isinstance(raised.value.cause, ValidationError)

    with pytest.raises(HowlerModelValidationError) as init_raised:
        FoundationDocument(**{**_document_data(), "child": {"name": "child", "count": "invalid"}})
    assert isinstance(init_raised.value.cause, ValidationError)
    assert str(init_raised.value) == str(init_raised.value.cause)
    assert "child.count" in str(init_raised.value)

    with pytest.raises(HowlerModelValidationError):
        FoundationDocument.model_validate_json('{"from": "missing required fields"}')

    with pytest.raises(HowlerModelValidationError):
        FoundationDocument.model_validate_strings({"from": "missing required fields"})

    model = FoundationDocument.model_validate(_document_data())
    with pytest.raises(HowlerModelValidationError):
        model["child.count"] = "invalid"  # pyright: ignore[reportIndexIssue]

    with pytest.raises(HowlerModelValidationError):
        validate_field_value(FoundationDocument, "child.count", "invalid")

    assert validate_field_value(FoundationDocument, "tags", None) == []


def test_dotted_input_helper_builds_nested_objects() -> None:
    """The dotted-input helper creates each nested mapping along a path."""
    assert flat_to_nested({}) == {}
    assert flat_to_nested({"a.b.c": None}) == {"a": {"b": {"c": None}}}


def test_model_registry_resolves_identifiers_and_validates_explicit_fields() -> None:
    """Model metadata derives identifiers and rejects invalid explicit declarations."""

    class IdentifierDocument(HowlerESModel):
        title: Keyword

    class ExplicitIdentifierDocument(HowlerESModel):
        document_key: Keyword
        title: Keyword

    registry = ModelRegistry()
    registry.register(IdentifierDocument)
    registry.register(ExplicitIdentifierDocument, id_field="document_key")
    assert registry.metadata(IdentifierDocument).id_field == "identifierdocument_id"
    assert registry.metadata(ExplicitIdentifierDocument).id_field == "document_key"

    with pytest.raises(HowlerTypeError):
        registry.register(IdentifierDocument, id_field=123)  # type: ignore[arg-type]
    with pytest.raises(HowlerValueError):
        registry.register(IdentifierDocument, id_field="missing")
    with pytest.raises(HowlerValueError):
        registry.register(IdentifierDocument, id_field="_id")

    with pytest.raises(HowlerValueError):

        class InvalidFieldDocument(HowlerESModel):
            InvalidName: Keyword

        registry.register(InvalidFieldDocument)


def test_model_registry_inherits_field_metadata_without_sharing_field_views() -> None:
    """Derived models include inherited fields while keeping each field view independent."""

    class BaseDocument(HowlerESModel):
        inherited: Keyword

    class DerivedDocument(BaseDocument):
        own: Integer

    registry = ModelRegistry()
    registry.register(BaseDocument, index=True, store=True)
    registry.register_derived(DerivedDocument, BaseDocument)

    base_fields = registry.fields(BaseDocument)
    derived_fields = registry.fields(DerivedDocument)
    assert set(derived_fields) == {"inherited", "own"}
    assert "own" not in base_fields
    assert base_fields is not derived_fields
    assert registry.metadata(DerivedDocument).index is True
    assert registry.mapping(DerivedDocument)["properties"]["inherited"]["type"] == "keyword"


def test_derived_model_can_override_an_inherited_field() -> None:
    """A derived Pydantic model uses its own definition for an overridden field."""

    class BaseDocument(HowlerESModel):
        shared: Keyword = "base"

    class DerivedDocument(BaseDocument):
        shared: Keyword = "derived"

    registry = ModelRegistry()
    registry.register(BaseDocument)
    registry.register_derived(DerivedDocument, BaseDocument)

    assert registry.fields(BaseDocument)["shared"].default == "base"
    assert registry.fields(DerivedDocument)["shared"].default == "derived"
    assert DerivedDocument.model_validate({}).shared == "derived"


def test_index_defaults_and_compound_overrides_reach_flat_fields() -> None:
    """Model-level mapping defaults flow into children unless a field overrides them."""
    flat = model_registry.flat_fields(IndexedParent)
    assert flat["child.inherited"].metadata is not None
    assert flat["child.inherited"].metadata.index is True
    assert flat["child.explicitly_indexed"].metadata is not None
    assert flat["child.explicitly_indexed"].metadata.index is True
    assert flat["child.explicitly_unindexed"].metadata is not None
    assert flat["child.explicitly_unindexed"].metadata.index is False
    assert flat["unindexed_child.inherited"].metadata is not None
    assert flat["unindexed_child.inherited"].metadata.index is False
    assert flat["unindexed_child.explicitly_indexed"].metadata is not None
    assert flat["unindexed_child.explicitly_indexed"].metadata.index is True


def test_partial_ignore_unknown_propagates_through_mapping_values() -> None:
    """Partial read normalization ignores stale plugin fields nested inside typed mappings."""

    class Leaf(HowlerEmbeddedModel):
        value: Keyword | None = None

    class Root(HowlerESModel):
        grouped: mapping(Leaf, index=False)
        nested: mapping(list[mapping(Leaf, index=False)], index=False)

    partial = construct_partial(
        Root,
        {
            "grouped": {"team": {"value": "keep", "old_plugin_field": "drop"}},
            "nested": {"team": [{"key": {"value": "keep", "old_plugin_field": "drop"}}]},
        },
        ignore_unknown=True,
    )
    assert partial.as_primitives() == {
        "grouped": {"team": {"value": "keep"}},
        "nested": {"team": [{"key": {"value": "keep"}}]},
    }


def test_unaliased_trailing_underscore_fields_serialize_consistently_with_registry() -> None:
    """Fields ending in '_' without an explicit alias still serialize without the trailing '_'."""

    class TrailingProbe(HowlerESModel):
        from_: Keyword

    model = TrailingProbe.model_validate({"from_": "value"})
    assert "from" in model_registry.fields(TrailingProbe)
    assert "from" in model_registry.mapping(TrailingProbe)["properties"]
    assert model.as_primitives() == {"from": "value"}


def test_any_field_converts_nested_datetimes_to_primitive_formats() -> None:
    """Arbitrary values containing datetimes still serialize to JSON-compatible primitives."""

    class ArbitraryDoc(HowlerESModel):
        raw: AnyField

    dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    doc = ArbitraryDoc.model_validate({"raw": {"when": dt, "items": [dt, None], "drop": None}})

    assert doc.as_primitives() == {"raw": {"when": TIMESTAMP, "items": [TIMESTAMP, None]}}
    assert doc.as_primitives(timestamp_format="iso") == {
        "raw": {"when": "2024-01-02T03:04:05+00:00", "items": ["2024-01-02T03:04:05+00:00", None]}
    }
    assert doc.as_primitives(timestamp_format="posix") == {"raw": {"when": 1704164645, "items": [1704164645, None]}}


def test_model_dump_omits_synthetic_index_and_round_trips() -> None:
    """Standard model_dump omits __index so instances round-trip cleanly through strict validation."""

    class IndexedDoc(HowlerESModel):
        _include_index = True
        name: Keyword

    doc = IndexedDoc.model_validate({"name": "alpha"})
    dumped = doc.model_dump(by_alias=True)
    assert "__index" not in dumped
    assert IndexedDoc.model_validate(dumped).name == "alpha"
    assert doc.as_primitives() == {"name": "alpha", "__index": "indexeddoc"}
