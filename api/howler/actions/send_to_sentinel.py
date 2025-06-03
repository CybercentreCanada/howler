import json
import os
import requests

from howler.common.loader import datastore
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit

OPERATION_ID = "send_to_sentinel"

def execute(query: str, **kwargs):
    """Send hit to Microsoft Sentinel.

    Args:
        query (str): The query on which to apply this automation.
    """

    report = []
    ds = datastore()

    hit: Hit = ds.hit.search(query, as_obj=True)["items"]
    if not hit:
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "Invalid Hit",
                "message": f"Hit with ID {query} does not exist.",
            }
        )
        return report
    if len(hit) > 1:
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "Multiple Hits Found",
                "message": f"Multiple hits found for query {query}. Please refine your query.",
            }
        )
        return report
    hit = hit[0]

    # Get bearer token
    try:
        credentials = json.loads(os.environ['HOWLER_SENTINEL_INGEST_CREDENTIALS'])
    except (KeyError, json.JSONDecodeError):
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "Invalid Credentials",
                "message": "Environment variable HOWLER_GRAPH_ALERT_CREDENTIALS is invalid or not set.",
            }
        )
        return report

    token_request_url = f"https://login.microsoftonline.com/{hit.azure.tenant_id}/oauth2/v2.0/token"
    data = {
        'grant_type': 'client_credentials',
        'client_id': credentials['client_id'],
        'client_secret': credentials['client_secret'],
        'scope': 'https://monitor.azure.com/.default'
    }
    response = requests.post(token_request_url, data=data)
    if response.status_code != 200:
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "Authentication failed",
                "message": f"Authentication to Microsoft Graph API failed with status code {response.status_code}.",
            }
        )
        return report
    token = response.json()["access_token"]

    uri = f"https://{credentials['dce']}.ingest.monitor.azure.com/dataCollectionRules/{credentials['dcr']}/" + \
          f"streams/{credentials['table']}?api-version=2021-11-01-preview"

    payload = [
        {
            "TimeGenerated": hit.event.ingested.isoformat(),
            "Title": hit.howler.analytic,
            "RawData": {"Hit": hit.as_primitives(), "From": "Howler"}
        }
    ]
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    response = requests.post(uri, headers=headers, json=payload)
    if response.status_code != 204:
        report.append(
            {
                "query": query,
                "outcome": "error",
                "title": "Azure RM API request failed",
                "message": f"POST request to Azure RM failed with status code {response.status_code}.",
            }
        )
        return report

    return report

def specification():
    return {
        "id": OPERATION_ID,
        "title": "Send hit to Microsoft Sentinel",
        "priority": 8,
        "i18nKey": "Send hit to Microsoft Sentinel",
        "description": {
            "short": "Send hit to Microsoft Sentinel",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [
            {
                "args": {},
                "options": {},
                "validation": {}
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
