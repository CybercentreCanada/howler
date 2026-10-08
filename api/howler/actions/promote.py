from typing import Annotated, Optional

from pydantic import model_validator

import howler.helper.hit as hit_helper
from howler.actions.models import (
    ActionArguments,
    ActionDescription,
    ActionSpecification,
    ActionStep,
    EmptyToNone,
    StepValidationRule,
    one_of,
)
from howler.common.loader import datastore
from howler.datastore.operations import OdmHelper
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import (
    Assessment,
    AssessmentEscalationMap,
    Escalation,
)
from howler.utils.str_utils import sanitize_lucene_query

OPERATION_ID = "promote"
MAX_HITS_BASIC = 10
MAX_HITS_ADVANCED = 1000

ESCALATIONS = [esc for esc in Escalation.list() if esc != Escalation.MISS]
EVIDENCE_ASSESSMENTS = [
    assessment for assessment in Assessment.list() if AssessmentEscalationMap[assessment] == Escalation.EVIDENCE
]

odm_helper = OdmHelper(Hit)


class PromoteArguments(ActionArguments):
    """Arguments of the promote operation."""

    escalation: Annotated[str, one_of("escalation", ESCALATIONS)] = Escalation.ALERT.value
    assessment: Annotated[Optional[str], EmptyToNone, one_of("assessment", Assessment.list)] = None
    rationale: Annotated[Optional[str], EmptyToNone] = None

    @model_validator(mode="after")
    def _validate_assessment(self) -> "PromoteArguments":
        if self.escalation != Escalation.EVIDENCE:
            return self

        if not self.assessment:
            raise ValueError("You must provide an assessment value when promoting to evidence.")

        if self.assessment not in EVIDENCE_ASSESSMENTS:
            raise ValueError(
                f"'{self.assessment}' is not an evidence assessment. Must be one of: {', '.join(EVIDENCE_ASSESSMENTS)}."
            )

        return self


def execute(
    query: str,
    escalation: Escalation = Escalation.ALERT,
    assessment: Optional[str] = None,
    rationale: Optional[str] = None,
    **kwargs,
):
    """Promote a hit.

    Args:
        query (str): The query on which to apply this automation.
        escalation (str, optional): The escalation to promote to. Defaults to "alert".
        assessment (str, optional): Required if escalation is evidence, assessment to apply.
        rationale (str, optional): The optional rationale to apply if promoting to evidence.
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
                    *hit_helper.promote_hit(escalation=escalation),
                    odm_helper.update("howler.assessment", None),
                    odm_helper.update("howler.rationale", None),
                    odm_helper.update("howler.triaged", None),
                ],
            )
        else:
            if not assessment:
                report.append(
                    {
                        "query": query,
                        "outcome": "error",
                        "title": "Missing assessment",
                        "message": "You must provide as assessment value when promoting to evidence.",
                    }
                )
                return report

            ds.hit.update_by_query(query, hit_helper.assess_hit(assessment, rationale))

        report.append(
            {
                "query": query,
                "outcome": "success",
                "title": "Executed Successfully",
                "message": f"Promoted to '{escalation}' for all matching hits.",
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


def specification() -> ActionSpecification:
    """Specify various properties of the action, such as title, descriptions, permissions and input steps."""
    return ActionSpecification(
        id=OPERATION_ID,
        title="Promote Hit",
        i18n_key="operations.promote",
        description=ActionDescription(short="Promote a hit", long=execute.__doc__),
        roles=["automation_basic", "actionrunner_basic"],
        steps=[
            ActionStep(
                args={"escalation": []},
                options={"escalation": ESCALATIONS},
                validation={"warn": StepValidationRule(query="howler.escalation:$escalation")},
            ),
            ActionStep(
                args={"assessment": ["escalation:evidence"], "rationale": ["escalation:evidence"]},
                options={
                    "assessment": {
                        "escalation:evidence": EVIDENCE_ASSESSMENTS,
                        "escalation:alert": [],
                        "escalation:hit": [],
                    }
                },
            ),
        ],
        triggers=VALID_TRIGGERS,
        arguments=PromoteArguments,
    )
