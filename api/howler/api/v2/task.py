"""Task-related v2 API endpoints."""

from typing import Literal, cast

from flask import request

from howler.api import bad_request, forbidden, make_subapi_blueprint, ok
from howler.common.exceptions import ForbiddenException
from howler.common.swagger import generate_swagger_docs
from howler.odm.models.user import User
from howler.security.login import api_login
from howler.services import task_service

SUB_API = "task"
task_api = make_subapi_blueprint(SUB_API, api_version=2)
task_api._doc = "Search tasks assigned to the authenticated user"  # type: ignore[attr-defined]

TASK_FILTERS = {"all", "complete", "incomplete"}
TaskFilter = Literal["all", "complete", "incomplete"]


def _parse_integer_parameter(name: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
    """Parse and validate an integer pagination parameter from the query string."""
    raw_value = request.args.get(name)
    if raw_value is None:
        return default

    if not raw_value.isascii() or not raw_value.isdigit():
        raise ValueError(f"'{name}' must be an integer.")

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"'{name}' must be an integer.") from error

    if value < minimum:
        raise ValueError(f"'{name}' must be at least {minimum}.")
    if maximum is not None and value > maximum:
        raise ValueError(f"'{name}' must be at most {maximum}.")

    return value


@generate_swagger_docs()
@task_api.route("/search", methods=["GET"])
@api_login(required_priv=["R"])
def search_tasks(user: User, **kwargs):
    """Return an authenticated user's assigned tasks with pagination.

    Optional query parameters:
    offset: Zero-based task offset (default 0).
    rows: Number of tasks to return, from 1 to 100 (default 25).
    filter: One of all, complete, or incomplete (default incomplete).
    """
    try:
        offset = _parse_integer_parameter("offset", 0, minimum=0)
        rows = _parse_integer_parameter("rows", 25, minimum=1, maximum=100)
    except ValueError as error:
        return bad_request(err=str(error))

    task_filter = request.args.get("filter", "incomplete")
    if task_filter not in TASK_FILTERS:
        return bad_request(err="'filter' must be one of: all, complete, incomplete.")

    try:
        result = task_service.search_tasks(user, offset=offset, rows=rows, task_filter=cast(TaskFilter, task_filter))
        return ok(result)
    except ForbiddenException as error:
        return forbidden(err=error.message)
