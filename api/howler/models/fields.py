"""Reusable Pydantic types and Elasticsearch mappings for Howler models."""

from __future__ import annotations

import json
import re
import types
from copy import copy, deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum as PyEnum
from ipaddress import ip_address
from typing import Annotated, Callable, Iterable, Union, get_args, get_origin
from typing import Any as TypingAny

import arrow
import validators
from elasticsearch import dsl
from pydantic import BeforeValidator
from pydantic import Field as PydanticField
from pydantic.fields import FieldInfo
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

    kind: str
    index: bool | None = None
    store: bool | None = None
    copy_to: tuple[str, ...] = ()
    reference: str | None = None
    deprecated: bool = False
    deprecated_description: str | None = None
    sync: bool = True
    options: tuple[tuple[str, TypingAny], ...] = field(default_factory=tuple)
    optional: bool = False


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


def _dsl_field(
    field_type: Callable[..., dsl.Field],
    annotation: TypingAny,
    kind: str,
    *,
    doc_values: bool = True,
    mapping_options: dict[str, TypingAny] | None = None,
    **kwargs: TypingAny,
) -> TypingAny:
    copy_to = _copy_to(kwargs.pop("copyto", None))
    es_field = field_type(
        **_mapping_options(index=kwargs.get("index"), copy_to=copy_to, doc_values=doc_values, extra=mapping_options)
    )
    return _annotated(annotation, kind, es_field, copy_to=copy_to, **kwargs)


def _dsl_keyword(
    annotation: TypingAny,
    kind: str,
    *,
    mapping_options: dict[str, TypingAny] | None = None,
    **kwargs: TypingAny,
) -> TypingAny:
    return _dsl_field(
        dsl.Keyword,
        annotation,
        kind,
        mapping_options={"ignore_above": 8191, **(mapping_options or {})},
        **kwargs,
    )


def _howler_metadata(
    kind: str, inherit: HowlerFieldMetadata | None, overrides: dict[str, TypingAny]
) -> HowlerFieldMetadata:
    """Normalize builder spellings once, preserving child options unless explicitly overridden."""
    if "copyto" in overrides:
        overrides["copy_to"] = _copy_to(overrides.pop("copyto"))
    if "options" in overrides:
        overrides["options"] = tuple(sorted((overrides["options"] or {}).items()))
    return replace(inherit, **overrides) if inherit else HowlerFieldMetadata(kind=kind, **overrides)


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
    constraints: dict[str, TypingAny] | None = None,
    inherit: HowlerFieldMetadata | None = None,
    inherited_alias: str | None = None,
    **field_options: TypingAny,
) -> TypingAny:
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
    metadata.append(_howler_metadata(kind, inherit, field_options))

    pydantic_options = dict(constraints or {})
    if description is not None:
        pydantic_options["description"] = description
    # An inherited wire alias does not declare a new DSL mapping: the child's
    # mapped field already carries its storage name, which can differ from it.
    if (wire_alias := alias if alias is not None else inherited_alias) is not None:
        pydantic_options["alias"] = wire_alias
    if default_factory is not None:
        pydantic_options["default_factory"] = default_factory
    elif default is not PydanticUndefined:
        pydantic_options["default"] = default
    metadata.append(PydanticField(**pydantic_options))
    return _make_annotated(annotation, *metadata)


def _make_annotated(annotation: TypingAny, *metadata: TypingAny) -> TypingAny:
    if not metadata:
        return annotation
    return Annotated[(annotation, *metadata)]


def _is_mapped_field_metadata(metadata: TypingAny) -> bool:
    """Return whether metadata is an Elasticsearch DSL mapped-field dictionary."""
    return isinstance(metadata, dict) and set(metadata) >= {"_field", "_es_name", "exclude"}


