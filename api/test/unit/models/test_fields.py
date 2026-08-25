"""Differential tests for reusable Pydantic/DSL field types."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from pydantic import ConfigDict, TypeAdapter

from howler import odm
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

CLASSIFICATION_CONFIG = str(Path(__file__).parents[2] / "classification.yml")
TYPE_ADAPTER_CONFIG = ConfigDict(arbitrary_types_allowed=True)
VALID_TIMESTAMP = "2024-01-02T03:04:05.000000Z"


def _validate(annotation: Any, value: Any) -> Any:
    return TypeAdapter(annotation, config=TYPE_ADAPTER_CONFIG).validate_python(value)


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (odm.ClassificationObject, ClassificationValue)):
        return str(value)
    return value


@pytest.mark.parametrize(
    ("legacy_field", "annotation", "valid_value", "invalid_value"),
    [
        (odm.Boolean(), boolean(), "value", None),
        (odm.Keyword(), keyword(), 123, b"bytes"),
        (odm.EmptyableKeyword(), emptyable_keyword(), "", b"bytes"),
        (odm.UpperKeyword(), upper_keyword(), "MiXeD", b"bytes"),
        (odm.LowerKeyword(), lower_keyword(), "MiXeD", b"bytes"),
        (odm.CaseInsensitiveKeyword(), case_insensitive_keyword(), "MiXeD", b"bytes"),
        (odm.ValidatedKeyword(r"^[a-z]+$"), validated_keyword(r"^[a-z]+$"), "valid", "INVALID"),
        (odm.IP(), ip(), "127.0.0.1", "999.0.0.1"),
        (odm.Domain(strict=False), domain(strict=False), "EXAMPLE.com", "invalid!domain"),
        (odm.Email(), email(), "Example@example.com", "not-an-email"),
        (odm.URI(), uri(), "HTTPS://Example.com/path", "not a uri"),
        (odm.URIPath(), uri_path(), "/path?q=1", "path"),
        (odm.MAC(), mac(), "aa:bb:cc:dd:ee:ff", "not-a-mac"),
        (odm.PhoneNumber(), phone_number(), "613-555-0123", "not-a-phone"),
        (odm.SSDeepHash(), ssdeep_hash(), "3:abc:def", "invalid"),
        (odm.SHA1(), sha1(), "a" * 40, "a" * 39),
        (odm.SHA256(), sha256(), "a" * 64, "a" * 63),
        (odm.HowlerHash(), howler_hash(), "a" * 32, "G"),
        (odm.MD5(), md5(), "a" * 32, "a" * 31),
        (odm.Platform(), platform(), "Linux", "BSD"),
        (odm.Processor(), processor(), "x64", "arm64"),
        (odm.Enum(["one", "two"]), enum(["one", "two"]), "one", "three"),
        (odm.Text(), text(), "some text", ""),
        (odm.IndexText(), index_text(), 123, None),
        (odm.Integer(min=1, max=3), integer(min=1, max=3), "2", 4),
        (odm.Long(min=1, max=3), long(min=1, max=3), "2", 4),
        (odm.Float(), float_field(), "1.5", "not-a-float"),
        (odm.Date(), date(), VALID_TIMESTAMP, "not-a-date"),
        (odm.Json(), json_field(), {"key": "value"}, {1, 2}),
        (odm.Any(), any_field(), {"anything": object()}, None),
        (
            odm.Classification(yml_config=CLASSIFICATION_CONFIG),
            classification(yml_config=CLASSIFICATION_CONFIG),
            "U//REL TO D1",
            "D//BOB//REL TO SOUP",
        ),
        (
            odm.ClassificationString(yml_config=CLASSIFICATION_CONFIG),
            classification_string(yml_config=CLASSIFICATION_CONFIG),
            "UNRESTRICTED",
            "D//BOB//REL TO SOUP",
        ),
    ],
)
def test_primitive_field_validation_matches_legacy(
    legacy_field: odm._Field,
    annotation: Any,
    valid_value: Any,
    invalid_value: Any,
) -> None:
    """Accepted values normalize identically and rejected values remain rejected."""
    assert _normalize(_validate(annotation, valid_value)) == _normalize(legacy_field.check(valid_value))

    legacy_error = None
    new_error = None
    try:
        legacy_field.check(invalid_value)
    except Exception as error:
        legacy_error = error
    try:
        _validate(annotation, invalid_value)
    except Exception as error:
        new_error = error

    assert (legacy_error is None) == (new_error is None)


def test_uuid_generation_and_explicit_value() -> None:
    """Identifiers are generated for null input and explicit values are preserved."""
    generated = _validate(uuid(), None)
    assert isinstance(generated, str)
    assert generated
    assert _validate(uuid(), "explicit") == "explicit"


@pytest.mark.parametrize(
    ("legacy_field", "annotation", "input_value"),
    [
        (odm.Keyword(default="fallback"), keyword(default="fallback"), ""),
        (odm.Text(default="fallback"), text(default="fallback"), None),
        (odm.Integer(default=7), integer(default=7), ""),
        (odm.Float(default=1.5), float_field(default=1.5), 0),
        (odm.Enum(["one", "two"], default="one"), enum(["one", "two"], default="one"), None),
        (
            odm.ClassificationString(default="UNRESTRICTED", yml_config=CLASSIFICATION_CONFIG),
            classification_string(default="UNRESTRICTED", yml_config=CLASSIFICATION_CONFIG),
            "",
        ),
    ],
)
def test_explicit_empty_values_use_configured_defaults(
    legacy_field: odm._Field,
    annotation: Any,
    input_value: Any,
) -> None:
    """Field defaults apply to the same explicit empty values as the legacy validators."""
    assert _validate(annotation, input_value) == legacy_field.check(input_value)


@pytest.mark.parametrize(
    ("legacy_field", "annotation", "value"),
    [
        (odm.IP(), ip(), None),
        (odm.Domain(), domain(), ""),
        (odm.Email(), email(), ""),
        (odm.URI(), uri(), ""),
        (odm.Date(), date(), None),
    ],
)
def test_nullable_legacy_primitives_remain_nullable(
    legacy_field: odm._Field,
    annotation: Any,
    value: Any,
) -> None:
    """Explicit null-like values accepted by legacy fields remain accepted."""
    assert _validate(annotation, value) == legacy_field.check(value)


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
def test_each_primitive_has_an_explicit_dsl_mapping(
    annotation: Any,
    expected_mapping: dict[str, Any],
) -> None:
    """Every reusable primitive exposes its required Elasticsearch mapping."""
    model_type = type(
        f"Mapping{expected_mapping['type']}{id(annotation)}",
        (HowlerESModel,),
        {"__annotations__": {"value": annotation}},
    )
    actual = model_registry.mapping(model_type)["properties"]["value"]
    assert actual.items() >= expected_mapping.items()
