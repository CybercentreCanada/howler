from typing import Optional

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
    description="A file is defined as a set of information that has "
    "been created on, or has existed on a filesystem.",
)
class File(odm.Model):
    accessed: Optional[str] = odm.Optional(odm.Date(description="Last time the file was accessed."))
    attributes: Optional[list[str]] = odm.Optional(odm.List(odm.Keyword(), description="Array of file attributes."))
    created: Optional[str] = odm.Optional(odm.Date(description="File creation time."))
    ctime: Optional[str] = odm.Optional(odm.Date(description="Last time the file attributes or metadata changed."))
    device: Optional[str] = odm.Optional(odm.Keyword(description="Device that is the source of the file."))
    directory: Optional[str] = odm.Optional(
        odm.Keyword(
            description="Directory where the file is located. It should include the drive letter, when appropriate."
        )
    )
    drive_letter: Optional[str] = odm.Optional(
        odm.Keyword(description="Drive letter where the file is located. This field is only relevant on Windows.")
    )
    extension: Optional[str] = odm.Optional(odm.Keyword(description="File extension, excluding the leading dot."))
    fork_name: Optional[str] = odm.Optional(
        odm.Keyword(description="A fork is additional data associated with a filesystem object.")
    )
    gid: Optional[str] = odm.Optional(odm.Keyword(description="Primary group ID (GID) of the file."))
    group: Optional[str] = odm.Optional(odm.Keyword(description="Primary group name of the file."))
    inode: Optional[str] = odm.Optional(odm.Keyword(description="Inode representing the file in the filesystem."))
    mime_type: Optional[str] = odm.Optional(
        odm.Keyword(
            description="MIME type should identify the format of the file or stream of "
            "bytes using IANA official types, where possible."
        )
    )
    mode: Optional[str] = odm.Optional(odm.Keyword(description="Mode of the file in octal representation."))
    mtime: Optional[str] = odm.Optional(odm.Date(description="Last time the file content was modified."))
    name: Optional[str] = odm.Optional(
        odm.Keyword(description="Name of the file including the extension, without the directory.")
    )
    owner: Optional[str] = odm.Optional(odm.Keyword(description="File owner’s username."))
    path: Optional[str] = odm.Optional(
        odm.Keyword(
            description="Full path to the file, including the file name. "
            "It should include the drive letter, when appropriate."
        )
    )
    size: Optional[int] = odm.Integer(description="File size in bytes.", optional=True)
    target_path: Optional[str] = odm.Optional(odm.Keyword(description="Target path for symlinks."))
    type: Optional[str] = odm.Optional(odm.Enum(values=FILE_TYPE, description="File type (file, dir, or symlink)."))
    uid: Optional[str] = odm.Optional(
        odm.Keyword(description="The user ID (UID) or security identifier (SID) of the file owner.")
    )

    code_signature: Optional[CodeSignature] = odm.Optional(
        odm.Compound(
            CodeSignature,
            description="These fields contain information about binary code signatures.",
        )
    )
    elf: Optional[ELF] = odm.Optional(
        odm.Compound(
            ELF,
            description="These fields contain Linux Executable Linkable Format (ELF) metadata.",
        )
    )
    hash: Optional[Hashes] = odm.Optional(
        odm.Compound(
            Hashes,
            description="These fields contain Windows Portable Executable (PE) metadata.",
        )
    )
    pe: Optional[PE] = odm.Optional(odm.Compound(PE, description="Hashes, usually file hashes."))
