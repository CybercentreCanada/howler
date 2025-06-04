import requests
from howler.common.exceptions import HowlerRuntimeError
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import Assessment, HitStatus

from sentinel.utils.tenant_utils import get_token

logger = get_logger(__file__)

OPERATION_ID = "update_defender_xdr_alert"

properties_map = {
    "graph": {
        "status": {
            HitStatus.OPEN: "new",
            HitStatus.IN_PROGRESS: "inProgress",
            HitStatus.ON_HOLD: "inProgress",
            HitStatus.RESOLVED: "resolved",
        },
        "classification": {
            Assessment.AMBIGUOUS: "unknown",
            Assessment.SECURITY: "informationalExpectedActivity",
            Assessment.DEVELOPMENT: "informationalExpectedActivity",
            Assessment.FALSE_POSITIVE: "falsePositive",
            Assessment.LEGITIMATE: "informationalExpectedActivity",
            Assessment.TRIVIAL: "falsePositive",
            Assessment.RECON: "truePositive",
            Assessment.ATTEMPT: "truePositive",
            Assessment.COMPROMISE: "truePositive",
            Assessment.MITIGATED: "truePositive",
            None: "unknown",
        },
        "determination": {
            Assessment.AMBIGUOUS: "unknown",
            Assessment.SECURITY: "securityTesting",
            Assessment.DEVELOPMENT: "confirmedUserActivity",
            Assessment.FALSE_POSITIVE: "other",
            Assessment.LEGITIMATE: "lineOfBusinessApplication",
            Assessment.TRIVIAL: "other",
            Assessment.RECON: "multiStagedAttack",
            Assessment.ATTEMPT: "other",
            Assessment.COMPROMISE: "maliciousUserActivity",
            Assessment.MITIGATED: "other",
            None: "unknown",
        },
    },
}


def execute(query: str, **kwargs):
    """Update Microsoft Defender XDR alert.

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

    for hit in hits:
        try:
            token, credentials = get_token(hit.azure.tenant_id)
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

        token_request_url = f"https://login.microsoftonline.com/{hit.azure.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": credentials["client_id"],
            "client_secret": credentials["client_secret"],
            "scope": "https://graph.microsoft.com/.default",
        }
        response = requests.post(token_request_url, data=data, timeout=5.0)

        if not response.ok:
            logger.warning("Failed to authenticate to Microsoft Graph.")
            report.append(
                {
                    "query": query,
                    "outcome": "error",
                    "title": "Authentication failed",
                    "message": f"Authentication to Microsoft Graph API failed with status code {response.status_code}.",
                }
            )
            continue

        token = response.json()["access_token"]

        # Fetch alert details
        alert_url = f"https://graph.microsoft.com/v1.0/security/alerts_v2/{hit.rule.id}"
        response = requests.get(alert_url, headers={"Authorization": f"Bearer {token}"}, timeout=5.0)
        if not response.ok:
            logger.warning("GET request to Microsoft Graph failed with status code %s.", response.status_code)
            report.append(
                {
                    "query": query,
                    "outcome": "error",
                    "title": "Microsoft Graph API request failed",
                    "message": f"GET request to Microsoft Graph failed with status code {response.status_code}.",
                }
            )
            continue
        alert_data = response.json()

        # Update alert
        if (
            "assessment" in hit.howler
            and hit.howler.assessment in properties_map["graph"]["classification"]
            and hit.howler.assessment in properties_map["graph"]["determination"]
        ):
            classification = properties_map["graph"]["classification"][hit.howler.assessment]
            determination = properties_map["graph"]["determination"][hit.howler.assessment]
        else:
            classification = alert_data["classification"]
            determination = alert_data["determination"]

        status = properties_map["graph"]["status"][hit.howler.status]
        assigned_to = alert_data["assignedTo"]

        data = {
            "assignedTo": assigned_to,
            "classification": classification,
            "determination": determination,
            "status": status,
        }

        response = requests.patch(
            alert_url,
            json=data,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=5.0,
        )
        if not response.ok:
            report.append(
                {
                    "query": query,
                    "outcome": "error",
                    "title": "Microsoft Graph API request failed",
                    "message": f"PATCH request to Microsoft Graph failed with status code {response.status_code}.",
                }
            )

        report.append(
            {
                "query": f"howler.id:{hit.howler.id}",
                "outcome": "success",
                "title": "Alert updated in XDR Defender",
                "message": "Howler has successfuly propagated changes to this alert to XDR Defender.",
            }
        )

    return report


def specification():
    "Update Defender action specification"
    return {
        "id": OPERATION_ID,
        "title": "Update Microsoft Defender XDR alert",
        "priority": 8,
        "description": {
            "short": "Update Microsoft Defender XDR alert",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [{"args": {}, "options": {}, "validation": {}}],
        "triggers": VALID_TRIGGERS,
    }
