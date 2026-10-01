"""Pydantic serialization behavior against retired-ODM golden outcomes."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Any

import pytest

from howler.models import (
    HowlerEmbeddedModel,
    compound,
    date,
    ip,
    keyword,
    list_field,
    mapping,
    optional,
    register_model,
)
from howler.models.ecs.related import Related
from howler.models.hit import Hit
from test.unit.models._goldens import serialization_golden

GOLDEN_PATH = Path(__file__).parent / "fixtures/legacy_serialization_edge_goldens.json"
GOLDEN_SHA256 = "51bc9f928f2489889b2cc3288c7eff718f9f3f81bf197b0ab704987b3c1516e7"
STEP9_SOURCE_HEAD = "3071fc4ea45d4b2dd44a7ee1646095426097d061"


@register_model(index=True, store=True, embedded=True)
class SerializationGoldenInner(HowlerEmbeddedModel):
    nested_ip_field: ip()
    nested_timestamp_field: date()
    nested_keyword_field: keyword()


@register_model(index=True, store=True, embedded=True)
class SerializationGoldenProbe(HowlerEmbeddedModel):
    ip_field: ip()
    timestamp_field: date()
    keyword_field: keyword()
    ips_in_list: list_field(ip())
    ip_as_optional: optional(ip())
    timestamp_in_mapping: mapping(date())
    inner_model_field: compound(SerializationGoldenInner)
    list_of_ip_like_strings: list_field(keyword())
    optional_ip_like_string: optional(keyword())


@pytest.fixture(scope="module")
def probe() -> SerializationGoldenProbe:
    return SerializationGoldenProbe.model_validate(serialization_golden()["probe_input"])


def test_edge_fixture_has_pinned_legacy_provenance() -> None:
    data = serialization_golden()
    assert data["fixture_version"] == 1
    assert data["capture"]["source_head"] == STEP9_SOURCE_HEAD
    assert "api/.venv/bin/python" in data["capture"]["command"]
    assert hashlib.sha256(GOLDEN_PATH.read_bytes()).hexdigest() == GOLDEN_SHA256


@pytest.mark.parametrize(
    ("case", "kwargs"),
    [
        ("default", {}),
        ("ip.encoded_bytes", {"ip_format": "encoded_bytes"}),
        ("ip.int", {"ip_format": "int"}),
        ("ip.str", {"ip_format": "str"}),
        ("ip.invalid_fallback", {"ip_format": "invalid_format"}),
        ("ip.none_fallback", {"ip_format": None}),
        ("timestamp.iso", {"timestamp_format": "iso"}),
        ("timestamp.posix", {"timestamp_format": "posix"}),
        ("timestamp.invalid_fallback", {"timestamp_format": "invalid_format"}),
        ("timestamp.none_fallback", {"timestamp_format": None}),
    ],
)
def test_nested_list_optional_and_mapping_serialization_matches_legacy_golden(
    case: str, kwargs: dict[str, Any], probe: SerializationGoldenProbe
) -> None:
    expected = serialization_golden()["primitives"][case]
    assert probe.as_primitives(**kwargs) == expected


def test_encoded_ip_bytes_are_exact_for_scalar_list_optional_and_compound_fields(
    probe: SerializationGoldenProbe,
) -> None:
    actual = probe.as_primitives(ip_format="encoded_bytes")
    expected = serialization_golden()["probe_input"]

    assert base64.b64decode(actual["ip_field"]) == ip_address(expected["ip_field"]).packed
    assert [base64.b64decode(value) for value in actual["ips_in_list"]] == [
        ip_address(value).packed for value in expected["ips_in_list"]
    ]
    assert base64.b64decode(actual["ip_as_optional"]) == ip_address(expected["ip_as_optional"]).packed
    assert (
        base64.b64decode(actual["inner_model_field"]["nested_ip_field"])
        == ip_address(expected["inner_model_field"]["nested_ip_field"]).packed
    )


def test_posix_dates_cover_top_level_mapping_and_compound_fields(probe: SerializationGoldenProbe) -> None:
    actual = probe.as_primitives(timestamp_format="posix")
    expected_epoch = int(
        datetime.fromisoformat(
            serialization_golden()["probe_input"]["timestamp_field"].replace("Z", "+00:00")
        ).timestamp()
    )

    assert actual["timestamp_field"] == expected_epoch
    assert actual["timestamp_in_mapping"] == {"key": expected_epoch}
    assert actual["inner_model_field"]["nested_timestamp_field"] == expected_epoch


def test_related_duplicates_and_tuple_ids_match_frozen_outcomes() -> None:
    goldens = serialization_golden()
    duplicate = Related.model_validate({"id": "indicator-2", "ids": ["indicator-1", "indicator-2"]})
    tuple_ids = Related.model_validate({"id": "indicator-2", "ids": ("indicator-1", "indicator-2")})

    assert duplicate.as_primitives() == goldens["related_duplicate"]
    assert duplicate.ids == ["indicator-1", "indicator-2"]
    assert tuple_ids.as_primitives() == goldens["related_tuple"]
    assert tuple_ids.ids == ["indicator-1", "indicator-2"]


def test_hit_related_id_propagates_and_full_defaults_match_legacy_golden() -> None:
    goldens = serialization_golden()
    related_hit = Hit.model_validate(
        {"howler": {"analytic": "Test Analytic", "hash": "a"}, "related": {"id": "indicator-3"}}
    )
    assert related_hit.related is not None
    assert related_hit.related.id == "indicator-3"
    assert related_hit.related.ids == ["indicator-3"]

    default_hit = Hit.model_validate({"howler": {"id": "hit-2", "analytic": "a", "hash": "abcd"}})
    primitives = default_hit.as_primitives()
    primitives.pop("timestamp", None)
    assert primitives == goldens["hit_default_without_timestamp"]
