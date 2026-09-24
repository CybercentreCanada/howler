"""Generate validated synthetic values from Pydantic field annotations."""

import random
import string
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, get_args, get_origin

from pydantic import BaseModel

from howler.common.loader import get_classification
from howler.models.registry import field_metadata, unwrap_annotation
from howler.utils.uid import get_random_id

WORDS = "cyber security technology network infrastructure detection investigation analyst service cloud".split()


def get_random_word() -> str:
    """Return a synthetic word."""
    return random.choice(WORDS)


def get_random_hash(hash_len: int) -> str:
    """Return a hexadecimal hash of the requested length."""
    return "".join(random.choices("0123456789abcdef", k=hash_len))


def get_random_iso_date(epoch: float | None = None) -> str:
    """Return a UTC timestamp, optionally from an epoch value."""
    value = datetime.fromtimestamp(epoch, timezone.utc) if epoch is not None else datetime.now(timezone.utc)
    return value.isoformat().replace("+00:00", "Z")


def get_random_string(smin: int = 4, smax: int = 24) -> str:
    """Return a random alphabetic string."""
    return "".join(random.choices(string.ascii_letters, k=random.randint(smin, smax)))


def get_random_host() -> str:
    """Return an example hostname."""
    return f"{get_random_word()}.example.com"


def get_random_ip() -> str:
    """Return a synthetic IPv4 address."""
    return ".".join(str(random.randint(1, 254)) for _ in range(4))


def get_random_filename() -> str:
    """Return an example filename."""
    return f"{get_random_word()}.txt"


def get_random_user_agent() -> str:
    """Return an example browser user agent."""
    return "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/108.0.0.0 Safari/537.36"


def get_random_user() -> str:
    """Return a development user."""
    return random.choice(["admin", "user", "shawn-h"])


def random_department() -> tuple[str, str]:
    """Return a synthetic organization name and identifier."""
    return random.choice([("Cyber Centre", "CCCS"), ("Shared Services", "SSC"), ("Statistics", "STAT")])


def random_data_for_field(annotation: Any, name: str = "", minimal: bool = False) -> Any:  # noqa: C901
    """Generate a value using container types, field vocabulary, and validation constraints."""
    unwrapped = unwrap_annotation(annotation)
    origin = get_origin(unwrapped)
    metadata = field_metadata(annotation)
    kind = metadata.kind if metadata else ""
    options = dict(metadata.options) if metadata else {}
    if origin is list:
        return [random_data_for_field(get_args(unwrapped)[0], name, minimal) for _ in range(random.randint(1, 3))]
    if origin is dict:
        return {f"key_{index}": random_data_for_field(get_args(unwrapped)[1], name, minimal) for index in range(2)}
    if isinstance(unwrapped, type) and issubclass(unwrapped, BaseModel):
        return _random_model_data(unwrapped, minimal)
    if kind in {"Classification", "ClassificationString"}:
        return get_classification().UNRESTRICTED
    if kind == "Enum":
        return random.choice([value for value in options["values"] if value is not None])
    if kind == "Boolean" or unwrapped is bool:
        return random.choice([True, False])
    if kind in {"Integer", "Long", "Float"} or unwrapped in (int, float):
        # Pydantic stores numeric constraints on the Annotated field, including nullable wrappers.
        constraints = []
        current = annotation
        while get_origin(current) is Annotated:
            current, *items = get_args(current)
            constraints.extend(items)
        low, high = 0, 100
        for constraint in constraints:
            if getattr(constraint, "ge", None) is not None:
                low = constraint.ge
            if getattr(constraint, "le", None) is not None:
                high = constraint.le
        high = max(low, high)
        return random.uniform(low, high) if kind == "Float" else random.randint(int(low), int(high))
    if kind == "Date":
        return (datetime.now(timezone.utc) - timedelta(seconds=random.randint(0, 86400))).isoformat()
    if kind == "UUID":
        return get_random_id()
    if name in {"sha384", "sha512"}:
        return "".join(random.choices("0123456789abcdef", k={"sha384": 96, "sha512": 128}[name]))
    if kind in {"MD5", "SHA1", "SHA256", "HowlerHash"}:
        length = {"MD5": 32, "SHA1": 40}.get(kind, 64)
        return "".join(random.choices("0123456789abcdef", k=length))
    if kind == "IP":
        return get_random_ip()
    if kind == "MAC":
        return "00:11:22:33:44:55"
    if kind == "Domain":
        return get_random_host()
    if kind == "Email":
        return f"{get_random_word()}@example.com"
    if kind == "URI":
        return f"https://{get_random_host()}/sample"
    if kind == "URIPath":
        return "/sample/path"
    if kind == "PhoneNumber":
        return "613-555-0100"
    if kind == "SSDeepHash":
        return "3:abcdefghijk:abcdefghijk"
    if kind == "Platform":
        return "Linux"
    if kind == "Processor":
        return "x64"
    if kind == "UpperKeyword":
        return get_random_word().upper()
    if kind == "Text":
        return "Synthetic security event for investigation."
    if "user" in name or name == "uname":
        return get_random_user()
    return get_random_word()


def _random_model_data(model: type[BaseModel], minimal: bool) -> dict[str, Any]:
    data = {}
    for name, info in model.model_fields.items():
        if name == "meta" or (minimal and not info.is_required()):
            continue
        annotation = Annotated[(info.annotation, *info.metadata)] if info.metadata else info.annotation
        data[info.alias or name] = random_data_for_field(annotation, name, minimal)
    return data


def random_model_obj(model: type[BaseModel], as_json: bool = False) -> Any:
    """Create and validate a fully populated sample model."""
    data = _random_model_data(model, False)
    return data if as_json else model.model_validate(data)


def random_minimal_obj(model: type[BaseModel], as_json: bool = False) -> Any:
    """Create a sample with only required fields and model defaults."""
    data = _random_model_data(model, True)
    return data if as_json else model.model_validate(data)
