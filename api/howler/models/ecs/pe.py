"""ECS Windows Portable Executable (PE) field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, Keyword, register_model


@register_model(
    index=True,
    store=True,
    description="These fields contain Windows Portable Executable (PE) metadata.",
    embedded=True,
)
class PE(HowlerEmbeddedModel):
    """These fields contain Windows Portable Executable (PE) metadata."""

    architecture: Keyword | None = None
    """CPU architecture target for the file."""
    company: Keyword | None = None
    """Internal company name of the file, provided at compile-time."""
    description: Keyword | None = None
    """Internal description of the file, provided at compile-time."""
    file_version: Keyword | None = None
    """Internal version of the file, provided at compile-time."""
    imphash: Keyword | None = None
    """A hash of the imports in a PE file."""
    original_file_name: Keyword | None = None
    """Internal name of the file, provided at compile-time."""
    pehash: Keyword | None = None
    """A hash of the PE header and data from one or more PE sections."""
    product: Keyword | None = None
    """Internal product name of the file, provided at compile-time."""
