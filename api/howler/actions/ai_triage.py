"""Queue AI-generated triage dossiers for selected alerts."""

from typing import Any

from howler.actions import ADVANCED_ROLES
from howler.common.logging import get_logger
from howler.config import CLASSIFICATION
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.user import User
from howler.services import ai_service

logger = get_logger(__file__)

OPERATION_ID = "ai_triage"
ROLES = ["automation_basic", "automation_advanced", "actionrunner_basic", "actionrunner_advanced"]
MAX_HITS_BASIC = 10
MAX_HITS_ADVANCED = 50
SKIP_CENTRAL_LIMIT = True


def execute(
    query: str,
    user: User | None = None,
    auth_token: str | None = None,
    prompt: str | None = None,
    **kwargs: Any,
) -> list[dict[str, Any]]:
    """Queue one alert job per eligible hit and return a normal action report."""

    def report(outcome: str, title: str, message: str) -> list[dict[str, Any]]:
        return [{"query": query, "outcome": outcome, "title": title, "message": message}]

    try:
        if not ai_service.is_available():
            return report(
                "error", "AI triage unavailable", "AI triage is not enabled or is missing valid local configuration."
            )

        if not user:
            return report("error", "No user specified", "AI Triage cannot run without a provided user.")

        if CLASSIFICATION.enforce and not user.access_control:
            return report(
                "error",
                "Invalid Access Control",
                "AI Triage cannot run without a provided user with valid access control.",
            )

        if not auth_token:
            return report("error", "Authentication required", "AI triage requires a Bearer authorization token.")

        max_hits = MAX_HITS_ADVANCED if ADVANCED_ROLES & set(user.type) else MAX_HITS_BASIC
        count = ai_service.enqueue_alerts(query, user, auth_token, prompt=prompt, max_hits=max_hits)
    except Exception:
        # Redis and datastore errors can contain connection details or secrets.
        logger.error("Unable to enqueue AI triage alerts")  # noqa: TRY400
        return report(
            "error", "AI triage could not be queued", "Alerts could not be durably queued. Please retry later."
        )

    if count is None:
        return report(
            "error",
            "Hit limit exceeded",
            "The query matches more eligible alerts than this action can process; narrow the query and retry.",
        )

    if count == 0:
        return report("skipped", "No matching alerts", "No unresolved, unassessed alerts matched the query.")

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
        "roles": ROLES,
        "requires_auth_token": True,
        "steps": [{"args": {"prompt": []}, "optional_args": ["prompt"]}],
        "triggers": VALID_TRIGGERS,
    }
