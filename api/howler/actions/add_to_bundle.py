"""Deprecated add_to_bundle action — delegates to add_to_case via bundle_compat_service."""

from typing import Optional

from howler.common.exceptions import NotFoundException
from howler.common.loader import datastore
from howler.odm.models.action import VALID_TRIGGERS
from howler.services import bundle_compat_service, case_service
from howler.utils.str_utils import sanitize_lucene_query

OPERATION_ID = "add_to_bundle"


def execute(query: str, bundle_id: Optional[str] = None, **kwargs):
    """Add a set of hits matching the query to the specified bundle (deprecated — uses cases).

    Args:
        query (str): The query containing the matching hits
        bundle_id (str): The ``howler.id`` of the bundle to add the hits to.
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
        matching_hits = ds.hit.search(query, rows=1000)["items"]

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

        added = []
        skipped = []
        for hit in matching_hits:
            child_label = f"hits/{hit.howler.analytic} ({hit.howler.id})"
            try:
                case_service.append_case_item(
                    case_id,
                    item_type="hit",
                    item_value=hit.howler.id,
                    item_path=child_label,
                )
                added.append(hit.howler.id)
            except Exception:
                skipped.append(hit.howler.id)

        if skipped:
            report.append(
                {
                    "query": f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in skipped)})",
                    "outcome": "skipped",
                    "title": "Skipped Hits",
                    "message": "These hits could not be added (already present or invalid).",
                }
            )

        if added:
            report.append(
                {
                    "query": f"howler.id:({' OR '.join(sanitize_lucene_query(h) for h in added)})",
                    "outcome": "success",
                    "title": "Executed Successfully",
                    "message": "The specified bundle has had all matching hits added.",
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
        "title": "Add to Bundle (Deprecated)",
        "priority": 6,
        "i18nKey": f"operations.{OPERATION_ID}",
        "description": {
            "short": "Add a set of hits to a bundle (deprecated — uses cases)",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [
            {
                "args": {"bundle_id": []},
                "options": {},
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
