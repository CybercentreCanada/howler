"""ECS process field set."""

from __future__ import annotations

from howler.models import HowlerEmbeddedModel, boolean, date, integer, keyword, long, mapping, register_model
from howler.models.ecs.code_signature import CodeSignature
from howler.models.ecs.hash import Hashes
from howler.models.ecs.pe import PE
from howler.models.ecs.user import ShortUser


@register_model(index=True, store=True, description="Information about the char device.", embedded=True)
class CharDevice(HowlerEmbeddedModel):
    """Information about the char device."""

    major: integer(optional=True)
    """The major number identifies the driver associated with the device."""
    minor: integer(optional=True)
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

    id: integer(optional=True)
    """Thread ID."""
    name: keyword(optional=True)
    """Thread name."""


@register_model(index=True, store=True, description="Entry Meta-Information.", embedded=True)
class EntryMeta(HowlerEmbeddedModel):
    """Entry Meta-Information."""

    type: keyword(optional=True)
    """SESSIONNAME from Process Environment Variable"""


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class ParentParentProcess(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: list[keyword()] | None = None
    """Array of process arguments, starting with the absolute path to the executable."""
    args_count: integer(optional=True)
    """Length of the process.args array."""
    code_signature: CodeSignature | None = None
    """Information about binary code signatures."""
    command_line: keyword(optional=True)
    """Full command line that started the process, including the absolute path to the executable, and all arguments."""
    end: date(optional=True)
    """The time the process ended."""
    entity_id: keyword(optional=True)
    """OID Hash of the process."""
    entry_meta: EntryMeta | None = None
    """Process Meta Information."""
    env_vars: mapping(keyword(), optional=True)
    ("Environment variables (env_vars) set at the time of the event. May be filtered to protect sensitive information.")
    executable: keyword(optional=True)
    """Absolute path to the process executable."""
    exit_code: integer(optional=True)
    """The exit code of the process, if this is a termination event."""
    hash: Hashes | None = None
    """Hashes, usually file hashes"""
    interactive: boolean(optional=True)
    """Whether the process is connected to an interactive shell."""
    name: keyword(optional=True)
    """Process name."""
    pe: PE | None = None
    """Windows Portable Executable (PE) metadata."""
    pid: long(optional=True)
    """Process id."""
    same_as_process: boolean(optional=True)
    """This boolean is used to identify if a leader process is the same as the top level process."""
    start: date(optional=True)
    """The time the process started."""
    title: keyword(optional=True)
    """Process title."""
    uptime: integer(optional=True)
    """Seconds the process has been up."""
    user: ShortUser | None = None
    """The effective user (euid)."""
    working_directory: keyword(optional=True)
    """The working directory of the process."""


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class ParentProcess(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: list[keyword()] | None = None
    """Array of process arguments, starting with the absolute path to the executable."""
    args_count: integer(optional=True)
    """Length of the process.args array."""
    code_signature: CodeSignature | None = None
    """Information about binary code signatures."""
    command_line: keyword(optional=True)
    """Full command line that started the process, including the absolute path to the executable, and all arguments."""
    end: date(optional=True)
    """The time the process ended."""
    entity_id: keyword(optional=True)
    """OID Hash of the process."""
    entry_meta: EntryMeta | None = None
    """Process Meta Information."""
    env_vars: mapping(keyword(), optional=True)
    ("Environment variables (env_vars) set at the time of the event. May be filtered to protect sensitive information.")
    executable: keyword(optional=True)
    """Absolute path to the process executable."""
    exit_code: integer(optional=True)
    """The exit code of the process, if this is a termination event."""
    hash: Hashes | None = None
    """Hashes, usually file hashes"""
    interactive: boolean(optional=True)
    """Whether the process is connected to an interactive shell."""
    name: keyword(optional=True)
    """Process name."""
    parent: ParentParentProcess | None = None
    """Information about the parent process."""
    pe: PE | None = None
    """Windows Portable Executable (PE) metadata."""
    pid: long(optional=True)
    """Process id."""
    same_as_process: boolean(optional=True)
    """This boolean is used to identify if a leader process is the same as the top level process."""
    start: date(optional=True)
    """The time the process started."""
    title: keyword(optional=True)
    """Process title."""
    uptime: integer(optional=True)
    """Seconds the process has been up."""
    user: ShortUser | None = None
    """The effective user (euid)."""
    working_directory: keyword(optional=True)
    """The working directory of the process."""


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class Process(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: list[keyword()] | None = None
    """Array of process arguments, starting with the absolute path to the executable."""
    args_count: integer(optional=True)
    """Length of the process.args array."""
    code_signature: CodeSignature | None = None
    """Information about binary code signatures."""
    command_line: keyword(optional=True)
    """Full command line that started the process, including the absolute path to the executable, and all arguments."""
    end: date(optional=True)
    """The time the process ended."""
    entity_id: keyword(optional=True)
    """OID Hash of the process."""
    entry_meta: EntryMeta | None = None
    """Process Meta Information."""
    env_vars: mapping(keyword(), optional=True)
    ("Environment variables (env_vars) set at the time of the event. May be filtered to protect sensitive information.")
    executable: keyword(optional=True)
    """Absolute path to the process executable."""
    exit_code: integer(optional=True)
    """The exit code of the process, if this is a termination event."""
    hash: Hashes | None = None
    """Hashes, usually file hashes"""
    interactive: boolean(optional=True)
    """Whether the process is connected to an interactive shell."""
    name: keyword(optional=True)
    """Process name."""
    parent: ParentProcess | None = None
    """Information about the parent process."""
    pe: PE | None = None
    """Windows Portable Executable (PE) metadata."""
    pid: long(optional=True)
    """Process id."""
    same_as_process: boolean(optional=True)
    """This boolean is used to identify if a leader process is the same as the top level process."""
    start: date(optional=True)
    """The time the process started."""
    title: keyword(optional=True)
    """Process title."""
    uptime: integer(optional=True)
    """Seconds the process has been up."""
    user: ShortUser | None = None
    """The effective user (euid)."""
    working_directory: keyword(optional=True)
    """The working directory of the process."""
