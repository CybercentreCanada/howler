from howler.common.loader import datastore
from howler.datastore.operations import OdmHelper
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit

hit_helper = OdmHelper(Hit)

OPERATION_ID = "change_field"


def execute(query: str, field: str, value: str, **kwargs):
    """Change one of the fields of a hit

    Args:
        query (str): The query to run this action on
        field (str): The field to update.
        value (str): The value to set it to. Must be a string.
    """
    if field not in Hit.flat_fields():
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Invalid field",
                "message": (f"Field '{field}' does not exist. You must pick a valid entry from the howler index."),
            }
        ]

    report = []

    try:
        datastore().hit.update_by_query(
            query,
            [hit_helper.update(field, value)],
        )

        report.append(
            {
                "query": query,
                "outcome": "success",
                "title": "Executed Successfully",
                "message": f"Field '{field}' updated to value '{value}' for all matching hits.",
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
        "title": "Change Field",
        "i18nKey": f"operations.{OPERATION_ID}",
        "description": {
            "short": "Change one of the fields of a hit",
            "long": execute.__doc__,
        },
        "roles": ["automation_advanced", "admin"],
        "steps": [
            {
                "args": {"field": [], "value": []},
                "options": {"field": list(Hit.flat_fields().keys())},
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
