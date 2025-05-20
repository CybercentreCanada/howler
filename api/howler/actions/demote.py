from typing import Optional

import howler.helper.hit as hit_helper
from howler.common.loader import datastore
from howler.datastore.operations import OdmHelper
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import (
    Assessment,
    AssessmentEscalationMap,
    Escalation,
    HitStatus,
)
from howler.odm.models.user import User
from howler.utils.str_utils import sanitize_lucene_query

OPERATION_ID = "demote"

ESCALATIONS = [esc for esc in Escalation.list() if esc != Escalation.EVIDENCE]

odm_helper = OdmHelper(Hit)


def execute(
    query: str,
    escalation: Escalation = Escalation.HIT,
    assessment: Optional[str] = None,
    rationale: Optional[str] = None,
    user: Optional[User] = None,
    **kwargs,
):
    """Demote a hit.

    Args:
        query (str): The query on which to apply this automation.
        escalation (str, optional): The escalation to demote to. Defaults to "hit".
        assessment (str, optional): The assessment to apply if demoting to miss. Required if escalation is "miss".
        rationale (str, optional): The optional rationale to apply if demoting to miss.
    """
    if escalation not in ESCALATIONS:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Invalid Escalation",
                "message": f"'{escalation}' is not a valid escalation.",
            }
        ]

    report = []

    ds = datastore()

    skipped_hits = ds.hit.search(
        f"({query}) AND howler.escalation:{sanitize_lucene_query(escalation)}",
        fl="howler.id",
    )["items"]

    if len(skipped_hits) > 0:
        report.append(
            {
                "query": f"howler.id:({' OR '.join(h.howler.id for h in skipped_hits)})",
                "outcome": "skipped",
                "title": "Skipped Hit with Escalation",
                "message": f"These hits already have the escalation {escalation}.",
            }
        )

    try:
        if escalation in [Escalation.HIT, Escalation.ALERT]:
            ds.hit.update_by_query(
                query,
                [
                    *hit_helper.demote_hit(escalation=escalation),
                    odm_helper.update("howler.assessment", None),
                    odm_helper.update("howler.rationale", None),
                ],
            )
        else:
            if not assessment:
                report.append(
                    {
                        "query": query,
                        "outcome": "error",
                        "title": "Missing assessment",
                        "message": "You must provide as assessment value when demoting to miss.",
                    }
                )
                return report

            ds.hit.update_by_query(
                query,
                [
                    *hit_helper.assess_hit(assessment, rationale),
                    odm_helper.update(
                        "howler.assignment",
                        user.get("uname", "automation") if user else "automation",
                    ),
                    odm_helper.update("howler.status", HitStatus.RESOLVED),
                ],
            )

        report.append(
            {
                "query": query,
                "outcome": "success",
                "title": "Executed Successfully",
                "message": f"Demoted to '{escalation}' for all matching hits.",
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
        "title": "Demote Hit",
        "i18nKey": "operations.demote",
        "description": {
            "short": "Demote a hit",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [
            {
                "args": {"escalation": []},
                "options": {"escalation": ESCALATIONS},
                "validation": {"warn": {"query": "howler.escalation:$escalation"}},
            },
            {
                "args": {
                    "assessment": ["escalation:miss"],
                    "rationale": ["escalation:miss"],
                },
                "options": {
                    "assessment": {
                        "escalation:miss": [
                            assessment
                            for assessment in Assessment.list()
                            if AssessmentEscalationMap[assessment] == Escalation.MISS
                        ],
                        "escalation:alert": [],
                        "escalation:hit": [],
                    }
                },
            },
        ],
        "triggers": VALID_TRIGGERS,
    }
