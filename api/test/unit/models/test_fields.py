from __future__ import annotations

import base64
from datetime import datetime
from ipaddress import ip_address
from pathlib import Path
from typing import Annotated, Any

import pytest
from pydantic import ConfigDict, TypeAdapter, ValidationError

from howler.common.classification import InvalidClassification
from howler.models import (
    IP,
    MAC,
    MD5,
    SHA1,
    SHA256,
    URI,
    Boolean,
    CaseInsensitiveKeyword,
    ClassificationValue,
    Date,
    Domain,
    Email,
    EmptyableKeyword,
    Float,
    HowlerEmbeddedModel,
    HowlerESModel,
    HowlerHash,
    HowlerModelValidationError,
    IndexText,
    Integer,
    Json,
    Keyword,
    Long,
    LowerKeyword,
    PhoneNumber,
    Platform,
    Processor,
    SSDeepHash,
    StrictKeyword,
    Text,
    UpperKeyword,
    URIPath,
    classification,
    classification_string,
    domain,
    enum,
    mapping,
    metadata,
    model_registry,
    validated_keyword,
)

CONFIG = str(Path(__file__).parents[2] / "classification.yml")
ADAPTER_CONFIG = ConfigDict(arbitrary_types_allowed=True)


def _dump_ips(model: Any, ip_format: Any) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_none=True, context={"ip_format": ip_format})


@pytest.mark.parametrize(
    ("annotation", "value", "expected"),
    [
        (Boolean, "value", True),
        (Keyword, 123, "123"),
        (StrictKeyword, "value", "value"),
        (EmptyableKeyword, "", ""),
        (UpperKeyword, "MiXeD", "MIXED"),
        (LowerKeyword, "MiXeD", "mixed"),
        (CaseInsensitiveKeyword, "MiXeD", "MiXeD"),
        (validated_keyword(r"^[a-z]+$"), "valid", "valid"),
        (IP, "127.0.0.1", "127.0.0.1"),
        (Domain, "EXAMPLE.com", "example.com"),
        (domain(strict=False), "EXAMPLE.com", "example.com"),
        (Email, "Example@example.com", "example@example.com"),
        (URI, "HTTPS://Example.com/path", "https://example.com/path"),
        (URIPath, "/path?q=1", "/path?q=1"),
        (MAC, "aa:bb:cc:dd:ee:ff", "aa:bb:cc:dd:ee:ff"),
        (PhoneNumber, "613-555-0123", "613-555-0123"),
        (SSDeepHash, "3:abc:def", "3:abc:def"),
        (SHA1, "a" * 40, "a" * 40),
        (SHA256, "a" * 64, "a" * 64),
        (HowlerHash, "a" * 32, "a" * 32),
        (MD5, "a" * 32, "a" * 32),
        (Platform, "Linux", "Linux"),
        (Processor, "x64", "x64"),
        (enum(["one", "two"]), "one", "one"),
        (Text, "some text", "some text"),
        (IndexText, 123, "123"),
        (Annotated[Integer, metadata(ge=1, le=3)], "2", 2),
        (Annotated[Long, metadata(ge=1, le=3)], "2", 2),
        (Float, "1.5", 1.5),
        (Date, "2024-01-02T03:04:05.000000Z", datetime.fromisoformat("2024-01-02T03:04:05+00:00")),
        (Json, {"key": "value"}, '{"key": "value"}'),
        (classification(yml_config=CONFIG), "U", "UNRESTRICTED"),
        (classification_string(yml_config=CONFIG), "UNRESTRICTED", "UNRESTRICTED"),
    ],
)
def test_field_normalization(annotation: Any, value: Any, expected: Any) -> None:
    result = TypeAdapter(annotation, config=ADAPTER_CONFIG).validate_python(value)
    if isinstance(result, ClassificationValue):
        result = str(result)
    assert result == expected


