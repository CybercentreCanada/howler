import pytest

from howler.models import HowlerModelValidationError, model_registry
from howler.models.event import Event
from howler.models.hit import Hit


@pytest.mark.parametrize(
    ("model", "name", "howler"),
    [
        (Hit, "hit", {"id": "hit-1", "analytic": "test", "hash": "abcd"}),
        (Event, "event", {"id": "event-1", "hash": "abcd"}),
    ],
)
def test_identifier_and_primitives(model, name, howler):
    primitives = model.model_validate({"howler": howler}).as_primitives()
    assert model_registry.metadata(model).id_field == "howler.id"
    assert primitives["__index"] == name and primitives["howler"]["id"] == howler["id"]


def test_hit_defaults_and_strict_fields():
    data = {"howler": {"id": "hit-1", "analytic": "a", "hash": "abcd"}}
    primitives = Hit.model_validate(data).as_primitives()
    assert primitives["ecs"]["version"] == "8.3.0" and primitives["classification"] == "UNRESTRICTED"
    assert primitives["howler"]["score"] == 0 and primitives["howler"]["status"] == "open"
    assert all(not values for values in primitives["howler"]["labels"].values()) and primitives["tags"] == []
    with pytest.raises(HowlerModelValidationError):
        Hit.model_validate({**data, "not_a_real_field": True})


def test_hit_mapping_and_optional_ip_serialization():
    properties = model_registry.mapping(Hit)["properties"]
    howler = properties["howler"]["properties"]
    assert howler["incidents"]["type"] == howler["log"]["type"] == "object"
    assert properties["dns"]["properties"]["answers"]["properties"]["class"]["type"] == "keyword"
    assert properties["file"]["properties"]["elf"]["properties"]["header"]["properties"]["class"]["type"] == "keyword"
    assert (
        howler["comment"]["properties"]["value"]["type"] == howler["log"]["properties"]["explanation"]["type"] == "text"
    )
    hit = Hit.model_validate(
        {
            "howler": {"analytic": "test", "hash": "a"},
            "source": {
                "ip": "127.0.0.1",
                "original": {"domain": "Example.COM"},
            },
        }
    )
    assert hit.source.original.domain == "example.com"
    assert hit.model_dump(by_alias=True, context={"ip_format": "int"})["source"]["ip"] == 2130706433
    access = {"__access_lvl__", "__access_req__", "__access_grp1__", "__access_grp2__"}
    assert access <= properties.keys() and access <= hit.as_primitives(hidden_fields=True).keys()


def test_event_nested_log_primitives():
    event = Event.model_validate(
        {
            "howler": {
                "id": "event-2",
                "hash": "abcd",
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
    assert event.as_primitives()["howler"]["log"][0]["explanation"] == "Reviewed"
