"""HOWLER's built in Object Document Model tool.

The classes in this module can be composed to build database
independent data models in python. This gives us:
- single source of truth for our data schemas
- database independent serialization
- type checking


"""

from __future__ import annotations

import copy
import json
import re
import typing
from datetime import datetime
from enum import Enum as PyEnum
from enum import EnumMeta
from typing import Any as _Any
from typing import Dict, Tuple, Union
from typing import Mapping as _Mapping
from venv import logger

import arrow
import validators
from dateutil.tz import tzutc

from howler.common import loader
from howler.common.exceptions import (
    HowlerKeyError,
    HowlerNotImplementedError,
    HowlerTypeError,
    HowlerValueError,
)
from howler.common.net import is_valid_domain, is_valid_ip
from howler.utils.dict_utils import flatten, recursive_update
from howler.utils.isotime import now_as_iso
from howler.utils.uid import get_random_id

BANNED_FIELDS = {
    "_id",
    "__access_grp1__",
    "__access_lvl__",
    "__access_req__",
    "__access_grp2__",
}
DATEFORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
FIELD_SANITIZER = re.compile("^[a-z][a-z0-9_-]*$")
FLATTENED_OBJECT_SANITIZER = re.compile("^[a-z][a-z0-9_.]*$")
NOT_INDEXED_SANITIZER = re.compile("^[A-Za-z0-9_ -]*$")
UTC_TZ = tzutc()

DOMAIN_REGEX = (
    r"(?:(?:[A-Za-z0-9\u00a1-\uffff][A-Za-z0-9\u00a1-\uffff_-]{0,62})?[A-Za-z0-9\u00a1-\uffff]\.)+"
    r"(?:xn--)?(?:[A-Za-z0-9\u00a1-\uffff]{2,}\.?)"
)
DOMAIN_ONLY_REGEX = f"^{DOMAIN_REGEX}$"
EMAIL_REGEX = f"^[a-zA-Z0-9!#$%&'*+/=?^_‘{{|}}~-]+(?:\\.[a-zA-Z0-9!#$%&'*+/=?^_‘{{|}}~-]+)*@({DOMAIN_REGEX})$"
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
IP_REGEX = f"(?:{IPV4_REGEX}|{IPV6_REGEX})"
IP_ONLY_REGEX = f"^{IP_REGEX}$"
PRIVATE_IP = (
    r"(?:(?:127|10)(?:\.(?:[2](?:[0-5][0-5]|[01234][6-9])|[1][0-9][0-9]|[1-9][0-9]|[0-9])){3})|"
    r"(?:172\.(?:1[6-9]|2[0-9]|3[0-1])(?:\.(?:2[0-4][0-9]|25[0-5]|[1][0-9][0-9]|[1-9][0-9]|[0-9])){2}|"
    r"(?:192\.168(?:\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])){2}))"
)
PHONE_REGEX = r"^(\+?\d{1,2})?[ .-]?(\(\d{3}\)|\d{3})[ .-](\d{3})[ .-](\d{4})$"
SSDEEP_REGEX = r"^[0-9]{1,18}:[a-zA-Z0-9/+]{0,64}:[a-zA-Z0-9/+]{0,64}$"
MD5_REGEX = r"^[a-f0-9]{32}$"
SHA1_REGEX = r"^[a-f0-9]{40}$"
SHA256_REGEX = r"^[a-f0-9]{64}$"
HOWLER_HASH_REGEX = r"^[a-f0-9]{1,64}$"
MAC_REGEX = r"^(?:(?:[0-9a-f]{2}-){5}[0-9a-f]{2}|(?:[0-9a-f]{2}:){5}[0-9a-f]{2})$"
URI_PATH = r"(?:[/?#]\S*)"
FULL_URI = f"^((?:(?:[A-Za-z]*:)?//)?(?:\\S+(?::\\S*)?@)?({IP_REGEX}|{DOMAIN_REGEX})(?::\\d{{2,5}})?){URI_PATH}?$"
PLATFORM_REGEX = r"^(Windows|Linux|MacOS|Android|iOS)$"
PROCESSOR_REGEX = r"^x(64|86)$"


def flat_to_nested(data: dict[str, _Any]) -> dict[str, _Any]:
    sub_data: dict[str, _Any] = {}
    nested_keys = []
    for key, value in data.items():
        if "." in key:
            child, sub_key = key.split(".", 1)
            nested_keys.append(child)
            try:
                sub_data[child][sub_key] = value
            except (KeyError, TypeError):
                sub_data[child] = {sub_key: value}
        else:
            sub_data[key] = value

    for key in nested_keys:
        sub_data[key] = flat_to_nested(sub_data[key])

    return sub_data


class KeyMaskException(HowlerKeyError):
    pass


