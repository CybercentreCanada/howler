import importlib
import os
import re
from pathlib import Path
from types import ModuleType
from typing import Any, Optional

from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.odm.models.user import User
from howler.plugins import get_plugins

logger = get_logger(__file__)

PLUGIN_PATH = Path(os.environ.get("HWL_PLUGIN_DIRECTORY", "/etc/howler/plugins"))
RESERVED_ACTION_KWARGS = frozenset(
    {"auth_token", "trusted_auth_token", "action_id", "trigger", "request_id", "query", "user"}
)

# Roles that grant advanced hit limits
ADVANCED_ROLES = {"automation_advanced", "actionrunner_advanced", "admin"}


def sanitize_operation_kwargs(data: dict[str, Any]) -> dict[str, Any]:
    """Remove dispatcher-owned arguments from persisted operation data."""
    return {key: value for key, value in data.items() if key not in RESERVED_ACTION_KWARGS}


def _is_builtin_operation(operation_id: str) -> bool:
    """Whether an operation resolves to a module shipped in this package."""
    module = Path(__file__).parent / f"{operation_id}.py"
    return module.parent == Path(__file__).parent and module.is_file()


def __sanitize_specification(spec: dict[str, Any]) -> dict[str, Any]:
    """Adapt the specification for use in the UI

    Args:
        spec (dict[str, Any]): The raw specification

    Returns:
        dict[str, Any]: The sanitized specification for use in the UI
    """
    return {
        **spec,
        "description": {
            **spec["description"],
            "long": re.sub(r"\n +(request_id|query).+", "", spec["description"]["long"])
            .replace("\n    ", "\n")
            .replace("Args:", "Args:\n"),
        },
        "steps": [
            {
                **step,
                "args": {k: list(v) for k, v in step["args"].items()},
                **({"optional_args": list(step["optional_args"])} if "optional_args" in step else {}),
            }
            for step in spec.get("steps", [])
        ],
    }


