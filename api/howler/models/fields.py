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
from typing import Annotated, Callable, Iterable
from typing import Any as TypingAny

import arrow
import validators
from elasticsearch import dsl
from pydantic import BeforeValidator
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
    r"(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}"
    r"(?::[0-9a-fA-F]{1,4}){1,2}|(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|(?:[0-9a-fA-F]{1,4}:){1,2}"
    r"(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|"
    r":(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|"
    r"::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.)"
    r"{3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|(?:[0-9a-fA-F]{1,4}:){1,4}:"
    r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|"
    r"[01]?[0-9][0-9]?))"
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

    kind: str
    index: bool | None = None
    store: bool | None = None
    copy_to: tuple[str, ...] = ()
    reference: str | None = None
    deprecated: bool = False
    deprecated_description: str | None = None
    sync: bool = True
    options: tuple[tuple[str, TypingAny], ...] = field(default_factory=tuple)


class ClassificationValue:
    """Normalized classification value with the legacy comparison helpers."""

    def __init__(self, engine: ClassificationEngine, value: TypingAny, is_user_classification: bool = False):
        self.engine = engine
        self.is_user_classification = is_user_classification
        source = value.value if isinstance(value, ClassificationValue) else value
        self.value: str = engine.normalize_classification(source, skip_auto_select=is_user_classification)

    def get_access_control_parts(self) -> dict[str, TypingAny]:
        """Return the hidden Elasticsearch access-control fields."""
        return self.engine.get_access_control_parts(self.value, user_classification=self.is_user_classification)

    def min(self, other: ClassificationValue) -> ClassificationValue:
        """Return the least restrictive union of two classifications."""
        return ClassificationValue(
            self.engine,
            self.engine.min_classification(self.value, other.value),
            self.is_user_classification,
        )

    def max(self, other: ClassificationValue) -> ClassificationValue:
        """Return the most restrictive intersection of two classifications."""
        return ClassificationValue(
            self.engine,
            self.engine.max_classification(self.value, other.value),
            self.is_user_classification,
        )

    def intersect(self, other: ClassificationValue) -> ClassificationValue:
        """Return the user-classification intersection."""
        return ClassificationValue(
            self.engine,
            self.engine.intersect_user_classification(self.value, other.value),
            self.is_user_classification,
        )

    def long(self) -> str:
        """Return the normalized long classification."""
        return self.engine.normalize_classification(self.value, skip_auto_select=self.is_user_classification)

    def small(self) -> str:
        """Return the normalized short classification."""
        return self.engine.normalize_classification(
            self.value,
            long_format=False,
            skip_auto_select=self.is_user_classification,
        )

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ClassificationValue) and self.value == other.value

    def __le__(self, other: ClassificationValue) -> bool:
        return self.engine.is_accessible(other.value, self.value)

    def __lt__(self, other: ClassificationValue) -> bool:
        return self.engine.is_accessible(other.value, self.value)

    def __ge__(self, other: ClassificationValue) -> bool:
        return self.engine.is_accessible(self.value, other.value)

    def __gt__(self, other: ClassificationValue) -> bool:
        return not self.engine.is_accessible(other.value, self.value)


