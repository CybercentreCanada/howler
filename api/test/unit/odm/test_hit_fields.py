import json
from hashlib import md5

import pytest
from utils.example_hashes import EXAMPLE_HASHES

from howler.common.exceptions import HowlerValueError
from howler.odm.models.hit import Hit
from howler.odm.randomizer import get_random_hash
from howler.services import hit_service


def test_build_ecs_alert():
    user_hash = md5(json.dumps({"test": "potato"}).encode()).hexdigest()

    hit, warnings = hit_service.convert_hit(
        {
            "howler.analytic": "ECS",
            "destination.autonomous_systems.number": 1,
            "destination.autonomous_systems.organization_name": "Test LLC",
            "destination.user.domain": "example.com",
            "destination.user.email": "user@example.com",
            "destination.user.full_name": "Example User",
            "destination.user.group.domain": "example.com",
            "destination.user.group.id": "group_id",
            "destination.user.group.name": "Example Group",
            "destination.user.hash": user_hash,
            "destination.user.id": "user_id",
            "destination.user.name": "User name",
            "destination.user.roles": ["user", "admin"],
            "event.count": 1,
            "message": "Testing Message Log",
            "observer.egress.zone": "Z",
            "observer.hostname": "name of host",
            "observer.ingress.zone": "TZ",
            "observer.ip": ["127.0.0.1", "8.8.8.8"],
            "observer.mac": ["mac-address-1", "mac-address-2"],
            "observer.name": "test",
            "observer.product": "tester",
            "observer.serial_number": "1A34ABC45",
            "observer.type": "public",
            "observer.vendor": "porttest",
            "observer.version": "123.234.456",
            "observer.ingress.interface.name": "Interface name",
            "rule.author": "TT",
            "rule.category": "C",
            "rule.description": "testing description",
            "rule.id": 1,
            "rule.license": "T",
            "rule.name": "test",
            "rule.reference": "Y",
            "rule.ruleset": "TR",
            "rule.uuid": 0,
            "rule.version": "1.0.0",
            "network.protocol": "prot",
            "source.autonomous_systems.number": 1,
            "source.autonomous_systems.organization_name": "Test LLC",
            "source.user.domain": "example.com",
            "source.user.email": "user@example.com",
            "source.user.full_name": "Example User",
            "source.user.group.domain": "example.com",
            "source.user.group.id": "group_id",
            "source.user.group.name": "Example Group",
            "source.user.hash": user_hash,
            "source.user.id": "user_id",
            "source.user.name": "User name",
            "source.user.roles": ["user", "admin"],
            "threat.enrichments.indicator": {
                "first_seen": "2024-11-10T19:07:46.0956672Z",
                "port": 2,
                "description": "Description for indicator",
                "file": {"size": 256},
            },
            "threat.enrichments.matched.atomic": "0c415dd718e3b3728707d579cf8214f54c2942e964975a5f925e0b82fea644b4",
        },
        unique=False,
    )
    assert hit.destination.autonomous_systems.number == 1
    assert hit.destination.user.name == "User name"
    assert hit.network.protocol == "prot"
    assert hit.source.user.name == "User name"
    assert hit.rule.version == "1.0.0"
    assert hit.source.user.hash == user_hash
    assert hit.observer.hostname == "name of host"
    assert hit.observer.ip[1] == "8.8.8.8"
    assert hit.observer.ingress.zone == "TZ"
    assert hit.observer.ingress.interface.name == "Interface name"
    assert hit.observer.mac[1] == "mac-address-2"
    assert hit.threat.enrichments[0].indicator == {
        "first_seen": "2024-11-10T19:07:46.0956672Z",
        "port": 2,
        "description": "Description for indicator",
        "file": {"size": 256},
    }
    assert hit.message == "Testing Message Log"
    assert hit.event.count == 1
    assert (
        hit.threat.enrichments[0].matched.atomic == "0c415dd718e3b3728707d579cf8214f54c2942e964975a5f925e0b82fea644b4"
    )

    assert len(warnings) == 0


def test_howler_hashing():
    for length in range(0, 66):
        if length in [0, 65]:
            with pytest.raises(HowlerValueError):
                Hit({"howler.analytic": "Test Hash Analytic", "howler.hash": get_random_hash(length)})
        else:
            Hit({"howler.analytic": "Test Hash Analytic", "howler.hash": get_random_hash(length)})

    for _hash in EXAMPLE_HASHES.split("\n"):
        Hit({"howler.analytic": "Test Hash Analytic", "howler.hash": _hash})
