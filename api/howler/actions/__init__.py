import importlib
import os
import re
from pathlib import Path
from typing import Any, Optional

from howler.common.logging import get_logger
from howler.odm.models.user import User
from howler.plugins import get_plugins

logger = get_logger(__file__)

PLUGIN_PATH = Path(os.environ.get("HWL_PLUGIN_DIRECTORY", "/etc/howler/plugins"))


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
        "steps": [{**step, "args": {k: list(v) for k, v in step["args"].items()}} for step in spec.get("steps", [])],
    }


def __sanitize_report(report: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate identical entries with different queries

    Args:
        report (list[dict[str, Any]]): The unsanitized, verbose report

    Returns:
        list[dict[str, Any]]: The sanitized, concise report
    """
    by_message: dict[str, Any] = {}

    for entry in report:
        # if these three keys match, we should merge the queries that use them both. For example, when multiple hits
        # fail to transition for the same reason.
        key = f"{entry['title']}==={entry['message']}==={entry['outcome']}"

        if key in by_message:
            by_message[key].append(f'({entry["query"]})')
        else:
            by_message[key] = [f'({entry["query"]})']

    sanitized: list[dict[str, Any]] = []
    for key, queries in by_message.items():
        (title, message, outcome) = key.split("===")

        sanitized.append(
            {
                "query": " OR ".join(queries),
                "outcome": outcome,
                "title": title,
                "message": message,
            }
        )

    return sanitized


def execute(
    operation_id: str,
    query: str,
    user: User,
    request_id: Optional[str] = None,
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

    if not operation:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Unknown Action",
                "message": f"The operation ID provided ({operation_id}) does not match any enabled operations.",
            }
        ]

    missing_roles = set(operation.specification()["roles"]) - set(user["type"])
    if missing_roles:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Insufficient permissions",
                "message": (
                    f"The operation ID provided ({operation_id}) requires permissions you do not have "
                    f"({', '.join(missing_roles)}). Contact HOWLER Support for more information."
                ),
            }
        ]

    report = operation.execute(query=query, request_id=request_id, user=user, **kwargs)

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

            specifications.append(__sanitize_specification(operation.specification()))

        except Exception:  # pragma: no cover
            logger.exception("Error when initializing %s", module)

    for plugin in get_plugins():
        if not plugin.modules.operations:
            continue

        for operation in plugin.modules.operations:
            specifications.append(__sanitize_specification(operation.specification()))

    return specifications
