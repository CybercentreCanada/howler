"""ECS ELF field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, integer, keyword, list_field, register_model


@register_model(index=True, store=True, description="Definition of an ELF file segment.", embedded=True)
class Segment(HowlerEmbeddedModel):
    """Definition of an ELF file segment."""

    sections: keyword(optional=True, description="ELF object segment sections.")
    type: keyword(optional=True, description="ELF object segment type.")


@register_model(index=True, store=True, description="Definition of an ELF file section.", embedded=True)
class Section(HowlerEmbeddedModel):
    """Definition of an ELF file section."""

    chi2: integer(optional=True, description="Chi-square probability distribution of the section.")
    entropy: integer(optional=True, description="Shannon entropy calculation from the section.")
    flags: keyword(optional=True, description="ELF Section List flags.")
    name: keyword(optional=True, description="ELF Section List name.")
    physical_offset: keyword(optional=True, description="ELF Section List offset.")
    physical_size: integer(optional=True, description="ELF Section List physical size.")
    type: keyword(optional=True, description="ELF Section List type.")
    virtual_address: integer(optional=True, description="ELF Section List virtual address.")
    virtual_size: integer(optional=True, description="ELF Section List virtual size.")


@register_model(index=True, store=True, description="Header information about the ELF file.", embedded=True)
class Header(HowlerEmbeddedModel):
    """Header information about the ELF file."""

    abi_version: keyword(optional=True, description="Version of the ELF Application Binary Interface (ABI).")
    class_: keyword(optional=True, alias="class", description="Header class of the ELF file.")
    data: keyword(optional=True, description="Data table of the ELF header.")
    entrypoint: integer(optional=True, description="Header entrypoint of the ELF file.")
    object_version: keyword(optional=True, description="'0x1' for original ELF files.")
    os_abi: keyword(optional=True, description="Application Binary Interface (ABI) of the Linux OS.")
    type: keyword(optional=True, description="Header type of the ELF file.")
    version: keyword(optional=True, description="Version of the ELF header.")


@register_model(
    index=True,
    store=True,
    description="These fields contain Linux Executable Linkable Format (ELF) metadata.",
    embedded=True,
)
class ELF(HowlerEmbeddedModel):
    """These fields contain Linux Executable Linkable Format (ELF) metadata."""

    architecture: keyword(optional=True, description="Machine architecture of the ELF file.")
    byte_order: keyword(optional=True, description="Byte sequence of ELF file.")
    cpu_type: keyword(optional=True, description="CPU type of the ELF file.")
    creation_date: keyword(optional=True, description="Extracted when possible from the file's metadata.")
    exports: list_field(keyword(), default=[], description="List of exported element names and types.")
    header: compound(Header, optional=True, description="Header information about the ELF file.")
    imports: list_field(keyword(), optional=True, description="List of imported element names and types.")
    sections: list_field(
        compound(Section), optional=True, description="An array containing an object for each section of the ELF file."
    )
    segments: list_field(
        compound(Section), optional=True, description="An array containing an object for each segment of the ELF file."
    )
    shared_libraries: list_field(
        keyword(), optional=True, description="List of shared libraries used by this ELF object."
    )
    telfhash: keyword(optional=True, description="telfhash symbol hash for ELF file.")
