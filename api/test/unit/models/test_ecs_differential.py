"""Differential tests comparing migrated ECS models against the legacy ODM equivalents.

These tests exercise representative accepted/rejected inputs, defaults, aliases, and
``as_primitives()`` output for a representative sample of every migrated ECS group: simple
leaf models, alias handling (Python-keyword field names), nested compound models, list
handling, and the ``Related`` custom validator.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

import howler.odm.models.ecs.agent as legacy_agent
import howler.odm.models.ecs.dns as legacy_dns
import howler.odm.models.ecs.hash as legacy_hash
import howler.odm.models.ecs.related as legacy_related
import howler.odm.models.ecs.threat as legacy_threat
from howler.common.exceptions import HowlerValueError
from howler.models import model_registry
from howler.models.ecs.agent import Agent
from howler.models.ecs.dns import DNS, DNSAnswer
from howler.models.ecs.hash import Hashes
from howler.models.ecs.related import Related
from howler.models.ecs.threat import Threat


def test_agent_accepts_and_serializes_like_legacy() -> None:
    """A simple leaf ECS model produces identical primitives to the legacy ODM."""
    data = {"id": "agent-1", "name": "sensor", "type": "endpoint", "version": "1.0"}

    legacy = legacy_agent.Agent(data)
    new = Agent.model_validate(data)

    assert new.as_primitives() == legacy.as_primitives()


def test_agent_defaults_match_legacy() -> None:
    """Missing optional fields default to null/absent in both implementations."""
    legacy = legacy_agent.Agent({})
    new = Agent.model_validate({})

    assert new.as_primitives() == legacy.as_primitives() == {}


def test_dns_answer_class_alias_matches_legacy_reserved_word_handling() -> None:
    """The ``class`` reserved word is exposed the same way in both implementations."""
    data = {"class": "IN", "data": "1.2.3.4", "ttl": "30", "type": "A"}

    legacy = legacy_dns.DNSAnswer(data)
    new = DNSAnswer.model_validate(data)

    assert new.class_ == "IN"
    assert new.as_primitives() == legacy.as_primitives()
    assert new.as_primitives()["class"] == "IN"
    assert "class_" not in new.as_primitives()


def test_dns_resolved_ip_and_answers_round_trip() -> None:
    """Nested list-of-compound and list-of-IP fields match the legacy ODM output."""
    data = {
        "answers": [{"class": "IN", "name": "example.com"}],
        "resolved_ip": ["127.0.0.1", "2001:db8::1"],
    }

    legacy = legacy_dns.DNS(data)
    new = DNS.model_validate(data)

    assert new.as_primitives() == legacy.as_primitives()


def test_hashes_accepts_and_rejects_like_legacy() -> None:
    """Hash validators (MD5/SHA1/SHA256/ssdeep/validated keyword) match the legacy ODM."""
    valid = {
        "md5": "d41d8cd98f00b204e9800998ecf8427e",
        "sha1": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }
    legacy = legacy_hash.Hashes(valid)
    new = Hashes.model_validate(valid)
    assert new.as_primitives() == legacy.as_primitives()

    invalid = {"md5": "not-a-valid-md5-hash"}
    with pytest.raises(HowlerValueError):
        legacy_hash.Hashes(invalid)
    with pytest.raises(ValidationError):
        Hashes.model_validate(invalid)


def test_related_merges_deprecated_id_into_ids_like_legacy() -> None:
    """The deprecated ``id`` field merges into ``ids``, matching the legacy ``__init__``."""
    data = {"id": "abc", "ids": ["xyz"]}

    legacy = legacy_related.Related(data)
    new = Related.model_validate(data)

    assert new.ids == legacy.ids
    assert new.as_primitives()["ids"] == legacy.as_primitives()["ids"]


def test_related_defaults_and_lists() -> None:
    """Default empty lists match between implementations."""
    legacy = legacy_related.Related({})
    new = Related.model_validate({})

    assert new.as_primitives() == legacy.as_primitives()


def test_threat_technique_reuses_tactic_type_like_legacy() -> None:
    """Preserve the legacy quirk where ``threat.technique`` is typed as ``Tactic``."""
    data = {"technique": {"id": "T1000", "name": "Something"}}

    legacy = legacy_threat.Threat(data)
    new = Threat.model_validate(data)

    assert new.as_primitives() == legacy.as_primitives()
    assert new.technique.id == "T1000"


def test_agent_registry_metadata_matches_legacy_id_field_defaults() -> None:
    """The default id_field naming convention (``<name>_id``) matches the legacy ODM."""
    metadata = model_registry.metadata(Agent)
    assert metadata.id_field == "agent_id"
    assert metadata.index is True
    assert metadata.store is True
