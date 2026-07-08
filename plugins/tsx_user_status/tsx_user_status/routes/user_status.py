from flask import request
from howler.api import bad_request, internal_error, make_subapi_blueprint, not_found, ok
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.security import api_login

from tsx_user_status.constants import UserStatus
from tsx_user_status.exceptions import UserStatusError
from tsx_user_status.services.schedule_service import get_schedules
from tsx_user_status.services.user_status_service import UNSET, UserStatusService

SUB_API = "status"
status_api = make_subapi_blueprint(SUB_API, api_version=1)
status_api._doc = "User status operations"

logger = get_logger(__file__)


def _build_user_state(uname: str, name: str, status_service: UserStatusService) -> dict:
    """Read the full status/schedule/team state for a user.

    Args:
        uname: The user's unique identifier.
        name: Display name for the user.
        status_service: The shared :class:`UserStatusService` instance.

    Returns:
        Dict with keys ``"uname"``, ``"name"``, ``"status"``,
        ``"schedule"``, ``"team"``.

    Raises:
        UserStatusError: If any read fails.
    """
    shift = status_service.get_shift(uname) or {}
    return {
        "uname": uname,
        "name": name,
        "status": status_service.get_status(uname),
        "schedule": shift.get("schedule"),
        "team": shift.get("team"),
    }


@generate_swagger_docs()
@status_api.route("/users/<uname>", methods=["GET"])
@api_login(required_priv=["R"], required_type=["user"])
def get_user_state(uname: str, **kwargs):
    """Get a user's status, schedule, and team.

    Variables:
    uname        => The user's uname to look up

    Arguments:
    None

    Data Block:
    None

    Result example:
    {"api_response": {"uname": "john.doe", "name": "John Doe",
                      "status": "available", "schedule": "Day 7-15", "team": "MS",
                      "tags": {"portfolio": ["Portfolio A"], "products": ["Product A"],
                               "primary_disciplines": ["Discipline A"]}}}
    """
    from howler.common.loader import datastore

    from tsx_user_status.config import status_service

    ds = datastore()
    user_data = ds.user.get(uname, as_obj=False)
    if not user_data:
        return not_found(f"User '{uname}' not found")

    default_tags = {"portfolio": [], "products": [], "primary_disciplines": []}
    name = user_data.get("name", uname)
    tags = {**default_tags, **user_data.get("tags", {})}

    try:
        user_state = _build_user_state(uname, name, status_service)
        user_state["tags"] = tags
        return ok(user_state)
    except UserStatusError as e:
        return internal_error(err=str(e))


@generate_swagger_docs()
@status_api.route("/users/<uname>", methods=["PATCH"])
@api_login(required_priv=["W"], required_type=["user"])
def patch_user_state(uname: str, **kwargs):
    """Partially update a user's status/schedule/team (JSON Merge Patch).

    Fields omitted from the body are left untouched. Fields explicitly set
    to ``null`` are cleared.

    Variables:
    uname        => The user's uname to update

    Arguments:
    None

    Data Block:
    {
        "status": "available",    // optional; null clears
        "schedule": "Day 7-15",   // optional; null clears
        "team": "MS"              // optional; null clears
    }

    Result example:
    {"api_response": {"uname": "john.doe", "name": "John Doe",
                      "status": "available", "schedule": "Day 7-15", "team": "MS"}}
    """
    from howler.common.loader import datastore

    from tsx_user_status.config import status_service

    ds = datastore()
    user_data = ds.user.get(uname, as_obj=False)
    if not user_data:
        return not_found(f"User '{uname}' not found")

    name = user_data.get("name", uname)

    if not request.is_json:
        return bad_request("Request must be JSON")

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return bad_request("Request body must be a JSON object")

    status = data["status"] if "status" in data else UNSET
    schedule = data["schedule"] if "schedule" in data else UNSET
    team = data["team"] if "team" in data else UNSET

    if status is UNSET and schedule is UNSET and team is UNSET:
        return bad_request("Request body must include at least one of 'status', 'schedule', or 'team'")

    try:
        status_service.apply_patch(uname, status=status, schedule=schedule, team=team)
    except ValueError as e:
        return bad_request(str(e))
    except UserStatusError as e:
        return internal_error(err=str(e))

    try:
        return ok(_build_user_state(uname, name, status_service))
    except UserStatusError as e:
        return internal_error(err=str(e))


@generate_swagger_docs()
@status_api.route("/users", methods=["GET"])
@api_login(required_priv=["R"], required_type=["user"])
def get_all_statuses(**kwargs):
    """Get all users' statuses, schedules, teams, and tags.

    Returns all active users with their status, schedule, team, and tags. Users without an
    explicit value set will have ``null`` for that field.

    Variables:
    None

    Arguments:
    None

    Data Block:
    None

    Result example:
    {"api_response": [
        {"uname": "user1", "name": "User One", "status": "available",
         "schedule": "Day 7-15", "team": "MS",
         "tags": {"portfolio": ["Portfolio A"], "products": ["Product A"],
                  "primary_disciplines": ["Discipline A"]}},
        {"uname": "user2", "name": "User Two", "status": null,
         "schedule": null, "team": null,
         "tags": {"portfolio": [], "products": [], "primary_disciplines": []}}
    ]}
    """
    from tsx_user_status.config import status_service

    try:
        return ok(status_service.get_all_statuses())
    except UserStatusError as e:
        return internal_error(err=str(e))


@generate_swagger_docs()
@status_api.route("/statuses", methods=["GET"])
@api_login(required_priv=["R"], required_type=["user"])
def get_status_options(**kwargs):
    """Get the list of valid status values.

    Variables:
    None

    Arguments:
    None

    Data Block:
    None

    Result example:
    {"api_response": ["1", "2", ..., "15", "available", "busy", "unavailable", "away"]}
    """
    return ok([s.value for s in UserStatus])


@generate_swagger_docs()
@status_api.route("/schedules", methods=["GET"])
@api_login(required_priv=["R"], required_type=["user"])
def get_schedule_options(**kwargs):
    """Get the mapping of teams to their valid schedules.

    Variables:
    None

    Arguments:
    None

    Data Block:
    None

    Result example:
    {"api_response": {"MS": ["Day 7-15", "Day 9-17", ...], "CBCS": [...]}}
    """
    from tsx_user_status.config import config as plugin_config

    try:
        return ok(get_schedules(plugin_config))
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to load schedules")
        return internal_error(err=f"Failed to load schedules: {str(e)}")
