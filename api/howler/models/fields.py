"""Reusable Pydantic types and Elasticsearch mappings for Howler models."""

from __future__ import annotations

import json
import re
import types
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum as PyEnum
from ipaddress import ip_address
from typing import Annotated, Callable, Iterable, TypeAlias, cast
from typing import Any as TypingAny

import arrow
import validators
from pydantic import (
    BeforeValidator,
    PlainSerializer,
    SerializationInfo,
    WithJsonSchema,
)
from pydantic import Field as PydanticField
from pydantic_core import PydanticUndefined

from howler.common import loader
from howler.common.classification import Classification as ClassificationEngine
from howler.common.net import is_valid_domain, is_valid_ip
from howler.utils.uid import get_random_id

DATEFORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
FIELD_SANITIZER = re.compile(r"^[a-z][a-z0-9_-]*$")
FLATTENED_OBJECT_SANITIZER = re.compile(r"^[a-z][a-z0-9_.]*$")
NOT_INDEXED_SANITIZER = re.compile(r"^[A-Za-z0-9_ -]*$")

DOMAIN_REGEX = (
    r"(?:(?:[A-Za-z0-9\u00a1-\uffff][A-Za-z0-9\u00a1-\uffff_-]{0,62})?"
    r"[A-Za-z0-9\u00a1-\uffff]\.)+(?:xn--)?(?:[A-Za-z0-9\u00a1-\uffff]{2,}\.?)"
)
EMAIL_REGEX = re.compile(
    rf"^[a-zA-Z0-9!#$%&'*+/=?^_`\{{|}}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`\{{|}}~-]+)*@({DOMAIN_REGEX})$"
)
IPV4_REGEX = r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
IPV6_REGEX = (
    r"(?:(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|"
    r"(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|"
    r":(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|"
    r"::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|"
    r"(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|"
    r"(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9]))"
)
IP_ONLY_REGEX = re.compile(rf"^(?:{IPV4_REGEX}|{IPV6_REGEX})$")
URI_PATH_REGEX = r"(?:[/?#]\S*)"
FULL_URI_REGEX = re.compile(
    rf"^((?:(?:[A-Za-z]*:)?//)?(?:\S+(?::\S*)?@)?((?:{IPV4_REGEX}|{IPV6_REGEX})|{DOMAIN_REGEX})"
    rf"(?::\d{{2,5}})?){URI_PATH_REGEX}?$"
)
PHONE_REGEX = r"^(\+?\d{1,2})?[ .-]?(\(\d{3}\)|\d{3})[ .-](\d{3})[ .-](\d{4})$"
SSDEEP_REGEX = r"^[0-9]{1,18}:[a-zA-Z0-9/+]{0,64}:[a-zA-Z0-9/+]{0,64}$"
MD5_REGEX = r"^[a-f0-9]{32}$"
SHA1_REGEX = r"^[a-f0-9]{40}$"
SHA256_REGEX = r"^[a-f0-9]{64}$"
HOWLER_HASH_REGEX = r"^[a-f0-9]{1,64}$"
MAC_REGEX = r"^(?:(?:[0-9a-f]{2}-){5}[0-9a-f]{2}|(?:[0-9a-f]{2}:){5}[0-9a-f]{2})$"
PLATFORM_REGEX = r"^(Windows|Linux|MacOS|Android|iOS)$"
PROCESSOR_REGEX = r"^x(64|86)$"


@dataclass(frozen=True)
class HowlerFieldMetadata:
    """Canonical Howler metadata attached to an annotated Pydantic field."""

    kind: str | None = None
    index: bool | None = None
    store: bool | None = None
    copy_to: tuple[str, ...] = ()
    reference: str | None = None
    deprecated: bool = False
    deprecated_description: str | None = None
    sync: bool = True
    options: tuple[tuple[str, TypingAny], ...] = field(default_factory=tuple)
    optional: bool = False
    es_name: str | None = None
    _explicit: frozenset[str] = field(default_factory=frozenset, compare=False, repr=False)


