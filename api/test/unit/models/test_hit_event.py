"""Hit and Event identifiers, defaults, validation, and Elasticsearch mappings."""

from __future__ import annotations

import pytest

from howler.models import HowlerModelValidationError, model_registry
from howler.models.event import Event
from howler.models.hit import Hit

HIT_DATA = {
    "timestamp": "2024-01-02T03:04:05.000000Z",
    "howler": {"id": "hit-1", "analytic": "My Analytic", "hash": "abcd1234", "assessment": None},
    "related": {"ip": ["127.0.0.1"]},
}
EVENT_DATA = {"timestamp": "2024-01-02T03:04:05.000000Z", "howler": {"id": "event-1", "hash": "abcd1234"}}


def test_hit_identifier_and_primitives() -> None:
    """Hit uses its nested Howler ID and emits the collection name."""
    hit = Hit.model_validate(HIT_DATA)

    assert model_registry.metadata(Hit).id_field == "howler.id"
    assert hit.as_primitives()["__index"] == "hit"
    assert hit.as_primitives()["howler"]["id"] == "hit-1"


def test_event_identifier_and_primitives() -> None:
    """Event uses its nested Howler ID and emits the collection name."""
    event = Event.model_validate(EVENT_DATA)

    assert model_registry.metadata(Event).id_field == "howler.id"
    assert event.as_primitives()["__index"] == "event"
    assert event.as_primitives()["howler"]["id"] == "event-1"


def test_hit_rejects_unknown_top_level_fields() -> None:
    """The strict Hit model rejects undeclared fields."""
    with pytest.raises(HowlerModelValidationError):
        Hit.model_validate({**HIT_DATA, "not_a_real_field": True})


def test_hit_defaults_include_ecs_score_and_classification() -> None:
    """Minimal Hit input receives expected ECS, triage, label, and classification defaults."""
    hit = Hit.model_validate({"howler": {"id": "hit-2", "analytic": "a", "hash": "abcd"}})
    primitives = hit.as_primitives()

    assert primitives["ecs"]["version"] == "8.3.0"
    assert primitives["classification"] == "UNRESTRICTED"
    assert primitives["howler"]["score"] == 0
    assert primitives["howler"]["status"] == "open"
    assert primitives["howler"]["labels"] == {
        "assignments": [],
        "campaign": [],
        "generic": [],
        "insight": [],
        "mitigation": [],
        "operation": [],
        "threat": [],
        "tuning": [],
        "victim": [],
    }
    assert primitives["tags"] == []


def test_hit_list_of_compounds_and_alias_fields_map_as_objects() -> None:
    """Compound arrays map as objects and ECS aliases keep their serialized field names."""
    properties = model_registry.mapping(Hit)["properties"]
    howler_properties = properties["howler"]["properties"]

    assert howler_properties["incidents"]["type"] == "object"
    assert howler_properties["log"]["type"] == "object"
    assert properties["dns"]["properties"]["answers"]["properties"]["class"]["type"] == "keyword"
    assert properties["file"]["properties"]["elf"]["properties"]["header"]["properties"]["class"]["type"] == "keyword"
    assert howler_properties["analytic"]["normalizer"] == "lowercase_normalizer"
    assert howler_properties["detection"]["normalizer"] == "lowercase_normalizer"
    assert howler_properties["comment"]["properties"]["value"]["type"] == "text"
    assert howler_properties["log"]["properties"]["explanation"]["type"] == "text"


def test_hit_normalizes_domains_serializes_optional_ips_and_access_fields() -> None:
    """Nested domain values normalize while IP and classification output options are retained."""
    hit = Hit.model_validate(
        {
            **HIT_DATA,
            "source": {"ip": "127.0.0.1", "original": {"domain": "Example.COM"}},
        }
    )

    assert hit.source is not None
    assert hit.source.original is not None
    assert hit.source.original.domain == "example.com"
    assert hit.as_primitives(ip_format="int")["source"]["ip"] == 2130706433

    mappings = model_registry.mapping(Hit)["properties"]
    access_fields = ("__access_lvl__", "__access_req__", "__access_grp1__", "__access_grp2__")
    assert all(field in mappings for field in access_fields)
    primitives = hit.as_primitives(hidden_fields=True)
    assert all(field in primitives for field in access_fields)


def test_event_keeps_nested_log_validation_and_primitives() -> None:
    """Event log entries preserve their nested fields in serialized output."""
    event = Event.model_validate(
        {
            "howler": {
                "id": "event-2",
                "hash": "abcd1234",
                "log": [
                    {
                        "timestamp": "2024-01-02T03:04:05.000000Z",
                        "user": "analyst",
                        "key": "status",
                        "explanation": "Reviewed",
                    }
                ],
            }
        }
    )

    assert event.howler.log[0].user == "analyst"
    assert event.as_primitives()["howler"]["log"][0]["explanation"] == "Reviewed"
