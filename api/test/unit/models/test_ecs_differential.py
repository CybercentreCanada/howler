"""Representative ECS behavior against the frozen legacy serialization goldens.

These tests exercise representative accepted/rejected inputs, defaults, aliases, and
``as_primitives()`` output for a representative sample of every migrated ECS group: simple
leaf models, alias handling (Python-keyword field names), nested compound models, list
handling, and the ``Related`` custom validator.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from howler.models import model_registry
from howler.models.ecs.agent import Agent
from howler.models.ecs.dns import DNS, DNSAnswer
from howler.models.ecs.hash import Hashes
from howler.models.ecs.related import Related
from howler.models.ecs.threat import Threat
from test.unit.models._goldens import primitive_golden


def test_agent_accepts_and_serializes_like_legacy() -> None:
    """A simple leaf ECS model produces identical primitives to the legacy ODM."""
    data = {"id": "agent-1", "name": "sensor", "type": "endpoint", "version": "1.0"}

    new = Agent.model_validate(data)

    assert new.as_primitives() == primitive_golden("ecs.agent")


def test_agent_defaults_match_legacy() -> None:
    """Missing optional fields default to null/absent in both implementations."""
    new = Agent.model_validate({})

    assert new.as_primitives() == primitive_golden("ecs.agent.empty") == {}


def test_dns_answer_class_alias_matches_legacy_reserved_word_handling() -> None:
    """The ``class`` reserved word is exposed the same way in both implementations."""
    data = {"class": "IN", "data": "1.2.3.4", "ttl": "30", "type": "A"}

    new = DNSAnswer.model_validate(data)

    assert new.class_ == "IN"
    assert new.as_primitives() == primitive_golden("ecs.dns_answer")
    assert new.as_primitives()["class"] == "IN"
    assert "class_" not in new.as_primitives()


def test_dns_resolved_ip_and_answers_round_trip() -> None:
    """Nested list-of-compound and list-of-IP fields match the legacy ODM output."""
    data = {
        "answers": [{"class": "IN", "name": "example.com"}],
        "resolved_ip": ["127.0.0.1", "2001:db8::1"],
    }

    new = DNS.model_validate(data)

    assert new.as_primitives() == primitive_golden("ecs.dns")


def test_hashes_accepts_and_rejects_like_legacy() -> None:
    """Hash validators (MD5/SHA1/SHA256/ssdeep/validated keyword) match the legacy ODM."""
    valid = {
        "md5": "d41d8cd98f00b204e9800998ecf8427e",
        "sha1": "da39a3ee5e6b4b0d3255bfef95601890afd80709",
        "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    }
    new = Hashes.model_validate(valid)
    assert new.as_primitives() == primitive_golden("ecs.hashes")

    invalid = {"md5": "not-a-valid-md5-hash"}
    with pytest.raises(ValidationError):
        Hashes.model_validate(invalid)


def test_related_merges_deprecated_id_into_ids_like_legacy() -> None:
    """The deprecated ``id`` field merges into ``ids``, matching the legacy ``__init__``."""
    data = {"id": "abc", "ids": ["xyz"]}

    new = Related.model_validate(data)

    assert new.ids == ["xyz", "abc"]
    assert new.as_primitives() == primitive_golden("ecs.related")


def test_related_defaults_and_lists() -> None:
    """Default empty lists match between implementations."""
    new = Related.model_validate({})

    assert new.as_primitives() == primitive_golden("ecs.related.empty")


def test_threat_technique_reuses_tactic_type_like_legacy() -> None:
    """Preserve the legacy quirk where ``threat.technique`` is typed as ``Tactic``."""
    data = {"technique": {"id": "T1000", "name": "Something"}}

    new = Threat.model_validate(data)

    assert new.as_primitives() == primitive_golden("ecs.threat")
    assert new.technique.id == "T1000"


def test_agent_registry_metadata_matches_legacy_id_field_defaults() -> None:
    """The default id_field naming convention (``<name>_id``) matches the legacy ODM."""
    metadata = model_registry.metadata(Agent)
    assert metadata.id_field == "agent_id"
    assert metadata.index is True
    assert metadata.store is True
