"""Tests for the Howler Pydantic/DSL model foundation."""

from __future__ import annotations

import base64
from datetime import datetime
from ipaddress import ip_address
from pathlib import Path

import pytest
from pydantic import ValidationError

from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    HowlerModelValidationError,
    classification,
    compound,
    date,
    document_adapter,
    flattened_list_object,
    flattened_object,
    integer,
    ip,
    keyword,
    list_field,
    mapping,
    model_registry,
    optional,
    register_model,
    text,
    uuid,
)

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
    assert primitives["classification"] == "UNRESTRICTED"
    assert primitives["__access_lvl__"] == 100
    assert primitives["__access_grp1__"] == ["__EMPTY__"]

    encoded = model.as_primitives(ip_format="encoded_bytes", timestamp_format="posix")
    assert base64.b64decode(encoded["child"]["address"]) == ip_address("127.0.0.1").packed
    assert encoded["child"]["created"] == int(datetime.fromisoformat(TIMESTAMP.replace("Z", "+00:00")).timestamp())


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

    assert properties["from"]["type"] == "keyword"
    assert properties["from"]["index"] is True
    assert properties["from"]["doc_values"] is True
    assert properties["child"]["type"] == "object"
    assert properties["children"]["type"] == "object"
    assert properties["tags"]["type"] == "keyword"
    assert properties["child"]["properties"]["address"]["type"] == "ip"
    assert properties["counters"]["type"] == "object"
    assert properties["unindexed"] == {"type": "object", "enabled": False}
    assert properties["classification"]["type"] == "keyword"
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
