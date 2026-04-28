"""Deprecated remove_from_bundle action — delegates to case_service for item removal."""

from typing import Optional

from howler.actions import check_hit_limit
from howler.common.exceptions import NotFoundException
from howler.common.loader import datastore
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.user import User
from howler.services import bundle_compat_service, case_service
from howler.utils.str_utils import sanitize_lucene_query

OPERATION_ID = "remove_from_bundle"
MAX_HITS_BASIC = 10
MAX_HITS_ADVANCED = 1000
SKIP_CENTRAL_LIMIT = True  # This operation transforms the query, handles limit check locally


def execute(query: str, bundle_id: Optional[str] = None, user: Optional[User] = None, **kwargs):  # noqa: C901
    """Remove a set of hits matching the query from the specified bundle (deprecated — uses cases).

    Args:
        query (str): The query containing the matching hits
        bundle_id (str): The ``howler.id`` of the bundle to remove the hits from.
    """
    report = []

    if not bundle_id:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Invalid Bundle ID",
                "message": "Bundle ID cannot be empty.",
            }
        ]

    try:
        case_id = bundle_compat_service.find_case_for_bundle(bundle_id)
        if case_id is None:
            report.append(
                {
                    "query": query,
                    "outcome": "error",
                    "title": "Invalid Bundle",
                    "message": f"Either a hit with ID {bundle_id} does not exist, or it has no associated case.",
                }
            )
            return report

        ds = datastore()

        # Check hit limit against the query before searching
        if user:
            limit_error = check_hit_limit(query, user, MAX_HITS_BASIC, MAX_HITS_ADVANCED)
            if limit_error:
                return [limit_error]

        matching_hits = ds.hit.search(query, rows=MAX_HITS_ADVANCED)["items"]

        if not matching_hits:
            report.append(
                {
                    "query": query,
                    "outcome": "skipped",
                    "title": "No Matching Hits",
                    "message": "There were no hits matching this query.",
                }
            )
            return report

        # Get the case to check which hits are actually in it
        case = ds.case.get(case_id)
        if case is None:
            report.append(
                {
                    "query": query,
                    "outcome": "error",
                    "title": "Case Not Found",
                    "message": f"Associated case {case_id} no longer exists.",
                }
            )
            return report

        case_item_values = {item.value for item in case.items}
        values_to_remove = [h.howler.id for h in matching_hits if h.howler.id in case_item_values]
        skipped_ids = [h.howler.id for h in matching_hits if h.howler.id not in case_item_values]

        if skipped_ids:
            report.append(
                {
                    "query": f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in skipped_ids)})",
                    "outcome": "skipped",
                    "title": "Skipped Hits Not in Bundle",
                    "message": "These hits are not in the bundle.",
                }
            )

        if not values_to_remove:
            report.append(
                {
                    "query": query,
                    "outcome": "skipped",
                    "title": "No Matching Hits",
                    "message": "None of the matching hits were found in the bundle.",
                }
            )
            return report

        case_service.remove_case_items(case_id, values_to_remove)

        report.append(
            {
                "query": query,
                "outcome": "success",
                "title": "Executed Successfully",
                "message": f"Matching hits removed from bundle with id {bundle_id}",
            }
        )

    except NotFoundException as e:
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "Failed to Execute",
                "message": str(e),
            }
        )
    except Exception as e:
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "Failed to Execute",
                "message": f"Unknown exception occurred: {str(e)}",
            }
        )

    return report


def specification():
    """Specify various properties of the action, such as title, descriptions, permissions and input steps."""
    return {
        "id": OPERATION_ID,
        "title": "Remove from Bundle (Deprecated)",
        "priority": 5,
        "i18nKey": f"operations.{OPERATION_ID}",
        "description": {
            "short": "Remove a set of hits from a bundle (deprecated — uses cases)",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic", "actionrunner_basic"],
        "steps": [
            {
                "args": {"bundle_id": []},
                "options": {},
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
