"""Queue AI-generated triage dossiers for selected alerts."""

from typing import Any, cast

from howler.actions import ADVANCED_ROLES, check_hit_limit
from howler.common.logging import get_logger
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.user import User
from howler.services import ai_triage_service

logger = get_logger(__file__)

OPERATION_ID = "ai_triage"
ROLES = ["automation_basic", "automation_advanced", "actionrunner_basic", "actionrunner_advanced"]
MAX_HITS_BASIC = 10
MAX_HITS_ADVANCED = 50
SKIP_CENTRAL_LIMIT = True


def is_available() -> bool:
    """Return local configuration availability without contacting the provider."""
    return ai_triage_service.is_available()


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
        if not is_available():
            return report(
                "error", "AI triage unavailable", "AI triage is not enabled or is missing valid local configuration."
            )
        if not auth_token:
            return report("error", "Authentication required", "AI triage requires a Bearer authorization token.")

        filtered_query = f"({query}) AND NOT howler.status:resolved AND NOT howler.assessment:*"
        current_user = cast(User, user)
        max_hits = MAX_HITS_ADVANCED if ADVANCED_ROLES & set(current_user["type"]) else MAX_HITS_BASIC
        limit_error = check_hit_limit(
            filtered_query,
            current_user,
            MAX_HITS_BASIC,
            MAX_HITS_ADVANCED,
            access_control=current_user.access_control,
        )
        if limit_error:
            return [limit_error]

        count = ai_triage_service.enqueue_alerts(query, current_user, auth_token, prompt=prompt, max_hits=max_hits)
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
        "steps": [{"args": {}, "optional_args": ["prompt"]}],
        "triggers": VALID_TRIGGERS,
    }
