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
    register_model,
)
from howler.models.ecs.code_signature import CodeSignature
from howler.models.ecs.hash import Hashes
from howler.models.ecs.pe import PE
from howler.models.ecs.user import ShortUser


@register_model(index=True, store=True, description="Information about the char device.", embedded=True)
class CharDevice(HowlerEmbeddedModel):
    """Information about the char device."""

    major: integer(optional=True, description="The major number identifies the driver associated with the device.")
    minor: integer(
        optional=True,
        description="The minor number is used only by the driver specified by the major number; other parts of "
        "the kernel don't use it, and merely pass it along to the driver.",
    )


@register_model(index=True, store=True, description="Information about the controlling TTY device.", embedded=True)
class TTY(HowlerEmbeddedModel):
    """Information about the controlling TTY device."""

    char_device: compound(CharDevice, optional=True, description="Information about the char device.")


@register_model(index=True, store=True, description="Thread Information.", embedded=True)
class Thread(HowlerEmbeddedModel):
    """Thread Information."""

    id: integer(optional=True, description="Thread ID.")
    name: keyword(optional=True, description="Thread name.")


@register_model(index=True, store=True, description="Entry Meta-Information.", embedded=True)
class EntryMeta(HowlerEmbeddedModel):
    """Entry Meta-Information."""

    type: keyword(optional=True, description="SESSIONNAME from Process Environment Variable")


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class ParentParentProcess(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: list_field(
        keyword(),
        optional=True,
        description="Array of process arguments, starting with the absolute path to the executable.",
    )
    args_count: integer(optional=True, description="Length of the process.args array.")
    code_signature: compound(CodeSignature, optional=True, description="Information about binary code signatures.")
    command_line: keyword(
        optional=True,
        description="Full command line that started the process, including the absolute path to the "
        "executable, and all arguments.",
    )
    end: date(optional=True, description="The time the process ended.")
    entity_id: keyword(optional=True, description="OID Hash of the process.")
    entry_meta: compound(EntryMeta, optional=True, description="Process Meta Information.")
    env_vars: mapping(
        keyword(),
        optional=True,
        description="Environment variables (env_vars) set at the time of the event. May be filtered to "
        "protect sensitive information.",
    )
    executable: keyword(optional=True, description="Absolute path to the process executable.")
    exit_code: integer(optional=True, description="The exit code of the process, if this is a termination event.")
    hash: compound(Hashes, optional=True, description="Hashes, usually file hashes")
    interactive: boolean(optional=True, description="Whether the process is connected to an interactive shell.")
    name: keyword(optional=True, description="Process name.")
    pe: compound(PE, optional=True, description="Windows Portable Executable (PE) metadata.")
    pid: long(optional=True, description="Process id.")
    same_as_process: boolean(
        optional=True,
        description="This boolean is used to identify if a leader process is the same as the top level process.",
    )
    start: date(optional=True, description="The time the process started.")
    title: keyword(optional=True, description="Process title.")
    uptime: integer(optional=True, description="Seconds the process has been up.")
    user: compound(ShortUser, optional=True, description="The effective user (euid).")
    working_directory: keyword(optional=True, description="The working directory of the process.")


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class ParentProcess(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: list_field(
        keyword(),
        optional=True,
        description="Array of process arguments, starting with the absolute path to the executable.",
    )
    args_count: integer(optional=True, description="Length of the process.args array.")
    code_signature: compound(CodeSignature, optional=True, description="Information about binary code signatures.")
    command_line: keyword(
        optional=True,
        description="Full command line that started the process, including the absolute path to the "
        "executable, and all arguments.",
    )
    end: date(optional=True, description="The time the process ended.")
    entity_id: keyword(optional=True, description="OID Hash of the process.")
    entry_meta: compound(EntryMeta, optional=True, description="Process Meta Information.")
    env_vars: mapping(
        keyword(),
        optional=True,
        description="Environment variables (env_vars) set at the time of the event. May be filtered to "
        "protect sensitive information.",
    )
    executable: keyword(optional=True, description="Absolute path to the process executable.")
    exit_code: integer(optional=True, description="The exit code of the process, if this is a termination event.")
    hash: compound(Hashes, optional=True, description="Hashes, usually file hashes")
    interactive: boolean(optional=True, description="Whether the process is connected to an interactive shell.")
    name: keyword(optional=True, description="Process name.")
    parent: compound(ParentParentProcess, optional=True, description="Information about the parent process.")
    pe: compound(PE, optional=True, description="Windows Portable Executable (PE) metadata.")
    pid: long(optional=True, description="Process id.")
    same_as_process: boolean(
        optional=True,
        description="This boolean is used to identify if a leader process is the same as the top level process.",
    )
    start: date(optional=True, description="The time the process started.")
    title: keyword(optional=True, description="Process title.")
    uptime: integer(optional=True, description="Seconds the process has been up.")
    user: compound(ShortUser, optional=True, description="The effective user (euid).")
    working_directory: keyword(optional=True, description="The working directory of the process.")


@register_model(index=True, store=True, description="These fields contain information about a process.", embedded=True)
class Process(HowlerEmbeddedModel):
    """These fields contain information about a process."""

    args: list_field(
        keyword(),
        optional=True,
        description="Array of process arguments, starting with the absolute path to the executable.",
    )
    args_count: integer(optional=True, description="Length of the process.args array.")
    code_signature: compound(CodeSignature, optional=True, description="Information about binary code signatures.")
    command_line: keyword(
        optional=True,
        description="Full command line that started the process, including the absolute path to the "
        "executable, and all arguments.",
    )
    end: date(optional=True, description="The time the process ended.")
    entity_id: keyword(optional=True, description="OID Hash of the process.")
    entry_meta: compound(EntryMeta, optional=True, description="Process Meta Information.")
    env_vars: mapping(
        keyword(),
        optional=True,
        description="Environment variables (env_vars) set at the time of the event. May be filtered to "
        "protect sensitive information.",
    )
    executable: keyword(optional=True, description="Absolute path to the process executable.")
    exit_code: integer(optional=True, description="The exit code of the process, if this is a termination event.")
    hash: compound(Hashes, optional=True, description="Hashes, usually file hashes")
    interactive: boolean(optional=True, description="Whether the process is connected to an interactive shell.")
    name: keyword(optional=True, description="Process name.")
    parent: compound(ParentProcess, optional=True, description="Information about the parent process.")
    pe: compound(PE, optional=True, description="Windows Portable Executable (PE) metadata.")
    pid: long(optional=True, description="Process id.")
    same_as_process: boolean(
        optional=True,
        description="This boolean is used to identify if a leader process is the same as the top level process.",
    )
    start: date(optional=True, description="The time the process started.")
    title: keyword(optional=True, description="Process title.")
    uptime: integer(optional=True, description="Seconds the process has been up.")
    user: compound(ShortUser, optional=True, description="The effective user (euid).")
    working_directory: keyword(optional=True, description="The working directory of the process.")