@pytest.mark.parametrize(
    ("annotation", "value"),
    [
        (Keyword, b"bytes"),
        (StrictKeyword, 123),
        (EmptyableKeyword, b"bytes"),
        (UpperKeyword, b"bytes"),
        (LowerKeyword, b"bytes"),
        (CaseInsensitiveKeyword, b"bytes"),
        (validated_keyword(r"^[a-z]+$"), "INVALID"),
        (IP, "999.0.0.1"),
        (Domain, "invalid!domain"),
        (Email, "not-an-email"),
        (URI, "not a uri"),
        (URIPath, "path"),
        (MAC, "not-a-mac"),
        (PhoneNumber, "not-a-phone"),
        (SSDeepHash, "invalid"),
        (SHA1, "a" * 39),
        (SHA256, "a" * 63),
        (HowlerHash, "G"),
        (MD5, "a" * 31),
        (Platform, "BSD"),
        (Processor, "arm64"),
        (enum(["one", "two"]), "three"),
        (Text, ""),
        (Annotated[Integer, metadata(ge=1, le=3)], 0),
        (Annotated[Integer, metadata(ge=1, le=3)], 4),
        (Annotated[Long, metadata(ge=1, le=3)], 0),
        (Annotated[Long, metadata(ge=1, le=3)], 4),
        (Float, "not-a-float"),
        (Date, "not-a-date"),
        (Json, {"not-json"}),
        (classification_string(yml_config=CONFIG), "D//BOB//REL TO SOUP"),
    ],
)
def test_fields_reject_invalid_values(annotation: Any, value: Any) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(annotation, config=ADAPTER_CONFIG).validate_python(value)


def test_defaults_and_null_containers() -> None:
    class Probe(HowlerEmbeddedModel):
        kw: Keyword = "fallback"
        txt: Text = "fallback"
        num: Integer = 7
        flt: Float = 1.5
        empty_kw: EmptyableKeyword = ""
        cls_str: classification_string(default="UNRESTRICTED", yml_config=CONFIG)
        required_items: list[Keyword]
        optional_items: list[Keyword] | None = None
        maybe: Keyword | None = None
        nested_items: list[list[Keyword]] = []
        mapped_items: mapping(list[Keyword]) = {}
        nested_mapping: list[mapping(list[Keyword])] = []

    model = Probe.model_validate(
        {
            "kw": "",
            "txt": None,
            "num": "",
            "flt": 0,
            "empty_kw": None,
            "cls_str": "",
            "required_items": None,
            "nested_items": [None, ["a"]],
            "mapped_items": {"k": None},
            "nested_mapping": [{"k": None}],
            "maybe": "",
        }
    )
    assert (model.kw, model.txt, model.num, model.flt, model.empty_kw, model.cls_str) == (
        "fallback",
        "fallback",
        7,
        1.5,
        "",
        "UNRESTRICTED",
    )
    assert (model.required_items, model.optional_items, model.nested_items, model.mapped_items) == (
        [],
        None,
        [[], ["a"]],
        {"k": []},
    )
    assert model.maybe is None and model.nested_mapping == [{"k": []}]
    with pytest.raises(ValidationError):
        TypeAdapter(mapping(Integer, index=True)).validate_python({"Invalid-Key": 1})
    for annotation, value, expected in [
        (Boolean, None, False),
        (IndexText, None, "None"),
        (enum(["one"], default="one"), None, "one"),
        (Date, None, None),
        (IP, None, None),
        (Domain, "", None),
        (Email, "", None),
        (URI, "", None),
    ]:
        assert TypeAdapter(annotation).validate_python(value) == expected


def test_classification_error_and_access_parts() -> None:
    adapter = TypeAdapter(classification(yml_config=CONFIG), config=ADAPTER_CONFIG)
    with pytest.raises(InvalidClassification):
        adapter.validate_python("D//BOB//REL TO SOUP")
    value = adapter.validate_python("U//REL TO D1, D2")
    assert str(value) == "UNRESTRICTED//REL TO DEPARTMENT 1, DEPARTMENT 2"
    assert value == adapter.validate_python(str(value))
    assert value != adapter.validate_python("R//GOD//G1")
    assert value.get_access_control_parts()["__access_lvl__"] == 100
    assert str(adapter.validate_python("U//REL TO D1")) == "UNRESTRICTED//ANY"


