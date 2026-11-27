import pytest

from howler.models import HowlerModelValidationError, model_registry
from howler.models.ecs.agent import Agent
from howler.models.ecs.dns import DNS, DNSAnswer
from howler.models.ecs.hash import Hashes
from howler.models.ecs.related import Related
from howler.models.ecs.threat import Threat
from howler.models.hit import Hit


@pytest.mark.parametrize("ids", [None, ["indicator-1", "indicator-2"], ("indicator-1", "indicator-2")])
def test_related_id_merges_without_duplicates(ids):
    related = Related.model_validate({"id": "indicator-2", "ids": ids} if ids is not None else {"id": "indicator-2"})
    assert related.as_primitives()["ids"] == (["indicator-2"] if ids is None else ["indicator-1", "indicator-2"])


def test_hit_accepts_dotted_related_id():
    hit = Hit.model_validate({"howler.analytic": "Test", "howler.hash": "a", "related.id": "indicator-3"})
    assert hit.as_primitives()["related"]["ids"] == ["indicator-3"]


def test_related_default_lists_are_independent():
    first, second = Related.model_validate({}), Related.model_validate({})
    assert all(getattr(first, name) == [] for name in ("hash", "hosts", "ip", "user", "ids"))
    first.ids.append("new-id")
    assert second.ids == []


def test_agent_identifier_metadata():
    assert Agent.model_validate({}).as_primitives() == {}
    assert Agent.model_validate({"id": None}).id is None
    details = model_registry.metadata(Agent)
    assert details.id_field == "agent_id" and details.index and details.store


def test_dns_reserved_alias_and_nested_answers():
    answer = DNSAnswer.model_validate({"class": "IN", "ttl": "30"})
    assert answer.class_ == "IN" and answer.as_primitives() == {"class": "IN", "ttl": 30}
    dns = DNS.model_validate({"answers": [{"class": "IN", "name": "example.com"}], "resolved_ip": ["127.0.0.1"]})
    assert dns.as_primitives()["answers"][0] == {"class": "IN", "name": "example.com"}


def test_hash_validation_and_threat_technique():
    hashes = Hashes.model_validate({"md5": "d41d8cd98f00b204e9800998ecf8427e"})
    assert hashes.md5 == "d41d8cd98f00b204e9800998ecf8427e"
    with pytest.raises(HowlerModelValidationError):
        Hashes.model_validate({"md5": "not-a-valid-md5-hash"})
    threat = Threat.model_validate({"technique": {"id": "T1000", "name": "Something"}})
    assert threat.as_primitives()["technique"] == {"id": "T1000", "name": "Something"}
