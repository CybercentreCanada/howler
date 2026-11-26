"""ECS operating system field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, register_model


@register_model(
    index=True,
    store=True,
    description="The OS fields contain information about the operating system.",
    embedded=True,
)
class OS(HowlerEmbeddedModel):
    """The OS fields contain information about the operating system."""

    family: Keyword | None = None
    """OS family (such as redhat, debian, freebsd, windows)."""
    full: Keyword | None = None
    """Operating system name, including the version or code name."""
    kernel: Keyword | None = None
    """Operating system kernel version as a raw string."""
    name: Keyword | None = None
    """Operating system name, without the version."""
    platform: Keyword | None = None
    """Operating system platform (such centos, ubuntu, windows)."""
    type: Keyword | None = None
    """Use the os.type field to categorize the operating system into one of the broad commercial families."""
    version: Keyword | None = None
    """Operating system version as a raw string."""
