from types import SimpleNamespace

from howler.models.hit import Hit
from howler.services import hit_service


def test_nested_ecs_payload_converts_without_warnings(monkeypatch):
    monkeypatch.setattr(hit_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=Hit)))
    user = {
        "domain": "example.com",
        "email": "user@example.com",
        "full_name": "Example User",
        "group.domain": "example.com",
        "group.id": "group_id",
        "group.name": "Example Group",
        "hash": "d41d8cd98f00b204e9800998ecf8427e",
        "id": "user_id",
        "name": "User name",
        "roles": ["user", "admin"],
    }
    indicator = {
        "first_seen": "2024-11-10T19:07:46.0956672Z",
        "port": 2,
        "description": "Description for indicator",
        "file": {"size": 256},
    }
    hit, warnings = hit_service.convert_hit(
        {
            "howler.analytic": "ECS",
            **{f"{side}.user.{field}": value for side in ("source", "destination") for field, value in user.items()},
            **{f"{side}.autonomous_systems.number": 1 for side in ("source", "destination")},
            "event.count": 1,
            "message": "Testing Message Log",
            "network.protocol": "prot",
            "observer.hostname": "name of host",
            "observer.ip": ["127.0.0.1", "8.8.8.8"],
            "observer.mac": ["mac-address-1", "mac-address-2"],
            "observer.ingress.zone": "TZ",
            "observer.ingress.interface.name": "Interface name",
            "rule.version": "1.0.0",
            "threat.enrichments.indicator": indicator,
            "threat.enrichments.matched.atomic": "indicator-hash",
        },
        unique=False,
    )
    for side in (hit.source, hit.destination):
        assert side.autonomous_systems.number == 1 and side.user.name == user["name"] and side.user.hash == user["hash"]
    assert hit.network.protocol == "prot" and hit.rule.version == "1.0.0"
    assert hit.observer.hostname == "name of host" and hit.observer.ip[1] == "8.8.8.8"
    assert hit.observer.ingress.zone == "TZ" and hit.observer.ingress.interface.name == "Interface name"
    assert hit.observer.mac[1] == "mac-address-2"
    actual = hit.as_primitives()["threat"]["enrichments"][0]["indicator"]
    assert {key: actual[key] for key in ("port", "description", "file")} == {
        key: indicator[key] for key in ("port", "description", "file")
    }
    assert actual["first_seen"].startswith("2024-11-10T19:07:46.095667")
    assert hit.threat.enrichments[0].matched.atomic == "indicator-hash"
    assert hit.message == "Testing Message Log" and hit.event.count == 1 and warnings == []
