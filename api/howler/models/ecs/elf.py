"""ECS ELF field set."""

from __future__ import annotations

from typing import Annotated

from howler.models import HowlerEmbeddedModel, Integer, Keyword, metadata, register_model


@register_model(index=True, store=True, description="Definition of an ELF file segment.", embedded=True)
class Segment(HowlerEmbeddedModel):
    """Definition of an ELF file segment."""

    sections: Keyword | None = None
    """ELF object segment sections."""
    type: Keyword | None = None
    """ELF object segment type."""


@register_model(index=True, store=True, description="Definition of an ELF file section.", embedded=True)
class Section(HowlerEmbeddedModel):
    """Definition of an ELF file section."""

    chi2: Integer | None = None
    """Chi-square probability distribution of the section."""
    entropy: Integer | None = None
    """Shannon entropy calculation from the section."""
    flags: Keyword | None = None
    """ELF Section List flags."""
    name: Keyword | None = None
    """ELF Section List name."""
    physical_offset: Keyword | None = None
    """ELF Section List offset."""
    physical_size: Integer | None = None
    """ELF Section List physical size."""
    type: Keyword | None = None
    """ELF Section List type."""
    virtual_address: Integer | None = None
    """ELF Section List virtual address."""
    virtual_size: Integer | None = None
    """ELF Section List virtual size."""


@register_model(index=True, store=True, description="Header information about the ELF file.", embedded=True)
class Header(HowlerEmbeddedModel):
    """Header information about the ELF file."""

    abi_version: Keyword | None = None
    """Version of the ELF Application Binary Interface (ABI)."""
    class_: Annotated[Keyword | None, metadata(alias="class")] = None
    """Header class of the ELF file."""
    data: Keyword | None = None
    """Data table of the ELF header."""
    entrypoint: Integer | None = None
    """Header entrypoint of the ELF file."""
    object_version: Keyword | None = None
    """'0x1' for original ELF files."""
    os_abi: Keyword | None = None
    """Application Binary Interface (ABI) of the Linux OS."""
    type: Keyword | None = None
    """Header type of the ELF file."""
    version: Keyword | None = None
    """Version of the ELF header."""


@register_model(
    index=True,
    store=True,
    description="These fields contain Linux Executable Linkable Format (ELF) metadata.",
    embedded=True,
)
class ELF(HowlerEmbeddedModel):
    """These fields contain Linux Executable Linkable Format (ELF) metadata."""

    architecture: Keyword | None = None
    """Machine architecture of the ELF file."""
    byte_order: Keyword | None = None
    """Byte sequence of ELF file."""
    cpu_type: Keyword | None = None
    """CPU type of the ELF file."""
    creation_date: Keyword | None = None
    """Extracted when possible from the file's metadata."""
    exports: list[Keyword] = []
    """List of exported element names and types."""
    header: Header | None = None
    """Header information about the ELF file."""
    imports: list[Keyword] | None = None
    """List of imported element names and types."""
    sections: list[Section] | None = None
    """An array containing an object for each section of the ELF file."""
    segments: list[Section] | None = None
    """An array containing an object for each segment of the ELF file."""
    shared_libraries: list[Keyword] | None = None
    """List of shared libraries used by this ELF object."""
    telfhash: Keyword | None = None
    """telfhash symbol hash for ELF file."""
