"""Live persistence and mapping checks for startup-declared model extensions."""

from typing import Annotated
from uuid import uuid4

import pytest
from pydantic import Field

from howler.datastore.store import ESStore
from howler.models import HowlerEmbeddedModel, ModelExtensionRegistry, fields, register_model
from howler.models.hit import Hit
from howler.utils.isotime import now_as_datetime


@register_model(index=True, store=True, embedded=True)
class ExtensionModel(HowlerEmbeddedModel):
    integer: fields.Integer = 1
    keyword: fields.Keyword = "keyword"
    boolean: fields.Boolean = True
    date: fields.Date = Field(default_factory=now_as_datetime)


@pytest.fixture(scope="module")
def collection():
    registry = ModelExtensionRegistry()
    registry.declare(Hit, "example", Annotated[ExtensionModel | None, Field(default=None)], plugin="test")
    model = registry.finalize(Hit)
    store = ESStore()
    name = f"extension-test-{uuid4().hex}"
    store.register(name, model)
    collection = getattr(store, name)
    try:
        for index in range(20):
            data = {"howler": {"id": str(index), "analytic": "extension test", "hash": "a" * 64}}
            if index >= 10:
                data["example"] = {}
            collection.save(str(index), data)
        collection.commit()
        yield collection
    finally:
        store.client.indices.delete(index=collection.index_name)


def test_get_namespace_field(collection):
    results = collection.search("example.keyword:*", fl="example.keyword")
    assert len(results["items"]) == 10
    assert all(hit.example.keyword == "keyword" for hit in results["items"])


def test_get_index_mapping(collection):
    properties = collection._get_index_mappings()["properties"]
    for name, field_type in {"integer": "integer", "keyword": "keyword", "boolean": "boolean", "date": "date"}.items():
        assert properties[f"example.{name}"]["type"] == field_type
