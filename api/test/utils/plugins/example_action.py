from typing import Optional

from howler.odm.models.action import VALID_TRIGGERS

OPERATION_ID = "test-plugin-execute"


def execute(query: str, category: str = "generic", label: Optional[str] = None, **kwargs):
    "Example Action"

    return [
        {
            "query": query,
            "outcome": "success",
            "title": "Executed Successfully",
            "message": "Example action ran successfully.",
        }
    ]


def specification():
    """Specify various properties of the action, such as title, descriptions, permissions and input steps."""
    return {
        "id": OPERATION_ID,
        "title": "Example Action",
        "priority": 99,
        "description": {
            "short": "Example Action",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [],
        "triggers": VALID_TRIGGERS,
    }