def _with_storage_index(item: TypingAny, index: bool) -> TypingAny:
    """Override the registry and DSL representations without mutating a reusable annotation."""
    if isinstance(item, HowlerFieldMetadata):
        return replace(item, index=index)
    if not _is_mapped_field_metadata(item) or item["_field"] is None:
        return item
    mapping = deepcopy(item)
    field = mapping["_field"]
    if isinstance(field, dsl.Object):
        field.enabled = index
    else:
        field.index = index
        if not isinstance(field, dsl.Text):
            field.doc_values = index
    return mapping


def _rebuild_generic_alias(annotation: TypingAny, origin: TypingAny, arguments: list[TypingAny]) -> TypingAny:
    """Rebuild a generic annotation after one or more nested metadata items move."""
    if origin is types.UnionType:
        rebuilt = arguments[0]
        for argument in arguments[1:]:
            rebuilt = rebuilt | argument
        return rebuilt
    if origin is Union:
        return Union[tuple(arguments)]
    if isinstance(annotation, types.GenericAlias):
        return types.GenericAlias(origin, tuple(arguments))

    # ``optional`` is normally given annotations from this module's built-in
    # list/dict factories. Retain support for other public generic aliases by
    # reconstructing them through their public origin subscription.
    subscription = arguments[0] if len(arguments) == 1 else tuple(arguments)
    return origin[subscription]


def _strip_annotated_mapped_field_metadata(
    annotation: TypingAny,
    index: bool | None,
) -> tuple[TypingAny, list[dict[str, TypingAny]]]:
    """Extract mapped-field metadata directly attached to an Annotated alias."""
    original_nested, *metadata = get_args(annotation)
    nested, nested_mappings = _strip_mapped_field_metadata(original_nested, index)
    if index is not None:
        metadata = [_with_storage_index(item, index) for item in metadata]
    mapping_metadata = [item for item in metadata if _is_mapped_field_metadata(item)]
    remaining_metadata = [item for item in metadata if not _is_mapped_field_metadata(item)]

    if index is None and not mapping_metadata and not nested_mappings and nested is original_nested:
        return annotation, []

    if mapping_metadata:
        # CPython considers union equality order-insensitive when caching Annotated
        # aliases, but Pydantic's left_to_right union mode is order-sensitive. The
        # source mapping dict was unhashable (and therefore never cacheable); retain
        # that distinction with a unique immutable metadata marker after lifting it.
        remaining_metadata.append(object())

    safe_annotation = _make_annotated(nested, *remaining_metadata) if remaining_metadata else nested
    return safe_annotation, [*mapping_metadata, *nested_mappings]


def _strip_mapped_field_metadata(
    annotation: TypingAny, index: bool | None
) -> tuple[TypingAny, list[dict[str, TypingAny]]]:
    """Move DSL mapping metadata outside a nullable union's hashable type arguments.

    Python 3.10's ``typing.Union`` hashes its members while constructing a union. The
    elasticsearch-dsl ``mapped_field`` metadata is a dict subclass and is deliberately
    unhashable, so a child ``Annotated`` containing it cannot be used directly as a
    union member. Keep Pydantic metadata (including child validators) in place and move
    only those DSL metadata dictionaries to the outer ``Annotated`` wrapper.
    """
    origin = get_origin(annotation)
    if origin is Annotated:
        return _strip_annotated_mapped_field_metadata(annotation, index)

    arguments = get_args(annotation)
    if not arguments:
        return annotation, []

    safe_arguments: list[TypingAny] = []
    mapped_metadata: list[dict[str, TypingAny]] = []
    changed = False
    # Lists and nullable branches use the same ES field as their wrapper. Object
    # keys and values have their own fields, so their index options stay independent.
    child_index = index if origin in (list, Union, types.UnionType) else None
    for argument in arguments:
        safe_argument, nested_mappings = _strip_mapped_field_metadata(argument, child_index)
        safe_arguments.append(safe_argument)
        mapped_metadata.extend(nested_mappings)
        changed = changed or safe_argument is not argument

    if not changed:
        return annotation, mapped_metadata

    return _rebuild_generic_alias(annotation, origin, safe_arguments), mapped_metadata


