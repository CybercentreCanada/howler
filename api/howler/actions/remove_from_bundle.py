from typing import Optional

from howler.common.exceptions import HowlerException
from howler.common.loader import datastore
from howler.datastore.operations import OdmHelper
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit
from howler.services import hit_service
from howler.utils.str_utils import sanitize_lucene_query

hit_helper = OdmHelper(Hit)

OPERATION_ID = "remove_from_bundle"


def execute(query: str, bundle_id: Optional[str] = None, **kwargs):
    """Remove a set of hits matching the query from the specified bundle.

    Args:
        query (str): The query containing the matching hits
        bundle_id (str): The `howler.id` of the bundle to remove the hits from.
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
        bundle_hit = hit_service.get_hit(bundle_id, as_odm=True)
        if not bundle_hit or not bundle_hit.howler.is_bundle:
            report.append(
                {
                    "query": query,
                    "outcome": "error",
                    "title": "Invalid Bundle",
                    "message": f"Either a hit with ID {bundle_id} does not exist, or it is not a bundle.",
                }
            )
            return report

        ds = datastore()

        skipped_hits = ds.hit.search(
            f"({query}) AND -howler.bundles:{sanitize_lucene_query(bundle_id)}",
            fl="howler.id",
        )["items"]

        if len(skipped_hits) > 0:
            report.append(
                {
                    "query": f"howler.id:({' OR '.join(h.howler.id for h in skipped_hits)})",
                    "outcome": "skipped",
                    "title": "Skipped Hit not in Bundle",
                    "message": "These hits already are not in the bundle.",
                }
            )

        safe_query = f"{query} AND (howler.bundles:{bundle_id})"

        matching_hits = ds.hit.search(safe_query)["items"]
        if len(matching_hits) < 1:
            report.append(
                {
                    "query": safe_query,
                    "outcome": "skipped",
                    "title": "No Matching Hits",
                    "message": "There were no hits matching this query.",
                }
            )
            return report

        ds.hit.update_by_query(
            safe_query,
            [hit_helper.list_remove("howler.bundles", bundle_id)],
        )

        hit_service.update_hit(
            bundle_id,
            [hit_helper.list_remove("howler.hits", h["howler"]["id"]) for h in ds.hit.search(safe_query)["items"]],
        )

        if len(ds.hit.get(bundle_id).howler.hits) < 1:
            hit_service.update_hit(bundle_id, [hit_helper.update("howler.is_bundle", False)])

        report.append(
            {
                "query": query,
                "outcome": "success",
                "title": "Executed Successfully",
                "message": f"Matching hits removed from bundle with id {bundle_id}",
            }
        )
    except HowlerException as e:
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
        "title": "Remove from Bundle",
        "priority": 5,
        "i18nKey": f"operations.{OPERATION_ID}",
        "description": {
            "short": "Remove a set of hits from a bundle",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [
            {
                "args": {"bundle_id": []},
                "options": {},
                "validation": {"error": {"query": "-howler.bundles:$bundle_id"}},
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
