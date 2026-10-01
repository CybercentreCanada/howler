"""Differential tests for Record/Hit/Event: id metadata, ``__index``, and primitive round trips."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from howler.models import model_registry
from howler.models.event import Event as NewEvent
from howler.models.hit import Hit as NewHit
from test.unit.models._goldens import primitive_golden, serialization_golden

HIT_DATA = {
    "timestamp": "2024-01-02T03:04:05.000000Z",
    "howler": {
        "id": "hit-1",
        "analytic": "My Analytic",
        "hash": "abcd1234",
        "assessment": None,
    },
    "related": {"ip": ["127.0.0.1"]},
}

EVENT_DATA = {
    "timestamp": "2024-01-02T03:04:05.000000Z",
    "howler": {"id": "event-1", "hash": "abcd1234"},
}


def test_hit_id_field_and_primitives_match_legacy() -> None:
    """``howler.id`` is the id field, and stored primitives match the legacy ODM."""
    new = NewHit.model_validate(HIT_DATA)

    assert model_registry.metadata(NewHit).id_field == "howler.id"

    new_primitives = new.as_primitives()

    assert new_primitives["__index"] == "hit"
    assert new_primitives == primitive_golden("hit")


def test_hit_rejects_unknown_fields_like_legacy() -> None:
    """Unknown top-level fields are rejected by both implementations."""
    bad_data = {**HIT_DATA, "not_a_real_field": True}

    with pytest.raises(ValidationError):
        NewHit.model_validate(bad_data)


def test_event_id_field_and_primitives_match_legacy() -> None:
    """``howler.id`` is the id field for events too, and primitives match."""
    new = NewEvent.model_validate(EVENT_DATA)

    assert model_registry.metadata(NewEvent).id_field == "howler.id"

    new_primitives = new.as_primitives()
    assert new_primitives["__index"] == "event"
    assert new_primitives == primitive_golden("event")


def test_hit_default_ecs_score_and_classification_match_legacy() -> None:
    """Default values (ECS version, score, classification) match the legacy ODM."""
    minimal = {"howler": {"id": "hit-2", "analytic": "a", "hash": "abcd"}}
    new = NewHit.model_validate(minimal)

    new_primitives = new.as_primitives()
    # "NOW" timestamps are intentionally not frozen; all remaining fields are exact.
    new_primitives.pop("timestamp")
    assert new_primitives["__index"] == "hit"
    assert new_primitives["ecs"]["version"] == "8.3.0"
    assert new_primitives["classification"] == "UNRESTRICTED"
    assert new_primitives == serialization_golden()["hit_default_without_timestamp"]


def test_hit_mapping_list_of_compound_is_object_not_nested() -> None:
    """List-of-compound fields (e.g. howler.incidents) map to ``object``, not ``nested``."""
    mapping = model_registry.mapping(NewHit)
    assert mapping["properties"]["howler"]["properties"]["incidents"]["type"] == "object"
    assert mapping["properties"]["howler"]["properties"]["log"]["type"] == "object"


def test_hit_mapping_preserves_aliases_normalizers_and_text_fields() -> None:
    """Aliased ECS keywords and Howler search fields retain their legacy mappings."""
    properties = model_registry.mapping(NewHit)["properties"]
    howler = properties["howler"]["properties"]

    assert properties["dns"]["properties"]["answers"]["properties"]["class"]["type"] == "keyword"
    assert properties["file"]["properties"]["elf"]["properties"]["header"]["properties"]["class"]["type"] == "keyword"
    assert howler["analytic"]["normalizer"] == "lowercase_normalizer"
    assert howler["detection"]["normalizer"] == "lowercase_normalizer"
    assert howler["comment"]["properties"]["value"]["type"] == "text"
    assert howler["log"]["properties"]["explanation"]["type"] == "text"


def test_optional_ip_and_original_domain_serialization_match_legacy() -> None:
    """Optional IP modes and normalized original-client domains match the legacy ODM."""
    data = {
        **HIT_DATA,
        "source": {
            "ip": "127.0.0.1",
            "original": {"domain": "Example.COM"},
        },
    }
    new = NewHit.model_validate(data)

    assert new.source is not None
    assert new.source.original is not None
    assert new.source.original.domain == "example.com"
    assert new.as_primitives(ip_format="int")["source"] == primitive_golden("hit.source")["source"]


def test_hit_classification_access_fields_generated() -> None:
    """The four hidden classification access-control fields are present in the mapping."""
    mapping = model_registry.mapping(NewHit)
    for field in ("__access_lvl__", "__access_req__", "__access_grp1__", "__access_grp2__"):
        assert field in mapping["properties"]

    new = NewHit.model_validate({"howler": {"id": "hit-3", "analytic": "a", "hash": "abcd"}})
    primitives = new.as_primitives(hidden_fields=True)
    for field in ("__access_lvl__", "__access_req__", "__access_grp1__", "__access_grp2__"):
        assert field in primitives
