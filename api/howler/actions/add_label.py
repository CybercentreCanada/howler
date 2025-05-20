from typing import Optional

from howler.common.loader import datastore
from howler.datastore.operations import OdmHelper
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import Label
from howler.utils.str_utils import sanitize_lucene_query

hit_helper = OdmHelper(Hit)

OPERATION_ID = "add_label"

CATEGORIES = list(Label.fields().keys())


def execute(query: str, category: str = "generic", label: Optional[str] = None, **kwargs):
    """Add a label to a hit.

    Args:
        query (str): The query on which to apply this automation.
        category (str, optional): The category of label to add. Defaults to "generic".
        label (str): The label content. Defaults to None.
    """
    if category not in CATEGORIES:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Invalid Category",
                "message": f"'{category}' is not a valid category.",
            }
        ]

    if not label:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Invalid Label",
                "message": "Label cannot be empty.",
            }
        ]

    report = []

    ds = datastore()

    skipped_hits = ds.hit.search(
        f"({query}) AND howler.labels.{category}:{sanitize_lucene_query((label))}",
        fl="howler.id",
    )["items"]

    if len(skipped_hits) > 0:
        report.append(
            {
                "query": f"howler.id:({' OR '.join(h.howler.id for h in skipped_hits)})",
                "outcome": "skipped",
                "title": "Skipped Hit with Label",
                "message": f"These hits already have the label {label}.",
            }
        )

    try:
        ds.hit.update_by_query(
            query,
            [hit_helper.list_add(f"howler.labels.{category}", label, if_missing=True)],
        )

        report.append(
            {
                "query": query,
                "outcome": "success",
                "title": "Executed Successfully",
                "message": f"Label '{label}' added to category '{category}' for all matching hits.",
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
        "title": "Add Label",
        "priority": 8,
        "i18nKey": "operations.add_label",
        "description": {
            "short": "Add a label to a hit",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [
            {
                "args": {"category": [], "label": []},
                "options": {"category": CATEGORIES},
                "validation": {"warn": {"query": "howler.labels.$category:$label"}},
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
