from howler import odm


@odm.model(index=True, store=True, description="Definition of an ELF file segment.")
class Segment(odm.Model):
    sections = odm.Optional(odm.Keyword(description="ELF object segment sections."))
    type = odm.Optional(odm.Keyword(description="ELF object segment type."))


@odm.model(index=True, store=True, description="Definition of an ELF file section.")
class Section(odm.Model):
    chi2 = odm.Optional(odm.Integer(description="Chi-square probability distribution of the section."))
    entropy = odm.Optional(odm.Integer(description="Shannon entropy calculation from the section."))
    flags = odm.Optional(odm.Keyword(description="ELF Section List flags."))
    name = odm.Optional(odm.Keyword(description="ELF Section List name."))
    physical_offset = odm.Optional(odm.Keyword(description="ELF Section List offset."))
    physical_size = odm.Optional(odm.Integer(description="ELF Section List physical size."))
    type = odm.Optional(odm.Keyword(description="ELF Section List type."))
    virtual_address = odm.Optional(odm.Integer(description="ELF Section List virtual address."))
    virtual_size = odm.Optional(odm.Integer(description="ELF Section List virtual size."))


@odm.model(index=True, store=True, description="Header information about the ELF file.")
class Header(odm.Model):
    abi_version = odm.Optional(odm.Keyword(description="Version of the ELF Application Binary Interface (ABI)."))
    class_ = odm.Optional(odm.Keyword(description="Header class of the ELF file."))
    data = odm.Optional(odm.Keyword(description="Data table of the ELF header."))
    entrypoint = odm.Optional(odm.Integer(description="Header entrypoint of the ELF file."))
    object_version = odm.Optional(odm.Keyword(description="'0x1' for original ELF files."))
    os_abi = odm.Optional(odm.Keyword(description="Application Binary Interface (ABI) of the Linux OS."))
    type = odm.Optional(odm.Keyword(description="Header type of the ELF file."))
    version = odm.Optional(odm.Keyword(description="Version of the ELF header."))


@odm.model(
    index=True,
    store=True,
    description="These fields contain Linux Executable Linkable Format (ELF) metadata.",
)
class ELF(odm.Model):
    architecture = odm.Optional(odm.Keyword(description="Machine architecture of the ELF file."))
    byte_order = odm.Optional(odm.Keyword(description="Byte sequence of ELF file."))
    cpu_type = odm.Optional(odm.Keyword(description="CPU type of the ELF file."))
    creation_date = odm.Optional(odm.Keyword(description="Extracted when possible from the file’s metadata."))
    exports = odm.List(
        odm.Keyword(),
        default=[],
        description="List of exported element names and types.",
    )
    header = odm.Optional(odm.Compound(Header, description="Header information about the ELF file."))
    imports = odm.Optional(odm.List(odm.Keyword(), description="List of imported element names and types."))
    sections = odm.Optional(
        odm.List(
            odm.Compound(
                Section,
                description="An array containing an object for each section of the ELF file.",
            )
        )
    )
    segments = odm.Optional(
        odm.List(
            odm.Compound(
                Section,
                description="An array containing an object for each segment of the ELF file.",
            )
        )
    )
    shared_libraries = odm.Optional(
        odm.List(
            odm.Keyword(),
            description="List of shared libraries used by this ELF object.",
        )
    )
    telfhash = odm.Optional(odm.Keyword(description="telfhash symbol hash for ELF file."))
