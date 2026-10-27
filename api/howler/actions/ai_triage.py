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
    """Return local configuration availability without contacting the provider."""
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
    """Queue one alert job per eligible hit and return a normal action report."""
    del request_id, action_id, trigger

    def report(outcome: str, title: str, message: str) -> list[dict[str, Any]]:
        return [{"query": query, "outcome": outcome, "title": title, "message": message}]

    if not is_available():
        return report(
            "error", "AI triage unavailable", "AI triage is not enabled or is missing valid local configuration."
        )
    if user is None:
        return report("error", "Authentication required", "You must be logged in to execute AI triage.")
    if not trusted_auth_token:
        return report("error", "Authentication required", "AI triage requires a Bearer authorization token.")

    try:
        count = ai_triage_service.enqueue_alerts(query, user, trusted_auth_token, prompt=prompt)
    except ai_triage_service.AIQueueValidationError as exc:
        return report("error", "AI triage could not be queued", str(exc))
    except Exception:
        # Redis and datastore errors can contain connection details or secrets.
        logger.error("Unable to enqueue AI triage alerts")  # noqa: TRY400
        return report(
            "error", "AI triage could not be queued", "Alerts could not be durably queued. Please retry later."
        )

    return report("success", "AI triage queued", f"AI triage was queued for {count} alert(s).")


def specification() -> dict[str, Any]:
    """Declare AI triage as an ordinary action with one optional argument."""
    return {
        "id": OPERATION_ID,
        "title": "AI Triage",
        "priority": 90,
        "i18nKey": f"operations.{OPERATION_ID}",
        "description": {
            "short": "Generate a conservative AI triage lead for eligible alerts",
            "long": (
                "Queue asynchronous AI triage for unresolved alerts that have no assessment. "
                "The provider receives only configured filtered alert data."
            ),
        },
        "roles": ["automation_basic", "automation_advanced", "actionrunner_basic", "actionrunner_advanced"],
        "requires_auth_token": True,
        "steps": [{"args": {}, "optional_args": ["prompt"]}],
        "triggers": VALID_TRIGGERS,
    }
