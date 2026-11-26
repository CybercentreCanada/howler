"""Validation, annotation, serialization, and mapping behavior for reusable fields."""

from __future__ import annotations

import base64
from datetime import datetime
from ipaddress import ip_address
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Any, get_args, get_origin

import pytest
from pydantic import ConfigDict, Field, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

from howler.common.classification import InvalidClassification
from howler.models import (
    ClassificationValue,
    HowlerEmbeddedModel,
    HowlerESModel,
    HowlerModelValidationError,
    any_field,
    boolean,
    case_insensitive_keyword,
    classification,
    classification_string,
    compound,
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
    list_field,
    long,
    lower_keyword,
    mac,
    mapping,
    md5,
    model_registry,
    phone_number,
    platform,
    processor,
    register_model,
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
from howler.models.fields import HowlerFieldMetadata, _make_annotated
from howler.models.registry import field_metadata

CLASSIFICATION_CONFIG = str(Path(__file__).parents[2] / "classification.yml")
TYPE_ADAPTER_CONFIG = ConfigDict(arbitrary_types_allowed=True)


@register_model(index=True, store=True, embedded=True)
class SerializationChild(HowlerEmbeddedModel):
    """Nested IP and timestamp values used in primitive output checks."""

    address: ip()
    created: date()
    address_text: keyword()
    timestamp_text: keyword()


@register_model(index=True, store=True)
class SerializationProbe(HowlerESModel):
    """Scalar and container fields used in primitive output checks."""

    address: ip()
    addresses: list_field(ip())
    optional_address: ip(optional=True)
    ip_text: keyword()
    ip_texts: list_field(keyword())
    optional_ip_text: keyword(optional=True)
    created: date()
    created_by_key: mapping(date())
    timestamp_text: keyword()
    child: compound(SerializationChild)


class NullableFieldModel(HowlerESModel):
    """Optional scalar and container fields keep their wrapped validation behavior."""

    maybe: keyword(optional=True, alias="external_value")  # pyright: ignore[reportInvalidTypeForm]
    disabled: keyword(optional=True, index=False, store=False)  # pyright: ignore[reportInvalidTypeForm]
    with_default: keyword(optional=True, default="fallback")  # pyright: ignore[reportInvalidTypeForm]
    items: list_field(keyword(), optional=True)  # pyright: ignore[reportInvalidTypeForm]
    values: mapping(integer(), optional=True, index=True, store=True)  # pyright: ignore[reportInvalidTypeForm]


class GeneratedIdentifierModel(HowlerEmbeddedModel):
    """Model used to check generated and explicit identifiers."""

    identifier: uuid()


@pytest.mark.parametrize(
    ("annotation", "value", "expected"),
    [
        (boolean(), "value", True),
        (keyword(), 123, "123"),
        (emptyable_keyword(), "", ""),
        (upper_keyword(), "MiXeD", "MIXED"),
        (lower_keyword(), "MiXeD", "mixed"),
        (case_insensitive_keyword(), "MiXeD", "MiXeD"),
        (validated_keyword(r"^[a-z]+$"), "valid", "valid"),
        (ip(), "127.0.0.1", "127.0.0.1"),
        (domain(strict=False), "EXAMPLE.com", "example.com"),
        (email(), "Example@example.com", "example@example.com"),
        (uri(), "HTTPS://Example.com/path", "https://example.com/path"),
        (uri_path(), "/path?q=1", "/path?q=1"),
        (mac(), "aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff"),
        (phone_number(), "613-555-0123", "613-555-0123"),
        (ssdeep_hash(), "3:abc:def", "3:abc:def"),
        (sha1(), "a" * 40, "a" * 40),
        (sha256(), "a" * 64, "a" * 64),
        (howler_hash(), "a" * 32, "a" * 32),
        (md5(), "a" * 32, "a" * 32),
        (platform(), "Linux", "Linux"),
        (processor(), "x64", "x64"),
        (enum(["one", "two"]), "one", "one"),
        (text(), "some text", "some text"),
        (index_text(), 123, "123"),
        (integer(min=1, max=3), "2", 2),
        (long(min=1, max=3), "2", 2),
        (float_field(), "1.5", 1.5),
        (date(), "2024-01-02T03:04:05.000000Z", datetime.fromisoformat("2024-01-02T03:04:05+00:00")),
        (json_field(), {"key": "value"}, '{"key": "value"}'),
        (classification(yml_config=CLASSIFICATION_CONFIG), "U", "UNRESTRICTED"),
        (classification_string(yml_config=CLASSIFICATION_CONFIG), "UNRESTRICTED", "UNRESTRICTED"),
    ],
)
def test_primitive_fields_validate_and_normalize(annotation: Any, value: Any, expected: Any) -> None:
    """Field validators coerce valid inputs and return their normalized values."""
    result = TypeAdapter(annotation, config=TYPE_ADAPTER_CONFIG).validate_python(value)
    if isinstance(expected, str) and isinstance(result, ClassificationValue):
        assert str(result).startswith(expected)
    else:
        assert result == expected


@pytest.mark.parametrize(
    ("annotation", "value"),
    [
        (keyword(), b"bytes"),
        (emptyable_keyword(), b"bytes"),
        (upper_keyword(), b"bytes"),
        (lower_keyword(), b"bytes"),
        (case_insensitive_keyword(), b"bytes"),
        (validated_keyword(r"^[a-z]+$"), "INVALID"),
        (ip(), "999.0.0.1"),
        (domain(), "invalid!domain"),
        (email(), "not-an-email"),
        (uri(), "not a uri"),
        (uri_path(), "path"),
        (mac(), "not-a-mac"),
        (phone_number(), "not-a-phone"),
        (ssdeep_hash(), "invalid"),
        (sha1(), "a" * 39),
        (sha256(), "a" * 63),
        (howler_hash(), "G"),
        (md5(), "a" * 31),
        (platform(), "BSD"),
        (processor(), "arm64"),
        (enum(["one", "two"]), "three"),
        (text(), ""),
        (integer(min=1, max=3), 0),
        (integer(min=1, max=3), 4),
        (long(min=1, max=3), 0),
        (long(min=1, max=3), 4),
        (float_field(), "not-a-float"),
        (date(), "not-a-date"),
        (json_field(), {"not-json"}),
        (classification_string(yml_config=CLASSIFICATION_CONFIG), "D//BOB//REL TO SOUP"),
    ],
)
def test_primitive_fields_reject_invalid_values(annotation: Any, value: Any) -> None:
    """Invalid values are rejected by the field's own validation contract."""
    with pytest.raises(ValidationError):
        TypeAdapter(annotation, config=TYPE_ADAPTER_CONFIG).validate_python(value)


def test_howler_hash_accepts_lengths_from_one_through_sixty_four() -> None:
    """Howler hashes accept every supported non-empty hexadecimal length."""
    adapter = TypeAdapter(howler_hash())
    for length in range(1, 65):
        value = "a" * length
        assert adapter.validate_python(value) == value

    for length in (0, 65):
        with pytest.raises(ValidationError):
            adapter.validate_python("a" * length)


def test_classification_field_rejects_unknown_levels() -> None:
    """Classification fields report unknown levels with the classification domain error."""
    with pytest.raises(InvalidClassification):
        TypeAdapter(classification(yml_config=CLASSIFICATION_CONFIG), config=TYPE_ADAPTER_CONFIG).validate_python(
            "D//BOB//REL TO SOUP"
        )


def test_field_defaults_and_nullable_values() -> None:
    """Configured defaults handle empty input while nullable fields accept explicit nulls."""
    assert TypeAdapter(keyword(default="fallback")).validate_python("") == "fallback"
    assert TypeAdapter(text(default="fallback")).validate_python(None) == "fallback"
    assert TypeAdapter(integer(default=7)).validate_python("") == 7
    assert TypeAdapter(float_field(default=1.5)).validate_python(0) == 1.5
    assert TypeAdapter(boolean()).validate_python(None) is False
    assert TypeAdapter(index_text()).validate_python(None) == "None"
    assert TypeAdapter(enum(["one", "two"], default="one")).validate_python(None) == "one"
    assert (
        TypeAdapter(classification_string(default="UNRESTRICTED", yml_config=CLASSIFICATION_CONFIG)).validate_python("")
        == "UNRESTRICTED"
    )
    assert TypeAdapter(date()).validate_python(None) is None
    assert TypeAdapter(ip()).validate_python(None) is None
    assert TypeAdapter(domain()).validate_python("") is None
    assert TypeAdapter(email()).validate_python("") is None
    assert TypeAdapter(uri()).validate_python("") is None


def test_keyword_can_disable_string_coercion() -> None:
    """Keyword fields optionally require string input instead of coercing values."""
    adapter = TypeAdapter(keyword(coerce=False))
    assert adapter.validate_python("value") == "value"
    with pytest.raises(ValidationError):
        adapter.validate_python(123)


def test_legacy_empty_hit_fields_are_normalized_during_ingest(monkeypatch: pytest.MonkeyPatch) -> None:
    from howler.models.hit import Hit
    from howler.services import hit_service

    monkeypatch.setattr(hit_service, "datastore", lambda: SimpleNamespace(hit=SimpleNamespace(model_class=Hit)))
    hit, warnings = hit_service.convert_hit({"howler.analytic": "Sample", "howler.detection": "", "tags": None}, False)
    assert warnings == []
    assert hit.howler.detection is None
    document = hit.as_primitives()
    assert document["tags"] == [] and "detection" not in document["howler"]

    assert TypeAdapter(list_field(keyword(), optional=True, default=[])).validate_python(None) is None
    assert TypeAdapter(emptyable_keyword(optional=True)).validate_python("") == ""
    assert TypeAdapter(boolean(optional=True)).validate_python(None) is None
    assert TypeAdapter(integer(optional=True)).validate_python(None) is None
    assert TypeAdapter(float_field(optional=True, default=0)).validate_python(None) is None
    assert TypeAdapter(json_field(optional=True)).validate_python(None) is None
    assert TypeAdapter(uuid(optional=True)).validate_python(None) is None
    with pytest.raises(ValidationError):
        TypeAdapter(keyword()).validate_python("")
    with pytest.raises(ValidationError):
        TypeAdapter(list_field(keyword(), optional=True)).validate_python([""])


def test_optional_metadata_preserves_mapping_and_validation() -> None:
    class Probe(HowlerESModel):
        address: ip(
            optional=True,
            alias="ip_address",
            index=False,
            store=False,
            copyto="__text__",
            deprecated=False,
            reference="new",
            sync=False,
        )

    details = model_registry.fields(Probe)["ip_address"].metadata
    assert details is not None and details.kind == "IP" and details.optional
    assert details.index is False and details.store is False and details.sync is False
    assert details.copy_to == ("__text__",) and details.reference == "new" and not details.deprecated
    assert "validation_regex" in dict(details.options)
    es_field = model_registry.mapping(Probe)["properties"]["ip_address"]
    assert es_field["type"] == "ip" and es_field["index"] is False and es_field["copy_to"] == "__text__"
    assert Probe.model_validate({"ip_address": "192.0.2.1"}).as_primitives(ip_format="int") == {
        "ip_address": int(ip_address("192.0.2.1"))
    }
    with pytest.raises(HowlerModelValidationError):
        Probe.model_validate({"ip_address": "invalid"})


@pytest.mark.parametrize(
    ("options", "wire", "stored"),
    [
        ({"alias": "wire", "es_name": "stored"}, "wire", "stored"),
        ({"alias": "wire", "es_name": "outer_stored"}, "wire", "outer_stored"),
        ({"alias": "outer_wire"}, "outer_wire", "outer_wire"),
        ({"alias": "outer_wire", "es_name": "outer_stored"}, "outer_wire", "outer_stored"),
    ],
)
def test_optional_wire_alias_and_storage_name(options, wire, stored):
    annotation = ip(optional=True, index=False, **options)
    probe = type("Probe", (HowlerESModel,), {"__annotations__": {"address": annotation}})
    assert set(model_registry.fields(probe)) == {wire}
    assert probe.model_validate({wire: "192.0.2.1"}).as_primitives() == {wire: "192.0.2.1"}
    properties = model_registry.mapping(probe)["properties"]
    assert set(properties) == {stored}
    assert properties[stored]["type"] == "ip" and properties[stored]["index"] is False


@pytest.mark.parametrize("array", [False, True], ids=["scalar", "list"])
@pytest.mark.parametrize("builder, indexed", [(ip, None), (ip, False), (ip, True), (text, False)])
def test_optional_index_reaches_the_storage_field(builder, indexed, array):
    names = {"alias": "wire", "es_name": "stored"}
    options = {"index": indexed, "copyto": "__text__"}
    annotation = (
        list_field(builder(**options), optional=True, **names) if array else builder(optional=True, **options, **names)
    )
    probe = type("Probe", (HowlerESModel,), {"__annotations__": {"value": annotation}})
    leaf = model_registry.flat_fields(probe)["wire"]
    assert leaf.multivalued is array and leaf.metadata.index is indexed
    storage = {"type": "ip" if builder is ip else "text", "copy_to": "__text__"}
    if indexed is not None:
        storage["index"] = indexed
        if builder is ip:
            storage["doc_values"] = indexed
    assert model_registry.mapping(probe)["properties"] == {"stored": storage}

    address = "192.0.2.1"
    model = probe.model_validate({"wire": [address] if array else address})
    output = int(ip_address(address)) if builder is ip else address
    assert model.as_primitives(ip_format="int") == {"wire": [output] if array else output}


def test_any_field_accepts_arbitrary_python_values() -> None:
    """An arbitrary field leaves its input value unchanged for the application."""
    marker = object()
    assert TypeAdapter(any_field(), config=TYPE_ADAPTER_CONFIG).validate_python(marker) is marker


def test_uuid_field_generates_distinct_defaults_and_accepts_explicit_values() -> None:
    """Identifier fields generate independent defaults and preserve caller-provided values."""
    first = GeneratedIdentifierModel.model_validate({})
    second = GeneratedIdentifierModel.model_validate({})
    explicit = GeneratedIdentifierModel.model_validate({"identifier": "given-id"})

    assert first.identifier
    assert second.identifier
    assert first.identifier != second.identifier
    assert explicit.identifier == "given-id"


def test_classification_values_normalize_and_expose_access_parts() -> None:
    """Classification values normalize labels, compare for equality, and expose access fields."""
    unrestricted = TypeAdapter(
        classification(yml_config=CLASSIFICATION_CONFIG), config=TYPE_ADAPTER_CONFIG
    ).validate_python("U//REL TO D1, D2")
    restricted = TypeAdapter(
        classification(yml_config=CLASSIFICATION_CONFIG), config=TYPE_ADAPTER_CONFIG
    ).validate_python("R//GOD//G1")

    assert isinstance(unrestricted, ClassificationValue)
    assert unrestricted.value == "UNRESTRICTED//REL TO DEPARTMENT 1, DEPARTMENT 2"
    assert str(unrestricted) == unrestricted.value
    assert str(restricted) == "RESTRICTED//ADMIN//ANY/GROUP 1"
    normalized_unrestricted = TypeAdapter(
        classification(yml_config=CLASSIFICATION_CONFIG), config=TYPE_ADAPTER_CONFIG
    ).validate_python("UNRESTRICTED//REL TO DEPARTMENT 1, DEPARTMENT 2")
    assert unrestricted == normalized_unrestricted
    assert unrestricted != restricted

    access_parts = unrestricted.get_access_control_parts()
    assert set(access_parts) == {"__access_lvl__", "__access_req__", "__access_grp1__", "__access_grp2__"}
    assert access_parts["__access_lvl__"] == 100
    assert isinstance(access_parts["__access_req__"], list)
    assert isinstance(access_parts["__access_grp1__"], list)
    assert isinstance(access_parts["__access_grp2__"], list)

    access_limited = TypeAdapter(
        classification(yml_config=CLASSIFICATION_CONFIG), config=TYPE_ADAPTER_CONFIG
    ).validate_python("U//REL TO D1")
    assert access_limited.value == "UNRESTRICTED//ANY"
    assert str(access_limited) == "UNRESTRICTED//ANY"


def test_ip_and_date_serialization_modes_cover_nested_containers() -> None:
    """Primitive output formats apply consistently to scalar, list, mapping, and compound fields."""
    model = SerializationProbe.model_validate(
        {
            "address": "127.0.0.1",
            "addresses": ["1.1.1.1", "ff02::1"],
            "optional_address": "192.168.0.1",
            "ip_text": "192.0.2.1",
            "ip_texts": ["192.0.2.2", "2001:db8::1"],
            "optional_ip_text": "192.0.2.3",
            "created": "2026-01-01T00:00:00.000000Z",
            "created_by_key": {"key": "2026-01-01T00:00:00.000000Z"},
            "timestamp_text": "2026-01-01T00:00:00.000000Z",
            "child": {
                "address": "10.0.0.1",
                "created": "2026-01-01T00:00:00.000000Z",
                "address_text": "10.0.0.2",
                "timestamp_text": "2026-01-01T00:00:00.000000Z",
            },
        }
    )

    encoded = model.as_primitives(ip_format="encoded_bytes")
    assert base64.b64decode(encoded["address"]) == ip_address("127.0.0.1").packed
    assert [base64.b64decode(value) for value in encoded["addresses"]] == [
        ip_address("1.1.1.1").packed,
        ip_address("ff02::1").packed,
    ]
    assert base64.b64decode(encoded["optional_address"]) == ip_address("192.168.0.1").packed
    assert base64.b64decode(encoded["child"]["address"]) == ip_address("10.0.0.1").packed
    integers = model.as_primitives(ip_format="int")
    assert integers["address"] == int(ip_address("127.0.0.1"))
    assert integers["addresses"] == [int(ip_address(value)) for value in ("1.1.1.1", "ff02::1")]
    assert integers["optional_address"] == int(ip_address("192.168.0.1"))
    assert integers["child"]["address"] == int(ip_address("10.0.0.1"))
    string_ips = model.as_primitives(ip_format="str")
    assert string_ips["address"] == "127.0.0.1"
    assert string_ips["addresses"] == ["1.1.1.1", "ff02::1"]

    for ip_mode in ("encoded_bytes", "int", "str", "unsupported", None):
        primitives = model.as_primitives(ip_format=ip_mode)
        assert primitives["ip_text"] == "192.0.2.1"
        assert primitives["ip_texts"] == ["192.0.2.2", "2001:db8::1"]
        assert primitives["optional_ip_text"] == "192.0.2.3"
        assert primitives["child"]["address_text"] == "10.0.0.2"
        assert primitives["timestamp_text"] == "2026-01-01T00:00:00.000000Z"
        assert primitives["child"]["timestamp_text"] == "2026-01-01T00:00:00.000000Z"

    posix = model.as_primitives(timestamp_format="posix")
    assert posix["created"] == 1767225600
    assert posix["created_by_key"] == {"key": 1767225600}
    assert posix["child"]["created"] == 1767225600
    iso = model.as_primitives(timestamp_format="iso")
    assert iso["created"] == "2026-01-01T00:00:00+00:00"
    assert iso["created_by_key"] == {"key": "2026-01-01T00:00:00+00:00"}

    fallback = model.as_primitives(ip_format="unsupported", timestamp_format="unsupported")
    assert fallback["address"] == "127.0.0.1"
    assert fallback["created"] == "2026-01-01T00:00:00.000000Z"
    none_fallback = model.as_primitives(ip_format=None, timestamp_format=None)
    assert none_fallback["address"] == "127.0.0.1"
    assert none_fallback["created"] == "2026-01-01T00:00:00.000000Z"


def test_make_annotated_preserves_generic_base_and_metadata_order() -> None:
    """Generic annotation arguments and metadata retain their declared order."""
    first_metadata = object()
    second_metadata = object()
    base_annotation = dict[str, list[int]]

    annotation = _make_annotated(base_annotation, first_metadata, second_metadata)

    assert get_origin(annotation) is Annotated
    assert get_args(annotation) == (base_annotation, first_metadata, second_metadata)


def test_list_field_keeps_child_and_container_metadata_separate() -> None:
    """List metadata stays on the container while child field metadata stays nested."""
    annotation = list_field(keyword(copyto="search", deprecated=True), alias="items", description="Searchable items")

    container_type, *container_metadata = get_args(annotation)
    child_type, *child_metadata = get_args(get_args(container_type)[0])
    container_metadata_value = next(item for item in container_metadata if isinstance(item, HowlerFieldMetadata))
    child_metadata_value = next(item for item in child_metadata if isinstance(item, HowlerFieldMetadata))
    container_field = next(item for item in container_metadata if isinstance(item, FieldInfo))

    assert get_origin(annotation) is Annotated
    assert get_origin(container_type) is list
    assert child_type is str
    assert container_metadata_value.kind == "List"
    assert child_metadata_value.kind == "Keyword"
    assert child_metadata_value.copy_to == ("search",)
    assert container_metadata.index(container_metadata_value) < container_metadata.index(container_field)
    assert container_field.alias == "items"
    assert container_field.description == "Searchable items"


def test_nullable_annotations_preserve_ordered_unions() -> None:
    """Nullable wrappers preserve both ordered-union validation branches."""
    first = Annotated[int | str, HowlerFieldMetadata(kind="Keyword"), Field(union_mode="left_to_right")]
    second = Annotated[str | int, HowlerFieldMetadata(kind="Keyword"), Field(union_mode="left_to_right")]

    value = TypeAdapter(tuple[first, second] | None).validate_python(("12", "12"))
    adapter = TypeAdapter(first | None)
    zero = adapter.validate_python("0")
    text_value = adapter.validate_python("not-a-number")

    assert type(value[0]) is int
    assert type(value[1]) is str
    assert value == (12, "12")
    assert adapter.validate_python(None) is None
    assert type(zero) is int and zero == 0
    assert type(text_value) is str and text_value == "not-a-number"


def test_nullable_fields_preserve_validation_defaults_aliases_and_mapping_metadata() -> None:
    """Nullable wrappers preserve nulls, defaults, aliases, validators, and DSL mapping flags."""
    defaults = NullableFieldModel.model_validate({})
    assert defaults.maybe is None
    assert defaults.disabled is None
    assert defaults.with_default == "fallback"
    assert defaults.items is None
    assert defaults.values is None

    explicit_nulls = NullableFieldModel.model_validate(
        {"external_value": None, "disabled": None, "items": None, "values": None}
    )
    assert explicit_nulls.maybe is None
    assert explicit_nulls.items is None
    assert explicit_nulls.values is None

    model = NullableFieldModel.model_validate(
        {"external_value": 123, "items": [1, "two"], "values": {"valid_key": "2"}}
    )
    assert model.maybe == "123"
    assert model.items == ["1", "two"]
    assert model.values == {"valid_key": 2}
    assert model.model_dump(by_alias=True)["external_value"] == "123"

    with pytest.raises(HowlerModelValidationError):
        NullableFieldModel.model_validate({"external_value": b"bytes"})
    with pytest.raises(HowlerModelValidationError):
        NullableFieldModel.model_validate({"items": [b"bytes"]})
    with pytest.raises(HowlerModelValidationError):
        NullableFieldModel.model_validate({"values": {"Invalid-Key": "2"}})

    fields = model_registry.fields(NullableFieldModel)
    disabled = fields["disabled"].metadata
    values = fields["values"].metadata
    assert disabled is not None and disabled.index is False and disabled.store is False
    assert values is not None and values.index is True and values.store is True

    properties = model_registry.mapping(NullableFieldModel)["properties"]
    assert properties["external_value"]["type"] == "keyword"
    assert properties["disabled"]["index"] is False
    assert properties["disabled"]["doc_values"] is False
    assert properties["items"]["type"] == "keyword"
    assert properties["values"]["type"] == "object"


def test_ip_validation_metadata_is_available_to_registry() -> None:
    """IP fields retain their validation metadata when inspected by the registry."""
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
def test_primitive_fields_expose_elasticsearch_mappings(annotation: Any, expected_mapping: dict[str, Any]) -> None:
    """Reusable field constructors expose the Elasticsearch type and key options."""
    model_type = type(
        f"FieldMapping{expected_mapping['type']}{id(annotation)}",
        (HowlerESModel,),
        {"__annotations__": {"value": annotation}},
    )
    actual = model_registry.mapping(model_type)["properties"]["value"]
    assert actual.items() >= expected_mapping.items()