def _copy_to(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(value)


def _mapping_options(
    *,
    index: bool | None,
    copy_to: tuple[str, ...],
    doc_values: bool,
    extra: dict[str, TypingAny] | None = None,
) -> dict[str, TypingAny]:
    options = dict(extra or {})
    if index is not None:
        options["index"] = index
        if doc_values:
            options["doc_values"] = index
    if copy_to:
        options["copy_to"] = copy_to[0]
    return options


def _annotated(
    annotation: TypingAny,
    kind: str,
    es_field: dsl.Field | None,
    *,
    validator: Callable[[TypingAny], TypingAny] | None = None,
    default_when: Callable[[TypingAny], bool] | None = None,
    default: TypingAny = PydanticUndefined,
    default_factory: Callable[[], TypingAny] | None = None,
    description: str | None = None,
    alias: str | None = None,
    es_name: str | None = None,
    index: bool | None = None,
    store: bool | None = None,
    copyto: str | Iterable[str] | None = None,
    reference: str | None = None,
    deprecated: bool = False,
    deprecated_description: str | None = None,
    sync: bool = True,
    options: dict[str, TypingAny] | None = None,
    constraints: dict[str, TypingAny] | None = None,
) -> TypingAny:
    copy_to = _copy_to(copyto)
    metadata: list[TypingAny] = []
    if validator is not None:
        effective_validator = validator
        if default is not PydanticUndefined and default is not None and default_when is not None:
            configured_default = default
            default_selector = default_when

            def apply_default(value: TypingAny) -> TypingAny:
                selected = deepcopy(configured_default) if default_selector(value) else value
                return validator(selected)

            effective_validator = apply_default
        metadata.append(BeforeValidator(effective_validator))
    if es_field is not None or es_name is not None or alias is not None:
        metadata.append(dsl.mapped_field(es_field, es_name=es_name or alias))
    metadata.append(
        HowlerFieldMetadata(
            kind=kind,
            index=index,
            store=store,
            copy_to=copy_to,
            reference=reference,
            deprecated=deprecated,
            deprecated_description=deprecated_description,
            sync=sync,
            options=tuple(sorted((options or {}).items())),
        )
    )

    field_options = dict(constraints or {})
    if description is not None:
        field_options["description"] = description
    if alias is not None:
        field_options["alias"] = alias
    if default_factory is not None:
        field_options["default_factory"] = default_factory
    elif default is not PydanticUndefined:
        field_options["default"] = default
    metadata.append(PydanticField(**field_options))
    return _make_annotated(annotation, *metadata)


def _make_annotated(annotation: TypingAny, *metadata: TypingAny) -> TypingAny:
    return getattr(Annotated, "__class_getitem__")((annotation, *metadata))


def _keyword_validator(value: TypingAny) -> str:
    if isinstance(value, bytes):
        raise ValueError("Keyword doesn't accept bytes values")  # noqa: TRY004
    if value in ("", None):
        raise ValueError("Empty strings are not allowed without defaults")
    return str(value)


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


def keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a non-empty string stored as an Elasticsearch keyword."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(
        str,
        "Keyword",
        mapping,
        validator=_keyword_validator,
        default_when=_empty_or_none,
        **kwargs,
    )


def emptyable_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword that distinguishes empty strings from null."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(
        str | None,
        "EmptyableKeyword",
        mapping,
        validator=_emptyable_keyword_validator,
        default_when=lambda value: value is None,
        **kwargs,
    )


def upper_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword normalized to uppercase."""

    def validate(value: TypingAny) -> str:
        return _keyword_validator(value).upper()

    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(str, "UpperKeyword", mapping, validator=validate, default_when=_empty_or_none, **kwargs)


def lower_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword normalized to lowercase."""

    def validate(value: TypingAny) -> str:
        return _keyword_validator(value).lower()

    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(str, "LowerKeyword", mapping, validator=validate, default_when=_empty_or_none, **kwargs)


def case_insensitive_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword using the lowercase Elasticsearch normalizer."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        normalizer="lowercase_normalizer",
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(
        str,
        "CaseInsensitiveKeyword",
        mapping,
        validator=_keyword_validator,
        default_when=_empty_or_none,
        **kwargs,
    )


def any_field(**kwargs: TypingAny) -> TypingAny:
    """Create an arbitrary, non-indexed value."""
    kwargs["index"] = False
    kwargs["store"] = False
    return _annotated(
        TypingAny,
        "Any",
        dsl.Keyword(index=False, doc_values=False),
        **kwargs,
    )


def validated_keyword(pattern: str | re.Pattern[str], **kwargs: TypingAny) -> TypingAny:
    """Create a keyword validated by a regular expression."""
    regex = re.compile(pattern)
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(
        str,
        "ValidatedKeyword",
        mapping,
        validator=_validated_keyword_validator(regex),
        default_when=_falsy,
        options={"validation_regex": regex.pattern},
        **kwargs,
    )


def ip(**kwargs: TypingAny) -> TypingAny:
    """Create an IP-address field."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Ip(**_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True))
    return _annotated(str | None, "IP", mapping, validator=_ip_validator, **kwargs)


def domain(*, strict: bool = True, **kwargs: TypingAny) -> TypingAny:
    """Create a normalized domain or hostname field."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(
        str | None,
        "Domain",
        mapping,
        validator=_domain_validator(strict),
        options={"strict": strict},
        **kwargs,
    )