def _explicit_metadata(
    *,
    index: bool | None,
    store: bool | None,
    resolved_copy_to: tuple[str, ...],
    reference: str | None,
    deprecated: bool | None,
    deprecated_description: str | None,
    sync: bool | None,
    optional: bool | None,
    es_name: str | None,
) -> HowlerFieldMetadata | None:
    values: dict[str, TypingAny] = {
        "index": index,
        "store": store,
        "copy_to": resolved_copy_to,
        "reference": reference,
        "deprecated": deprecated,
        "deprecated_description": deprecated_description,
        "sync": sync,
        "optional": optional,
        "es_name": es_name,
    }
    explicit = {key for key, value in values.items() if (bool(value) if key == "copy_to" else value is not None)}
    if not explicit:
        return None
    return HowlerFieldMetadata(
        index=index,
        store=store,
        copy_to=resolved_copy_to,
        reference=reference,
        deprecated=bool(deprecated) if deprecated is not None else False,
        deprecated_description=deprecated_description,
        sync=sync if sync is not None else True,
        optional=bool(optional) if optional is not None else False,
        es_name=es_name,
        _explicit=frozenset(explicit),
    )


def metadata(
    *,
    index: bool | None = None,
    store: bool | None = None,
    copyto: str | Iterable[str] | None = None,
    copy_to: str | Iterable[str] | None = None,
    reference: str | None = None,
    deprecated: bool | None = None,
    deprecated_description: str | None = None,
    sync: bool | None = None,
    optional: bool | None = None,
    es_name: str | None = None,
    default: TypingAny = PydanticUndefined,
    default_factory: Callable[[], TypingAny] | None = None,
    alias: str | None = None,
    description: str | None = None,
    ge: int | float | None = None,
    le: int | float | None = None,
) -> TypingAny:
    """Attach Howler metadata and optional Pydantic field settings to an annotated field."""
    pydantic_options: dict[str, TypingAny] = {}
    for key, value in (("description", description), ("alias", alias), ("ge", ge), ("le", le)):
        if value is not None:
            pydantic_options[key] = value
    if default_factory is not None:
        pydantic_options["default_factory"] = default_factory
    elif default is not PydanticUndefined:
        pydantic_options["default"] = default

    field_info = PydanticField(**pydantic_options)
    howler_meta = _explicit_metadata(
        index=index,
        store=store,
        resolved_copy_to=_copy_to(copy_to if copy_to is not None else copyto),
        reference=reference,
        deprecated=deprecated,
        deprecated_description=deprecated_description,
        sync=sync,
        optional=optional,
        es_name=es_name,
    )
    if howler_meta is not None:
        field_info.metadata.append(howler_meta)
    return field_info


class ClassificationValue:
    """Normalized classification value with its originating classification engine."""

    def __init__(self, engine: ClassificationEngine, value: TypingAny, is_user_classification: bool = False):
        self.engine = engine
        self.is_user_classification = is_user_classification
        source = value.value if isinstance(value, ClassificationValue) else value
        self.value: str = engine.normalize_classification(source, skip_auto_select=is_user_classification)

    def get_access_control_parts(self) -> dict[str, TypingAny]:
        """Return the hidden Elasticsearch access-control fields."""
        return self.engine.get_access_control_parts(self.value, user_classification=self.is_user_classification)

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ClassificationValue) and self.value == other.value