def _field_metadata(annotation: TypingAny) -> HowlerFieldMetadata | None:
    origin = get_origin(annotation)
    if origin is Annotated:
        nested, *items = get_args(annotation)
        metadata = next((item for item in items if isinstance(item, HowlerFieldMetadata)), None)
        return metadata or _field_metadata(nested)
    if origin in (Union, types.UnionType):
        for item in get_args(annotation):
            if item is not type(None) and (metadata := _field_metadata(item)) is not None:
                return metadata
    return None


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


def keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a non-empty string stored as an Elasticsearch keyword."""
    coerce = kwargs.pop("coerce", True)
    return _dsl_keyword(
        str,
        "Keyword",
        validator=_keyword_validator(coerce=coerce),
        default_when=_empty_or_none,
        **kwargs,
    )


def emptyable_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword that distinguishes empty strings from null."""
    return _dsl_keyword(
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

    return _dsl_keyword(str, "UpperKeyword", validator=validate, default_when=_empty_or_none, **kwargs)


def lower_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword normalized to lowercase."""

    def validate(value: TypingAny) -> str:
        return _keyword_validator()(value).lower()

    return _dsl_keyword(str, "LowerKeyword", validator=validate, default_when=_empty_or_none, **kwargs)


def case_insensitive_keyword(**kwargs: TypingAny) -> TypingAny:
    """Create a keyword using the lowercase Elasticsearch normalizer."""
    return _dsl_keyword(
        str,
        "CaseInsensitiveKeyword",
        mapping_options={"normalizer": "lowercase_normalizer"},
        validator=_keyword_validator(),
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
    return _special_validated("ValidatedKeyword", re.compile(pattern).pattern, **kwargs)


def ip(**kwargs: TypingAny) -> TypingAny:
    """Create an IP-address field."""
    return _dsl_field(
        dsl.Ip,
        str | None,
        "IP",
        validator=_ip_validator,
        options={"validation_regex": IP_ONLY_REGEX.pattern},
        **kwargs,
    )


def domain(*, strict: bool = True, **kwargs: TypingAny) -> TypingAny:
    """Create a normalized domain or hostname field."""
    return _dsl_keyword(
        str | None,
        "Domain",
        validator=_domain_validator(strict),
        options={"strict": strict},
        **kwargs,
    )


def email(**kwargs: TypingAny) -> TypingAny:
    """Create a normalized email-address field."""
    return _dsl_keyword(str | None, "Email", validator=_email_validator, **kwargs)


def uri(**kwargs: TypingAny) -> TypingAny:
    """Create a normalized URI field."""
    return _dsl_keyword(str | None, "URI", validator=_uri_validator, **kwargs)


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
    return _dsl_field(
        dsl.Text,
        str,
        "SSDeepHash",
        doc_values=False,
        mapping_options={"analyzer": "text_fuzzy"},
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
    mapping_options: dict[str, TypingAny] = {}
    if normalizer is not None:
        mapping_options["normalizer"] = normalizer
    return _dsl_keyword(
        str,
        kind,
        mapping_options=mapping_options,
        validator=_validated_keyword_validator(pattern),
        default_when=_falsy,
        options={"validation_regex": pattern},
        **kwargs,
    )


def enum(values: Iterable[TypingAny] | type[PyEnum], **kwargs: TypingAny) -> TypingAny:
    """Create a keyword restricted to an explicit set of values."""
    validator, allowed = _enum_validator(values)
    return _dsl_keyword(
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

    kwargs.setdefault("default_factory", get_random_id)
    return _dsl_keyword(str, "UUID", validator=validate, **kwargs)


def text(**kwargs: TypingAny) -> TypingAny:
    """Create non-empty analyzed text."""
    return _dsl_field(dsl.Text, str, "Text", doc_values=False, validator=_text_validator, default_when=_falsy, **kwargs)


def index_text(**kwargs: TypingAny) -> TypingAny:
    """Create analyzed text without non-empty validation."""
    return _dsl_field(dsl.Text, str, "IndexText", doc_values=False, validator=str, **kwargs)


def integer(*, min: int | None = None, max: int | None = None, **kwargs: TypingAny) -> TypingAny:
    """Create a bounded 32-bit Elasticsearch integer."""
    return _bounded_integer(dsl.Integer, "Integer", min=min, max=max, **kwargs)


def long(*, min: int | None = None, max: int | None = None, **kwargs: TypingAny) -> TypingAny:
    """Create a bounded 64-bit Elasticsearch integer."""
    return _bounded_integer(dsl.Long, "Long", min=min, max=max, **kwargs)


def _bounded_integer(
    field_type: Callable[..., dsl.Field],
    kind: str,
    *,
    min: int | None,
    max: int | None,
    **kwargs: TypingAny,
) -> TypingAny:
    constraints = {key: value for key, value in {"ge": min, "le": max}.items() if value is not None}
    return _dsl_field(
        field_type,
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
    return _dsl_field(dsl.Float, float, "Float", validator=_float_validator, default_when=_falsy, **kwargs)


def boolean(**kwargs: TypingAny) -> TypingAny:
    """Create a boolean field using legacy truthiness coercion."""
    return _dsl_field(dsl.Boolean, bool, "Boolean", validator=_boolean_validator, **kwargs)


def date(**kwargs: TypingAny) -> TypingAny:
    """Create a UTC-aware Elasticsearch date field."""
    return _dsl_field(
        dsl.Date,
        datetime | None,
        "Date",
        mapping_options={"format": "date_optional_time||epoch_millis"},
        validator=_date_validator,
        **kwargs,
    )


def json_field(**kwargs: TypingAny) -> TypingAny:
    """Create a JSON-encoded keyword field."""
    return _dsl_keyword(str, "Json", validator=_json_validator, **kwargs)


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

    return _dsl_field(
        dsl.Keyword,
        ClassificationValue,
        "Classification",
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

    return _dsl_field(
        dsl.Keyword,
        str,
        "ClassificationString",
        validator=validate,
        default_when=_falsy,
        **kwargs,
    )


def list_field(child_type: TypingAny, **kwargs: TypingAny) -> TypingAny:
    """Create a typed array field."""
    return _annotated(
        types.GenericAlias(list, (child_type,)),
        "List",
        None,
        validator=lambda value: [] if value is None else value,
        **kwargs,
    )


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
    child_metadata = _field_metadata(child_type)
    child_info = next((item for item in get_args(child_type)[1:] if isinstance(item, FieldInfo)), None)
    if child_info and child_info.alias is not None:
        # A wire alias belongs to the field, not to one branch of its nullable
        # union. Lift it without touching the child's DSL mapping or validators.
        base, *metadata = get_args(child_type)
        branch_info = copy(child_info)
        branch_info.alias = branch_info.validation_alias = branch_info.serialization_alias = None
        branch_info.alias_priority = None
        child_type = _make_annotated(base, *(branch_info if item is child_info else item for item in metadata))
    # Legacy Optional let Keyword.check use the child's default on "", but passed
    # explicit null through. EmptyableKeyword, in particular, retains the empty string.
    if child_metadata and child_metadata.kind in {"Keyword", "LowerKeyword", "UpperKeyword", "CaseInsensitiveKeyword"}:
        if child_info is None or child_info.default in (None, PydanticUndefined):
            kwargs["validator"] = lambda value: None if value == "" else value
    kwargs.setdefault("default", None)
    safe_child_type, mapped_field_metadata = _strip_mapped_field_metadata(child_type, kwargs.get("index"))
    nullable_field = _annotated(
        safe_child_type | None,
        "Optional",
        None,
        inherit=child_metadata,
        inherited_alias=child_info.alias if child_info else None,
        optional=True,
        **kwargs,
    )
    return _make_annotated(nullable_field, *mapped_field_metadata) if mapped_field_metadata else nullable_field


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
