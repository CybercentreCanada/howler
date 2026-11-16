"""Tests for the Howler Pydantic/DSL model foundation."""

from __future__ import annotations

import base64
from datetime import datetime
from ipaddress import ip_address
from pathlib import Path

import pytest
from pydantic import ValidationError

from howler.common.exceptions import HowlerTypeError, HowlerValueError
from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    HowlerModelValidationError,
    classification,
    compound,
    construct_partial,
    construct_safe,
    date,
    document_adapter,
    flat_to_nested,
    flattened_list_object,
    flattened_object,
    integer,
    ip,
    keyword,
    list_field,
    mapping,
    model_registry,
    optional,
    partial_primitives,
    register_model,
    strip_unknown_fields,
    text,
    uuid,
)
from howler.models.registry import ModelRegistry

CLASSIFICATION_CONFIG = str(Path(__file__).parents[2] / "classification.yml")
TIMESTAMP = "2024-01-02T03:04:05.000000Z"


@register_model(description="Embedded child", index=True, store=True, embedded=True)
class FoundationChild(HowlerEmbeddedModel):
    """Embedded model used by foundation tests."""

    name: keyword()
    count: integer(default=1)
    address: ip()
    created: date()


@register_model(description="Foundation document", id_field="document_id", index=True, store=True)
class FoundationDocument(HowlerESModel):
    """Top-level document used by foundation tests."""

    document_id: uuid()
    from_: keyword(alias="from")
    child: compound(FoundationChild)
    children: list_field(compound(FoundationChild), default=[])
    tags: list_field(keyword(), default=[])
    counters: mapping(integer(), default={}, index=True, store=True)
    unindexed: mapping(keyword(), default={}, index=False, store=False)
    flattened: flattened_object(default={})
    flattened_lists: flattened_list_object(default={})
    maybe: optional(keyword())
    maybe_ip: optional(ip())
    maybe_unindexed: optional(keyword(index=False, store=False))
    class_: optional(keyword(), alias="class")
    classification: classification(default="UNRESTRICTED", yml_config=CLASSIFICATION_CONFIG)


class FoundationBaseDocument(HowlerESModel):
    """Base document used to verify inherited mapping fields."""

    inherited: keyword()


class FoundationDerivedDocument(FoundationBaseDocument):
    """Derived document used to verify inherited mapping fields."""

    own: integer()


@register_model(index=False, store=False)
class FoundationUnindexedDocument(HowlerESModel):
    """Document used to verify model-wide field defaults."""

    value: keyword()
    body: text()


@register_model(embedded=True)
class IndexedChild(HowlerEmbeddedModel):
    """Embedded fields used to verify inherited mapping defaults."""

    inherited: keyword()
    explicitly_indexed: keyword(index=True)
    explicitly_unindexed: keyword(index=False)


