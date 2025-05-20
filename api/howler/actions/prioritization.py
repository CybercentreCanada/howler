from howler.common.loader import datastore
from howler.datastore.operations import OdmHelper
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit

hit_helper = OdmHelper(Hit)

OPERATION_ID = "prioritization"

VALID_FIELDS = ["reliability", "severity", "volume", "confidence", "score"]


def execute(query: str, field: str = "score", value: str = "0.0", **kwargs):
    """Change one of the priorization fields of a hit

    Args:
        query (str): The query to run this action on
        field (str, optional): The field to update. Defaults to "score".
        value (str, optional): The value to set it to. Must be a float in string format. Defaults to "0.0".
    """
    if field not in VALID_FIELDS:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Invalid field",
                "message": (
                    f"Field 'howler.{field}' does not exist. You must pick from one of the following "
                    + f"values: {', '.join(VALID_FIELDS)}."
                ),
            }
        ]

    report = []

    try:
        value: float = float(value)

        datastore().hit.update_by_query(
            query,
            [hit_helper.update(f"howler.{field}", value)],
        )

        report.append(
            {
                "query": query,
                "outcome": "success",
                "title": "Executed Successfully",
                "message": f"Field 'howler.{field}' updated to value '{value}' for all matching hits.",
            }
        )
    except ValueError:
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "Invalid Value",
                "message": f"'{value}' is not a valid value. It must be a float (i.e. 12.34)",
            }
        )
    except Exception as e:
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "Failed to Execute",
                "message": str(e),
            }
        )

    return report


def specification():
    """Specify various properties of the action, such as title, descriptions, permissions and input steps."""
    return {
        "id": OPERATION_ID,
        "title": "Change Prioritization",
        "priority": 10,
        "i18nKey": f"operations.{OPERATION_ID}",
        "description": {
            "short": "Change one of the prioritization fields of a hit",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [
            {
                "args": {"field": [], "value": []},
                "options": {"field": VALID_FIELDS},
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
