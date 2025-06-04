from howler.common.loader import datastore
from howler.datastore.operations import OdmHelper
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit

hit_helper = OdmHelper(Hit)

OPERATION_ID = "sentinel_synchronization"


def execute(query: str, **kwargs):
    """Handle synchronization of howler alerts into sentinel.

    Args:
        query (str): The query specifying alerts to syncrhonize with sentinel.
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
        f"({query}) AND -_exists_:sentinel.id",
        fl="howler.id",
    )["items"]

    if len(skipped_hits) > 0:
        report.append(
            {
                "query": f"howler.id:({' OR '.join(h.howler.id for h in skipped_hits)})",
                "outcome": "skipped",
                "title": "No matching sentinel alert",
                "message": "These hits do not have a matching incident in sentinel.",
            }
        )

    print("Update alerts into sentinel that match this query:", f"({query}) AND _exists_:sentinel.id")  # noqa: T201

    return report


def specification():
    """Specify various properties of the action, such as title, descriptions, permissions and input steps."""
    return {
        "id": OPERATION_ID,
        "title": "Synchronize with Sentinel",
        "priority": 16,
        "description": {
            "short": "Synchronize alerts with sentinel",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "triggers": [trigger for trigger in VALID_TRIGGERS if trigger != "create"],
    }