class _Field:
    def __init__(
        self,
        name=None,
        index=None,
        store=None,
        copyto=None,
        default=None,
        description=None,
        deprecated_description=None,
        reference=None,
        optional=False,
        deprecated=False,
    ):
        self.index = index
        self.store = store
        self.multivalued = False
        self.copyto = []
        if isinstance(copyto, str):
            self.copyto.append(copyto)
        elif copyto:
            self.copyto.extend(copyto)

        self.name = name
        self.parent_name = None
        self.getter_function = None
        self.setter_function = None
        self.description = description
        self.reference = reference
        self.optional = optional
        self.deprecated = deprecated
        self.deprecated_description = deprecated_description

        self.default = default
        self.default_set = default is not None

    # noinspection PyProtectedMember
    def __get__(self, obj, objtype=None):
        """Read the value of this field from the model instance (obj)."""
        if obj is None:
            return obj
        if self.name in obj._odm_removed:
            raise KeyMaskException(self.name)
        if self.getter_function is not None:
            return self.getter_function(obj, obj._odm_py_obj[self.name.rstrip("_")])

        return obj._odm_py_obj[self.name.rstrip("_")]

    # noinspection PyProtectedMember
    def __set__(self, obj, value):
        """Set the value of this field, calling a setter method if available."""
        if self.name in obj._odm_removed:
            raise KeyMaskException(self.name)
        value = self.check(value)
        if self.setter_function is not None:
            value = self.setter_function(obj, value)
        obj._odm_py_obj[self.name.rstrip("_")] = value

    def getter(self, method):
        """Decorator to create getter method for a field."""
        out = copy.deepcopy(self)
        out.getter_function = method
        return out

    def setter(self, method):
        """Let fields be used as a decorator to define a setter method.

        >>> expiry = Date()
        >>>
        >>> # noinspection PyUnusedLocal,PyUnresolvedReferences
        >>> @expiry.setter
        >>> def expiry(self, assign, value):
        >>>     assert value
        >>>     assign(value)
        """
        out = copy.deepcopy(self)
        out.setter_function = method
        return out

    def apply_defaults(self, index, store):
        """Used by the model decorator to pass through default parameters."""
        if self.index is None:
            self.index = index
        if self.store is None:
            self.store = store

    def fields(self):
        """Return the subfields/modified field data.

        For simple fields this is an identity function.
        """
        return {"": self}

    def check(self, value, **kwargs):
        raise HowlerNotImplementedError(
            "This function is not defined in the default field. " "Each fields has to have their own definition"
        )

    def __repr__(self) -> str:
        keys = [
            key
            for key in self.__dir__()
            if not key.startswith("_") and not callable(getattr(self, key)) and getattr(self, key) is not None
        ]
        return f"{type(self).__name__}({', '.join([f'{key}={str(getattr(self, key))}' for key in keys])})"


class _DeletedField:
    pass


class Date(_Field):
    """A field storing a datetime value."""

    def check(self, value, context=[], **kwargs):
        if value is None:
            return None

        if value == "NOW":
            value = now_as_iso()

        try:
            try:
                return datetime.strptime(value, DATEFORMAT).replace(tzinfo=UTC_TZ)
            except (TypeError, ValueError):
                return arrow.get(value).datetime
        except Exception as e:
            raise HowlerValueError(f"[{'.'.join(context) or self.name}]: {str(e)}")


class Boolean(_Field):
    """A field storing a boolean value."""

    def check(self, value, context=[], **kwargs):
        if self.optional and value is None:
            return None

        try:
            return bool(value)
        except ValueError as e:
            raise HowlerValueError(f"[{'.'.join(context) or self.name}]: {str(e)}")


class Json(_Field):
    """A field storing serializeable structure with their JSON encoded representations.

    Examples: metadata
    """

    def check(self, value, context=[], **kwargs):
        if self.optional and value is None:
            return None

        if not isinstance(value, str):
            try:
                return json.dumps(value)
            except (ValueError, OverflowError, TypeError) as e:
                raise HowlerValueError(f"[{'.'.join(context) or self.name}]: {str(e)}")

        return value


class Keyword(_Field):
    """A field storing a short string with a technical interpretation.

    Examples: file hashes, service names, document ids
    """

    def check(self, value, context=[], **kwargs):
        # We have a special case for bytes here due to how often strings and bytes
        # get mixed up in python apis
        if self.optional and value is None:
            return None

        if isinstance(value, bytes):
            raise HowlerValueError(f"[{'.'.join(context) or self.name}] Keyword doesn't accept bytes values")

        if value == "" or value is None:
            if self.default_set:
                value = self.default
            else:
                raise HowlerValueError(
                    f"[{'.'.join(context) or self.name}] Empty strings are not allowed without defaults"
                )

        if value is None:
            return None

        return str(value)


class EmptyableKeyword(_Field):
    """A keyword which allow to differentiate between empty and None values."""

    def check(self, value, context=[], **kwargs):
        if self.optional and value is None:
            return None

        # We have a special case for bytes here due to how often strings and bytes
        # get mixed up in python apis
        if isinstance(value, bytes):
            raise HowlerValueError(f"[{'.'.join(context) or self.name}] EmptyableKeyword doesn't accept bytes values")

        if value is None and self.default_set:
            value = self.default

        if value is None:
            return None

        return str(value)


class UpperKeyword(Keyword):
    """A field storing a short uppercase string with a technical interpretation."""

    def check(self, value, context=[], **kwargs):
        kw_val = super().check(value, context=context, **kwargs)

        if kw_val is None:
            return None

        return kw_val.upper()


class LowerKeyword(Keyword):
    """
    A field storing a short lowercase string with a technical interpretation.
    """

    def check(self, value, context=[], **kwargs):
        kw_val = super().check(value, context=context, **kwargs)

        if kw_val is None:
            return None

        return kw_val.lower()


class CaseInsensitiveKeyword(Keyword):
    """
    A field storing a string with a technical interpretation, but is case-insensitive when searching.
    """


class Any(Keyword):
    """A field that can hold any value whatsoever but which is stored as a
    Keyword in the datastore index
    """

    def __init__(self, *args, **kwargs):
        kwargs["index"] = False
        kwargs["store"] = False
        super().__init__(*args, **kwargs)

    def check(self, value, **_):
        return value


