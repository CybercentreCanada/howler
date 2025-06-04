import os

import requests
from howler.common.loader import datastore
from howler.odm.models.action import VALID_TRIGGERS
from howler.odm.models.hit import Hit
from pydash import get

OPERATION_ID = "azure_emit_hash"


def execute(query: str, field: str = "file.hash.sha256", **kwargs):
    "Emit hashes to sentinel"
    result = datastore().hit.search(query, rows=1)
    hits = result["items"]

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
        hash_value = get(hit, field)
        if hash_value:
            requests.post(
                os.environ["SHA256_LOGIC_APP_URL"],  # noqa: F821
                json={
                    "indicator": hash_value,
                    "type": "FileSha256",
                    "description": "Sent from Howler",
                    "action": "alert",
                    "severity": "high",
                },
                timeout=5.0,
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


def specification():
    "Specify various properties of the action, such as title, descriptions, permissions and input steps."
    return {
        "id": OPERATION_ID,
        "title": "Emit sha256 hash to Sentinel",
        "priority": 8,
        "i18nKey": "operations.add_label",
        "description": {
            "short": "Add a label to a hit",
            "long": execute.__doc__,
        },
        "roles": ["automation_basic"],
        "steps": [
            {
                "args": {"field": []},
                "options": {"field": [field for field in Hit.flat_fields().keys() if field.endswith("sha256")]},
            }
        ],
        "triggers": VALID_TRIGGERS,
    }
