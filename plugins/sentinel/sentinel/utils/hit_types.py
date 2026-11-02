from typing import Any


def sentinel_record_type(hit: Any) -> str | None:
    """Return the Sentinel-owned record discriminator when present."""
    return getattr(getattr(hit, "sentinel", None), "record_type", None)


def is_derived_evidence(hit: Any) -> bool:
    """Whether a hit is a derived child representing a Graph evidence object."""
    return sentinel_record_type(hit) == "evidence"
