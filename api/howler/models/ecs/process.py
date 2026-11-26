"""ECS process field set."""

from __future__ import annotations

from howler.models import Boolean, Date, HowlerEmbeddedModel, Integer, Keyword, Long, mapping, register_model
from howler.models.ecs.code_signature import CodeSignature
from howler.models.ecs.hash import Hashes
from howler.models.ecs.pe import PE
from howler.models.ecs.user import ShortUser


@register_model(index=True, store=True, description="Information about the char device.", embedded=True)
class CharDevice(HowlerEmbeddedModel):
    """Information about the char device."""

    major: Integer | None = None
    """The major number identifies the driver associated with the device."""
    minor: Integer | None = None
    (
        "The minor number is used only by the driver specified by the major number; other parts of the kernel don't "
        "use it, and merely pass it along to the driver."
    )


@register_model(index=True, store=True, description="Information about the controlling TTY device.", embedded=True)
class TTY(HowlerEmbeddedModel):
    """Information about the controlling TTY device."""

    char_device: CharDevice | None = None
    """Information about the char device."""


@register_model(index=True, store=True, description="Thread Information.", embedded=True)
class Thread(HowlerEmbeddedModel):
    """Thread Information."""

    id: Integer | None = None
    """Thread ID."""
    name: Keyword | None = None
    """Thread name."""


@register_model(index=True, store=True, description="Entry Meta-Information.", embedded=True)
class EntryMeta(HowlerEmbeddedModel):
    """Entry Meta-Information."""

    type: Keyword | None = None
    """SESSIONNAME from Process Environment Variable"""


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class ParentParentProcess(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: list[Keyword] | None = None
    """Array of process arguments, starting with the absolute path to the executable."""
    args_count: Integer | None = None
    """Length of the process.args array."""
    code_signature: CodeSignature | None = None
    """Information about binary code signatures."""
    command_line: Keyword | None = None
    """Full command line that started the process, including the absolute path to the executable, and all arguments."""
    end: Date | None = None
    """The time the process ended."""
    entity_id: Keyword | None = None
    """OID Hash of the process."""
    entry_meta: EntryMeta | None = None
    """Process Meta Information."""
    env_vars: mapping(Keyword, optional=True)
    ("Environment variables (env_vars) set at the time of the event. May be filtered to protect sensitive information.")
    executable: Keyword | None = None
    """Absolute path to the process executable."""
    exit_code: Integer | None = None
    """The exit code of the process, if this is a termination event."""
    hash: Hashes | None = None
    """Hashes, usually file hashes"""
    interactive: Boolean | None = None
    """Whether the process is connected to an interactive shell."""
    name: Keyword | None = None
    """Process name."""
    pe: PE | None = None
    """Windows Portable Executable (PE) metadata."""
    pid: Long | None = None
    """Process id."""
    same_as_process: Boolean | None = None
    """This boolean is used to identify if a leader process is the same as the top level process."""
    start: Date | None = None
    """The time the process started."""
    title: Keyword | None = None
    """Process title."""
    uptime: Integer | None = None
    """Seconds the process has been up."""
    user: ShortUser | None = None
    """The effective user (euid)."""
    working_directory: Keyword | None = None
    """The working directory of the process."""


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class ParentProcess(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: list[Keyword] | None = None
    """Array of process arguments, starting with the absolute path to the executable."""
    args_count: Integer | None = None
    """Length of the process.args array."""
    code_signature: CodeSignature | None = None
    """Information about binary code signatures."""
    command_line: Keyword | None = None
    """Full command line that started the process, including the absolute path to the executable, and all arguments."""
    end: Date | None = None
    """The time the process ended."""
    entity_id: Keyword | None = None
    """OID Hash of the process."""
    entry_meta: EntryMeta | None = None
    """Process Meta Information."""
    env_vars: mapping(Keyword, optional=True)
    ("Environment variables (env_vars) set at the time of the event. May be filtered to protect sensitive information.")
    executable: Keyword | None = None
    """Absolute path to the process executable."""
    exit_code: Integer | None = None
    """The exit code of the process, if this is a termination event."""
    hash: Hashes | None = None
    """Hashes, usually file hashes"""
    interactive: Boolean | None = None
    """Whether the process is connected to an interactive shell."""
    name: Keyword | None = None
    """Process name."""
    parent: ParentParentProcess | None = None
    """Information about the parent process."""
    pe: PE | None = None
    """Windows Portable Executable (PE) metadata."""
    pid: Long | None = None
    """Process id."""
    same_as_process: Boolean | None = None
    """This boolean is used to identify if a leader process is the same as the top level process."""
    start: Date | None = None
    """The time the process started."""
    title: Keyword | None = None
    """Process title."""
    uptime: Integer | None = None
    """Seconds the process has been up."""
    user: ShortUser | None = None
    """The effective user (euid)."""
    working_directory: Keyword | None = None
    """The working directory of the process."""


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class Process(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: list[Keyword] | None = None
    """Array of process arguments, starting with the absolute path to the executable."""
    args_count: Integer | None = None
    """Length of the process.args array."""
    code_signature: CodeSignature | None = None
    """Information about binary code signatures."""
    command_line: Keyword | None = None
    """Full command line that started the process, including the absolute path to the executable, and all arguments."""
    end: Date | None = None
    """The time the process ended."""
    entity_id: Keyword | None = None
    """OID Hash of the process."""
    entry_meta: EntryMeta | None = None
    """Process Meta Information."""
    env_vars: mapping(Keyword, optional=True)
    ("Environment variables (env_vars) set at the time of the event. May be filtered to protect sensitive information.")
    executable: Keyword | None = None
    """Absolute path to the process executable."""
    exit_code: Integer | None = None
    """The exit code of the process, if this is a termination event."""
    hash: Hashes | None = None
    """Hashes, usually file hashes"""
    interactive: Boolean | None = None
    """Whether the process is connected to an interactive shell."""
    name: Keyword | None = None
    """Process name."""
    parent: ParentProcess | None = None
    """Information about the parent process."""
    pe: PE | None = None
    """Windows Portable Executable (PE) metadata."""
    pid: Long | None = None
    """Process id."""
    same_as_process: Boolean | None = None
    """This boolean is used to identify if a leader process is the same as the top level process."""
    start: Date | None = None
    """The time the process started."""
    title: Keyword | None = None
    """Process title."""
    uptime: Integer | None = None
    """Seconds the process has been up."""
    user: ShortUser | None = None
    """The effective user (euid)."""
    working_directory: Keyword | None = None
    """The working directory of the process."""
