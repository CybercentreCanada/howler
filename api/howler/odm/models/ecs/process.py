from typing import Optional

from howler import odm
from howler.odm.models.ecs.code_signature import CodeSignature
from howler.odm.models.ecs.hash import Hashes
from howler.odm.models.ecs.pe import PE
from howler.odm.models.ecs.user import ShortUser


@odm.model(index=True, store=True, description="Information about the char device.")
class CharDevice(odm.Model):
    major = odm.Optional(odm.Integer(description="The major number identifies the driver associated with the device."))
    minor = odm.Optional(
        odm.Integer(
            description="The minor number is used only by the driver specified by the major number; other parts of "
            "the kernel don't use it, and merely pass it along to the driver."
        )
    )


@odm.model(index=True, store=True, description="Information about the controlling TTY device.")
class TTY(odm.Model):
    char_device = odm.Optional(odm.Compound(CharDevice, description="Information about the char device."))


@odm.model(index=True, store=True, description="Thread Information.")
class Thread(odm.Model):
    id: Optional[int] = odm.Optional(odm.Integer(description="Thread ID."))
    name: Optional[str] = odm.Optional(odm.Keyword(description="Thread name."))


@odm.model(index=True, store=True, description="Entry Meta-Information.")
class EntryMeta(odm.Model):
    type: Optional[str] = odm.Keyword(description="SESSIONNAME from Process Environment Variable", optional=True)


@odm.model(
    index=True,
    store=True,
    description="These fields contain information about a process.",
)
class ParentParentProcess(odm.Model):
    args = odm.Optional(
        odm.List(
            odm.Keyword(),
            description="Array of process arguments, starting with the absolute path to the executable.",
        )
    )
    args_count = odm.Optional(odm.Integer(description="Length of the process.args array."))
    code_signature = odm.Optional(
        odm.Compound(CodeSignature),
        description="Information about binary code signatures.",
    )
    command_line = odm.Optional(
        odm.Keyword(
            description="Full command line that started the process, including the absolute path to the "
            "executable, and all arguments."
        )
    )
    end = odm.Optional(odm.Date(description="The time the process ended."))
    entity_id = odm.Optional(odm.Keyword(description="OID Hash of the process."))
    entry_meta: Optional[EntryMeta] = odm.Optional(
        odm.Compound(EntryMeta),
        description="Process Meta Information.",
    )
    env_vars = odm.Optional(
        odm.Mapping(
            odm.Keyword(),
            description="Environment variables (env_vars) set at the time of the event. May be filtered to "
            "protect sensitive information.",
        )
    )
    executable = odm.Optional(odm.Keyword(description="Absolute path to the process executable."))
    exit_code = odm.Optional(odm.Integer(description="The exit code of the process, if this is a termination event."))
    hash = odm.Optional(odm.Compound(Hashes), description="Hashes, usually file hashes")
    interactive = odm.Optional(odm.Boolean(description="Whether the process is connected to an interactive shell."))
    name = odm.Optional(odm.Keyword(description="Process name."))
    pe = odm.Optional(
        odm.Compound(PE),
        description="Windows Portable Executable (PE) metadata.",
    )
    pid = odm.Optional(odm.Integer(description="Process id."))
    same_as_process = odm.Optional(
        odm.Boolean(
            description="This boolean is used to identify if a leader process is the same as the top level process."
        )
    )
    start = odm.Optional(odm.Date(description="The time the process started."))
    title = odm.Optional(odm.Keyword(description="Process title."))
    uptime = odm.Optional(odm.Integer(description="Seconds the process has been up."))
    user = odm.Optional(odm.Compound(ShortUser, description="The effective user (euid)."))
    working_directory = odm.Optional(odm.Keyword(description="The working directory of the process."))


