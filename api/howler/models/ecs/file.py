"""ECS file field set."""

from __future__ import annotations

from howler.models import Date, HowlerEmbeddedModel, Keyword, Long, enum, register_model
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

    accessed: Date | None = None
    """Last time the file was accessed."""
    attributes: list[Keyword] | None = None
    """Array of file attributes."""
    created: Date | None = None
    """File creation time."""
    ctime: Date | None = None
    """Last time the file attributes or metadata changed."""
    device: Keyword | None = None
    """Device that is the source of the file."""
    directory: Keyword | None = None
    """Directory where the file is located. It should include the drive letter, when appropriate."""
    drive_letter: Keyword | None = None
    """Drive letter where the file is located. This field is only relevant on Windows."""
    extension: Keyword | None = None
    """File extension, excluding the leading dot."""
    fork_name: Keyword | None = None
    """A fork is additional data associated with a filesystem object."""
    gid: Keyword | None = None
    """Primary group ID (GID) of the file."""
    group: Keyword | None = None
    """Primary group name of the file."""
    inode: Keyword | None = None
    """Inode representing the file in the filesystem."""
    mime_type: Keyword | None = None
    """MIME type should identify the format of the file or stream of bytes using IANA official types, where possible."""
    mode: Keyword | None = None
    """Mode of the file in octal representation."""
    mtime: Date | None = None
    """Last time the file content was modified."""
    name: Keyword | None = None
    """Name of the file including the extension, without the directory."""
    owner: Keyword | None = None
    """File owner's username."""
    path: Keyword | None = None
    """Full path to the file, including the file name. It should include the drive letter, when appropriate."""
    size: Long | None = None
    """File size in bytes."""
    target_path: Keyword | None = None
    """Target path for symlinks."""
    type: enum(values=FILE_TYPE, optional=True)
    """File type (file, dir, or symlink)."""
    uid: Keyword | None = None
    """The user ID (UID) or security identifier (SID) of the file owner."""

    code_signature: CodeSignature | None = None
    """These fields contain information about binary code signatures."""
    elf: ELF | None = None
    """These fields contain Linux Executable Linkable Format (ELF) metadata."""
    hash: Hashes | None = None
    """Hashes, usually file hashes."""
    pe: PE | None = None
    """These fields contain Windows Portable Executable (PE) metadata."""
