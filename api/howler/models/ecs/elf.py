"""ECS ELF field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, integer, keyword, list_field, optional, register_model


@register_model(index=True, store=True, description="Definition of an ELF file segment.", embedded=True)
class Segment(HowlerEmbeddedModel):
    """Definition of an ELF file segment."""

    sections: optional(keyword(), description="ELF object segment sections.")
    type: optional(keyword(), description="ELF object segment type.")


@register_model(index=True, store=True, description="Definition of an ELF file section.", embedded=True)
class Section(HowlerEmbeddedModel):
    """Definition of an ELF file section."""

    chi2: optional(integer(), description="Chi-square probability distribution of the section.")
    entropy: optional(integer(), description="Shannon entropy calculation from the section.")
    flags: optional(keyword(), description="ELF Section List flags.")
    name: optional(keyword(), description="ELF Section List name.")
    physical_offset: optional(keyword(), description="ELF Section List offset.")
    physical_size: optional(integer(), description="ELF Section List physical size.")
    type: optional(keyword(), description="ELF Section List type.")
    virtual_address: optional(integer(), description="ELF Section List virtual address.")
    virtual_size: optional(integer(), description="ELF Section List virtual size.")


@register_model(index=True, store=True, description="Header information about the ELF file.", embedded=True)
class Header(HowlerEmbeddedModel):
    """Header information about the ELF file."""

    abi_version: optional(keyword(), description="Version of the ELF Application Binary Interface (ABI).")
    class_: optional(keyword(), alias="class", description="Header class of the ELF file.")
    data: optional(keyword(), description="Data table of the ELF header.")
    entrypoint: optional(integer(), description="Header entrypoint of the ELF file.")
    object_version: optional(keyword(), description="'0x1' for original ELF files.")
    os_abi: optional(keyword(), description="Application Binary Interface (ABI) of the Linux OS.")
    type: optional(keyword(), description="Header type of the ELF file.")
    version: optional(keyword(), description="Version of the ELF header.")


@register_model(
    index=True,
    store=True,
    description="These fields contain Linux Executable Linkable Format (ELF) metadata.",
    embedded=True,
)
class ELF(HowlerEmbeddedModel):
    """These fields contain Linux Executable Linkable Format (ELF) metadata."""

    architecture: optional(keyword(), description="Machine architecture of the ELF file.")
    byte_order: optional(keyword(), description="Byte sequence of ELF file.")
    cpu_type: optional(keyword(), description="CPU type of the ELF file.")
    creation_date: optional(keyword(), description="Extracted when possible from the file's metadata.")
    exports: list_field(keyword(), default=[], description="List of exported element names and types.")
    header: optional(compound(Header), description="Header information about the ELF file.")
    imports: optional(list_field(keyword()), description="List of imported element names and types.")
    sections: optional(
        list_field(compound(Section)),
        description="An array containing an object for each section of the ELF file.",
    )
    segments: optional(
        list_field(compound(Section)),
        description="An array containing an object for each segment of the ELF file.",
    )
    shared_libraries: optional(list_field(keyword()), description="List of shared libraries used by this ELF object.")
    telfhash: optional(keyword(), description="telfhash symbol hash for ELF file.")
