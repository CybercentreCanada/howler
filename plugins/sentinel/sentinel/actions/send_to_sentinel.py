from typing import Any

import requests
from howler.common.exceptions import HowlerRuntimeError
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit

from sentinel.utils.tenant_utils import get_token

logger = get_logger(__file__)

OPERATION_ID = "send_to_sentinel"


def execute(query: str, **kwargs) -> list[dict[str, Any]]:
    """Send hit to Microsoft Sentinel.

    Args:
        query (str): The query on which to apply this automation.
    """
    report = []
    ds = datastore()

    hits: list[Hit] = ds.hit.search(query, as_obj=True)["items"]
    if not hits:
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "No hits returned by query",
                "message": f"No hits returned by '{query}'",
            }
        )
        return report

    from sentinel.config import config

    for hit in hits:
        if hit.azure and hit.azure.tenant_id:
            tenant_id = hit.azure.tenant_id
        elif hit.organization.id:
            tenant_id = hit.organization.id
        else:
            report.append(
                {
                    "query": f"howler.id:{hit.howler.id}",
                    "outcome": "skipped",
                    "title": "Azure Tenant ID is missing",
                    "message": "This alert does not have a set tenant ID.",
                }
            )
            continue

        try:
            token = get_token(tenant_id, "https://monitor.azure.com/.default")
        except HowlerRuntimeError as err:
            logger.exception("Error on token fetching")
            report.append(
                {
                    "query": f"howler.id:{hit.howler.id}",
                    "outcome": "error",
                    "title": "Invalid Credentials",
                    "message": err.message,
                }
            )
            continue

        ingestor = next((ingestor for ingestor in config.ingestors if ingestor.tenant_id == tenant_id), None)

        if not ingestor:
            report.append(
                {
                    "query": f"howler.id:{hit.howler.id}",
                    "outcome": "error",
                    "title": "Invalid Tenant ID",
                    "message": (
                        f"The tenant ID ({tenant_id}) associated with this alert has not been correctly configured."
                    ),
                }
            )
            continue

        uri = (
            f"https://{ingestor.dce}.ingest.monitor.azure.com/dataCollectionRules/{ingestor.dcr}/"
            + f"streams/{ingestor.table}?api-version=2021-11-01-preview"
        )

        payload = [
            {
                "TimeGenerated": hit.event.ingested.isoformat(),
                "Title": hit.howler.analytic,
                "RawData": {"Hit": hit.as_primitives(), "From": "Howler"},
            }
        ]
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

        response = requests.post(uri, headers=headers, json=payload, timeout=5.0)
        if not response.ok:
            logger.warning(
                "POST request to Azure Monitor failed with status code %s. Content:\n%s",
                response.status_code,
                response.text,
            )
            report.append(
                {
                    "query": f"howler.id:{hit.howler.id}",
                    "outcome": "error",
                    "title": "Azure Monitor API request failed",
                    "message": f"POST request to Azure Monitor failed with status code {response.status_code}.",
                }
            )
            continue

        report.append(
            {
                "query": f"howler.id:{hit.howler.id}",
                "outcome": "success",
                "title": "Alert updated in Sentinel",
                "message": "Howler has successfully propagated changes to this alert to Sentinel.",
            }
        )

    return report


def specification():
    "Send to Sentinel action specification"
    return {
        "id": OPERATION_ID,
        "title": "Send hit to Microsoft Sentinel",
        "priority": 8,
        "description": {
            "short": "Send hit to Microsoft Sentinel",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [{"args": {}, "options": {}, "validation": {}}],
        "triggers": VALID_TRIGGERS,
    }
