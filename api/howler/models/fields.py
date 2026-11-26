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
from typing import Annotated, Callable, Iterable, cast
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


def metadata(
    *,
    index: bool | None = None,
    store: bool | None = None,
    copyto: str | Iterable[str] | None = None,
    copy_to: str | Iterable[str] | None = None,
    reference: str | None = None,
    deprecated: bool = False,
    deprecated_description: str | None = None,
    sync: bool = True,
    optional: bool = False,
    es_name: str | None = None,
    default: TypingAny = PydanticUndefined,
    default_factory: Callable[[], TypingAny] | None = None,
    alias: str | None = None,
    description: str | None = None,
) -> TypingAny:
    """Attach Howler metadata and optional Pydantic field settings to an annotated field."""
    pydantic_options: dict[str, TypingAny] = {}
    if description is not None:
        pydantic_options["description"] = description
    if alias is not None:
        pydantic_options["alias"] = alias
    if default_factory is not None:
        pydantic_options["default_factory"] = default_factory
    elif default is not PydanticUndefined:
        pydantic_options["default"] = default

    field_info = PydanticField(**pydantic_options)
    resolved_copy_to = _copy_to(copy_to if copy_to is not None else copyto)
    has_howler_metadata = (
        index is not None
        or store is not None
        or bool(resolved_copy_to)
        or reference is not None
        or deprecated
        or deprecated_description is not None
        or not sync
        or optional
        or es_name is not None
    )
    if has_howler_metadata:
        field_info.metadata.append(
            HowlerFieldMetadata(
                index=index,
                store=store,
                copy_to=resolved_copy_to,
                reference=reference,
                deprecated=deprecated,
                deprecated_description=deprecated_description,
                sync=sync,
                optional=optional,
                es_name=es_name,
            )
        )
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


def _emptyable_keyword_validator(value: TypingAny) -> str | None:
    if isinstance(value, bytes):
        raise ValueError("EmptyableKeyword doesn't accept bytes values")  # noqa: TRY004
    return None if value is None else str(value)


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


def keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a non-empty string stored as an Elasticsearch keyword."""
    coerce = kwargs.pop("coerce", True)
    return _annotated(
        str,
        "Keyword",
        validator=_keyword_validator(coerce=coerce),
        default_when=_empty_or_none,
        **kwargs,
    )


def emptyable_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword that distinguishes empty strings from null."""
    return _annotated(
        str | None,
        "EmptyableKeyword",
        validator=_emptyable_keyword_validator,
        default_when=lambda value: value is None,
        **kwargs,
    )


def upper_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword normalized to uppercase."""

    def validate(value: TypingAny) -> str:
        return _keyword_validator()(value).upper()

    return _annotated(str, "UpperKeyword", validator=validate, default_when=_empty_or_none, **kwargs)


def lower_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword normalized to lowercase."""

    def validate(value: TypingAny) -> str:
        return _keyword_validator()(value).lower()

    return _annotated(str, "LowerKeyword", validator=validate, default_when=_empty_or_none, **kwargs)


