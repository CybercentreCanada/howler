"""ECS file field set."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    compound,
    date,
    enum,
    keyword,
    list_field,
    long,
    optional,
    register_model,
)
from howler.models.ecs.code_signature import CodeSignature
from howler.models.ecs.elf import ELF
from howler.models.ecs.hash import Hashes
from howler.models.ecs.pe import PE

FILE_TYPE = ["file", "dir", "symlink"]


@register_model(
    index=True,
    store=True,
    description="A file is defined as a set of information that has been created on, or has existed on a filesystem.",
    embedded=True,
)
class File(HowlerEmbeddedModel):
    """A file is defined as a set of information that has been created on, or has existed on a filesystem."""

    accessed: optional(date(), description="Last time the file was accessed.")
    attributes: optional(list_field(keyword()), description="Array of file attributes.")
    created: optional(date(), description="File creation time.")
    ctime: optional(date(), description="Last time the file attributes or metadata changed.")
    device: optional(keyword(), description="Device that is the source of the file.")
    directory: optional(
        keyword(),
        description="Directory where the file is located. It should include the drive letter, when appropriate.",
    )
    drive_letter: optional(
        keyword(), description="Drive letter where the file is located. This field is only relevant on Windows."
    )
    extension: optional(keyword(), description="File extension, excluding the leading dot.")
    fork_name: optional(keyword(), description="A fork is additional data associated with a filesystem object.")
    gid: optional(keyword(), description="Primary group ID (GID) of the file.")
    group: optional(keyword(), description="Primary group name of the file.")
    inode: optional(keyword(), description="Inode representing the file in the filesystem.")
    mime_type: optional(
        keyword(),
        description="MIME type should identify the format of the file or stream of "
        "bytes using IANA official types, where possible.",
    )
    mode: optional(keyword(), description="Mode of the file in octal representation.")
    mtime: optional(date(), description="Last time the file content was modified.")
    name: optional(keyword(), description="Name of the file including the extension, without the directory.")
    owner: optional(keyword(), description="File owner's username.")
    path: optional(
        keyword(),
        description="Full path to the file, including the file name. "
        "It should include the drive letter, when appropriate.",
    )
    size: optional(long(), description="File size in bytes.")
    target_path: optional(keyword(), description="Target path for symlinks.")
    type: optional(enum(values=FILE_TYPE), description="File type (file, dir, or symlink).")
    uid: optional(keyword(), description="The user ID (UID) or security identifier (SID) of the file owner.")

    code_signature: optional(
        compound(CodeSignature), description="These fields contain information about binary code signatures."
    )
    elf: optional(compound(ELF), description="These fields contain Linux Executable Linkable Format (ELF) metadata.")
    hash: optional(compound(Hashes), description="Hashes, usually file hashes.")
    pe: optional(compound(PE), description="These fields contain Windows Portable Executable (PE) metadata.")
