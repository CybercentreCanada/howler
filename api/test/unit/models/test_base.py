from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

import pytest
from pydantic import Field, ValidationError

from howler.common.exceptions import HowlerTypeError, HowlerValueError
from howler.models import (
    IP,
    UUID,
    AnyField,
    Date,
    HowlerEmbeddedModel,
    HowlerESModel,
    HowlerModelValidationError,
    Integer,
    Keyword,
    construct_partial,
    metadata,
    partial_primitives,
    register_model,
    validate_field_value,
)
from howler.models.registry import ModelRegistry

TIMESTAMP = "2024-01-02T03:04:05.000000Z"


@register_model(index=True, store=True, embedded=True)
class Child(HowlerEmbeddedModel):
    name: Keyword
    count: Integer = 1
    address: IP
    created: Date


@register_model(id_field="document_id", index=True, store=True)
class Document(HowlerESModel):
    document_id: UUID
    from_: Annotated[Keyword, metadata(alias="from")]
    child: Child
    children: list[Child] = []
    tags: list[Keyword] = []


def document_data():
    return {
        "document_id": "doc",
        "from": "source",
        "child": {"name": "first", "count": "2", "address": "127.0.0.1", "created": TIMESTAMP},
        "tags": ["one", 2],
    }


def test_model_alias_assignment_and_dotted_access() -> None:
    model = Document.model_validate(document_data())
    assert model.from_ == "source" and model.child.count == 2 and model.tags == ["one", "2"]
    model.child.count = "3"
    assert model.child.count == 3
    with pytest.raises(HowlerModelValidationError):
        model.child.count = "invalid"
    with pytest.raises(HowlerModelValidationError):
        Document.model_validate({**document_data(), "unknown": True})
    model["from"] = "updated"  # pyright: ignore[reportIndexIssue]
    model["child.count"] = "4"  # pyright: ignore[reportIndexIssue]
    assert model["from"] == "updated" and model["child.count"] == 4  # pyright: ignore[reportIndexIssue]
    assert model.get("missing.field", "fallback") == "fallback"
    assert "from" in model and "missing" not in model


def test_flattened_compound_list_input() -> None:
    data = {
        **document_data(),
        "children.name": ["one", "two"],
        "children.count": [1, 2],
        "children.address": ["127.0.0.1", "2001:db8::1"],
        "children.created": [TIMESTAMP, TIMESTAMP],
    }
    assert [item.name for item in Document.model_validate(data).children] == ["one", "two"]
    data["children.count"] = [1]
    with pytest.raises(HowlerModelValidationError):
        Document.model_validate(data)


def test_partial_projection_defaults_and_nested_id() -> None:
    class Nested(HowlerEmbeddedModel):
        id: Keyword

    class Projected(HowlerESModel):
        value: str = Field(alias="stored_value")
        omitted: str
        generated: str = Field(default_factory=lambda: pytest.fail("Omitted default factory ran"))
        defaulted: str = "unused"
        nullable: str | None = None
        nested: Nested

    partial = construct_partial(Projected, {"stored_value": "selected", "id": "synthetic", "nested": {"id": "real"}})
    assert partial.model_dump(by_alias=True) == {
        "stored_value": "selected",
        "nullable": None,
        "nested": {"id": "real"},
    }
    assert partial.model_fields_set == {"value", "nested", "meta"}
    with pytest.raises(ValueError, match="Unknown field"):
        partial_primitives(Document, {"unknown": True})
    with pytest.raises(HowlerModelValidationError):
        construct_partial(Document, {"child": None})


def test_validation_error_translation() -> None:
    with pytest.raises(HowlerModelValidationError) as raised:
        Document.model_validate({"from": "missing required fields"})
    assert raised.value.errors and isinstance(raised.value.cause, ValidationError)
    with pytest.raises(HowlerModelValidationError, match="child.count") as raised:
        Document(**{**document_data(), "child": {"name": "child", "count": "invalid"}})
    assert str(raised.value) == str(raised.value.cause)
    for validate in (Document.model_validate_json, Document.model_validate_strings):
        with pytest.raises(HowlerModelValidationError):
            validate(
                '{"from": "missing required fields"}'
                if validate == Document.model_validate_json
                else {"from": "missing required fields"}
            )
    model = Document.model_validate(document_data())
    with pytest.raises(HowlerModelValidationError):
        model["child.count"] = "invalid"  # pyright: ignore[reportIndexIssue]
    with pytest.raises(HowlerModelValidationError):
        validate_field_value(Document, "child.count", "invalid")
    assert validate_field_value(Document, "tags", None) == []


def test_registry_identifiers_and_invalid_fields() -> None:
    class Identifier(HowlerESModel):
        title: Keyword

    class Explicit(HowlerESModel):
        document_key: Keyword

    registry = ModelRegistry()
    registry.register(Identifier)
    registry.register(Explicit, id_field="document_key")
    assert registry.metadata(Identifier).id_field == "identifier_id"
    assert registry.metadata(Explicit).id_field == "document_key"
    for name in ("missing", "_id"):
        with pytest.raises(HowlerValueError):
            registry.register(Identifier, id_field=name)
    with pytest.raises(HowlerTypeError):
        registry.register(Identifier, id_field=123)  # type: ignore[arg-type]
    with pytest.raises(HowlerValueError):

        class Invalid(HowlerESModel):
            InvalidName: Keyword

        registry.register(Invalid)


def test_any_nested_datetime_serialization() -> None:
    class ArbitraryDoc(HowlerESModel):
        raw: AnyField

    dt = datetime(2024, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    doc = ArbitraryDoc.model_validate({"raw": {"when": dt, "items": [dt, None], "drop": None}})
    assert doc.as_primitives() == {"raw": {"when": TIMESTAMP, "items": [TIMESTAMP, None]}}
