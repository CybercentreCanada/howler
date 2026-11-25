"""Related identifiers and representative ECS model behavior."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from howler.models import model_registry
from howler.models.ecs.agent import Agent
from howler.models.ecs.dns import DNS, DNSAnswer
from howler.models.ecs.hash import Hashes
from howler.models.ecs.related import Related
from howler.models.ecs.threat import Threat
from howler.models.hit import Hit


class TestRelated:
    """Tests for identifiers merged into ECS related fields."""

    def test_related_id_is_added_to_ids(self) -> None:
        related = Related.model_validate({"id": "indicator-1"})

        assert related.id == "indicator-1"
        assert related.ids == ["indicator-1"]

    def test_related_id_merges_without_duplicates(self) -> None:
        related = Related.model_validate({"id": "indicator-2", "ids": ["indicator-1", "indicator-2"]})
        tuple_ids = Related.model_validate({"id": "indicator-2", "ids": ("indicator-1", "indicator-2")})

        assert related.ids == ["indicator-1", "indicator-2"]
        assert tuple_ids.ids == ["indicator-1", "indicator-2"]
        assert related.as_primitives()["ids"] == ["indicator-1", "indicator-2"]

    def test_hit_accepts_dotted_related_id(self) -> None:
        hit = Hit.model_validate({"howler.analytic": "Test Analytic", "howler.hash": "a", "related.id": "indicator-3"})

        assert hit.related is not None
        assert hit.related.id == "indicator-3"
        assert hit.related.ids == ["indicator-3"]
        assert hit.as_primitives()["related"]["ids"] == ["indicator-3"]

    def test_related_default_lists_are_independent(self) -> None:
        first = Related.model_validate({})
        second = Related.model_validate({})
        assert first.hash == []
        assert first.hosts == []
        assert first.ip == []
        assert first.user == []
        assert first.ids == []
        first.ids.append("new-id")
        assert second.ids == []


class TestECSModels:
    """Tests for representative ECS field sets and validators."""

    def test_agent_accepts_fields_and_uses_derived_identifier_metadata(self) -> None:
        agent = Agent.model_validate({"id": "agent-1", "name": "sensor", "type": "endpoint", "version": "1.0"})

        assert agent.id == "agent-1"
        assert agent.name == "sensor"
        assert agent.as_primitives()["type"] == "endpoint"
        assert model_registry.metadata(Agent).id_field == "agent_id"
        assert model_registry.metadata(Agent).index is True
        assert model_registry.metadata(Agent).store is True

    def test_empty_agent_omits_optional_fields(self) -> None:
        assert Agent.model_validate({}).as_primitives() == {}

    def test_agent_identifier_is_nullable(self) -> None:
        assert Agent.model_validate({"id": None}).id is None

    def test_dns_answer_serializes_reserved_word_alias(self) -> None:
        answer = DNSAnswer.model_validate({"class": "IN", "data": "1.2.3.4", "ttl": "30", "type": "A"})

        assert answer.class_ == "IN"
        primitives = answer.as_primitives()
        assert primitives["class"] == "IN"
        assert "class_" not in primitives
        assert primitives["ttl"] == 30

    def test_dns_round_trip_handles_nested_answers_and_ip_lists(self) -> None:
        dns = DNS.model_validate(
            {
                "answers": [{"class": "IN", "name": "example.com"}],
                "resolved_ip": ["127.0.0.1", "2001:db8::1"],
            }
        )

        assert dns.answers[0].class_ == "IN"
        assert dns.resolved_ip == ["127.0.0.1", "2001:db8::1"]
        assert dns.as_primitives()["answers"][0]["name"] == "example.com"

    def test_hash_fields_validate_supported_algorithms(self) -> None:
        hashes = Hashes.model_validate(
            {
                "md5": "d41d8cd98f00b204e9800998ecf8427e",
                "sha1": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
                "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            }
        )
        assert hashes.md5 == "d41d8cd98f00b204e9800998ecf8427e"
        assert hashes.sha1 == "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        assert hashes.sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

        with pytest.raises(ValidationError):
            Hashes.model_validate({"md5": "not-a-valid-md5-hash"})

    def test_threat_technique_keeps_its_tactic_fields(self) -> None:
        threat = Threat.model_validate({"technique": {"id": "T1000", "name": "Something"}})
        assert threat.technique is not None
        assert threat.technique.id == "T1000"
        assert threat.as_primitives()["technique"]["name"] == "Something"
