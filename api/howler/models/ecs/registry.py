"""ECS Windows Registry field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, register_model


@register_model(
    index=True,
    store=True,
    description="Fields related to data written to Windows Registry.",
    embedded=True,
)
class RegistryData(HowlerEmbeddedModel):
    """Fields related to data written to Windows Registry."""

    bytes: Keyword | None = None
    """Original bytes written with base64 encoding."""
    strings: list[Keyword] | None = None
    """Content when writing string types."""
    type: Keyword | None = None
    """Standard registry type for encoding contents."""


@register_model(index=True, store=True, description="Fields related to Windows Registry operations.", embedded=True)
class Registry(HowlerEmbeddedModel):
    """Fields related to Windows Registry operations."""

    data: RegistryData | None = None
    """Fields related to data written to Windows Registry."""
    hive: Keyword | None = None
    """Abbreviated name for the hive."""
    key: Keyword | None = None
    """Hive-relative path of keys."""
    path: Keyword | None = None
    """Full path, including hive, key and value."""
    value: Keyword | None = None
    """Name of the value written."""
