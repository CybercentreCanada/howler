"""ECS file field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, compound, date, enum, keyword, list_field, long, register_model
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

    accessed: date(optional=True, description="Last time the file was accessed.")
    attributes: list_field(keyword(), optional=True, description="Array of file attributes.")
    created: date(optional=True, description="File creation time.")
    ctime: date(optional=True, description="Last time the file attributes or metadata changed.")
    device: keyword(optional=True, description="Device that is the source of the file.")
    directory: keyword(
        optional=True,
        description="Directory where the file is located. It should include the drive letter, when appropriate.",
    )
    drive_letter: keyword(
        optional=True, description="Drive letter where the file is located. This field is only relevant on Windows."
    )
    extension: keyword(optional=True, description="File extension, excluding the leading dot.")
    fork_name: keyword(optional=True, description="A fork is additional data associated with a filesystem object.")
    gid: keyword(optional=True, description="Primary group ID (GID) of the file.")
    group: keyword(optional=True, description="Primary group name of the file.")
    inode: keyword(optional=True, description="Inode representing the file in the filesystem.")
    mime_type: keyword(
        optional=True,
        description="MIME type should identify the format of the file or stream of "
        "bytes using IANA official types, where possible.",
    )
    mode: keyword(optional=True, description="Mode of the file in octal representation.")
    mtime: date(optional=True, description="Last time the file content was modified.")
    name: keyword(optional=True, description="Name of the file including the extension, without the directory.")
    owner: keyword(optional=True, description="File owner's username.")
    path: keyword(
        optional=True,
        description="Full path to the file, including the file name. "
        "It should include the drive letter, when appropriate.",
    )
    size: long(optional=True, description="File size in bytes.")
    target_path: keyword(optional=True, description="Target path for symlinks.")
    type: enum(values=FILE_TYPE, optional=True, description="File type (file, dir, or symlink).")
    uid: keyword(optional=True, description="The user ID (UID) or security identifier (SID) of the file owner.")

    code_signature: compound(
        CodeSignature, optional=True, description="These fields contain information about binary code signatures."
    )
    elf: compound(
        ELF, optional=True, description="These fields contain Linux Executable Linkable Format (ELF) metadata."
    )
    hash: compound(Hashes, optional=True, description="Hashes, usually file hashes.")
    pe: compound(PE, optional=True, description="These fields contain Windows Portable Executable (PE) metadata.")
