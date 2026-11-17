from howler.common.loader import datastore
from howler.datastore.howler_store import finalize_models
from howler.datastore.operations import OdmHelper
from howler.models import model_extensions
from howler.models.action import VALID_TRIGGERS
from howler.models.hit import Hit
from howler.models.registry import model_registry
from howler.plugins import get_plugins

OPERATION_ID = "change_field"


def execute(query: str, field: str, value: str, **kwargs):
    """Change one of the fields of a hit

    Args:
        query (str): The query to run this action on
        field (str): The field to update.
        value (str): The value to set it to. Must be a string.
    """
    ds = datastore()
    hit_model = ds.hit.model_class or Hit
    if field not in model_registry.flat_fields(hit_model):
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
        ds.hit.update_by_query(
            query,
            [OdmHelper(hit_model).update(field, value)],
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
    hit_model = (
        model_extensions.finalize(Hit) if model_extensions.is_finalized(Hit) else finalize_models(get_plugins())["hit"]
    )
    return {
        "id": OPERATION_ID,
        "title": "Change Field",
        "i18nKey": f"operations.{OPERATION_ID}",
        "description": {
            "short": "Change one of the fields of a hit",
            "long": execute.__doc__,
        },
        "roles": ["automation_advanced", "actionrunner_advanced", "admin"],
        "steps": [
            {
                "args": {"field": [], "value": []},
                "options": {"field": list(model_registry.flat_fields(hit_model))},
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