def _copy_to(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _howler_metadata(kind: str, overrides: dict[str, TypingAny]) -> HowlerFieldMetadata:
    """Normalize builder spellings once into canonical field metadata."""
    if "copyto" in overrides:
        overrides["copy_to"] = _copy_to(overrides.pop("copyto"))
    if "options" in overrides:
        overrides["options"] = tuple(sorted((overrides["options"] or {}).items()))
    return HowlerFieldMetadata(kind=kind, **overrides)


def _build_validator(
    validator: Callable[[TypingAny], TypingAny],
    kind: str,
    *,
    default: TypingAny,
    default_when: Callable[[TypingAny], bool] | None,
    optional: bool,
) -> BeforeValidator:
    effective_validator = validator
    if default is not PydanticUndefined and default is not None and default_when is not None:
        configured_default = default
        default_selector = default_when

        def apply_default(value: TypingAny) -> TypingAny:
            selected = deepcopy(configured_default) if default_selector(value) else value
            return validator(selected)

        effective_validator = apply_default

    if optional:
        null_empty_keyword = kind in {
            "Keyword",
            "LowerKeyword",
            "UpperKeyword",
            "CaseInsensitiveKeyword",
        } and default in (None, PydanticUndefined)
        inner_validator = effective_validator

        def guard_optional(value: TypingAny) -> TypingAny:
            if value is None or (null_empty_keyword and value == ""):
                return None
            return inner_validator(value)

        effective_validator = guard_optional

    return BeforeValidator(effective_validator)


def _annotated(
    annotation: TypingAny,
    kind: str,
    *,
    validator: Callable[[TypingAny], TypingAny] | None = None,
    serializers: tuple[TypingAny, ...] = (),
    default_when: Callable[[TypingAny], bool] | None = None,
    default: TypingAny = PydanticUndefined,
    default_factory: Callable[[], TypingAny] | None = None,
    description: str | None = None,
    alias: str | None = None,
    es_name: str | None = None,
    constraints: dict[str, TypingAny] | None = None,
    optional: bool = False,
    **field_options: TypingAny,
) -> TypingAny:
    if optional:
        non_null = _make_annotated(annotation, PydanticField(**constraints)) if constraints else annotation
        annotation = non_null | None
        if default is PydanticUndefined and default_factory is None:
            default = None
        field_options["optional"] = True

    annotations: list[TypingAny] = []
    if validator is not None:
        annotations.append(
            _build_validator(
                validator,
                kind,
                default=default,
                default_when=default_when,
                optional=optional,
            )
        )
    annotations.extend(serializers)

    resolved_es_name = es_name if es_name is not None else alias
    if resolved_es_name is not None:
        field_options["es_name"] = resolved_es_name
    annotations.append(_howler_metadata(kind, field_options))

    pydantic_options = {} if optional else dict(constraints or {})
    if description is not None:
        pydantic_options["description"] = description
    if alias is not None:
        pydantic_options["alias"] = alias
    if default_factory is not None:
        pydantic_options["default_factory"] = default_factory
    elif default is not PydanticUndefined:
        pydantic_options["default"] = default
    annotations.append(PydanticField(**pydantic_options))
    return _make_annotated(annotation, *annotations)


def _make_annotated(annotation: TypingAny, *metadata: TypingAny) -> TypingAny:
    if not metadata:
        return annotation
    return Annotated[(annotation, *metadata)]


def _keyword_validator(*, coerce: bool = True) -> Callable[[TypingAny], str]:
    def validate(value: TypingAny) -> str:
        if isinstance(value, bytes):
            raise ValueError("Keyword doesn't accept bytes values")  # noqa: TRY004
        if not coerce and not isinstance(value, str):
            raise ValueError("Keyword value must be a string when coercion is disabled")
        if value in ("", None):
            raise ValueError("Empty strings are not allowed without defaults")
        return str(value)

    return validate


def _empty_or_none(value: TypingAny) -> bool:
    return value is None or value == ""


def _falsy(value: TypingAny) -> bool:
    return not value


def _emptyable_keyword_validator(value: TypingAny) -> str:
    if isinstance(value, bytes):
        raise ValueError("EmptyableKeyword doesn't accept bytes values")  # noqa: TRY004
    if value is None:
        raise ValueError("EmptyableKeyword doesn't accept None without optional or default")
    return str(value)


def _upper_keyword_validator(value: TypingAny) -> str:
    return _keyword_validator()(value).upper()


def _lower_keyword_validator(value: TypingAny) -> str:
    return _keyword_validator()(value).lower()


def _uuid_validator(value: TypingAny) -> str:
    return str(get_random_id() if value is None else value)


def _classification_validator(
    *,
    is_user_classification: bool = False,
    yml_config: str | None = None,
) -> Callable[[TypingAny], ClassificationValue]:
    def validate(value: TypingAny) -> ClassificationValue:
        engine = loader.get_classification(yml_config=yml_config)
        return ClassificationValue(engine, value, is_user_classification)

    return validate


def _classification_string_validator(*, yml_config: str | None = None) -> Callable[[TypingAny], str]:
    def validate(value: TypingAny) -> str:
        if not value:
            raise ValueError("Empty classification is not allowed without defaults")
        engine = loader.get_classification(yml_config=yml_config)
        if not engine.is_valid(value):
            raise ValueError(f"Invalid classification: {value}")
        return str(value)

    return validate


NULL_EMPTY_KEYWORD_KINDS = frozenset(
    {
        "Keyword",
        "LowerKeyword",
        "UpperKeyword",
        "CaseInsensitiveKeyword",
    }
)

DEFAULT_WHEN_BY_KIND: dict[str, Callable[[TypingAny], bool]] = {
    "Keyword": _empty_or_none,
    "LowerKeyword": _empty_or_none,
    "UpperKeyword": _empty_or_none,
    "CaseInsensitiveKeyword": _empty_or_none,
    "EmptyableKeyword": lambda value: value is None,
    "Integer": _empty_or_none,
    "Long": _empty_or_none,
    "SSDeepHash": _falsy,
    "ValidatedKeyword": _falsy,
    "URIPath": _falsy,
    "MAC": _falsy,
    "PhoneNumber": _falsy,
    "SHA1": _falsy,
    "SHA256": _falsy,
    "HowlerHash": _falsy,
    "MD5": _falsy,
    "Platform": _falsy,
    "Processor": _falsy,
    "Enum": _falsy,
    "Text": _falsy,
    "Float": _falsy,
    "ClassificationString": _falsy,
}


def _text_validator(value: TypingAny) -> str:
    if not value:
        raise ValueError("Empty strings are not allowed without defaults")
    return str(value)


def _date_validator(value: TypingAny) -> datetime | None:
    if value is None:
        return None
    if value == "NOW":
        return arrow.utcnow().datetime
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(value, DATEFORMAT).replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return arrow.get(value).datetime


def _integer_validator(value: TypingAny) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(str(error)) from error


def _float_validator(value: TypingAny) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(str(error)) from error


def _boolean_validator(value: TypingAny) -> bool:
    return bool(value)


def _ip_validator(value: TypingAny) -> str | None:
    if not value:
        return None
    if not isinstance(value, str) or not IP_ONLY_REGEX.match(value):
        raise ValueError(f"{value!r} is not a valid IP address")
    return value


def _domain_validator(strict: bool) -> Callable[[TypingAny], str | None]:
    def validate(value: TypingAny) -> str | None:
        if not value:
            return None
        domain_result = validators.domain(value)
        if isinstance(domain_result, Exception) and strict:
            raise ValueError(f"{value!r} did not pass domain validation")
        hostname_result = validators.hostname(value)
        if isinstance(hostname_result, Exception):
            raise ValueError(f"{value!r} did not pass hostname validation")  # noqa: TRY004
        return str(value).lower()

    return validate


def _email_validator(value: TypingAny) -> str | None:
    if not value:
        return None
    validation_result = validators.email(value)
    if isinstance(validation_result, Exception):
        raise ValueError(f"{value!r} did not pass email validation")  # noqa: TRY004
    match = EMAIL_REGEX.match(value)
    if match is None or not is_valid_domain(match.group(1)):
        raise ValueError(f"{value!r} does not contain a valid domain")
    return str(value).lower()


def _uri_validator(value: TypingAny) -> str | None:
    if not value:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{value!r} did not pass URI validation")  # noqa: TRY004
    match = FULL_URI_REGEX.match(value)
    if match is None:
        raise ValueError(f"{value!r} did not pass URI validation")
    host = match.group(2)
    if not is_valid_domain(host) and not is_valid_ip(host):
        raise ValueError(f"{host!r} is not a valid domain or IP")
    return match.group(0).replace(match.group(1), match.group(1).lower())


def _validated_keyword_validator(pattern: str | re.Pattern[str]) -> Callable[[TypingAny], str]:
    validation_regex = re.compile(pattern)

    def validate(value: TypingAny) -> str:
        if not value:
            raise ValueError("Empty strings are not allowed without defaults")
        if not isinstance(value, str) or not validation_regex.match(value):
            raise ValueError(f"{value!r} does not match {validation_regex.pattern}")
        return str(value)

    return validate


def _enum_validator(
    values: Iterable[TypingAny] | type[PyEnum],
) -> tuple[Callable[[TypingAny], str], tuple[TypingAny, ...]]:
    if isinstance(values, type) and issubclass(values, PyEnum):
        allowed = tuple(member.value for member in values)
    else:
        allowed = tuple(values)

    def validate(value: TypingAny) -> str:
        if not value:
            raise ValueError("Empty enums are not allowed without defaults")
        if value not in allowed:
            raise ValueError(f"{value!r} is not one of {allowed!r}")
        return str(value)

    return validate, allowed


def _json_validator(value: TypingAny) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(str(error)) from error


def _mapping_validator(pattern: re.Pattern[str]) -> Callable[[TypingAny], TypingAny]:
    def validate(value: TypingAny) -> TypingAny:
        if not isinstance(value, dict):
            raise ValueError("Mapping values must be dictionaries")  # noqa: TRY004
        invalid = [key for key in value if not isinstance(key, str) or not pattern.match(key)]
        if invalid:
            raise ValueError(f"Illegal mapping key: {invalid[0]}")
        return value

    return validate


def format_datetime(value: datetime, output_format: str | None = None) -> str | int:
    """Format a datetime using a Howler primitive timestamp mode."""
    if output_format == "iso":
        return value.isoformat()
    if output_format == "posix":
        return int(value.timestamp())
    normalized = value.astimezone(timezone.utc) if value.tzinfo is not None else value
    return normalized.strftime(DATEFORMAT)


def _ip_serializer(value: str | None, info: SerializationInfo) -> str | int | None:
    if value is None:
        return None
    ip_format = info.context.get("ip_format") if info.context else None
    return ip_to_primitive(value, ip_format)


def _date_serializer(value: datetime | None, info: SerializationInfo) -> str | int | None:
    if value is None:
        return None
    timestamp_format = info.context.get("timestamp_format") if info.context else None
    return format_datetime(value, timestamp_format)


def _classification_serializer(value: ClassificationValue | None) -> str | None:
    return None if value is None else str(value)


Keyword: TypeAlias = Annotated[
    str,
    BeforeValidator(_keyword_validator(coerce=True)),
    HowlerFieldMetadata(kind="Keyword"),
]
StrictKeyword: TypeAlias = Annotated[
    str,
    BeforeValidator(_keyword_validator(coerce=False)),
    HowlerFieldMetadata(kind="Keyword"),
]
EmptyableKeyword: TypeAlias = Annotated[
    str,
    BeforeValidator(_emptyable_keyword_validator),
    HowlerFieldMetadata(kind="EmptyableKeyword"),
]
UpperKeyword: TypeAlias = Annotated[
    str,
    BeforeValidator(_upper_keyword_validator),
    HowlerFieldMetadata(kind="UpperKeyword"),
]
LowerKeyword: TypeAlias = Annotated[
    str,
    BeforeValidator(_lower_keyword_validator),
    HowlerFieldMetadata(kind="LowerKeyword"),
]
CaseInsensitiveKeyword: TypeAlias = Annotated[
    str,
    BeforeValidator(_keyword_validator(coerce=True)),
    HowlerFieldMetadata(kind="CaseInsensitiveKeyword"),
]
AnyField: TypeAlias = Annotated[
    TypingAny,
    HowlerFieldMetadata(kind="Any", index=False, store=False),
]
IP: TypeAlias = Annotated[
    str | None,
    BeforeValidator(_ip_validator),
    PlainSerializer(_ip_serializer, return_type=TypingAny),
    WithJsonSchema({"anyOf": [{"type": "string"}, {"type": "null"}]}, mode="serialization"),
    HowlerFieldMetadata(kind="IP", options=(("validation_regex", IP_ONLY_REGEX.pattern),)),
]
Domain: TypeAlias = Annotated[
    str | None,
    BeforeValidator(_domain_validator(True)),
    HowlerFieldMetadata(kind="Domain", options=(("strict", True),)),
]
Email: TypeAlias = Annotated[
    str | None,
    BeforeValidator(_email_validator),
    HowlerFieldMetadata(kind="Email"),
]
URI: TypeAlias = Annotated[
    str | None,
    BeforeValidator(_uri_validator),
    HowlerFieldMetadata(kind="URI"),
]
URIPath: TypeAlias = Annotated[
    str,
    BeforeValidator(_validated_keyword_validator(URI_PATH_REGEX)),
    HowlerFieldMetadata(kind="URIPath", options=(("validation_regex", URI_PATH_REGEX),)),
]
MAC: TypeAlias = Annotated[
    str,
    BeforeValidator(_validated_keyword_validator(MAC_REGEX)),
    HowlerFieldMetadata(kind="MAC", options=(("validation_regex", MAC_REGEX),)),
]
PhoneNumber: TypeAlias = Annotated[
    str,
    BeforeValidator(_validated_keyword_validator(PHONE_REGEX)),
    HowlerFieldMetadata(kind="PhoneNumber", options=(("validation_regex", PHONE_REGEX),)),
]
SSDeepHash: TypeAlias = Annotated[
    str,
    BeforeValidator(_validated_keyword_validator(SSDEEP_REGEX)),
    HowlerFieldMetadata(kind="SSDeepHash", options=(("validation_regex", SSDEEP_REGEX),)),
]
SHA1: TypeAlias = Annotated[
    str,
    BeforeValidator(_validated_keyword_validator(SHA1_REGEX)),
    HowlerFieldMetadata(kind="SHA1", options=(("validation_regex", SHA1_REGEX),)),
]
SHA256: TypeAlias = Annotated[
    str,
    BeforeValidator(_validated_keyword_validator(SHA256_REGEX)),
    HowlerFieldMetadata(kind="SHA256", options=(("validation_regex", SHA256_REGEX),)),
]
HowlerHash: TypeAlias = Annotated[
    str,
    BeforeValidator(_validated_keyword_validator(HOWLER_HASH_REGEX)),
    HowlerFieldMetadata(kind="HowlerHash", options=(("validation_regex", HOWLER_HASH_REGEX),)),
]
MD5: TypeAlias = Annotated[
    str,
    BeforeValidator(_validated_keyword_validator(MD5_REGEX)),
    HowlerFieldMetadata(kind="MD5", options=(("validation_regex", MD5_REGEX),)),
]
Platform: TypeAlias = Annotated[
    str,
    BeforeValidator(_validated_keyword_validator(PLATFORM_REGEX)),
    HowlerFieldMetadata(kind="Platform", options=(("validation_regex", PLATFORM_REGEX),)),
]
Processor: TypeAlias = Annotated[
    str,
    BeforeValidator(_validated_keyword_validator(PROCESSOR_REGEX)),
    HowlerFieldMetadata(kind="Processor", options=(("validation_regex", PROCESSOR_REGEX),)),
]
UUID: TypeAlias = Annotated[
    str,
    BeforeValidator(_uuid_validator),
    HowlerFieldMetadata(kind="UUID"),
    PydanticField(default_factory=get_random_id),
]
Text: TypeAlias = Annotated[
    str,
    BeforeValidator(_text_validator),
    HowlerFieldMetadata(kind="Text"),
]
IndexText: TypeAlias = Annotated[
    str,
    BeforeValidator(str),
    HowlerFieldMetadata(kind="IndexText"),
]
Integer: TypeAlias = Annotated[
    int,
    BeforeValidator(_integer_validator),
    HowlerFieldMetadata(kind="Integer"),
]
Long: TypeAlias = Annotated[
    int,
    BeforeValidator(_integer_validator),
    HowlerFieldMetadata(kind="Long"),
]
Float: TypeAlias = Annotated[
    float,
    BeforeValidator(_float_validator),
    HowlerFieldMetadata(kind="Float"),
]
Boolean: TypeAlias = Annotated[
    bool,
    BeforeValidator(_boolean_validator),
    HowlerFieldMetadata(kind="Boolean"),
]
Date: TypeAlias = Annotated[
    datetime | None,
    BeforeValidator(_date_validator),
    PlainSerializer(_date_serializer, return_type=TypingAny),
    WithJsonSchema(
        {"anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}]},
        mode="serialization",
    ),
    HowlerFieldMetadata(kind="Date"),
]
Json: TypeAlias = Annotated[
    str,
    BeforeValidator(_json_validator),
    HowlerFieldMetadata(kind="Json"),
]
Classification: TypeAlias = Annotated[
    ClassificationValue,
    BeforeValidator(_classification_validator(is_user_classification=False)),
    PlainSerializer(_classification_serializer, return_type=str),
    HowlerFieldMetadata(kind="Classification", options=(("is_user_classification", False),)),
]
UserClassification: TypeAlias = Annotated[
    ClassificationValue,
    BeforeValidator(_classification_validator(is_user_classification=True)),
    PlainSerializer(_classification_serializer, return_type=str),
    HowlerFieldMetadata(kind="Classification", options=(("is_user_classification", True),)),
]
ClassificationString: TypeAlias = Annotated[
    str,
    BeforeValidator(_classification_string_validator()),
    HowlerFieldMetadata(kind="ClassificationString"),
]
FlattenedObject: TypeAlias = Annotated[
    dict[str, Json],
    BeforeValidator(_mapping_validator(FLATTENED_OBJECT_SANITIZER)),
    HowlerFieldMetadata(kind="FlattenedObject"),
]
FlattenedListObject: TypeAlias = Annotated[
    dict[str, list[Json]],
    BeforeValidator(_mapping_validator(FLATTENED_OBJECT_SANITIZER)),
    HowlerFieldMetadata(kind="FlattenedListObject"),
]


def validated_keyword(pattern: str | re.Pattern[str], **kwargs: TypingAny) -> TypingAny:
    """Create a keyword validated by a regular expression."""
    return _special_validated("ValidatedKeyword", re.compile(pattern).pattern, **kwargs)


def domain(*, strict: bool = True, **kwargs: TypingAny) -> TypingAny:
    """Create a normalized domain or hostname field."""
    return _annotated(
        str | None,
        "Domain",
        validator=_domain_validator(strict),
        options={"strict": strict},
        **kwargs,
    )


def _special_validated(
    kind: str,
    pattern: str,
    **kwargs: TypingAny,
) -> TypingAny:
    return _annotated(
        str,
        kind,
        validator=_validated_keyword_validator(pattern),
        default_when=_falsy,
        options={"validation_regex": pattern},
        **kwargs,
    )


def enum(values: Iterable[TypingAny] | type[PyEnum], **kwargs: TypingAny) -> TypingAny:
    """Create a keyword restricted to an explicit set of values."""
    validator, allowed = _enum_validator(values)
    return _annotated(
        str,
        "Enum",
        validator=validator,
        default_when=_falsy,
        options={"values": allowed},
        **kwargs,
    )


def classification(
    *,
    is_user_classification: bool = False,
    yml_config: str | None = None,
    **kwargs: TypingAny,
) -> TypingAny:
    """Create a normalized classification value."""
    return _annotated(
        ClassificationValue,
        "Classification",
        validator=_classification_validator(
            is_user_classification=is_user_classification,
            yml_config=yml_config,
        ),
        serializers=(
            PlainSerializer(
                _classification_serializer,
                return_type=cast(type[TypingAny], str | None) if kwargs.get("optional") else str,
            ),
        ),
        options={"is_user_classification": is_user_classification},
        **kwargs,
    )


def classification_string(*, yml_config: str | None = None, **kwargs: TypingAny) -> TypingAny:
    """Create a validated classification stored as a plain string."""
    return _annotated(
        str,
        "ClassificationString",
        validator=_classification_string_validator(yml_config=yml_config),
        default_when=_falsy,
        **kwargs,
    )


def mapping(child_type: TypingAny, **kwargs: TypingAny) -> TypingAny:
    """Create a typed dynamic-key mapping."""
    sanitizer = (
        FIELD_SANITIZER
        if kwargs.get("index") is not False or kwargs.get("store") is not False
        else NOT_INDEXED_SANITIZER
    )
    return _annotated(
        types.GenericAlias(dict, (str, child_type)),
        "Mapping",
        validator=_mapping_validator(sanitizer),
        **kwargs,
    )


def ip_to_primitive(value: str, output_format: str | None) -> str | int:
    """Serialize an IP value using a legacy Howler primitive mode."""
    if output_format == "encoded_bytes":
        import base64

        return base64.b64encode(ip_address(value).packed).decode("utf-8")
    if output_format == "int":
        return int(ip_address(value))
    if output_format == "str":
        return str(ip_address(value))
    return value
