"""ECS process field set."""

from __future__ import annotations

from howler.models import (
    HowlerEmbeddedModel,
    boolean,
    compound,
    date,
    integer,
    keyword,
    list_field,
    long,
    mapping,
    optional,
    register_model,
)
from howler.models.ecs.code_signature import CodeSignature
from howler.models.ecs.hash import Hashes
from howler.models.ecs.pe import PE
from howler.models.ecs.user import ShortUser


@register_model(index=True, store=True, description="Information about the char device.", embedded=True)
class CharDevice(HowlerEmbeddedModel):
    """Information about the char device."""

    major: optional(integer(), description="The major number identifies the driver associated with the device.")
    minor: optional(
        integer(),
        description="The minor number is used only by the driver specified by the major number; other parts of "
        "the kernel don't use it, and merely pass it along to the driver.",
    )


@register_model(index=True, store=True, description="Information about the controlling TTY device.", embedded=True)
class TTY(HowlerEmbeddedModel):
    """Information about the controlling TTY device."""

    char_device: optional(compound(CharDevice), description="Information about the char device.")


@register_model(index=True, store=True, description="Thread Information.", embedded=True)
class Thread(HowlerEmbeddedModel):
    """Thread Information."""

    id: optional(integer(), description="Thread ID.")
    name: optional(keyword(), description="Thread name.")


@register_model(index=True, store=True, description="Entry Meta-Information.", embedded=True)
class EntryMeta(HowlerEmbeddedModel):
    """Entry Meta-Information."""

    type: optional(keyword(), description="SESSIONNAME from Process Environment Variable")


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class ParentParentProcess(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: optional(
        list_field(keyword()),
        description="Array of process arguments, starting with the absolute path to the executable.",
    )
    args_count: optional(integer(), description="Length of the process.args array.")
    code_signature: optional(compound(CodeSignature), description="Information about binary code signatures.")
    command_line: optional(
        keyword(),
        description="Full command line that started the process, including the absolute path to the "
        "executable, and all arguments.",
    )
    end: optional(date(), description="The time the process ended.")
    entity_id: optional(keyword(), description="OID Hash of the process.")
    entry_meta: optional(compound(EntryMeta), description="Process Meta Information.")
    env_vars: optional(
        mapping(keyword()),
        description="Environment variables (env_vars) set at the time of the event. May be filtered to "
        "protect sensitive information.",
    )
    executable: optional(keyword(), description="Absolute path to the process executable.")
    exit_code: optional(integer(), description="The exit code of the process, if this is a termination event.")
    hash: optional(compound(Hashes), description="Hashes, usually file hashes")
    interactive: optional(boolean(), description="Whether the process is connected to an interactive shell.")
    name: optional(keyword(), description="Process name.")
    pe: optional(compound(PE), description="Windows Portable Executable (PE) metadata.")
    pid: optional(long(), description="Process id.")
    same_as_process: optional(
        boolean(),
        description="This boolean is used to identify if a leader process is the same as the top level process.",
    )
    start: optional(date(), description="The time the process started.")
    title: optional(keyword(), description="Process title.")
    uptime: optional(integer(), description="Seconds the process has been up.")
    user: optional(compound(ShortUser), description="The effective user (euid).")
    working_directory: optional(keyword(), description="The working directory of the process.")


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class ParentProcess(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: optional(
        list_field(keyword()),
        description="Array of process arguments, starting with the absolute path to the executable.",
    )
    args_count: optional(integer(), description="Length of the process.args array.")
    code_signature: optional(compound(CodeSignature), description="Information about binary code signatures.")
    command_line: optional(
        keyword(),
        description="Full command line that started the process, including the absolute path to the "
        "executable, and all arguments.",
    )
    end: optional(date(), description="The time the process ended.")
    entity_id: optional(keyword(), description="OID Hash of the process.")
    entry_meta: optional(compound(EntryMeta), description="Process Meta Information.")
    env_vars: optional(
        mapping(keyword()),
        description="Environment variables (env_vars) set at the time of the event. May be filtered to "
        "protect sensitive information.",
    )
    executable: optional(keyword(), description="Absolute path to the process executable.")
    exit_code: optional(integer(), description="The exit code of the process, if this is a termination event.")
    hash: optional(compound(Hashes), description="Hashes, usually file hashes")
    interactive: optional(boolean(), description="Whether the process is connected to an interactive shell.")
    name: optional(keyword(), description="Process name.")
    parent: optional(compound(ParentParentProcess), description="Information about the parent process.")
    pe: optional(compound(PE), description="Windows Portable Executable (PE) metadata.")
    pid: optional(long(), description="Process id.")
    same_as_process: optional(
        boolean(),
        description="This boolean is used to identify if a leader process is the same as the top level process.",
    )
    start: optional(date(), description="The time the process started.")
    title: optional(keyword(), description="Process title.")
    uptime: optional(integer(), description="Seconds the process has been up.")
    user: optional(compound(ShortUser), description="The effective user (euid).")
    working_directory: optional(keyword(), description="The working directory of the process.")


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class Process(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: optional(
        list_field(keyword()),
        description="Array of process arguments, starting with the absolute path to the executable.",
    )
    args_count: optional(integer(), description="Length of the process.args array.")
    code_signature: optional(compound(CodeSignature), description="Information about binary code signatures.")
    command_line: optional(
        keyword(),
        description="Full command line that started the process, including the absolute path to the "
        "executable, and all arguments.",
    )
    end: optional(date(), description="The time the process ended.")
    entity_id: optional(keyword(), description="OID Hash of the process.")
    entry_meta: optional(compound(EntryMeta), description="Process Meta Information.")
    env_vars: optional(
        mapping(keyword()),
        description="Environment variables (env_vars) set at the time of the event. May be filtered to "
        "protect sensitive information.",
    )
    executable: optional(keyword(), description="Absolute path to the process executable.")
    exit_code: optional(integer(), description="The exit code of the process, if this is a termination event.")
    hash: optional(compound(Hashes), description="Hashes, usually file hashes")
    interactive: optional(boolean(), description="Whether the process is connected to an interactive shell.")
    name: optional(keyword(), description="Process name.")
    parent: optional(compound(ParentProcess), description="Information about the parent process.")
    pe: optional(compound(PE), description="Windows Portable Executable (PE) metadata.")
    pid: optional(long(), description="Process id.")
    same_as_process: optional(
        boolean(),
        description="This boolean is used to identify if a leader process is the same as the top level process.",
    )
    start: optional(date(), description="The time the process started.")
    title: optional(keyword(), description="Process title.")
    uptime: optional(integer(), description="Seconds the process has been up.")
    user: optional(compound(ShortUser), description="The effective user (euid).")
    working_directory: optional(keyword(), description="The working directory of the process.")