@register_model(index=True, store=True)
class IndexedParent(HowlerESModel):
    """Document used to check compound-level mapping overrides."""

    child: compound(IndexedChild)
    unindexed_child: compound(IndexedChild, index=False)


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
    with pytest.raises(ValidationError):
        model.child.count = "invalid"
    with pytest.raises(ValidationError):
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
    with pytest.raises(ValidationError):
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

    encoded = model.as_primitives(ip_format="encoded_bytes", timestamp_format="posix")
    assert base64.b64decode(encoded["child"]["address"]) == ip_address("127.0.0.1").packed
    assert encoded["child"]["created"] == int(datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00")).timestamp())

    data = _document_data()
    data["maybe_ip"] = "127.0.0.1"
    assert FoundationDocument.model_validate(data).as_primitives(ip_format="int")["maybe_ip"] == 2130706433


def test_document_adapter_round_trip_preserves_metadata() -> None:
    """The Howler adapter preserves aliases, empty collections, and ES metadata."""
    model = FoundationDocument.model_validate(_document_data())
    model.meta.id = "es-id"
    model.meta.index = "howler-foundation"
    model.meta.version = 4

    document = document_adapter.to_doc(model)
    source = document.to_dict(skip_empty=False)

    assert source["from"] == "source"
    assert source["children"] == []
    assert source["tags"] == ["one", "2"]
    assert source["__access_lvl__"] == 100
    assert document.meta.id == "es-id"
    assert document.meta.version == 4

    restored = document_adapter.from_doc(FoundationDocument, document)
    assert restored.as_primitives() == model.as_primitives()
    assert restored.meta.id == "es-id"
    assert restored.meta.version == 4


def test_document_adapter_ignores_synthetic_stored_fields() -> None:
    """Stored access/id helpers aren't treated as strict model input."""
    model = FoundationDocument.model_validate(_document_data())
    document = document_adapter.to_doc(model)
    document.id = "stored-id"
    document.__access_lvl__ = 100

    restored = document_adapter.from_doc(FoundationDocument, document)

    assert restored.document_id == "document-1"


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

    clean = strip_unknown_fields(FoundationDocument, data)
    model = FoundationDocument.model_validate(clean)

    assert "removed_plugin_field" not in clean
    assert "removed_child_field" not in clean["child"]
    assert model.counters["dynamic_key"] == 2


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
    with pytest.raises(ValidationError):
        FoundationDocument.model_validate(data)

    data["counters"] = {"good": 1}
    data["unindexed"] = {"Bad Key": "value", "4key": "value"}
    model = FoundationDocument.model_validate(data)
    assert model.unindexed["Bad Key"] == "value"


def test_stable_validation_error_translation() -> None:
    """Pydantic validation errors translate to the Howler exception hierarchy."""
    with pytest.raises(HowlerModelValidationError) as raised:
        FoundationDocument.validate_howler({"from": "missing required fields"})

    assert raised.value.errors
    assert isinstance(raised.value.cause, ValidationError)


class SafeFlag(HowlerEmbeddedModel):
    """Nested flag used by safe-construction tests."""

    uuid: uuid()
    name: keyword()
    fans: list_field(integer(), default=[])


class SafeSpeed(HowlerEmbeddedModel):
    """Nested speed values used by safe-construction tests."""

    fast: integer(default=1)
    slow: keyword(default="abc")
    count: list_field(integer())


class SafeDocument(HowlerESModel):
    """Document used to check partial recovery of valid values."""

    speed: compound(SafeSpeed, default={})
    flags: list_field(compound(SafeFlag))


def test_safe_construction_keeps_valid_values_and_reports_rejected_paths() -> None:
    """Lenient construction returns valid subvalues and the rejected input separately."""
    model, dropped = construct_safe(
        SafeDocument,
        {
            "speed": {"fast": "abc", "count": ["100", 100, "hundred", "9dy"]},
            "flags": [
                "abc",
                {"uuid": "bad"},
                {"name": "good"},
                {"name": "some-good", "fans": [1, "99", "many"]},
            ],
            "cats": "red",
        },
    )

    assert isinstance(model, SafeDocument)
    assert model.speed.fast == 1
    assert model.speed.slow == "abc"
    assert model.speed.count == [100, 100]
    assert [flag.name for flag in model.flags] == ["good", "some-good"]
    assert all(flag.uuid for flag in model.flags)
    assert model.flags[0].fans == []
    assert model.flags[1].fans == [1, 99]
    assert dropped["cats"] == "red"
    assert dropped["speed"]["fast"] == "abc"
    assert set(dropped["speed"]["count"]) == {"hundred", "9dy"}
    assert dropped["flags"][0] == "abc"
    assert dropped["flags"][1] == {"uuid": "bad"}
    assert dropped["flags"][2] == {"fans": ["many"]}


def test_safe_construction_returns_non_object_input_unchanged() -> None:
    """A non-object input cannot produce a document and is returned as rejected input."""
    model, dropped = construct_safe(SafeDocument, "invalid")
    assert model is None
    assert dropped == "invalid"


def test_dotted_input_helper_builds_nested_objects() -> None:
    """The dotted-input helper creates each nested mapping along a path."""
    assert flat_to_nested({}) == {}
    assert flat_to_nested({"a.b.c": None}) == {"a": {"b": {"c": None}}}


def test_model_registry_resolves_identifiers_and_validates_explicit_fields() -> None:
    """Model metadata derives identifiers and rejects invalid explicit declarations."""

    class IdentifierDocument(HowlerESModel):
        title: keyword()

    class ExplicitIdentifierDocument(HowlerESModel):
        document_key: keyword()
        title: keyword()

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
            InvalidName: keyword()

        registry.register(InvalidFieldDocument)


def test_model_registry_inherits_field_metadata_without_sharing_field_views() -> None:
    """Derived models include inherited fields while keeping each field view independent."""

    class BaseDocument(HowlerESModel):
        inherited: keyword()

    class DerivedDocument(BaseDocument):
        own: integer()

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
        shared: keyword(default="base")

    class DerivedDocument(BaseDocument):
        shared: keyword(default="derived")

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