def __sanitize_report(report: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate identical entries with different queries

    Args:
        report (list[dict[str, Any]]): The unsanitized, verbose report

    Returns:
        list[dict[str, Any]]: The sanitized, concise report
    """
    by_message: dict[tuple[str, str, str], list[str]] = {}

    for entry in report:
        # if these three keys match, we should merge the queries that use them both. For example, when multiple hits
        # fail to transition for the same reason.
        key = (
            entry["title"],
            entry["message"],
            entry["outcome"],
        )

        if key in by_message:
            by_message[key].append(f"({entry['query']})")
        else:
            by_message[key] = [f"({entry['query']})"]

    sanitized: list[dict[str, Any]] = []
    for key, queries in by_message.items():
        title, message, outcome = key
        entry = {
            "query": " OR ".join(queries),
            "outcome": outcome,
            "title": title,
            "message": message,
        }
        sanitized.append(entry)

    return sanitized


def _get_operation(operation_id: str) -> ModuleType | None:
    """Find and return an operation module by ID."""
    operation = None
    try:
        operation = importlib.import_module(f"howler.actions.{operation_id}")
    except ImportError:
        pass

    if not operation:
        for plugin in get_plugins():
            if not plugin.modules.operations:
                continue

            operation = next(
                (operation for operation in plugin.modules.operations if operation.OPERATION_ID == operation_id), None
            )

            if operation:
                break

    return operation


def check_hit_limit(
    query: str, user: User, max_hits_basic: int | None, max_hits_advanced: int | None
) -> dict[str, Any] | None:
    """Check if the user exceeds hit count limits. Returns error dict if exceeded, None otherwise.

    Args:
        query: The query to check hit count for (should be the effective query the operation will execute).
        user: The user executing the action.
        max_hits_basic: Maximum hits allowed for basic users (None for no limit).
        max_hits_advanced: Maximum hits allowed for advanced users (None for no limit).

    Returns:
        Error dict if limit exceeded, None otherwise.
    """
    is_advanced = bool(ADVANCED_ROLES & set(user["type"]))
    limit = max_hits_advanced if is_advanced else max_hits_basic

    if limit is not None:
        hit_count = datastore().hit.search(query, rows=0)["total"]
        if hit_count > limit:
            return {
                "query": query,
                "outcome": "error",
                "title": "Hit limit exceeded",
                "message": (
                    f"This action affects {hit_count} hits, but you can only process {limit} at a time. "
                    "Contact an administrator for bulk operations."
                ),
            }
    return None


def _check_hit_limit(operation: ModuleType, query: str, user: User) -> dict[str, Any] | None:
    """Central hit limit check using raw query. Skipped if operation sets SKIP_CENTRAL_LIMIT."""
    max_hits_basic = getattr(operation, "MAX_HITS_BASIC", None)
    max_hits_advanced = getattr(operation, "MAX_HITS_ADVANCED", None)
    return check_hit_limit(query, user, max_hits_basic, max_hits_advanced)


def execute(
    operation_id: str,
    query: str,
    user: User | None,
    request_id: Optional[str] = None,
    trusted_auth_token: str | None = None,
    action_id: str | None = None,
    trigger: str | None = None,
    **kwargs,
) -> list[dict[str, Any]]:
    """Execute a specification

    Args:
        operation_id (str): The id of the operation to run
        query (str): The query to run this action on
        user (dict[str, Any]): The user running this action
        request_id (str, None): A user-provided ID, can be used to track the progress of their excecution via websockets

    Returns:
        list[dict[str, Any]]: A report on the execution
    """
    operation = _get_operation(operation_id)

    if not operation:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Unknown Action",
                "message": f"The operation ID provided ({operation_id}) does not match any enabled operations.",
            }
        ]

    if not user:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Authentication required",
                "message": "You must be logged in to execute actions.",
            }
        ]

    specification = operation.specification()
    user_roles = set(user["type"])
    is_admin = "admin" in user_roles
    required_roles = set(specification["roles"])
    has_roles = required_roles & user_roles
    if not is_admin and not has_roles:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Insufficient permissions",
                "message": (
                    f"The operation ID provided ({operation_id}) requires permissions you do not have "
                    f"(missing one of: {', '.join(sorted(required_roles))}). "
                    "Contact HOWLER Support for more information."
                ),
            }
        ]

    operation_requires_token = bool(specification.get("requires_auth_token", False))
    if operation_requires_token and not trusted_auth_token:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Authentication required",
                "message": "This operation requires a Bearer authorization token.",
            }
        ]

    # Persisted action data is untrusted. Never let it impersonate the
    # independently parsed request authorization context.
    safe_kwargs = sanitize_operation_kwargs(kwargs)

    # Skip central limit check if operation handles it locally with transformed query
    if not getattr(operation, "SKIP_CENTRAL_LIMIT", False):
        limit_error = _check_hit_limit(operation, query, user)
        if limit_error:
            return [limit_error]

    if operation_requires_token:
        safe_kwargs["trusted_auth_token"] = trusted_auth_token
        safe_kwargs["action_id"] = action_id
        safe_kwargs["trigger"] = trigger
    elif not _is_builtin_operation(operation_id) and trusted_auth_token:
        # Older plugins consume auth_token without declaring the capability.
        # This value comes only from the Bearer-only request parser above.
        safe_kwargs["auth_token"] = trusted_auth_token

    report = operation.execute(query=query, request_id=request_id, user=user, **safe_kwargs)

    return __sanitize_report(report)


def specifications() -> list[dict[str, Any]]:
    """A list of specifications for the available operations

    Returns:
        list[dict[str, Any]]: A list of specifications
    """
    specifications = []

    for module in (
        _file
        for _file in Path(__file__).parent.iterdir()
        if _file.suffix == ".py" and _file.name not in ["__init__.py", "example_plugin.py"]
    ):
        try:
            operation = importlib.import_module(f"howler.actions.{module.stem}")

            if hasattr(operation, "is_available") and not operation.is_available():
                continue

            specifications.append(__sanitize_specification(operation.specification()))

        except Exception:  # pragma: no cover
            logger.exception("Error when initializing %s", module)

    for plugin in get_plugins():
        if not plugin.modules.operations:
            continue

        for operation in plugin.modules.operations:
            specifications.append(__sanitize_specification(operation.specification()))

    return specifications
