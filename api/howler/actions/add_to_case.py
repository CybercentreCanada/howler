import chevron

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import DataStoreException, VersionConflictException
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.user import User
from howler.services import case_service

logger = get_logger(__file__)

OPERATION_ID = "add_to_case"


def execute(  # noqa: C901
    query: str,
    case_id: str | None = None,
    destination: str = "related/{{howler.analytic}} ({{howler.id}})",
    user: User | None = None,
    **kwargs,
):
    """Add matching alerts to a given case.

    Args:
        query (str): The query on which to apply this automation.
        case_id (str): The ID of the case to add the alerts to.
        destination (str): A Mustache-compatible template string for the case path at which each
            alert will be placed, in the form "path/to/parent/name". The hit's fields are
            available as template variables. Defaults to "related/{{howler.analytic}} ({{howler.id}})".
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

    case, version = case_service.get_case(case_id, as_odm=True, version=True, user=user)
    if not case:
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

    for hit in hits:
        rendered_destination = chevron.render(destination, hit.as_primitives())
        try:
            item_path, name = rendered_destination.rsplit("/", maxsplit=1)
        except ValueError:
            item_path = None
            name = rendered_destination

        try:
            parent = case_service.get_parent_from_path(case, item_path, create_if_missing=True, user=user)

            case_service.append_case_item(
                case,
                item_type="hit",
                item_value=hit.howler.id,
                item_name=name,
                item_parent=parent.id if parent else None,
                user=user,
            )
            added.append(hit.howler.id)
        except InvalidDataException as e:
            skipped.append(f"{hit.howler.id}: {e}")
        except NotFoundException as e:  # pragma: no cover
            skipped.append(f"{hit.howler.id}: {e}")
        except Exception as e:  # pragma: no cover
            skipped.append(f"{hit.howler.id}: {e}")

    try:
        case.save(refresh="wait_for", version=version)
    except (DataStoreException, VersionConflictException):
        logger.exception("Exception on save:")
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Case update failed",
                "message": "There was a datastore error or version conflict when updating the case.",
            }
        ]

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
                    "destination": [],
                },
                "options": {},
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
