"""Services for searching tasks embedded in cases."""

from typing import Any, Literal

from howler.common.exceptions import ForbiddenException
from howler.common.loader import datastore
from howler.odm.models.user import User
from howler.services import case_service
from howler.utils.str_utils import sanitize_lucene_query

TaskFilter = Literal["all", "complete", "incomplete"]

_CASE_CONTEXT_FIELDS = ("case_id", "title", "status", "start", "end", "updated")
_CASE_SEARCH_FIELDS = (
    "case_id,title,status,start,end,updated,"
    "items.id,items.parent,items.name,items.value,items.classification,"
    "tasks.id,tasks.complete,tasks.assignment,tasks.summary,tasks.item"
)


def _task_sort_key(task: dict[str, Any]) -> tuple[str, str, str, bool]:
    """Build a stable ordering for tasks within a case."""
    return (
        str(task.get("id") or ""),
        str(task.get("summary") or ""),
        str(task.get("item") or ""),
        task.get("complete", False) is True,
    )


def search_tasks(user: User, offset: int = 0, rows: int = 25, task_filter: TaskFilter = "incomplete") -> dict[str, Any]:
    """Search the authenticated user's tasks and paginate across embedded case tasks.

    Cases are streamed in the datastore's stable ID order. Tasks are explicitly sorted by
    their IDs, so pagination remains deterministic even when multiple tasks share a case.
    Only task records assigned to ``user.uname`` are included in the response.
    """
    if not user.access_control:
        raise ForbiddenException("Cannot search tasks without case access controls.")

    username = user.uname
    query = f'tasks.assignment:"{sanitize_lucene_query(username)}"'
    cases = datastore().case.stream_search(
        query,
        fl=_CASE_SEARCH_FIELDS,
        access_control=user.access_control,
        as_obj=False,
    )

    items: list[dict[str, Any]] = []
    matching_tasks_seen = 0
    has_more = False

    try:
        for case_data in cases:
            raw_tasks = case_data.get("tasks", [])
            if not isinstance(raw_tasks, list):
                continue

            matching_tasks = [
                task
                for task in raw_tasks
                if isinstance(task, dict)
                and task.get("assignment") == username
                and (
                    task_filter == "all"
                    or (task_filter == "complete" and task.get("complete", False) is True)
                    or (task_filter == "incomplete" and task.get("complete", False) is not True)
                )
            ]

            for task in sorted(matching_tasks, key=_task_sort_key):
                if matching_tasks_seen < offset:
                    matching_tasks_seen += 1
                    continue

                if len(items) >= rows:
                    has_more = True
                    break

                case_context = {
                    "__index": "case",
                    **{field: case_data[field] for field in _CASE_CONTEXT_FIELDS if field in case_data},
                }
                case_context["items"] = case_data.get("items", [])
                case_service.filter_case_items_by_classification(case_context, user.classification)

                items.append({"task": task, "case": case_context})
                matching_tasks_seen += 1

            if has_more:
                break
    finally:
        close = getattr(cases, "close", None)
        if callable(close):
            close()

    return {"items": items, "offset": offset, "rows": rows, "has_more": has_more}
