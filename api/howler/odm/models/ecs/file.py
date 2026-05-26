from howler import odm
from howler.odm.models.ecs.code_signature import CodeSignature
from howler.odm.models.ecs.elf import ELF
from howler.odm.models.ecs.hash import Hashes
from howler.odm.models.ecs.pe import PE

# from howler.odm.models.ecs.x509 import X509

FILE_TYPE = ["file", "dir", "symlink"]


@odm.model(
    index=True,
    store=True,
    description="A file is defined as a set of information that has been created on, or has existed on a filesystem.",
)
class File(odm.Model):
    accessed: str | None = odm.Optional(odm.Date(description="Last time the file was accessed."))
    attributes: list[str] | None = odm.Optional(odm.List(odm.Keyword(), description="Array of file attributes."))
    created: str | None = odm.Optional(odm.Date(description="File creation time."))
    ctime: str | None = odm.Optional(odm.Date(description="Last time the file attributes or metadata changed."))
    device: str | None = odm.Optional(odm.Keyword(description="Device that is the source of the file."))
    directory: str | None = odm.Optional(
        odm.Keyword(
            description="Directory where the file is located. It should include the drive letter, when appropriate."
        )
    )
    drive_letter: str | None = odm.Optional(
        odm.Keyword(description="Drive letter where the file is located. This field is only relevant on Windows.")
    )
    extension: str | None = odm.Optional(odm.Keyword(description="File extension, excluding the leading dot."))
    fork_name: str | None = odm.Optional(
        odm.Keyword(description="A fork is additional data associated with a filesystem object.")
    )
    gid: str | None = odm.Optional(odm.Keyword(description="Primary group ID (GID) of the file."))
    group: str | None = odm.Optional(odm.Keyword(description="Primary group name of the file."))
    inode: str | None = odm.Optional(odm.Keyword(description="Inode representing the file in the filesystem."))
    mime_type: str | None = odm.Optional(
        odm.Keyword(
            description="MIME type should identify the format of the file or stream of "
            "bytes using IANA official types, where possible."
        )
    )
    mode: str | None = odm.Optional(odm.Keyword(description="Mode of the file in octal representation."))
    mtime: str | None = odm.Optional(odm.Date(description="Last time the file content was modified."))
    name: str | None = odm.Optional(
        odm.Keyword(description="Name of the file including the extension, without the directory.")
    )
    owner: str | None = odm.Optional(odm.Keyword(description="File owner’s username."))
    path: str | None = odm.Optional(
        odm.Keyword(
            description="Full path to the file, including the file name. "
            "It should include the drive letter, when appropriate."
        )
    )
    size: int | None = odm.Long(description="File size in bytes.", optional=True)
    target_path: str | None = odm.Optional(odm.Keyword(description="Target path for symlinks."))
    type: str | None = odm.Optional(odm.Enum(values=FILE_TYPE, description="File type (file, dir, or symlink)."))
    uid: str | None = odm.Optional(
        odm.Keyword(description="The user ID (UID) or security identifier (SID) of the file owner.")
    )

    code_signature: CodeSignature | None = odm.Optional(
        odm.Compound(
            CodeSignature,
            description="These fields contain information about binary code signatures.",
        )
    )
    elf: ELF | None = odm.Optional(
        odm.Compound(
            ELF,
            description="These fields contain Linux Executable Linkable Format (ELF) metadata.",
        )
    )
    hash: Hashes | None = odm.Optional(
        odm.Compound(
            Hashes,
            description="These fields contain Windows Portable Executable (PE) metadata.",
        )
    )
    pe: PE | None = odm.Optional(odm.Compound(PE, description="Hashes, usually file hashes."))
