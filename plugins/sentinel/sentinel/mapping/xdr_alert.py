import logging
from datetime import datetime
from typing import Any,  Optional
from dateutil import parser
from howler.common.exceptions import NonRecoverableError
from howler.config import config
from sentinel.mapping.xdr_alert_evidence import (
    default_unknown_evidence,
    evidence_function_map
)


# Configure logger
logger = logging.getLogger(__name__)


class XDRAlert:
    """Class to handle mapping of Graph alerts to Howler hits."""

    DEFAULT_CUSTOMER_NAME = "Unknown Customer"

    def __init__(self, tid_mapping: Optional[dict[str, str]] = None, default_customer_name: Optional[str] = None):
        # Allow overriding TID mapping and default customer name
        self.tid_mapping = tid_mapping or {}
        self.default_customer_name = default_customer_name or self.DEFAULT_CUSTOMER_NAME

    def get_customer_name(self, tid: str) -> str:
        """Get customer name from TID, return default if not found."""
        return self.tid_mapping.get(tid, self.default_customer_name)

    def map_severity(self, graph_severity: int) -> int:
        """Map Graph severity to int."""
        severity = {
            3: 75,
            2: 50,
            1: 25,
            0: 10,
        }

        return severity.get(graph_severity, 50)

    def map_status(self, graph_status: int) -> str:
        """Map Graph status to Howler status."""
        status = {
            1: "open",
            2: "in-progress",
            3: "resolved",
        }

        return status.get(graph_status, "open")

    def map_service_source(self, graph_service_source: int) -> str:
        service_map = {
            1: "Microsoft Defender for Endpoint",
            2: "Microsoft Defender for Identity",
            3: "Microsoft Defender for Cloud Apps",
            4: "Microsoft Defender for Office 365",
            5: "Microsoft 365 Defender",
            6: "Azure AD Identity Protection",
            7: "Microsoft App Governance",
            8: "Data Loss Prevention",
            # Yes, 9 should be here, but Graph has reserved it as "UnknownFutureValue"
            10: "Microsoft Defender for Cloud",
            11: "Microsoft Sentinel",
        }
        return service_map.get(graph_service_source, "Unknown Service Source")

    def map_classification(self, graph_classification: str) -> str:
        """Map Graph classification to Howler classification."""
        # Added integer values since the serialization of the graph alert is emitting integers at some point
        classification = {
            "informationalExpectedActivity": "legitimate",
            "falsePositive": "false-positive",
            "truePositive": "compromise",
            "unknown": "ambiguous",
            "TRUEPOSITIVE": "compromise",
            "FALSEPOSITIVE": "false-positive",
            "UNDETERMINED": "ambiguous",
            "SECURITYTEST": "legitimate",
            0: "ambiguous",
            1: "false-positive",
            2: "compromise",
            3: "legitimate",
            4: "ambiguous",  # unknownFutureValue
        }
        # TODO evaluate if we should set this field if new alert
        return classification.get(graph_classification, "ambiguous")

    def map_alert(
        self, graph_alert: dict[str, Any], customer_id: str
    ) -> dict[str, Any] | None:
        """Map a single Graph alert to a Howler hit."""
        # Handle None input gracefully
        if graph_alert is None:
            logger.warning("Received None graph_alert, cannot process")
            return None
            
        customer_name = self.get_customer_name(customer_id)
        if customer_name == self.DEFAULT_CUSTOMER_NAME:
            logger.warning("Customer name not found for tenant ID: %s", graph_alert.get("tenantId", ""))
            return None

        alert_id = graph_alert.get("id", "")
        created = graph_alert.get("createdDateTime", datetime.now().isoformat())
        severity = self.map_severity(graph_alert.get("severity", "medium"))
        status = self.map_status(graph_alert.get("status", "new"))
        display_name = graph_alert.get("title", "MSGraph")

        victim_labels = []

        if graph_alert.get("os"):
            victim_labels.append(graph_alert.get("os"))
        if graph_alert.get("relatedUser", {}).get("userName"):
            victim_labels.append(graph_alert.get("relatedUser", {}).get("userName"))
        if graph_alert.get("computerDnsName"):
            victim_labels.append(graph_alert.get("computerDnsName"))

        # Get assignment and remove "User-" prefix if present
        assigned_to = graph_alert.get("assignedTo", "unassigned")
        if isinstance(assigned_to, str) and assigned_to.startswith("User-"):
            assigned_to = assigned_to[5:]
        
        # Get classification for conditional assessment
        classification = graph_alert.get("classification")

        howler_hit = {
            "timestamp": created,
            "message": graph_alert.get("recommendedActions", ""),
            "organization": {"name": customer_name, "id": customer_id},
            "howler": {
                "analytic": "MSGraph",
                "score": severity / 100.0,
                "status": status,
                "detection": display_name,
                "outline": {
                    "summary": graph_alert.get("description", ""),
                    "indicators": [],
                    "threat": graph_alert.get("threatDisplayName", ""),
                    "target": graph_alert.get("computerDnsName", ""),
                },
                "assignment": assigned_to,
                "escalation": "hit",
                "is_bundle": False,
                "bundle_size": 0,
                "labels": {
                    "insight": [],
                    "mitigation": [],
                    "assignments": [],
                    "campaign": [],
                    "victim": victim_labels,
                    "threat": [],
                    "operation": [],
                    "generic": [],
                },
                "dossier": [
                    {
                        "content": [display_name],
                        "metadata": [graph_alert],
                        "label": {"en": "MSGraph Alert", "fr": "Alerte MSGraph"},
                        "format": "markdown",
                    }
                ],
            },
            "evidence": {"data": []},
            "event": {
                "created": created,
                "kind": "alert",
                "category": ["threat"],
                "type": ["indicator"],
                "severity": severity,
                "action": graph_alert.get("title", ""),
                "provider": self.map_service_source(
                    graph_alert.get("detectionSource", "")
                ),
                "reason": display_name,
                "risk_score": severity / 100.0,
            },
            "rule": {
                "id": alert_id,
            },

        }

        # Add assessment conditionally if classification is not null
        if classification is not None:
            howler_hit["howler"]["assessment"] = self.map_classification(classification)

        # Call mapping helper methods
        self._map_timestamps(graph_alert, howler_hit)
        self._map_graph_host_link(graph_alert, howler_hit)
        self._populate_event_provider(howler_hit)
        self._populate_comments(graph_alert, howler_hit)
        self._map_evidence(graph_alert, howler_hit)

        return howler_hit

    def _map_timestamps(self, graph_alert: dict[str, Any], howler_hit: dict[str, Any]) -> None:
        """Map timestamps from Graph alert to Howler hit."""
        # Add all timestamps from Graph to event object
        for time_field in [
            "createdDateTime",
            "lastUpdateDateTime",
            "firstActivityDateTime",
            "lastActivityDateTime",
        ]:
            if time_field in graph_alert and graph_alert[time_field]:
                try:
                    timestamp = graph_alert[time_field]
                    dt_obj = parser.isoparse(timestamp)
                    # Map specific timestamps to Howler fields
                    if time_field == "createdDateTime":
                        howler_hit["event"]["created"] = dt_obj.isoformat()
                    elif time_field == "firstActivityDateTime":
                        howler_hit["event"]["start"] = dt_obj.isoformat()
                    elif time_field == "lastActivityDateTime":
                        howler_hit["event"]["end"] = dt_obj.isoformat()
                except Exception:
                    logger.warning("Invalid timestamp format for %s: %s", time_field, graph_alert[time_field])


    def _map_graph_host_link(self, graph_alert: dict[str, Any], howler_hit: dict[str, Any]) -> None:
        """Map Graph host link from Graph alert to Howler hit using the same logic as in xdr_incident.py."""
        link: dict[str, str] = {
            "icon": "https://security.microsoft.com/favicon.ico",
            "title": "Open in Microsoft XDR portal",
            "href": graph_alert.get("alertWebUrl", "")
        }
        if graph_alert.get("alertWebUrl"):
            howler_hit["howler"]["links"] = howler_hit["howler"].get("links", [])
            howler_hit["howler"]["links"].append(link)


    def _populate_event_provider(self, howler_hit: dict[str, Any]) -> None:
        """Ensure event.provider is populated."""
        if "provider" not in howler_hit["event"] or not howler_hit["event"]["provider"]:
            howler_hit["event"]["provider"] = "MSGraphAlertCollector"

    def _populate_comments(
        self, graph_alert: dict[str, Any], howler_hit: dict[str, Any]
    ) -> None:
        """Populate comments in the Howler hit."""
        if "comments" in graph_alert and isinstance(graph_alert["comments"], list):
            comments = []

            for comment in graph_alert.get("comments", []):
                values = [
                    comment.get("comment", comment.get("Comment", None)),
                    comment.get("createdBy", comment.get("createdByDisplayName", None)),
                    comment.get("createdTime", comment.get("createdDateTime", None)),
                ]
                if not all(values):
                    logger.info("Invalid comment format in alert: %s", comment)
                    continue
                comments.append(
                    {"value": values[0], "user": f"{values[1]}\n\n---\n\n*(Imported from Microsoft XDR)", "timestamp": values[2]}
                )
            if "comment" not in howler_hit["howler"]:
                howler_hit["howler"]["comment"] = []
            howler_hit["howler"]["comment"].extend(comments)

    def _map_evidence(
        self, graph_alert: dict[str, Any], howler_hit: dict[str, Any]
    ) -> None:
        """Map evidence from Graph alert to Howler hit."""
        if "evidence" not in config.core.plugins:  
            raise NonRecoverableError("Sentinel requires the evidence plugin to be enabled")         
        if "evidence" not in howler_hit or not isinstance(howler_hit["evidence"], list):
            howler_hit["evidence"] = []

        for evidence in graph_alert.get("evidence", []):
            odata = evidence.get("@odata.type", "")
            if not odata:
                continue
            func_name = odata.split(".")[-1]
            evidence_func = evidence_function_map.get(func_name)
            mapped_evidence = None
            if evidence_func:
                mapped_evidence = evidence_func(evidence)
            if not isinstance(mapped_evidence, dict):
                logger.warning("Evidence mapping failed or returned non-dict for type: %s, using default.", odata)
                mapped_evidence = default_unknown_evidence(evidence)
            howler_hit["evidence"].append(mapped_evidence)
