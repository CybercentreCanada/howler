import inspect
from typing import Optional, cast

from howler.actions import check_hit_limit
from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.helper.workflow import Workflow
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.howler_data import (
    Assessment,
    HitStatusTransition,
    Status,
    Vote,
)
from howler.odm.models.user import User
from howler.services import comms_service, hit_service
from howler.utils.list_utils import flatten_list

OPERATION_ID = "transition"
MAX_HITS_BASIC = 10
MAX_HITS_ADVANCED = 1000
SKIP_CENTRAL_LIMIT = True  # This operation transforms the query, handles limit check locally

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
            entry = f"transition:{str(wf['transition'])}"

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
    # Build effective query with status filter
    effective_query = f"({query}) AND howler.status:{status}"

    # Check hit limit against the effective query (not raw query)
    limit_error = check_hit_limit(effective_query, user, MAX_HITS_BASIC, MAX_HITS_ADVANCED)
    if limit_error:
        return [limit_error]

    is_advanced = "automation_advanced" in user.type or "actionrunner_advanced" in user.type or "admin" in user.type
    rows = MAX_HITS_ADVANCED if is_advanced else MAX_HITS_BASIC
    result = datastore().hit.search(effective_query, rows=rows)

    hits = result["items"]
    ids = [hit["howler"]["id"] for hit in hits]

    if len(hits) < 1:
        return [
            {
                "query": query,
                "outcome": "skipped",
                "title": "No matching hits",
                "message": "No hits matched this query, so the automation skipped.",
            }
        ]

    report = []

    if rows < result["total"]:
        report.append(
            {
                "query": query,
                "outcome": "skipped",
                "title": "Too Many Hits",
                "message": (
                    f"A maximum of {rows} hits can be processed at once, but {result['total']} matched the query."
                ),
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

    try:
        kwargs.pop("refresh", None)
        hit_service.transition_hits(
            hits,
            cast(HitStatusTransition, HitStatusTransition[transition]),
            user,
            refresh="wait_for",
            **kwargs,
        )
    except (InvalidDataException, NotFoundException) as error:
        report.append(
            {
                "query": f"howler.id:({' OR '.join(ids)})",
                "outcome": "error",
                "title": "An error occurred while processing.",
                "message": str(error),
            }
        )
        successful_hit_count = 0
    else:
        successful_hit_count = len(ids)
        report.append(
            {
                "query": f"howler.id:({' OR '.join(ids)})",
                "outcome": "success",
                "title": "Transition Executed Successfully",
                "message": f"The transition {transition} successfully executed on {successful_hit_count} hits.",
            }
        )

    if request_id is not None:
        comms_service.emit(
            "automation",
            {
                "request_id": request_id,
                "processed": len(ids),
                "total": len(ids),
            },
        )

    log.info(
        "Transition %s processed on %s hits (%s successful)",
        transition,
        len(ids),
        successful_hit_count,
    )

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
        "roles": ["automation_basic", "actionrunner_basic"],
        "steps": [
            {
                "args": {"status": []},
                "options": {"status": Status.list()},
                "validation": {"error": {"query": "-howler.status:$status"}},
            },
            {
                "args": {"transition": []},
                "options": {
                    "transition": {f"status:{status}": hit_service.get_transitions(status) for status in Status.list()},
                },
            },
            {
                "args": __parse_workflow_actions(hit_service.get_hit_workflow()),
                "options": {"vote": Vote.list(), "assessment": Assessment.list()},
            },
        ],
        "triggers": [trigger for trigger in VALID_TRIGGERS if trigger != "create"],
    }
