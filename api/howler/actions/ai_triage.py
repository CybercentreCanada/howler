"""Queue AI-generated triage dossiers for selected alerts."""

from typing import Any

from howler.common.logging import get_logger
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.user import User
from howler.services import ai_triage_service

logger = get_logger(__file__)

OPERATION_ID = "ai_triage"
MAX_HITS_BASIC = 10
MAX_HITS_ADVANCED = 50
SKIP_CENTRAL_LIMIT = True


def is_available() -> bool:
    """Return local configuration availability without calling the provider."""
    return ai_triage_service.is_available()


def execute(
    query: str,
    user: User | None = None,
    request_id: str | None = None,
    action_id: str | None = None,
    trigger: str | None = None,
    prompt: str | None = None,
    trusted_auth_token: str | None = None,
    **_kwargs: Any,
) -> list[dict[str, Any]]:
    """Queue a run and return a backward-compatible accepted report entry."""
    if not is_available():
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "AI triage unavailable",
                "message": "AI triage is not enabled or is missing valid local configuration.",
            }
        ]
    if user is None:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Authentication required",
                "message": "You must be logged in to execute AI triage.",
            }
        ]
    if not trusted_auth_token:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Authentication required",
                "message": "AI triage requires a Bearer authorization token.",
            }
        ]

    try:
        run = ai_triage_service.enqueue_action(
            query,
            user,
            request_id=request_id,
            action_id=action_id,
            trigger=trigger,
            trusted_auth_token=trusted_auth_token,
            prompt=prompt,
        )
    except ai_triage_service.AIQueueValidationError as exc:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "AI triage could not be queued",
                "message": str(exc),
            }
        ]
    except Exception:
        # Redis and datastore exceptions can include connection details or other
        # secrets. Keep them out of reports and logs.
        logger.error("Unable to enqueue AI triage run")  # noqa: TRY400
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "AI triage could not be queued",
                "message": "The run could not be durably queued. Please retry later.",
            }
        ]

    return [
        {
            "query": query,
            "outcome": "success",
            "title": "AI triage queued",
            "message": f"AI triage was queued for {run['counts']['total']} alert(s).",
            "run_id": run["run_id"],
            "status": "queued",
        }
    ]


def specification() -> dict[str, Any]:
    """Declare the operation and its only optional action argument."""
    return {
        "id": OPERATION_ID,
        "title": "AI Triage",
        "priority": 90,
        "i18nKey": f"operations.{OPERATION_ID}",
        "description": {
            "short": "Generate a conservative AI triage lead for eligible alerts",
            "long": (
                "Queue a durable AI triage run for unresolved alerts that have no assessment. "
                "The provider receives only the configured filtered alert data."
            ),
        },
        "roles": ["automation_basic", "automation_advanced", "actionrunner_basic", "actionrunner_advanced"],
        "requires_auth_token": True,
        "steps": [{"args": {}, "optional_args": ["prompt"]}],
        "triggers": VALID_TRIGGERS,
    }