def email(**kwargs: TypingAny) -> TypingAny:
    """Create a normalized email-address field."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(str | None, "Email", mapping, validator=_email_validator, **kwargs)


def uri(**kwargs: TypingAny) -> TypingAny:
    """Create a normalized URI field."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(str | None, "URI", mapping, validator=_uri_validator, **kwargs)


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
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Text(
        analyzer="text_fuzzy",
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=False),
    )
    return _annotated(
        str,
        "SSDeepHash",
        mapping,
        validator=_validated_keyword_validator(SSDEEP_REGEX),
        default_when=_falsy,
        options={"validation_regex": SSDEEP_REGEX},
        **kwargs,
    )


def sha1(**kwargs: TypingAny) -> TypingAny:
    """Create a SHA-1 hash field."""
    return _special_validated("SHA1", SHA1_REGEX, normalizer="lowercase_normalizer", **kwargs)


def sha256(**kwargs: TypingAny) -> TypingAny:
    """Create a SHA-256 hash field."""
    return _special_validated("SHA256", SHA256_REGEX, normalizer="lowercase_normalizer", **kwargs)


def howler_hash(**kwargs: TypingAny) -> TypingAny:
    """Create a variable-length Howler hash field."""
    return _special_validated("HowlerHash", HOWLER_HASH_REGEX, normalizer="lowercase_normalizer", **kwargs)


def md5(**kwargs: TypingAny) -> TypingAny:
    """Create an MD5 hash field."""
    return _special_validated("MD5", MD5_REGEX, normalizer="lowercase_normalizer", **kwargs)


def platform(**kwargs: TypingAny) -> TypingAny:
    """Create a supported-platform field."""
    return _special_validated("Platform", PLATFORM_REGEX, **kwargs)


def processor(**kwargs: TypingAny) -> TypingAny:
    """Create a supported-processor field."""
    return _special_validated("Processor", PROCESSOR_REGEX, **kwargs)


def _special_validated(
    kind: str,
    pattern: str,
    *,
    normalizer: str | None = None,
    **kwargs: TypingAny,
) -> TypingAny:
    copy_to = _copy_to(kwargs.get("copyto"))
    extra: dict[str, TypingAny] = {"ignore_above": 8191}
    if normalizer is not None:
        extra["normalizer"] = normalizer
    mapping = dsl.Keyword(**_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True, extra=extra))
    return _annotated(
        str,
        kind,
        mapping,
        validator=_validated_keyword_validator(pattern),
        default_when=_falsy,
        options={"validation_regex": pattern},
        **kwargs,
    )


def enum(values: Iterable[TypingAny] | type[PyEnum], **kwargs: TypingAny) -> TypingAny:
    """Create a keyword restricted to an explicit set of values."""
    validator, allowed = _enum_validator(values)
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(
        str,
        "Enum",
        mapping,
        validator=validator,
        default_when=_falsy,
        options={"values": allowed},
        **kwargs,
    )


def uuid(**kwargs: TypingAny) -> TypingAny:
    """Create a string identifier with a generated default."""

    def validate(value: TypingAny) -> str:
        return str(get_random_id() if value is None else value)

    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    kwargs.setdefault("default_factory", get_random_id)
    return _annotated(str, "UUID", mapping, validator=validate, **kwargs)


def text(**kwargs: TypingAny) -> TypingAny:
    """Create non-empty analyzed text."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Text(**_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=False))
    return _annotated(str, "Text", mapping, validator=_text_validator, default_when=_falsy, **kwargs)


def index_text(**kwargs: TypingAny) -> TypingAny:
    """Create analyzed text without non-empty validation."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Text(**_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=False))
    return _annotated(str, "IndexText", mapping, validator=str, **kwargs)