def test_optional_metadata_preserves_mapping_and_ip_serialization() -> None:
    class Probe(HowlerESModel):
        address: Annotated[
            IP | None,
            metadata(
                optional=True,
                alias="wire",
                es_name="stored",
                index=False,
                store=False,
                copyto="__text__",
                reference="new",
                sync=False,
            ),
        ] = None
        values: mapping(Integer, optional=True, index=True, store=True)

    details = model_registry.fields(Probe)["wire"].metadata
    assert details.kind == "IP" and details.optional and details.index is False and details.store is False
    assert details.sync is False and details.copy_to == ("__text__",) and details.reference == "new"
    assert "validation_regex" in dict(details.options)
    storage = model_registry.mapping(Probe)["properties"]["stored"]
    assert storage["type"] == "ip" and storage["index"] is False and storage["doc_values"] is False
    assert storage["copy_to"] == "__text__"
    values = model_registry.fields(Probe)["values"].metadata
    assert values.index is True and values.store is True
    assert model_registry.mapping(Probe)["properties"]["values"]["type"] == "object"
    probe = Probe.model_validate({"wire": "192.0.2.1"})
    assert _dump_ips(probe, "int") == {"wire": int(ip_address("192.0.2.1"))}
    assert base64.b64decode(_dump_ips(probe, "encoded_bytes")["wire"]) == ip_address("192.0.2.1").packed
    with pytest.raises(HowlerModelValidationError):
        Probe.model_validate({"wire": "invalid"})


@pytest.mark.parametrize("array", [False, True])
@pytest.mark.parametrize("builder, indexed", [(IP, None), (IP, False), (IP, True), (Text, False)])
def test_optional_index_reaches_storage(builder, indexed, array):
    options = {"index": indexed, "copyto": "__text__"}
    annotation = (
        Annotated[
            list[Annotated[builder, metadata(**options)]] | None,
            metadata(es_name="stored", optional=True, alias="wire"),
        ]
        if array
        else Annotated[builder | None, metadata(optional=True, alias="wire", es_name="stored", **options)]
    )
    probe = type("Probe", (HowlerESModel,), {"__annotations__": {"value": annotation}, "value": None})
    leaf = model_registry.flat_fields(probe)["wire"]
    assert leaf.multivalued is array and leaf.metadata.index is indexed
    storage = {"type": "ip" if builder is IP else "text", "copy_to": "__text__"}
    if indexed is not None:
        storage["index"] = indexed
        if builder is IP:
            storage["doc_values"] = indexed
    assert model_registry.mapping(probe)["properties"] == {"stored": storage}
    value = "192.0.2.1"
    model = probe.model_validate({"wire": [value] if array else value})
    expected = int(ip_address(value)) if builder is IP else value
    assert _dump_ips(model, "int") == {"wire": [expected] if array else expected}


def test_serialization_modes() -> None:
    class Child(HowlerEmbeddedModel):
        address: IP
        created: Date

    class Probe(HowlerESModel):
        address: IP
        addresses: list[IP]
        optional_address: IP | None = None
        text: Keyword
        created: Date
        created_by_key: mapping(Date)
        child: Child

    timestamp = "2026-01-01T00:00:00.000000Z"
    model = Probe.model_validate(
        {
            "address": "127.0.0.1",
            "addresses": ["1.1.1.1", "ff02::1"],
            "optional_address": "192.168.0.1",
            "text": "192.0.2.1",
            "created": timestamp,
            "created_by_key": {"key": timestamp},
            "child": {"address": "10.0.0.1", "created": timestamp},
        }
    )
    for mode in ("encoded_bytes", "int", "str", "unsupported", None):
        data = _dump_ips(model, mode)

        def convert(value):
            if mode == "encoded_bytes":
                return base64.b64encode(ip_address(value).packed).decode()
            return int(ip_address(value)) if mode == "int" else value

        assert data["address"] == convert("127.0.0.1")
        assert data["addresses"] == [convert("1.1.1.1"), convert("ff02::1")]
        assert data["optional_address"] == convert("192.168.0.1") and data["child"]["address"] == convert("10.0.0.1")
        assert data["text"] == "192.0.2.1"
    data = model.as_primitives()
    assert data["created"] == data["child"]["created"] == timestamp
    assert data["created_by_key"] == {"key": timestamp}
