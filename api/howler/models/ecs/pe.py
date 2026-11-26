"""ECS Windows Portable Executable (PE) field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, register_model


@register_model(
    index=True,
    store=True,
    description="These fields contain Windows Portable Executable (PE) metadata.",
    embedded=True,
)
class PE(HowlerEmbeddedModel):
    """These fields contain Windows Portable Executable (PE) metadata."""

    architecture: keyword(optional=True)
    """CPU architecture target for the file."""
    company: keyword(optional=True)
    """Internal company name of the file, provided at compile-time."""
    description: keyword(optional=True)
    """Internal description of the file, provided at compile-time."""
    file_version: keyword(optional=True)
    """Internal version of the file, provided at compile-time."""
    imphash: keyword(optional=True)
    """A hash of the imports in a PE file."""
    original_file_name: keyword(optional=True)
    """Internal name of the file, provided at compile-time."""
    pehash: keyword(optional=True)
    """A hash of the PE header and data from one or more PE sections."""
    product: keyword(optional=True)
    """Internal product name of the file, provided at compile-time."""
