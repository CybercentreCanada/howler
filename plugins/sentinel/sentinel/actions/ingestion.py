from howler.common.loader import datastore
from howler.datastore.operations import OdmHelper
from howler.odm.models.hit import Hit

hit_helper = OdmHelper(Hit)

OPERATION_ID = "sentinel_ingestion"


def execute(query: str, **kwargs):
    """Handle ingestion of howler alerts into sentinel.

    Args:
        query (str): The query specifying alerts to ingest into sentinel.
    """
    report = [
        {
            "query": query,
            "outcome": "skipped",
            "title": "Not Yet Implemented",
            "message": "This functionality hasn't been implemented yet.",
        }
    ]

    ds = datastore()

    skipped_hits = ds.hit.search(
        f"({query}) AND _exists_:sentinel.id",
        fl="howler.id",
    )["items"]

    if len(skipped_hits) > 0:
        report.append(
            {
                "query": f"howler.id:({' OR '.join(h.howler.id for h in skipped_hits)})",
                "outcome": "skipped",
                "title": "Skipped Hit with matching sentinel alert",
                "message": "These hits already have a matching incident in sentinel.",
            }
        )

    print("Ingest alerts into sentinel that match this query:", query)  # noqa: T201

    return report


def specification():
    """Specify various properties of the action, such as title, descriptions, permissions and input steps."""
    return {
        "id": OPERATION_ID,
        "title": "Ingest into Sentinel",
        "priority": 15,
        "description": {
            "short": "Ingest alerts into sentinel",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "triggers": ["create"],
    }
