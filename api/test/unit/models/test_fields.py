"""Deterministic Pydantic field behavior checked against cutover goldens."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ConfigDict, TypeAdapter

from howler.models import (
    ClassificationValue,
    HowlerESModel,
    any_field,
    boolean,
    case_insensitive_keyword,
    classification,
    classification_string,
    date,
    domain,
    email,
    emptyable_keyword,
    enum,
    float_field,
    howler_hash,
    index_text,
    integer,
    ip,
    json_field,
    keyword,
    long,
    lower_keyword,
    mac,
    md5,
    model_registry,
    phone_number,
    platform,
    processor,
    sha1,
    sha256,
    ssdeep_hash,
    text,
    upper_keyword,
    uri,
    uri_path,
    uuid,
    validated_keyword,
)
from howler.models.registry import field_metadata

CLASSIFICATION_CONFIG = str(Path(__file__).parents[2] / "classification.yml")
TYPE_ADAPTER_CONFIG = ConfigDict(arbitrary_types_allowed=True)
FIXTURE_PATH = Path(__file__).parent / "fixtures/legacy_field_validation_goldens.json"
FIELD_GOLDENS = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
FIELD_GOLDEN_SHA256 = "e97490f8c3ccfd921a199ed314a5d5da1916e2644bc4e7a5a927947e6d0772ae"
STEP9_SOURCE_HEAD = "3071fc4ea45d4b2dd44a7ee1646095426097d061"

FIELD_ANNOTATIONS: dict[str, Any] = {
    "Boolean": boolean(),
    "Keyword": keyword(),
    "EmptyableKeyword": emptyable_keyword(),
    "UpperKeyword": upper_keyword(),
    "LowerKeyword": lower_keyword(),
    "CaseInsensitiveKeyword": case_insensitive_keyword(),
    "ValidatedKeyword": validated_keyword(r"^[a-z]+$"),
    "IP": ip(),
    "Domain": domain(strict=False),
    "Email": email(),
    "URI": uri(),
    "URIPath": uri_path(),
    "MAC": mac(),
    "PhoneNumber": phone_number(),
    "SSDeepHash": ssdeep_hash(),
    "SHA1": sha1(),
    "SHA256": sha256(),
    "HowlerHash": howler_hash(),
    "MD5": md5(),
    "Platform": platform(),
    "Processor": processor(),
    "Enum": enum(["one", "two"]),
    "Text": text(),
    "IndexText": index_text(),
    "Integer": integer(min=1, max=3),
    "Long": long(min=1, max=3),
    "Float": float_field(),
    "Date": date(),
    "Json": json_field(),
    "Any": any_field(),
    "Classification": classification(yml_config=CLASSIFICATION_CONFIG),
    "ClassificationString": classification_string(yml_config=CLASSIFICATION_CONFIG),
}


def _normalize(value: Any) -> Any:
    if type(value) is object:
        return "<object>"
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, ClassificationValue):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def _outcome(annotation: Any, value: Any) -> dict[str, Any]:
    try:
        result = TypeAdapter(annotation, config=TYPE_ADAPTER_CONFIG).validate_python(value)
        return {"accepted": True, "normalized": _normalize(result)}
    except Exception:
        return {"accepted": False}


def _restore_fixture_input(value: Any) -> Any:
    if isinstance(value, dict) and set(value) == {"$object"}:
        return object()
    if isinstance(value, dict) and set(value) == {"$bytes"}:
        return value["$bytes"].encode()
    if isinstance(value, dict) and set(value) == {"$set"}:
        return set(value["$set"])
    if isinstance(value, dict):
        return {key: _restore_fixture_input(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_restore_fixture_input(item) for item in value]
    return value


def _assert_matches_golden(actual: dict[str, Any], expected: dict[str, Any]) -> None:
    """Compare acceptance and exact normalized output, ignoring implementation error classes."""
    assert actual["accepted"] is expected["accepted"]
    if expected["accepted"]:
        assert actual["normalized"] == expected["normalized"]


def test_field_golden_fixture_is_well_formed() -> None:
    assert FIELD_GOLDENS["fixture_version"] == 1
    assert FIELD_GOLDENS["source"].startswith("Legacy ODM")
    assert FIELD_GOLDENS["capture"]["source_head"] == STEP9_SOURCE_HEAD
    assert FIELD_GOLDENS["capture"]["command"].startswith("One-off api/.venv/bin/python capture")
    assert hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest() == FIELD_GOLDEN_SHA256
    assert set(FIELD_GOLDENS["primitive_cases"]) == set(FIELD_ANNOTATIONS)


@pytest.mark.parametrize("name", sorted(FIELD_ANNOTATIONS))
def test_primitive_validation_matches_frozen_outcomes(name: str) -> None:
    """All former differential valid/invalid probes use immutable expected outcomes."""
    annotation = FIELD_ANNOTATIONS[name]
    expected = FIELD_GOLDENS["primitive_cases"][name]
    valid_input = _restore_fixture_input(expected["valid_input"])
    if name == "Any":
        assert type(valid_input["anything"]) is object
    _assert_matches_golden(_outcome(annotation, valid_input), expected["valid"])
    _assert_matches_golden(_outcome(annotation, _restore_fixture_input(expected["invalid_input"])), expected["invalid"])


@pytest.mark.parametrize(
    ("name", "annotation", "value"),
    [
        ("Keyword", keyword(default="fallback"), ""),
        ("Text", text(default="fallback"), None),
        ("Integer", integer(default=7), ""),
        ("Float", float_field(default=1.5), 0),
        ("Enum", enum(["one", "two"], default="one"), None),
        (
            "ClassificationString",
            classification_string(default="UNRESTRICTED", yml_config=CLASSIFICATION_CONFIG),
            "",
        ),
    ],
)
def test_explicit_empty_values_match_frozen_defaults(name: str, annotation: Any, value: Any) -> None:
    expected = FIELD_GOLDENS["default_cases"][name]
    assert value == expected["input"]
    _assert_matches_golden(_outcome(annotation, value), expected["expected"])


@pytest.mark.parametrize(
    ("name", "annotation", "value"),
    [
        ("IP", ip(), None),
        ("Domain", domain(), ""),
        ("Email", email(), ""),
        ("URI", uri(), ""),
        ("Date", date(), None),
    ],
)
def test_nullable_primitive_outcomes_are_frozen(name: str, annotation: Any, value: Any) -> None:
    expected = FIELD_GOLDENS["nullable_cases"][name]
    assert value == expected["input"]
    _assert_matches_golden(_outcome(annotation, value), expected["expected"])


def test_ip_validation_metadata_is_explicit() -> None:
    metadata = field_metadata(ip())
    assert metadata is not None
    assert "validation_regex" in dict(metadata.options)


@pytest.mark.parametrize(
    ("annotation", "expected_mapping"),
    [
        (any_field(), {"type": "keyword", "index": False, "doc_values": False}),
        (boolean(), {"type": "boolean"}),
        (case_insensitive_keyword(), {"type": "keyword", "normalizer": "lowercase_normalizer"}),
        (classification(yml_config=CLASSIFICATION_CONFIG), {"type": "keyword"}),
        (classification_string(yml_config=CLASSIFICATION_CONFIG), {"type": "keyword"}),
        (date(), {"type": "date", "format": "date_optional_time||epoch_millis"}),
        (domain(), {"type": "keyword"}),
        (email(), {"type": "keyword"}),
        (emptyable_keyword(), {"type": "keyword"}),
        (enum(["one"]), {"type": "keyword"}),
        (float_field(), {"type": "float"}),
        (howler_hash(), {"type": "keyword", "normalizer": "lowercase_normalizer"}),
        (index_text(), {"type": "text"}),
        (integer(), {"type": "integer"}),
        (ip(), {"type": "ip"}),
        (json_field(), {"type": "keyword"}),
        (keyword(), {"type": "keyword"}),
        (long(), {"type": "long"}),
        (lower_keyword(), {"type": "keyword"}),
        (mac(), {"type": "keyword"}),
        (md5(), {"type": "keyword", "normalizer": "lowercase_normalizer"}),
        (phone_number(), {"type": "keyword"}),
        (platform(), {"type": "keyword"}),
        (processor(), {"type": "keyword"}),
        (sha1(), {"type": "keyword", "normalizer": "lowercase_normalizer"}),
        (sha256(), {"type": "keyword", "normalizer": "lowercase_normalizer"}),
        (ssdeep_hash(), {"type": "text", "analyzer": "text_fuzzy"}),
        (text(), {"type": "text"}),
        (upper_keyword(), {"type": "keyword"}),
        (uri(), {"type": "keyword"}),
        (uri_path(), {"type": "keyword"}),
        (uuid(), {"type": "keyword"}),
        (validated_keyword(r"^[a-z]+$"), {"type": "keyword"}),
    ],
)
def test_each_primitive_has_an_explicit_dsl_mapping(annotation: Any, expected_mapping: dict[str, Any]) -> None:
    """Every reusable primitive exposes its required Elasticsearch mapping."""
    model_type = type(
        f"Mapping{expected_mapping['type']}{id(annotation)}",
        (HowlerESModel,),
        {"__annotations__": {"value": annotation}},
    )
    actual = model_registry.mapping(model_type)["properties"]["value"]
    assert actual.items() >= expected_mapping.items()
