from flask import abort, make_response
from howler import config as howler_config
from howler.api import make_subapi_blueprint
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from redis import RedisError

from tsx_user_status.services.schedule_service import fetch_schedules_from_blob

SUB_API = "status/healthz"
healthz_api = make_subapi_blueprint(SUB_API, api_version=1)
healthz_api._doc = "Health check tsx_user_status Plugin API endpoints"

logger = get_logger(__file__)


def _check_required_schedule_fields(config: object) -> list[str]:
    """Validate that the required schedule config fields are present and non-empty.

    Args:
        config: Plugin config object.

    Returns:
        A list of problem descriptions; empty if all required fields are set.
    """
    required_fields = [
        "schedules_account",
        "schedules_container",
        "schedules_blob",
        "schedules_key",
    ]
    problems: list[str] = []
    for field in required_fields:
        value = getattr(config, field, None)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"Missing or empty schedule config field: {field}")
    return problems


def _check_schedules_blob(config: object) -> list[str]:
    """Check that the schedules blob is reachable and contains valid data.

    Args:
        config: Plugin config object.

    Returns:
        A list of problem descriptions; empty if the blob is healthy.
    """
    problems = _check_required_schedule_fields(config)
    if problems:
        return problems

    try:
        from azure.core.exceptions import AzureError

        schedules = fetch_schedules_from_blob(config)
        if not schedules:
            return ["Schedules blob is empty"]
        return []
    except ImportError as exc:
        return [f"Missing Azure Blob dependency: {type(exc).__name__}"]
    except AzureError as exc:
        return [f"Schedules blob connectivity failed: {type(exc).__name__}"]
    except ValueError as exc:
        return [str(exc)]
    except Exception as exc:  # noqa: BLE001
        return [f"Schedules blob check failed: {type(exc).__name__}"]


@generate_swagger_docs()
@healthz_api.route("/live", methods=["GET"])
def liveness(**_):
    """Check if the plugin is responding.

    Variables:
    None

    Arguments:
    None

    Result Example:
    OK or FAIL
    """
    return make_response("OK")


@generate_swagger_docs()
@healthz_api.route("/ready", methods=["GET"])
def readiness(**_):
    """Check if the plugin is ready for use.

    Checks that the persistent Redis connection is alive and that the
    schedules blob is reachable and contains valid data.

    Variables:
    None

    Arguments:
    None

    Result Example:
    OK or FAIL
    """
    from tsx_user_status.config import config as plugin_config

    problems: list[str] = []

    try:
        if not howler_config.redis_persistent.ping():
            problems.append("Persistent Redis ping returned false")
    except (ConnectionError, RedisError) as exc:
        problems.append(f"Persistent Redis connectivity failed: {type(exc).__name__}")

    problems.extend(_check_schedules_blob(plugin_config))

    if problems:
        for problem in problems:
            logger.error("Plugin readiness check failed: %s", problem)
        abort(503)

    return make_response("OK")


@healthz_api.errorhandler(503)
def _service_unavailable(_):
    """Handle errors exposed in healthz routes."""
    return "FAIL", 503
