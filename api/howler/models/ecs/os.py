"""ECS operating system field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, register_model


@register_model(
    index=True,
    store=True,
    description="The OS fields contain information about the operating system.",
    embedded=True,
)
class OS(HowlerEmbeddedModel):
    """The OS fields contain information about the operating system."""

    family: keyword(optional=True, description="OS family (such as redhat, debian, freebsd, windows).")
    full: keyword(optional=True, description="Operating system name, including the version or code name.")
    kernel: keyword(optional=True, description="Operating system kernel version as a raw string.")
    name: keyword(optional=True, description="Operating system name, without the version.")
    platform: keyword(optional=True, description="Operating system platform (such centos, ubuntu, windows).")
    type: keyword(
        optional=True,
        description="Use the os.type field to categorize the operating system into one of the broad "
        "commercial families.",
    )
    version: keyword(optional=True, description="Operating system version as a raw string.")