def integer(*, min: int | None = None, max: int | None = None, **kwargs: TypingAny) -> TypingAny:
    """Create a bounded 32-bit Elasticsearch integer."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Integer(**_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True))
    constraints = {key: value for key, value in {"ge": min, "le": max}.items() if value is not None}
    return _annotated(
        int,
        "Integer",
        mapping,
        validator=_integer_validator,
        default_when=_empty_or_none,
        constraints=constraints,
        options={"min": min, "max": max},
        **kwargs,
    )


def long(*, min: int | None = None, max: int | None = None, **kwargs: TypingAny) -> TypingAny:
    """Create a bounded 64-bit Elasticsearch integer."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Long(**_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True))
    constraints = {key: value for key, value in {"ge": min, "le": max}.items() if value is not None}
    return _annotated(
        int,
        "Long",
        mapping,
        validator=_integer_validator,
        default_when=_empty_or_none,
        constraints=constraints,
        options={"min": min, "max": max},
        **kwargs,
    )


def float_field(**kwargs: TypingAny) -> TypingAny:
    """Create a floating-point field."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Float(**_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True))
    return _annotated(float, "Float", mapping, validator=_float_validator, default_when=_falsy, **kwargs)


def boolean(**kwargs: TypingAny) -> TypingAny:
    """Create a boolean field using legacy truthiness coercion."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Boolean(**_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True))
    return _annotated(bool, "Boolean", mapping, validator=_boolean_validator, **kwargs)


def date(**kwargs: TypingAny) -> TypingAny:
    """Create a UTC-aware Elasticsearch date field."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Date(
        format="date_optional_time||epoch_millis",
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(datetime | None, "Date", mapping, validator=_date_validator, **kwargs)


def json_field(**kwargs: TypingAny) -> TypingAny:
    """Create a JSON-encoded keyword field."""
    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(str, "Json", mapping, validator=_json_validator, **kwargs)


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

    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(
        ClassificationValue,
        "Classification",
        mapping,
        validator=validate,
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

    copy_to = _copy_to(kwargs.get("copyto"))
    mapping = dsl.Keyword(
        ignore_above=8191,
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=True),
    )
    return _annotated(
        str,
        "ClassificationString",
        mapping,
        validator=validate,
        default_when=_falsy,
        **kwargs,
    )


def list_field(child_type: TypingAny, **kwargs: TypingAny) -> TypingAny:
    """Create a typed array field."""
    return _annotated(types.GenericAlias(list, (child_type,)), "List", None, **kwargs)


def mapping(child_type: TypingAny, **kwargs: TypingAny) -> TypingAny:
    """Create a typed dynamic-key mapping."""
    sanitizer = (
        FIELD_SANITIZER
        if kwargs.get("index") is not False or kwargs.get("store") is not False
        else NOT_INDEXED_SANITIZER
    )
    mapping = dsl.Object(enabled=False) if kwargs.get("index") is False else dsl.Object()
    return _annotated(
        types.GenericAlias(dict, (str, child_type)),
        "Mapping",
        mapping,
        validator=_mapping_validator(sanitizer),
        **kwargs,
    )


def flattened_object(**kwargs: TypingAny) -> TypingAny:
    """Create a dotted-key object whose values are JSON encoded."""
    mapping = dsl.Object(enabled=False) if kwargs.get("index") is False else dsl.Object()
    return _annotated(
        types.GenericAlias(dict, (str, json_field())),
        "FlattenedObject",
        mapping,
        validator=_mapping_validator(FLATTENED_OBJECT_SANITIZER),
        **kwargs,
    )


def flattened_list_object(**kwargs: TypingAny) -> TypingAny:
    """Create a dotted-key object containing lists of JSON values."""
    mapping = dsl.Object(enabled=False) if kwargs.get("index") is False else dsl.Object()
    return _annotated(
        types.GenericAlias(dict, (str, types.GenericAlias(list, (json_field(),)))),
        "FlattenedListObject",
        mapping,
        validator=_mapping_validator(FLATTENED_OBJECT_SANITIZER),
        **kwargs,
    )


def compound(model_type: type[TypingAny], **kwargs: TypingAny) -> TypingAny:
    """Create an embedded object field."""
    return _annotated(model_type, "Compound", None, **kwargs)


def optional(child_type: TypingAny, **kwargs: TypingAny) -> TypingAny:
    """Create a nullable field with a null default."""
    kwargs.setdefault("default", None)
    return _annotated(child_type | None, "Optional", None, **kwargs)


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
