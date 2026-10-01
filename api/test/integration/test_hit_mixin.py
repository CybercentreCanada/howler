"""Integration coverage for Pydantic Hit persistence through its datastore collection.

The former Hit ODM mixin's ``store``, ``ds`` and ``save`` descriptors were removed with the
legacy model layer. These tests retain the useful live-Elasticsearch checks at the collection
boundary used by the Pydantic model runtime.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from howler.common import loader
from howler.datastore.collection import ESCollection
from howler.datastore.howler_store import HowlerDatastore
from howler.models.hit import Hit
from howler.sample_data.helper import generate_useful_hit


@pytest.fixture(scope="module")
def lookups():
    return loader.get_lookups()


@pytest.fixture(scope="module")
def usernames(datastore_connection: HowlerDatastore) -> list[str]:
    return [user["uname"] for user in datastore_connection.user.search("uname:*")["items"]]


@pytest.fixture()
def stored_hit(datastore_connection: HowlerDatastore, lookups, usernames: list[str]) -> Iterator[Hit]:
    """Persist one generated Pydantic Hit, then remove the test document."""
    hit = generate_useful_hit(lookups, usernames, prune_hit=False)
    datastore_connection.hit.save(hit.howler.id, hit)
    datastore_connection.hit.commit()
    try:
        yield hit
    finally:
        datastore_connection.hit.delete(hit.howler.id)
        datastore_connection.hit.commit()


def test_hit_collection_is_bound_to_pydantic_model(datastore_connection: HowlerDatastore) -> None:
    assert isinstance(datastore_connection.hit, ESCollection)

    model_class = datastore_connection.hit.model_class
    assert model_class is datastore_connection.hit.schema_model
    assert issubclass(model_class, Hit)
    if model_class is not Hit:
        # Typed plugin extensions finalize Hit as a direct subclass. Without extensions,
        # the base model itself is the finalized schema.
        assert model_class.__base__ is Hit
        assert set(Hit.model_fields) < set(model_class.model_fields)


def test_hit_collection_save_round_trips_model(datastore_connection: HowlerDatastore, stored_hit: Hit) -> None:
    retrieved = datastore_connection.hit.get(stored_hit.howler.id)

    assert isinstance(retrieved, Hit)
    assert retrieved.howler.id == stored_hit.howler.id
    assert retrieved.howler.analytic == stored_hit.howler.analytic
    assert retrieved.as_primitives() == stored_hit.as_primitives()


def test_hit_collection_search_finds_persisted_model(datastore_connection: HowlerDatastore, stored_hit: Hit) -> None:
    result = datastore_connection.hit.search(f"howler.id:{stored_hit.howler.id}", rows=1)

    assert result["total"] == 1
    assert result["items"][0]["howler"]["id"] == stored_hit.howler.id