def case_insensitive_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword using the lowercase Elasticsearch normalizer."""
    return _annotated(
        str,
        "CaseInsensitiveKeyword",
        validator=_keyword_validator(),
        default_when=_empty_or_none,
        **kwargs,
    )


def any_field(**kwargs: TypingAny) -> TypingAny:
    """Create an arbitrary, non-indexed value."""
    kwargs["index"] = False
    kwargs["store"] = False
    return _annotated(TypingAny, "Any", **kwargs)


def validated_keyword(pattern: str | re.Pattern[str], **kwargs: TypingAny) -> TypingAny:
    """Create a keyword validated by a regular expression."""
    return _special_validated("ValidatedKeyword", re.compile(pattern).pattern, **kwargs)


def ip(**kwargs: TypingAny) -> TypingAny:
    """Create an IP-address field."""
    return _annotated(
        str | None,
        "IP",
        validator=_ip_validator,
        serializers=(
            PlainSerializer(_ip_serializer, return_type=TypingAny),
            WithJsonSchema({"anyOf": [{"type": "string"}, {"type": "null"}]}, mode="serialization"),
        ),
        options={"validation_regex": IP_ONLY_REGEX.pattern},
        **kwargs,
    )


def domain(*, strict: bool = True, **kwargs: TypingAny) -> TypingAny:
    """Create a normalized domain or hostname field."""
    return _annotated(
        str | None,
        "Domain",
        validator=_domain_validator(strict),
        options={"strict": strict},
        **kwargs,
    )


def email(**kwargs: TypingAny) -> TypingAny:
    """Create a normalized email-address field."""
    return _annotated(str | None, "Email", validator=_email_validator, **kwargs)


def uri(**kwargs: TypingAny) -> TypingAny:
    """Create a normalized URI field."""
    return _annotated(str | None, "URI", validator=_uri_validator, **kwargs)


def uri_path(**kwargs: TypingAny) -> TypingAny:
    """Create a URI path field."""
    return _special_validated("URIPath", URI_PATH_REGEX, **kwargs)


def mac(**kwargs: TypingAny) -> TypingAny:
    """Create a MAC-address field."""
    return _special_validated("MAC", MAC_REGEX, **kwargs)


def phone_number(**kwargs: TypingAny) -> TypingAny:
    """Create a phone-number field."""
    return _special_validated("PhoneNumber", PHONE_REGEX, **kwargs)


def ssdeep_hash(**kwargs: TypingAny) -> TypingAny:
    """Create an ssdeep fuzzy-hash field."""
    return _annotated(
        str,
        "SSDeepHash",
        validator=_validated_keyword_validator(SSDEEP_REGEX),
        default_when=_falsy,
        options={"validation_regex": SSDEEP_REGEX},
        **kwargs,
    )


def sha1(**kwargs: TypingAny) -> TypingAny:
    """Create a SHA-1 hash field."""
    return _special_validated("SHA1", SHA1_REGEX, **kwargs)


def sha256(**kwargs: TypingAny) -> TypingAny:
    """Create a SHA-256 hash field."""
    return _special_validated("SHA256", SHA256_REGEX, **kwargs)


def howler_hash(**kwargs: TypingAny) -> TypingAny:
    """Create a variable-length Howler hash field."""
    return _special_validated("HowlerHash", HOWLER_HASH_REGEX, **kwargs)


def md5(**kwargs: TypingAny) -> TypingAny:
    """Create an MD5 hash field."""
    return _special_validated("MD5", MD5_REGEX, **kwargs)


def platform(**kwargs: TypingAny) -> TypingAny:
    """Create a supported-platform field."""
    return _special_validated("Platform", PLATFORM_REGEX, **kwargs)


def processor(**kwargs: TypingAny) -> TypingAny:
    """Create a supported-processor field."""
    return _special_validated("Processor", PROCESSOR_REGEX, **kwargs)


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


def uuid(**kwargs: TypingAny) -> TypingAny:
    """Create a string identifier with a generated default."""

    def validate(value: TypingAny) -> str:
        return str(get_random_id() if value is None else value)

    if not kwargs.get("optional") and "default" not in kwargs:
        kwargs.setdefault("default_factory", get_random_id)
    return _annotated(str, "UUID", validator=validate, **kwargs)


def text(**kwargs: TypingAny) -> TypingAny:
    """Create non-empty analyzed text."""
    return _annotated(str, "Text", validator=_text_validator, default_when=_falsy, **kwargs)


def index_text(**kwargs: TypingAny) -> TypingAny:
    """Create analyzed text without non-empty validation."""
    return _annotated(str, "IndexText", validator=str, **kwargs)


def integer(*, min: int | None = None, max: int | None = None, **kwargs: TypingAny) -> TypingAny:
    """Create a bounded 32-bit Elasticsearch integer."""
    return _bounded_integer("Integer", min=min, max=max, **kwargs)


def long(*, min: int | None = None, max: int | None = None, **kwargs: TypingAny) -> TypingAny:
    """Create a bounded 64-bit Elasticsearch integer."""
    return _bounded_integer("Long", min=min, max=max, **kwargs)


def _bounded_integer(
    kind: str,
    *,
    min: int | None,
    max: int | None,
    **kwargs: TypingAny,
) -> TypingAny:
    constraints = {key: value for key, value in {"ge": min, "le": max}.items() if value is not None}
    return _annotated(
        int,
        kind,
        validator=_integer_validator,
        default_when=_empty_or_none,
        constraints=constraints,
        options={"min": min, "max": max},
        **kwargs,
    )


def float_field(**kwargs: TypingAny) -> TypingAny:
    """Create a floating-point field."""
    return _annotated(float, "Float", validator=_float_validator, default_when=_falsy, **kwargs)


def boolean(**kwargs: TypingAny) -> TypingAny:
    """Create a boolean field using legacy truthiness coercion."""
    return _annotated(bool, "Boolean", validator=_boolean_validator, **kwargs)


def date(**kwargs: TypingAny) -> TypingAny:
    """Create a UTC-aware Elasticsearch date field."""
    return _annotated(
        datetime | None,
        "Date",
        validator=_date_validator,
        serializers=(
            PlainSerializer(_date_serializer, return_type=TypingAny),
            WithJsonSchema(
                {"anyOf": [{"type": "string", "format": "date-time"}, {"type": "null"}]},
                mode="serialization",
            ),
        ),
        **kwargs,
    )


def json_field(**kwargs: TypingAny) -> TypingAny:
    """Create a JSON-encoded keyword field."""
    return _annotated(str, "Json", validator=_json_validator, **kwargs)


def classification(
    *,
    is_user_classification: bool = False,
    yml_config: str | None = None,
    **kwargs: TypingAny,
) -> TypingAny:
    """Create a normalized classification value."""
    engine = loader.get_classification(yml_config=yml_config)

    def validate(value: TypingAny) -> ClassificationValue:
        return ClassificationValue(engine, value, is_user_classification)

    return _annotated(
        ClassificationValue,
        "Classification",
        validator=validate,
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
    engine = loader.get_classification(yml_config=yml_config)

    def validate(value: TypingAny) -> str:
        if not value:
            raise ValueError("Empty classification is not allowed without defaults")
        if not engine.is_valid(value):
            raise ValueError(f"Invalid classification: {value}")
        return str(value)

    return _annotated(
        str,
        "ClassificationString",
        validator=validate,
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


def flattened_object(**kwargs: TypingAny) -> TypingAny:
    """Create a dotted-key object whose values are JSON encoded."""
    return _annotated(
        types.GenericAlias(dict, (str, json_field())),
        "FlattenedObject",
        validator=_mapping_validator(FLATTENED_OBJECT_SANITIZER),
        **kwargs,
    )


def flattened_list_object(**kwargs: TypingAny) -> TypingAny:
    """Create a dotted-key object containing lists of JSON values."""
    return _annotated(
        types.GenericAlias(dict, (str, types.GenericAlias(list, (json_field(),)))),
        "FlattenedListObject",
        validator=_mapping_validator(FLATTENED_OBJECT_SANITIZER),
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
