"""ECS operating system field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="The OS fields contain information about the operating system.",
    embedded=True,
)
class OS(HowlerEmbeddedModel):
    """The OS fields contain information about the operating system."""

    family: optional(keyword(), description="OS family (such as redhat, debian, freebsd, windows).")
    full: optional(keyword(), description="Operating system name, including the version or code name.")
    kernel: optional(keyword(), description="Operating system kernel version as a raw string.")
    name: optional(keyword(), description="Operating system name, without the version.")
    platform: optional(keyword(), description="Operating system platform (such centos, ubuntu, windows).")
    type: optional(
        keyword(),
        description="Use the os.type field to categorize the operating system into one of the broad "
        "commercial families.",
    )
    version: optional(keyword(), description="Operating system version as a raw string.")
