"""ECS Windows Registry field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, keyword, list_field, optional, register_model


@register_model(
    index=True,
    store=True,
    description="Fields related to data written to Windows Registry.",
    embedded=True,
)
class RegistryData(HowlerEmbeddedModel):
    """Fields related to data written to Windows Registry."""

    bytes: optional(keyword(), description="Original bytes written with base64 encoding.")
    strings: optional(list_field(keyword()), description="Content when writing string types.")
    type: optional(keyword(), description="Standard registry type for encoding contents.")


@register_model(index=True, store=True, description="Fields related to Windows Registry operations.", embedded=True)
class Registry(HowlerEmbeddedModel):
    """Fields related to Windows Registry operations."""

    data: optional(compound(RegistryData), description="Fields related to data written to Windows Registry.")
    hive: optional(keyword(), description="Abbreviated name for the hive.")
    key: optional(keyword(), description="Hive-relative path of keys.")
    path: optional(keyword(), description="Full path, including hive, key and value.")
    value: optional(keyword(), description="Name of the value written.")