class ValidatedKeyword(Keyword):
    """Keyword field which the values are validated by a regular expression"""

    def __init__(self, validation_regex, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validation_regex = re.compile(validation_regex)

    def __deepcopy__(self, memo=None):
        # NOTE: This deepcopy code does not work with a sub-class that add args of kwargs that should be copied.
        #       If that is the case, the sub-class should implement its own deepcopy function.
        valid_fields = ["name", "index", "store", "copyto", "default", "description"]
        if "validation_regex" in self.__class__.__init__.__code__.co_varnames:
            return self.__class__(
                self.validation_regex.pattern,
                **{k: v for k, v in self.__dict__.items() if k in valid_fields},
            )
        else:
            return self.__class__(**{k: v for k, v in self.__dict__.items() if k in valid_fields})

    def check(self, value, context=[], **kwargs):
        if self.optional and value is None:
            return None

        if not value:
            if self.default_set:
                value = self.default
            else:
                raise HowlerValueError(
                    f"[{'.'.join(context) or self.name}]: Empty strings are not allowed without defaults"
                )

        if value is None:
            return value

        if not self.validation_regex.match(value):
            raise HowlerValueError(
                f"[{'.'.join(context) or self.name}]: '{value}' not match the "
                f"validator: {self.validation_regex.pattern}"
            )

        return str(value)


class IP(Keyword):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validation_regex = re.compile(IP_ONLY_REGEX)

    def check(self, value, context=[], **kwargs):
        if not value:
            return None

        if not self.validation_regex.match(value):
            raise HowlerValueError(
                f"[{'.'.join(context) or self.name}]: '{value}' not match the "
                f"validator: {self.validation_regex.pattern}"
            )

        return value


class Domain(Keyword):
    def __init__(self, *args, strict=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.strict = strict

    def check(self, value, context=[], **kwargs):
        if not value:
            return None

        domain_result = validators.domain(value)
        # We'll only raise the exception if strict mode is enabled - otherwise, we'll check hostname validation as well
        if isinstance(domain_result, Exception) and self.strict:
            raise HowlerValueError(
                f"[{'.'.join(context) or self.name}] '{value}' did not pass validation."
            ) from domain_result

        hostname_result = validators.hostname(value)
        if isinstance(hostname_result, Exception):
            raise HowlerValueError(
                f"[{'.'.join(context) or self.name}] '{value}' did not pass validation."
            ) from hostname_result

        return value.lower()


class Email(Keyword):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validation_regex = re.compile(EMAIL_REGEX)

    def check(self, value, context=[], **kwargs):
        if not value:
            return None

        validation_result = validators.email(value)
        if isinstance(validation_result, Exception):
            raise HowlerValueError(
                f"[{'.'.join(context) or self.name}] '{value}' did not pass validation."
            ) from validation_result

        match = self.validation_regex.match(value)
        if not is_valid_domain(match.group(1)):
            raise HowlerValueError(
                f"[{'.'.join(context) or self.name}] '{match.group(1)}' in email '{value}'" " is not a valid Domain."
            )

        return value.lower()


class URI(Keyword):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validation_regex = re.compile(FULL_URI)

    def check(self, value, context=[], **kwargs):
        if not value:
            return None

        match = self.validation_regex.match(value)
        if not match:
            raise HowlerValueError(
                f"[{'.'.join(context) or self.name}] '{value}' not match the "
                f"validator: {self.validation_regex.pattern}"
            )

        if not is_valid_domain(match.group(2)) and not is_valid_ip(match.group(2)):
            raise HowlerValueError(
                f"[{'.'.join(context) or self.name}] '{match.group(2)}' in URI '{value}'"
                " is not a valid Domain or IP."
            )

        return match.group(0).replace(match.group(1), match.group(1).lower())


class URIPath(ValidatedKeyword):
    def __init__(self, *args, **kwargs):
        super().__init__(URI_PATH, *args, **kwargs)


class MAC(ValidatedKeyword):
    def __init__(self, *args, **kwargs):
        super().__init__(MAC_REGEX, *args, **kwargs)


class PhoneNumber(ValidatedKeyword):
    def __init__(self, *args, **kwargs):
        super().__init__(PHONE_REGEX, *args, **kwargs)


class SSDeepHash(ValidatedKeyword):
    def __init__(self, *args, **kwargs):
        super().__init__(SSDEEP_REGEX, *args, **kwargs)


class SHA1(ValidatedKeyword):
    def __init__(self, *args, **kwargs):
        super().__init__(SHA1_REGEX, *args, **kwargs)


class SHA256(ValidatedKeyword):
    def __init__(self, *args, **kwargs):
        super().__init__(SHA256_REGEX, *args, **kwargs)


class HowlerHash(ValidatedKeyword):
    def __init__(self, *args, **kwargs):
        super().__init__(HOWLER_HASH_REGEX, *args, **kwargs)


class MD5(ValidatedKeyword):
    def __init__(self, *args, **kwargs):
        super().__init__(MD5_REGEX, *args, **kwargs)


class Platform(ValidatedKeyword):
    def __init__(self, *args, **kwargs):
        super().__init__(PLATFORM_REGEX, *args, **kwargs)


class Processor(ValidatedKeyword):
    def __init__(self, *args, **kwargs):
        super().__init__(PROCESSOR_REGEX, *args, **kwargs)


class Enum(Keyword):
    """A field storing a short string that has predefined list of possible values"""

    def __init__(self, values: PyEnum | list[typing.Any] | set[typing.Any], *args, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(values, set):
            self.values = values
        elif isinstance(values, (list, tuple)):
            self.values = set(values)
        elif isinstance(values, (PyEnum, EnumMeta)):
            self.values = set([e.value for e in values])
        else:
            raise HowlerTypeError(f"Type unsupported for Enum odm: {type(values)}")

    def check(self, value, context=[], **kwargs):
        if self.optional and value is None:
            return None

        if not value:
            if self.default_set:
                value = self.default
            else:
                raise HowlerValueError(f"[{'.'.join(context)}] Empty enums are not allow without defaults")

        if value not in self.values:
            raise HowlerValueError(f"[{'.'.join(context)}] {value} not in the possible values: {self.values}")

        if value is None:
            return value

        return str(value)


class UUID(Keyword):
    """A field storing an auto-generated unique ID if None is provided"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_set = True

    def check(self, value, **kwargs):
        if value is None:
            value = get_random_id()

        return str(value)


class Text(_Field):
    """A field storing human readable text data."""

    def check(self, value, context=[], **kwargs):
        if self.optional and value is None:
            return None

        if not value:
            if self.default_set:
                value = self.default
            else:
                raise HowlerValueError(f"[{'.'.join(context)}] Empty strings are not allowed without defaults")

        if value is None:
            return None

        return str(value)


class IndexText(_Field):
    """A special field with special processing rules to simplify searching."""

    def check(self, value, **kwargs):
        if self.optional and value is None:
            return None

        return str(value)


class Integer(_Field):
    """A field storing an integer value."""

    def check(self, value, context=[], **kwargs):
        if self.optional and value is None:
            return None

        if value is None or value == "":
            if self.default_set:
                return self.default

        try:
            return int(value)
        except ValueError as e:
            raise HowlerValueError(f"[{'.'.join(context)}]: {str(e)}")


class Float(_Field):
    """A field storing a floating point value."""

    def check(self, value, context=[], **kwargs):
        if self.optional and value is None:
            return None

        if not value:
            if self.default_set:
                return self.default
        try:
            return float(value)
        except ValueError as e:
            raise HowlerValueError(f"[{'.'.join(context)}]: {str(e)}")


class ClassificationObject(object):
    def __init__(self, engine, value, is_uc=False):
        self.engine = engine
        self.is_uc = is_uc
        self.value = engine.normalize_classification(value, skip_auto_select=is_uc)

    def get_access_control_parts(self):
        return self.engine.get_access_control_parts(self.value, user_classification=self.is_uc)

    def min(self, other):
        return ClassificationObject(
            self.engine,
            self.engine.min_classification(self.value, other.value),
            is_uc=self.is_uc,
        )

    def max(self, other):
        return ClassificationObject(
            self.engine,
            self.engine.max_classification(self.value, other.value),
            is_uc=self.is_uc,
        )

    def intersect(self, other):
        return ClassificationObject(
            self.engine,
            self.engine.intersect_user_classification(self.value, other.value),
            is_uc=self.is_uc,
        )

    def long(self):
        return self.engine.normalize_classification(self.value, skip_auto_select=self.is_uc)

    def small(self):
        return self.engine.normalize_classification(self.value, long_format=False, skip_auto_select=self.is_uc)

    def __str__(self):
        return self.value

    def __eq__(self, other):
        return self.value == other.value

    def __ne__(self, other):
        return self.value != other.value

    def __le__(self, other):
        return self.engine.is_accessible(other.value, self.value)

    def __lt__(self, other):
        return self.engine.is_accessible(other.value, self.value)

    def __ge__(self, other):
        return self.engine.is_accessible(self.value, other.value)

    def __gt__(self, other):
        return not self.engine.is_accessible(other.value, self.value)


class Classification(Keyword):
    """A field storing access control classification."""

    def __init__(self, *args, is_user_classification=False, yml_config=None, **kwargs):
        """An expanded classification is one that controls the access to the document
        which holds it.
        """
        super().__init__(*args, **kwargs)
        self.engine = loader.get_classification(yml_config=yml_config)
        self.is_uc = is_user_classification

    def check(self, value, **kwargs):
        if self.optional and value is None:
            return None

        if isinstance(value, ClassificationObject):
            return ClassificationObject(self.engine, value.value, is_uc=self.is_uc)

        return ClassificationObject(self.engine, value, is_uc=self.is_uc)


class ClassificationString(Keyword):
    """A field storing the classification as a string only."""

    def __init__(self, *args, yml_config=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine = loader.get_classification(yml_config=yml_config)

    def check(self, value, context=[], **kwargs):
        if self.optional and value is None:
            return None

        if not value:
            if self.default_set:
                value = self.default
            else:
                raise HowlerValueError(
                    f"[{'.'.join(context) or self.name}]: Empty classification is not allowed without defaults"
                )

        if not self.engine.is_valid(value):
            raise HowlerValueError(f"[{'.'.join(context) or self.name}]: Invalid classification: {value}")

        return str(value)


class TypedList(list):
    def __init__(self, type_p, *items, context=[], **kwargs):
        self.context = context
        self.type = type_p

        super().__init__([type_p.check(el, context=self.context, **kwargs) for el in items])

    def append(self, item):
        super().append(self.type.check(item, context=self.context))

    def extend(self, sequence):
        super().extend(self.type.check(item, context=self.context) for item in sequence)

    def insert(self, index, item):
        super().insert(index, self.type.check(item, context=self.context))

    def __setitem__(self, index, item):
        if isinstance(index, slice):
            item = [self.type.check(val, context=self.context) for val in item]
            super().__setitem__(index, item)
        else:
            super().__setitem__(index, self.type.check(item, context=self.context))


class List(_Field):
    """A field storing a sequence of typed elements."""

    def __init__(self, child_type, **kwargs):
        super().__init__(**kwargs)
        self.child_type = child_type

    def check(self, value, **kwargs):
        if self.optional and value is None:
            return None

        if isinstance(self.child_type, Compound) and isinstance(value, dict):
            # Search queries of list of compound fields will return dotted paths of list of
            # values. When processed through the flat_fields function, since this function
            # has no idea about the data layout, it will transform the dotted paths into
            # a dictionary of items then contains a list of object instead of a list
            # of dictionaries with single items.

            # The following piece of code transforms the dictionary of list into a list of
            # dictionaries so the rest of the model validation can go through.

            fixed_values = []
            check_key = None
            length = None
            for key, val in flatten(value).items():
                if not isinstance(val, list):
                    val = [val]

                if length is None:
                    check_key = key
                    length = len(val)

                    for entry in val:
                        fixed_values.append({key: entry})
                elif len(val) != length:
                    raise HowlerValueError(
                        "Flattened fields creating list of ODMs must have equal length. Key "
                        f"{key} has length {len(val)} compared to key {check_key} with length {length}."
                    )
                else:
                    for i in range(len(val)):
                        fixed_values[i][key] = val[i]

            return TypedList(
                self.child_type,
                *fixed_values,
                **kwargs,
            )

        if value is None:
            logger.warning("Value is None, but optional is not set to True. Using an empty list to avoid errors.")
            value = []

        return TypedList(self.child_type, *value, **kwargs)

    def apply_defaults(self, index, store):
        """Initialize the default settings for the child field."""
        # First apply the default to the list itself
        super().apply_defaults(index, store)
        # Then pass through the initialized values on the list to the child type
        self.child_type.apply_defaults(self.index, self.store)

    def fields(self):
        out = dict()
        for name, field_data in self.child_type.fields().items():
            field_data = copy.deepcopy(field_data)
            field_data.apply_defaults(self.index, self.store)
            out[name] = field_data
        return out


class TypedMapping(dict):
    def __init__(self, type_p, index, store, sanitizer, context=[], **items):
        self.index = index
        self.store = store
        self.sanitizer = sanitizer
        self.context = context

        for key in items.keys():
            if not self.sanitizer.match(key):
                raise HowlerKeyError(f"[{'.'.join(self.context)}]: Illegal key {key}")

        super().__init__({key: type_p.check(el, context=self.context) for key, el in items.items()})
        self.type = type_p

    def __setitem__(self, key, item):
        if not self.sanitizer.match(key):
            raise HowlerKeyError(f"[{'.'.join(self.context)}]: Illegal key: {key}")

        return super().__setitem__(key, self.type.check(item, context=self.context))

    def update(self, *args, **kwargs):
        # Update supports three input layouts:
        # 1. A single dictionary
        if len(args) == 1 and isinstance(args[0], dict):
            for key in args[0].keys():
                if not self.sanitizer.match(key):
                    raise HowlerKeyError(f"[{'.'.join(self.context)}]: Illegal key: {key}")

            return super().update({key: self.type.check(item, context=self.context) for key, item in args[0].items()})

        # 2. A list of key value pairs as if you were constructing a dictionary
        elif args:
            for key, _ in args:
                if not self.sanitizer.match(key):
                    raise HowlerKeyError(f"[{'.'.join(self.context)}]: Illegal key: {key}")

            return super().update({key: self.type.check(item, context=self.context) for key, item in args})

        # 3. Key values as arguments, can be combined with others
        if kwargs:
            for key in kwargs.keys():
                if not self.sanitizer.match(key):
                    raise HowlerKeyError(f"[{'.'.join(self.context)}]: Illegal key: {key}")

            return super().update({key: self.type.check(item, context=self.context) for key, item in kwargs.items()})


class Mapping(_Field):
    """A field storing a sequence of typed elements."""

    def __init__(self, child_type, **kwargs):
        self.child_type = child_type
        super().__init__(**kwargs)

    def check(self, value, **kwargs):
        if self.optional and value is None:
            return None

        if self.index or self.store:
            sanitizer = FIELD_SANITIZER
        else:
            sanitizer = NOT_INDEXED_SANITIZER

        return TypedMapping(self.child_type, self.index, self.store, sanitizer, **value)

    def apply_defaults(self, index, store):
        """Initialize the default settings for the child field."""
        # First apply the default to the list itself
        super().apply_defaults(index, store)
        # Then pass through the initialized values on the list to the child type
        self.child_type.apply_defaults(self.index, self.store)


class FlattenedListObject(Mapping):
    """A field storing a flattened object"""

    def __init__(self, **kwargs):
        super().__init__(List(Json()), **kwargs)

    def check(self, value, **kwargs):
        if self.optional and value is None:
            return None

        return TypedMapping(self.child_type, self.index, self.store, FLATTENED_OBJECT_SANITIZER, **value)

    def apply_defaults(self, index, store):
        """Initialize the default settings for the child field."""
        # First apply the default to the list itself
        super().apply_defaults(index, store)
        # Then pass through the initialized values on the list to the child type
        self.child_type.apply_defaults(self.index, self.store)


class FlattenedObject(Mapping):
    """A field storing a flattened object"""

    def __init__(self, **kwargs):
        super().__init__(Json(), **kwargs)

    def check(self, value, context=[], **kwargs):
        if self.optional and value is None:
            return None

        return TypedMapping(
            self.child_type,
            self.index,
            self.store,
            FLATTENED_OBJECT_SANITIZER,
            context=context,
            **value,
        )

    def apply_defaults(self, index, store):
        """Initialize the default settings for the child field."""
        # First apply the default to the list itself
        super().apply_defaults(index, store)
        # Then pass through the initialized values on the list to the child type
        self.child_type.apply_defaults(self.index, self.store)


class Compound(_Field):
    def __init__(self, field_type, **kwargs):
        super().__init__(**kwargs)
        self.child_type = field_type

    def check(
        self,
        value,
        mask=None,
        ignore_extra_values=False,
        extra_fields={},
        context=[],
        **kwargs,
    ):
        if self.optional and value is None:
            return None

        if isinstance(value, self.child_type):
            return value

        return self.child_type(
            value,
            mask=mask,
            ignore_extra_values=ignore_extra_values,
            extra_fields=extra_fields,
            context=context,
        )

    def fields(self):
        out = dict()
        for name, field_data in self.child_type.fields().items():
            field_data = copy.deepcopy(field_data)
            field_data.apply_defaults(self.index, self.store)
            out[name] = field_data
        return out


class Optional(_Field):
    """A wrapper field to allow simple types (int, float, bool) to take None values."""

    def __init__(self, child_type: _Field, **kwargs):
        if child_type.default_set:
            kwargs["default"] = child_type.default
        else:
            child_type.default_set = True
        super().__init__(**kwargs)
        self.default_set = True
        self.child_type = child_type
        self.child_type.optional = True

    def check(self, value, *args, **kwargs):
        if value is None:
            return None

        return self.child_type.check(value, *args, **kwargs)

    def fields(self):
        return self.child_type.fields()

    def apply_defaults(self, index, store):
        super().apply_defaults(index, store)
        self.child_type.apply_defaults(self.index, self.store)


class Model:
    @classmethod
    def fields(cls, skip_mappings=False) -> _Mapping[str, _Field]:
        """Describe the elements of the model.

        For compound fields return the field object.

        Args:
            skip_mappings (bool): Skip over mappings where the real subfield names are unknown.
        """
        if skip_mappings and hasattr(cls, "_odm_field_cache_skip"):
            return cls._odm_field_cache_skip

        if not skip_mappings and hasattr(cls, "_odm_field_cache"):
            return cls._odm_field_cache

        out = dict()
        for name, field_data in cls.__dict__.items():
            if isinstance(field_data, _Field):
                if skip_mappings and isinstance(field_data, Mapping):
                    continue
                out[name.rstrip("_")] = field_data

        if skip_mappings:
            cls._odm_field_cache_skip = out
        else:
            cls._odm_field_cache = out
        return out

    @classmethod
    def add_namespace(cls, namespace: str, field: _Field):
        field.name = namespace

        if hasattr(cls, "_odm_field_cache_skip"):
            cls._odm_field_cache_skip[namespace.rstrip("_")] = field

        if hasattr(cls, "_odm_field_cache"):
            cls._odm_field_cache[namespace.rstrip("_")] = field

        return setattr(cls, namespace, field)

    @staticmethod
    def _recurse_fields(name, field, show_compound, skip_mappings, multivalued=False):
        name = name.rstrip("_")
        out = dict()
        for sub_name, sub_field in field.fields().items():
            sub_field.multivalued = multivalued or isinstance(field, List)

            if skip_mappings and isinstance(sub_field, Mapping):
                continue

            elif isinstance(sub_field, (List, Optional, Compound)) and sub_name != "":
                out.update(
                    Model._recurse_fields(
                        f"{name}.{sub_name}",
                        sub_field.child_type,
                        show_compound,
                        skip_mappings,
                        multivalued=multivalued or isinstance(sub_field, List),
                    )
                )

            elif sub_name:
                out[f"{name}.{sub_name}"] = sub_field

            else:
                out[name] = sub_field

        if isinstance(field, Compound) and show_compound:
            out[name] = field

        return out

    @classmethod
    def flat_fields(cls, show_compound=False, skip_mappings=False) -> _Mapping[str, _Field]:
        """Describe the elements of the model.

        Recurse into compound fields, concatenating the names with '.' separators.

        Args:
            show_compound (bool): Show compound as valid fields.
            skip_mappings (bool): Skip over mappings where the real subfield names are unknown.
        """
        out = dict()
        for name, field in cls.__dict__.items():
            if isinstance(field, _Field):
                if skip_mappings and isinstance(field, Mapping):
                    continue
                out.update(
                    Model._recurse_fields(
                        name,
                        field,
                        show_compound,
                        skip_mappings,
                        multivalued=isinstance(field, List),
                    )
                )
        return out

    @classmethod
    def markdown(
        cls,
        toc_depth=1,
        include_autogen_note=True,
        defaults=None,
        url_prefix="/howler-docs/odm/class/",
    ) -> Union[str, Dict]:
        markdown_content = (
            (
                '??? success "Auto-Generated Documentation"\n    '
                "This set of documentation is automatically generated from source, and will help ensure any change to "
                "functionality will always be documented and available on release.\n\n"
            )
            if include_autogen_note
            else ""
        )

        # Header
        markdown_content += f"{'#'*toc_depth} {cls.__name__}\n\n> {cls.__description}\n\n"

        # Table
        table = "| Field | Type | Description | Required | Default |\n| :--- | :--- | :--- | :--- | :--- |\n"

        # Determine the type of Field we're dealing with
        # if possible return the Model class if wrapped in Compound
        def get_type(field_class: _Field) -> Tuple[str, Model]:
            if field_class.__class__ == Optional:
                return get_type(field_class.child_type)
            elif field_class.__class__ == Compound:
                name = field_class.child_type.__name__

                return (
                    f"[{name}]({url_prefix}{name.lower()})",
                    field_class.child_type,
                )
            elif field_class.__class__ in [Mapping, List]:
                child_type, child_class = (
                    field_class.child_type.__class__.__name__,
                    field_class.child_type.__class__,
                )
                if field_class.child_type.__class__ == Compound:
                    child_type, child_class = get_type(field_class.child_type)
                return f"{field_class.__class__.__name__} [{child_type}]", child_class
            elif field_class.__class__.__name__ == "type":
                return field_class.__name__, None

            return field_class.__class__.__name__, None

        for field, info in cls.fields().items():
            field_type, field_class = get_type(info)

            # Field description
            description = info.description
            if description is None and info.__class__ == Optional:
                description = info.child_type.description
                if info.child_type.reference:
                    description += f'<br><a href="{info.child_type.reference}">Reference Link</a><br>'
            elif info.reference:
                description += f'<br><a href="{info.reference}">Reference Link</a><br>'

            # If field type is Enum, then show the possible values that can be used in the description
            if field_type == "Enum":
                values = info.child_type.values if info.__class__ != Enum else info.values
                none_value = False
                if None in values:
                    none_value = True
                    values.remove(None)

                values = [f'"{v}"' if v else str(v) for v in sorted(values)]
                values.append("None") if none_value else None
                description = f'{description}<br>Values:<br>`{", ".join(values)}`'

            # Is this a required field?
            if info.__class__ != Optional and not info.optional:
                required = ":material-checkbox-marked-outline: Yes"
            else:
                required = ":material-minus-box-outline: Optional"

            if info.deprecated:
                required += " :material-alert-box-outline: Deprecated - "
                required += info.deprecated_description
            elif info.__class__ == Optional and info.child_type.deprecated:
                required += " :material-alert-box-outline: Deprecated - "
                required += info.child_type.deprecated_description

            # Determine the correct default values to display
            default = f"`{info.default}`"
            # If the field is a model, then provide a link to that documentation
            if field_class and issubclass(field_class, Model) and isinstance(info.default, dict):
                ref_link = field_type[field_type.index("(") : field_type.index(")") + 1]
                default = f"See [{field_class.__name__}]{ref_link} for more details."

            # Handle how to display values from provided defaults (different from field defaults)
            elif isinstance(defaults, dict):
                val = defaults.get(field, {})
                default = f"`{val if not isinstance(val, dict) else info.default}`"
            elif isinstance(defaults, list):
                default = f"`{defaults}`"
            row = f"| {field} | {field_type} | {description} | {required} | {default} |\n"
            table += row

        markdown_content += table + "\n\n"

        return markdown_content

    # Allow attribute assignment by default in the constructor until it is removed
    __frozen = False
    # Descriptions of the model should be class-accessible only for markdown()
    __description = None

    def __init__(
        self,
        data: dict = None,
        mask: list = None,
        docid=None,
        ignore_extra_values=True,
        extra_fields={},
        context=[],
    ):
        if len(context) == 0:
            context = [self.__class__.__name__.lower()]

        if data is None:
            data = {}

        if not hasattr(data, "items"):
            raise HowlerTypeError(f"'{self.__class__.__name__}' object must be constructed with dict like")
        self._odm_py_obj = {}
        self._id = docid
        self.context = context

        # Parse the field mask for sub models
        mask_map = {}
        if mask is not None:
            for entry in mask:
                if "." in entry:
                    child, sub_key = entry.split(".", 1)
                    try:
                        mask_map[child].append(sub_key)
                    except KeyError:
                        mask_map[child] = [sub_key]
                else:
                    mask_map[entry] = None

        # Get the list of fields we expect this object to have
        fields = self.fields()
        self._odm_removed = {}
        if mask is not None:
            self._odm_removed = {k: v for k, v in fields.items() if k not in mask_map}
            fields = {k: v for k, v in fields.items() if k in mask_map}

        # Trim out keys that actually belong to sub sections
        data = flat_to_nested(data)

        # Check to make sure we can use all the data we are given
        self.unused_keys = set(data.keys()) - set(fields.keys()) - BANNED_FIELDS
        extra_keys = set(extra_fields.keys()) - set(data.keys())
        if self.unused_keys and not ignore_extra_values:
            raise HowlerValueError(
                f"[{'.'.join(context)}]: object was created with invalid parameters: " f"{', '.join(self.unused_keys)}"
            )

        # Pass each value through it's respective validator, and store it
        for name, field_type in fields.items():
            params = {"ignore_extra_values": ignore_extra_values}
            if name in mask_map and mask_map[name]:
                params["mask"] = mask_map[name]
            if name in extra_fields and extra_fields[name]:
                params["extra_fields"] = extra_fields[name]

            try:
                value = data[name]
            except KeyError:
                if field_type.default_set:
                    value = copy.copy(field_type.default)
                elif not field_type.optional:
                    raise HowlerValueError(f"[{'.'.join([*context, name])}]: value is missing from the object!")
                else:
                    value = None

            self._odm_py_obj[name.rstrip("_")] = field_type.check(value, context=[*context, name], **params)

            value = None

        for key in extra_keys:
            self._odm_py_obj[key.rstrip("_")] = Any().check(extra_fields[key], context=[*context, name])

        # Since the layout of model objects should be fixed, don't allow any further
        # attribute assignment
        self.__frozen = True

    def as_primitives(self, hidden_fields=False, strip_null=True) -> dict[str, typing.Any]:
        """Convert the object back into primitives that can be json serialized."""
        out = {}

        fields = self.fields()
        for key, value in self._odm_py_obj.items():
            field_type = fields.get(key, Any)
            if value is not None or (value is None and field_type.default_set):
                if strip_null and value is None:
                    continue

                if isinstance(value, Model):
                    out[key] = value.as_primitives(strip_null=strip_null)
                elif isinstance(value, datetime):
                    out[key] = value.strftime(DATEFORMAT)
                elif isinstance(value, TypedMapping):
                    out[key] = {
                        k: (v.as_primitives(strip_null=strip_null) if isinstance(v, Model) else v)
                        for k, v in value.items()
                    }
                elif isinstance(value, TypedList):
                    out[key] = [(v.as_primitives(strip_null=strip_null) if isinstance(v, Model) else v) for v in value]
                elif isinstance(value, ClassificationObject):
                    out[key] = str(value)
                    if hidden_fields:
                        out.update(value.get_access_control_parts())
                else:
                    out[key] = value
        return out

    def json(self):
        return json.dumps(self.as_primitives())

    def __eq__(self, other):
        if isinstance(other, dict):
            try:
                other = self.__class__(other)
            except (ValueError, KeyError):
                return False

        elif not isinstance(other, self.__class__):
            return False

        if len(self._odm_py_obj) != len(other._odm_py_obj):
            return False

        for name, field in self.fields().items():
            if name in self._odm_removed:
                continue
            if field.__get__(self) != field.__get__(other):
                return False

        return True

    def __repr__(self):
        if self._id:
            return f"<{self.__class__.__name__} [{self._id}] {self.json()}>"
        return f"<{self.__class__.__name__} {self.json()}>"

    def __getitem__(self, name):
        data = self._odm_py_obj
        for component in name.split("."):
            data = data[component.rstrip("_")]

        return data

    def get(self, name, default=None):
        try:
            return self[name]
        except KeyError:
            return default

    def __setitem__(self, name, value):
        if name not in self._odm_field_cache:
            raise HowlerKeyError(f"[{'.'.join(self.context)}]: {name}")
        return self.__setattr__(name, value)

    def __getattr__(self, name):
        # Any attribute that hasn't been explicitly declared is forbidden
        if name.rstrip("_") not in self.fields():
            raise HowlerKeyError(f"[{'.'.join(self.context)}]: {name}")

        return super().__getattr__(name)

    def __setattr__(self, name, value):
        # Any attribute that hasn't been explicitly declared is forbidden
        if self.__frozen and name.rstrip("_") not in self.fields():
            raise HowlerKeyError(f"[{'.'.join(self.context)}]: {name}")
        return object.__setattr__(self, name, value)

    def __contains__(self, name):
        return name.rstrip("_") in self.fields()


def recursive_set_name(field, name, to_parent=False):
    if not to_parent:
        field.name = name
    else:
        field.parent_name = name

    if isinstance(field, Optional):
        recursive_set_name(field.child_type, name)
    if isinstance(field, List):
        recursive_set_name(field.child_type, name, to_parent=True)


def model(index=None, store=None, description=None):
    """Decorator to create model objects."""

    def _finish_model(cls):
        cls._Model__description = description
        for name, field_data in cls.fields().items():
            if not FIELD_SANITIZER.match(name) or name in BANNED_FIELDS:
                raise HowlerValueError(f"Illegal variable name: {name}")

            recursive_set_name(field_data, name)
            field_data.apply_defaults(index=index, store=store)
        return cls

    return _finish_model


def _construct_field(field, value):
    if isinstance(field, List):
        clean, dropped = [], []
        for item in value:
            _c, _d = _construct_field(field.child_type, item)
            if _c is not None:
                clean.append(_c)
            if _d is not None and _d != "":
                dropped.append(_d)
        return clean or None, dropped or None

    elif isinstance(field, Compound):
        _c, _d = construct_safe(field.child_type, value)
        if len(_d) == 0:
            _d = None
        return _c, _d
    elif isinstance(field, Optional):
        return _construct_field(field.child_type, value)
    else:
        try:
            return field.check(value), None
        except (ValueError, TypeError):
            return None, value


def construct_safe(mod, data) -> tuple[_Any, dict]:
    if not isinstance(data, dict):
        return None, data
    fields = mod.fields()
    clean = {}
    dropped = {}
    for key, value in data.items():
        if key not in fields:
            dropped[key] = value
            continue

        _c, _d = _construct_field(fields[key], value)

        if _c is not None:
            clean[key] = _c
        if _d is not None:
            dropped[key] = _d

    try:
        return mod(clean), dropped
    except ValueError:
        return None, recursive_update(dropped, clean)
