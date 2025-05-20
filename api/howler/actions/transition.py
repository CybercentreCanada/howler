import inspect
from typing import Optional

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.helper.workflow import Workflow, WorkflowException
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.howler_data import (
    Assessment,
    HitStatus,
    HitStatusTransition,
    Vote,
)
from howler.odm.models.user import User
from howler.services import event_service, hit_service
from howler.utils.list_utils import flatten_list

OPERATION_ID = "transition"

log = get_logger(__file__)


def __parse_workflow_actions(workflow: Workflow) -> dict[str, set[str]]:
    """Take in a workflow, and parse the steps and transitions of that workflow into a format understood by the UI"""
    parsed_args: dict[str, set[str]] = {}

    for wf in workflow.transitions.values():
        if wf["transition"] in [
            HitStatusTransition.RE_EVALUATE,
            HitStatusTransition.PROMOTE,
            HitStatusTransition.DEMOTE,
        ]:
            continue

        wf_args = flatten_list(
            [
                [var for var in inspect.getfullargspec(m)[0] if var not in ["kwargs", "hit", "user", "transition"]]
                for m in wf["actions"]
            ]
        )

        for key in wf_args:
            entry = f'transition:{str(wf["transition"])}'

            if key in parsed_args:
                parsed_args[key].add(entry)
            else:
                parsed_args[key] = {entry}

    return parsed_args


def execute(
    query: str,
    status: str,
    transition: str,
    user: User,
    request_id: Optional[str] = None,
    **kwargs,
):
    """Attempt to excute a transition on a hit.

    The hit must be in the specified status in order for the action to execute - otherwise, the automation will filter
    out those options.

    Args:
        query (str): The query on which to apply this automation.
        request_id (str): The id of this automation run. Used to track the progress via websockets.
        status (str): The status from which to transition.
        transition (str): The transition to attempt to execute.
    """
    rows = 1000 if "automation_advanced" in user.type else 10
    hits = datastore().hit.search(f"({query}) AND howler.status:{status}", rows=rows, fl="howler.id")

    ids = [hit.howler.id for hit in hits["items"]]

    if len(ids) < 1:
        return [
            {
                "query": query,
                "outcome": "skipped",
                "title": "No matching hits",
                "message": "No hits matched this query, so the automation skipped.",
            }
        ]

    report = []

    if rows < hits["total"]:
        report.append(
            {
                "query": query,
                "outcome": "skipped",
                "title": "Too Many Hits",
                "message": f"A maximum of {rows} hits can be processed at once, but {hits['total']} matched the query.",
            }
        )

    num_skipped = datastore().hit.search(f"({query}) AND -howler.status:{status}", rows=1)["total"]

    if num_skipped > 0:
        report.append(
            {
                "query": f"({query}) AND -howler.status:{status}",
                "outcome": "skipped",
                "title": f"Skipped {num_skipped} hits",
                "message": f"These hits did not have the correct status ({status}), and were skipped.",
            }
        )

    success_ids = set()
    total_processed = 0
    for hit_id in ids:
        try:
            hit_service.transition_hit(
                hit_id,
                HitStatusTransition[transition],
                user,
                **kwargs,
            )
            success_ids.add(hit_id)
        except (InvalidDataException, NotFoundException, WorkflowException) as e:
            report.append(
                {
                    "query": f"howler.id:{hit_id}",
                    "outcome": "error",
                    "title": "An error occurred while processing.",
                    "message": str(e),
                }
            )

        total_processed += 1
        if total_processed % 10 == 0:
            log.debug("Transition executed on %s hits", total_processed)
            if request_id is not None:
                event_service.emit(
                    "automation",
                    {
                        "request_id": request_id,
                        "processed": total_processed,
                        "total": len(ids),
                    },
                )

    log.info(
        "Transition %s processed on %s hits (%s successful)",
        transition,
        len(ids),
        len(success_ids),
    )

    if len(success_ids) > 0:
        report.append(
            {
                "query": f"howler.id:({' OR '.join(success_ids)})",
                "outcome": "success",
                "title": "Transition Executed Successfully",
                "message": f"The transition {transition} successfully executed on {len(success_ids)} hits.",
            }
        )

    datastore().hit.commit()

    return report


def specification():
    """Specify various properties of the action, such as title, descriptions, permissions and input steps."""
    return {
        "id": OPERATION_ID,
        "title": "Transition",
        "priority": 9,
        "i18nKey": "operations.transition",
        "description": {
            "short": "Transition a hit",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [
            {
                "args": {"status": []},
                "options": {"status": HitStatus.list()},
                "validation": {"error": {"query": "-howler.status:$status"}},
            },
            {
                "args": {"transition": []},
                "options": {
                    "transition": {
                        f"status:{status}": hit_service.get_transitions(status) for status in HitStatus.list()
                    },
                },
            },
            {
                "args": __parse_workflow_actions(hit_service.get_hit_workflow()),
                "options": {"vote": Vote.list(), "assessment": Assessment.list()},
            },
        ],
        "triggers": [trigger for trigger in VALID_TRIGGERS if trigger != "create"],
    }
