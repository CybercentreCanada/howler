"""ECS Windows Portable Executable (PE) field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, keyword, optional, register_model


@register_model(
    index=True,
    store=True,
    description="These fields contain Windows Portable Executable (PE) metadata.",
    embedded=True,
)
class PE(HowlerEmbeddedModel):
    """These fields contain Windows Portable Executable (PE) metadata."""

    architecture: optional(keyword(), description="CPU architecture target for the file.")
    company: optional(keyword(), description="Internal company name of the file, provided at compile-time.")
    description: optional(keyword(), description="Internal description of the file, provided at compile-time.")
    file_version: optional(keyword(), description="Internal version of the file, provided at compile-time.")
    imphash: optional(keyword(), description="A hash of the imports in a PE file.")
    original_file_name: optional(keyword(), description="Internal name of the file, provided at compile-time.")
    pehash: optional(keyword(), description="A hash of the PE header and data from one or more PE sections.")
    product: optional(keyword(), description="Internal product name of the file, provided at compile-time.")