@odm.model(
    index=True,
    store=True,
    description="These fields contain information about a process.",
)
class ParentProcess(odm.Model):
    args = odm.Optional(
        odm.List(
            odm.Keyword(),
            description="Array of process arguments, starting with the absolute path to the executable.",
        )
    )
    args_count = odm.Optional(odm.Integer(description="Length of the process.args array."))
    code_signature = odm.Optional(
        odm.Compound(CodeSignature),
        description="Information about binary code signatures.",
    )
    command_line = odm.Optional(
        odm.Keyword(
            description="Full command line that started the process, including the absolute path to the "
            "executable, and all arguments."
        )
    )
    end = odm.Optional(odm.Date(description="The time the process ended."))
    entity_id = odm.Optional(odm.Keyword(description="OID Hash of the process."))
    entry_meta: Optional[EntryMeta] = odm.Optional(
        odm.Compound(EntryMeta),
        description="Process Meta Information.",
    )
    env_vars = odm.Optional(
        odm.Mapping(
            odm.Keyword(),
            description="Environment variables (env_vars) set at the time of the event. May be filtered to "
            "protect sensitive information.",
        )
    )
    executable = odm.Optional(odm.Keyword(description="Absolute path to the process executable."))
    exit_code = odm.Optional(odm.Integer(description="The exit code of the process, if this is a termination event."))
    hash = odm.Optional(odm.Compound(Hashes), description="Hashes, usually file hashes")
    interactive = odm.Optional(odm.Boolean(description="Whether the process is connected to an interactive shell."))
    name = odm.Optional(odm.Keyword(description="Process name."))
    parent = odm.Optional(
        odm.Compound(ParentParentProcess),
        description="Information about the parent process.",
    )
    pe = odm.Optional(
        odm.Compound(PE),
        description="Windows Portable Executable (PE) metadata.",
    )
    pid = odm.Optional(odm.Integer(description="Process id."))
    same_as_process = odm.Optional(
        odm.Boolean(
            description="This boolean is used to identify if a leader process is the same as the top level process."
        )
    )
    start = odm.Optional(odm.Date(description="The time the process started."))
    title = odm.Optional(odm.Keyword(description="Process title."))
    uptime = odm.Optional(odm.Integer(description="Seconds the process has been up."))
    user = odm.Optional(odm.Compound(ShortUser, description="The effective user (euid)."))
    working_directory = odm.Optional(odm.Keyword(description="The working directory of the process."))


@odm.model(
    index=True,
    store=True,
    description="These fields contain information about a process.",
)
class Process(odm.Model):
    args = odm.Optional(
        odm.List(
            odm.Keyword(),
            description="Array of process arguments, starting with the absolute path to the executable.",
        )
    )
    args_count = odm.Optional(odm.Integer(description="Length of the process.args array."))
    code_signature = odm.Optional(
        odm.Compound(CodeSignature),
        description="Information about binary code signatures.",
    )
    command_line = odm.Optional(
        odm.Keyword(
            description="Full command line that started the process, including the absolute path to the "
            "executable, and all arguments."
        )
    )
    end = odm.Optional(odm.Date(description="The time the process ended."))
    entity_id = odm.Optional(odm.Keyword(description="OID Hash of the process."))
    entry_meta: Optional[EntryMeta] = odm.Optional(
        odm.Compound(EntryMeta),
        description="Process Meta Information.",
    )
    env_vars = odm.Optional(
        odm.Mapping(
            odm.Keyword(),
            description="Environment variables (env_vars) set at the time of the event. May be filtered to "
            "protect sensitive information.",
        )
    )
    executable = odm.Optional(odm.Keyword(description="Absolute path to the process executable."))
    exit_code = odm.Optional(odm.Integer(description="The exit code of the process, if this is a termination event."))
    hash = odm.Optional(odm.Compound(Hashes), description="Hashes, usually file hashes")
    interactive = odm.Optional(odm.Boolean(description="Whether the process is connected to an interactive shell."))
    name = odm.Optional(odm.Keyword(description="Process name."))
    parent = odm.Optional(
        odm.Compound(ParentProcess),
        description="Information about the parent process.",
    )
    pe = odm.Optional(
        odm.Compound(PE),
        description="Windows Portable Executable (PE) metadata.",
    )
    pid = odm.Optional(odm.Integer(description="Process id."))
    same_as_process = odm.Optional(
        odm.Boolean(
            description="This boolean is used to identify if a leader process is the same as the top level process."
        )
    )
    start = odm.Optional(odm.Date(description="The time the process started."))
    title = odm.Optional(odm.Keyword(description="Process title."))
    uptime = odm.Optional(odm.Integer(description="Seconds the process has been up."))
    user = odm.Optional(odm.Compound(ShortUser, description="The effective user (euid)."))
    working_directory = odm.Optional(odm.Keyword(description="The working directory of the process."))
