"""ECS Windows Registry field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, list_field, register_model


@register_model(
    index=True,
    store=True,
    description="Fields related to data written to Windows Registry.",
    embedded=True,
)
class RegistryData(HowlerEmbeddedModel):
    """Fields related to data written to Windows Registry."""

    bytes: keyword(optional=True)
    """Original bytes written with base64 encoding."""
    strings: list_field(keyword(), optional=True)
    """Content when writing string types."""
    type: keyword(optional=True)
    """Standard registry type for encoding contents."""


@register_model(index=True, store=True, description="Fields related to Windows Registry operations.", embedded=True)
class Registry(HowlerEmbeddedModel):
    """Fields related to Windows Registry operations."""

    data: RegistryData | None = None
    """Fields related to data written to Windows Registry."""
    hive: keyword(optional=True)
    """Abbreviated name for the hive."""
    key: keyword(optional=True)
    """Hive-relative path of keys."""
    path: keyword(optional=True)
    """Full path, including hive, key and value."""
    value: keyword(optional=True)
    """Name of the value written."""
