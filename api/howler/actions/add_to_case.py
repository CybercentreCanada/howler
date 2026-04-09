from typing import Optional

import chevron

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.odm.models.action import VALID_TRIGGERS
from howler.services import case_service

OPERATION_ID = "add_to_case"


def execute(
    query: str,
    case_id: Optional[str] = None,
    path: str = "related",
    title_template: str = "{{howler.analytic}} ({{howler.id}})",
    **kwargs,
):
    """Add matching alerts to a given case.

    Args:
        query (str): The query on which to apply this automation.
        case_id (str): The ID of the case to add the alerts to.
        path (str): The path within the case at which to place the alerts. Defaults to "related".
        title_template (str): A Mustache-compatible template string used to generate each item's
            path suffix (title). The hit's fields are available as template variables.
            Defaults to "{{howler.analytic}} ({{howler.id}})".
    """
    if not case_id:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Missing Case ID",
                "message": "A case_id must be provided.",
            }
        ]

    ds = datastore()

    if ds.case.get(case_id) is None:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Case Not Found",
                "message": f"No case with ID '{case_id}' exists.",
            }
        ]

    hits = ds.hit.search(query, rows=1000)["items"]

    if not hits:
        return [
            {
                "query": query,
                "outcome": "skipped",
                "title": "No Matching Hits",
                "message": "No hits matched the query, so the action was skipped.",
            }
        ]

    report = []
    skipped = []
    added = []

    normalized_path = path.rstrip("/")

    for hit in hits:
        hit_data = hit.as_primitives()
        title = chevron.render(title_template, hit_data)
        item_path = f"{normalized_path}/{title}" if normalized_path else title

        try:
            case_service.append_case_item(
                case_id,
                item_type="hit",
                item_value=hit.howler.id,
                item_path=item_path,
            )
            added.append(hit.howler.id)
        except InvalidDataException as e:
            skipped.append(f"{hit.howler.id}: {e}")
        except NotFoundException as e:
            skipped.append(f"{hit.howler.id}: {e}")
        except Exception as e:
            skipped.append(f"{hit.howler.id}: {e}")

    if added:
        report.append(
            {
                "query": f"howler.id:({' OR '.join(added)})",
                "outcome": "success",
                "title": "Added to Case",
                "message": f"{len(added)} alert(s) successfully added to case '{case_id}'.",
            }
        )

    if skipped:
        report.append(
            {
                "query": query,
                "outcome": "skipped",
                "title": "Skipped Alerts",
                "message": f"{len(skipped)} alert(s) could not be added: {'; '.join(skipped)}",
            }
        )

    return report


def specification():
    """Specify various properties of the action, such as title, descriptions, permissions and input steps."""
    return {
        "id": OPERATION_ID,
        "title": "Add to Case",
        "priority": 9,
        "i18nKey": f"operations.{OPERATION_ID}",
        "description": {
            "short": "Add matching alerts to a case",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [
            {
                "args": {
                    "case_id": [],
                    "path": [],
                    "title_template": [],
                },
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
