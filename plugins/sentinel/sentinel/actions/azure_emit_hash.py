import functools
import os
from typing import Annotated, Any, Optional

import requests
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
from howler.common.logging import get_logger
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit
from pydantic import model_validator
from pydash import get

from sentinel.utils.hit_types import is_derived_evidence

logger = get_logger(__file__)

OPERATION_ID = "azure_emit_hash"


@functools.cache
def _sha256_fields() -> list[str]:
    return [field for field in Hit.flat_fields().keys() if field.endswith("sha256")]


class AzureEmitHashArguments(ActionArguments):
    """Arguments of the azure_emit_hash operation."""

    url: Annotated[Optional[str], EmptyToNone] = None
    field: Annotated[str, one_of("field", _sha256_fields)] = "file.hash.sha256"

    @model_validator(mode="after")
    def _require_url(self) -> "AzureEmitHashArguments":
        if not self.url and not os.environ.get("SHA256_LOGIC_APP_URL"):
            raise ValueError("url argument cannot be empty.")

        return self


def execute(
    query: str,
    url: Optional[str] = None,
    field: str = "file.hash.sha256",
    **kwargs,
) -> list[dict[str, Any]]:
    """Emit SHA256 hashes to Sentinel.

    Args:
        query (str): The query on which to apply this automation.
        url (str, optional): The Logic App URL to send hashes to.
        field (str): The SHA256 field to emit.
    """
    url = url or os.environ.get("SHA256_LOGIC_APP_URL")
    result = datastore().hit.search(query, rows=1)
    hits = result["items"]

    if not url:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "Action is not properly configured",
                "message": "url argument cannot be empty.",
            }
        ]

    if len(hits) < 1:
        return [
            {
                "query": query,
                "outcome": "error",
                "title": "No alert found",
                "message": "No alerts exist in this query.",
            }
        ]

    report = []
    hit = hits[0]

    if result["total"] > 1:
        report.append(
            {
                "query": f"{query} AND -howler.id:{hit.howler.id}",
                "outcome": "skipped",
                "title": "Action applies to a single alert",
                "message": "This action supports execution against a single alert at once, not bulk execution.",
            }
        )

    for hit in hits:
        if is_derived_evidence(hit):
            report.append(
                {
                    "query": f"howler.id:{hit.howler.id}",
                    "outcome": "skipped",
                    "title": "Derived Sentinel evidence is not an alert",
                    "message": "Evidence child hits are not emitted as independent indicators.",
                }
            )
            continue

        hash_value = get(hit, field)
        if hash_value:
            try:
                requests.post(
                    url,
                    json={
                        "indicator": hash_value,
                        "type": "FileSha256",
                        "description": "Sent from Howler",
                        "action": "alert",
                        "severity": "high",
                    },
                    timeout=5.0,
                )
                report.append(
                    {
                        "query": f"howler.id:{hit.howler.id}",
                        "outcome": "success",
                        "title": "Webhook Triggered",
                        "message": f"Field {field} from alert {hit.howler.id} was successfully sent to url {url}.",
                    }
                )
            except Exception:
                logger.exception("Exception on network call for alert %s", hit.howler.id)
                report.append(
                    {
                        "query": f"howler.id:{hit.howler.id}",
                        "outcome": "error",
                        "title": "Network error on execution",
                        "message": "Alert processing failed due to network errors.",
                    }
                )
        else:
            report.append(
                {
                    "query": f"howler.id:{hit.howler.id}",
                    "outcome": "error",
                    "title": "Hash does not exist on alert",
                    "message": f"The specified alert does not have a valid sha256 hash at path {field}.",
                }
            )

    return report


def specification() -> ActionSpecification:
    """Specify the action's UI metadata and argument validation."""
    return ActionSpecification(
        id=OPERATION_ID,
        title="Emit sha256 hash to Sentinel",
        priority=28,
        description=ActionDescription(short="Emit sha256 hash to Sentinel", long=execute.__doc__),
        roles=["automation_basic"],
        steps=[
            ActionStep(
                args={"url": [], "field": []},
                options={"field": _sha256_fields()},
                validation={"warn": StepValidationRule(query="-_exists_:$field")},
            )
        ],
        triggers=VALID_TRIGGERS,
        arguments=AzureEmitHashArguments,
    )
