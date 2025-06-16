import json
import logging
from datetime import datetime
from typing import Any, Optional

from dateutil import parser
from howler.common.exceptions import NonRecoverableError
from howler.config import config

from sentinel.mapping.xdr_alert_evidence import default_unknown_evidence, evidence_function_map

# Configure logger
logger = logging.getLogger(__name__)


class XDRAlert:
    """Class to handle mapping of Graph alerts to Howler hits."""

    DEFAULT_CUSTOMER_NAME = "Unknown Customer"

    def __init__(self, tid_mapping: Optional[dict[str, str]] = None, default_customer_name: Optional[str] = None):
        """Initialize XDRAlert mapper with optional tenant ID mapping and customer name.

        Args:
            tid_mapping: Dictionary mapping tenant IDs to customer names. Defaults to empty dict.
            default_customer_name: Default customer name when TID mapping lookup fails.
                                  Defaults to DEFAULT_CUSTOMER_NAME.
        """
        # Allow overriding TID mapping and default customer name
        self.tid_mapping = tid_mapping or {}
        self.default_customer_name = default_customer_name or self.DEFAULT_CUSTOMER_NAME

    def get_customer_name(self, tid: str) -> str:
        """Get customer name from tenant ID mapping.

        Args:
            tid: Tenant ID to look up in the mapping.

        Returns:
            Customer name if found in mapping, otherwise returns default customer name.
        """
        return self.tid_mapping.get(tid, self.default_customer_name)

    def map_severity(self, graph_severity: int) -> int:
        """Map Microsoft Graph severity level to Howler severity score.

        Converts Graph API severity integers (0-3) to Howler severity scores (10-75).
        Higher Graph severity values map to higher Howler scores.

        Args:
            graph_severity: Graph API severity level (0=low, 1=medium, 2=high, 3=critical).

        Returns:
            Howler severity score (10, 25, 50, or 75). Defaults to 50 for unknown values.
        """
        severity = {
            3: 75,
            2: 50,
            1: 25,
            0: 10,
        }

        return severity.get(graph_severity, 50)

    def map_status(self, graph_status: int) -> str:
        """Map Microsoft Graph alert status to Howler status string.

        Converts Graph API status integers to Howler-compatible status strings.

        Args:
            graph_status: Graph API status integer (1=new, 2=in-progress, 3=resolved).

        Returns:
            Howler status string ("open", "in-progress", or "resolved").
            Defaults to "open" for unknown values.
        """
        status = {
            1: "open",
            2: "in-progress",
            3: "resolved",
        }

        return status.get(graph_status, "open")

    def map_service_source(self, graph_service_source: int) -> str:
        """Map Microsoft Graph service source ID to human-readable service name.

        Converts Graph API service source integers to descriptive service names
        for various Microsoft Defender and security services.

        Args:
            graph_service_source: Graph API service source integer identifier.

        Returns:
            Human-readable service name string. Returns "Unknown Service Source"
            for unmapped values. Note: ID 9 is reserved by Graph as "UnknownFutureValue".
        """
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
        """Map Microsoft Graph alert classification to Howler assessment classification.

        Converts Graph API classification strings or integers to Howler-compatible
        assessment values. Handles both string and integer formats due to
        serialization variations in Graph alert data.

        Args:
            graph_classification: Graph API classification value (string or int).
                String values include: "informationalExpectedActivity", "falsePositive",
                "truePositive", "unknown", etc.
                Integer values: 0=ambiguous, 1=false-positive, 2=compromise,
                3=legitimate, 4=unknownFutureValue.

        Returns:
            Howler assessment classification ("legitimate", "false-positive",
            "compromise", or "ambiguous"). Defaults to "ambiguous" for unknown values.

        Note:
            TODO: Evaluate if this field should be set for new alerts.
        """
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

    def map_alert(self, graph_alert: dict[str, Any], customer_id: str) -> Optional[dict[str, Any]]:
        """Transform a Microsoft Graph alert into a Howler hit format.

        This is the main mapping function that converts a Graph API alert object
        into the Howler hit format, including all necessary field mappings,
        evidence processing, and metadata extraction.

        Args:
            graph_alert: Dictionary containing the Graph API alert data.
            customer_id: Tenant/customer identifier for organization mapping.

        Returns:
            Dictionary representing a Howler hit with all mapped fields, or None
            if the alert cannot be processed (e.g., None input, unknown customer).

        Note:
            Calls several helper methods to populate specific sections of the hit:
            _map_timestamps, _map_graph_host_link, _populate_event_provider,
            _populate_comments, and _map_evidence.
        """
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
                "data": [json.dumps(graph_alert)],
            },
            "evidence": {"data": []},
            "event": {
                "created": created,
                "kind": "alert",
                "category": ["threat"],
                "type": ["indicator"],
                "severity": severity,
                "action": graph_alert.get("title", ""),
                "provider": self.map_service_source(graph_alert.get("detectionSource", "")),
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
        """Extract and map timestamp fields from Graph alert to Howler hit event fields.

        Processes various timestamp fields from the Graph alert and maps them to
        appropriate Howler event fields. Handles timestamp parsing and validation.

        Args:
            graph_alert: Dictionary containing the Graph API alert data.
            howler_hit: Dictionary representing the Howler hit being constructed.

        Note:
            Maps createdDateTime to event.created, firstActivityDateTime to event.start,
            and lastActivityDateTime to event.end. Invalid timestamps are logged as warnings.
        """
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
        """Add Microsoft XDR portal link to Howler hit for easy navigation.

        Creates a clickable link in the Howler hit that opens the alert in the
        Microsoft XDR portal for detailed investigation.

        Args:
            graph_alert: Dictionary containing the Graph API alert data.
            howler_hit: Dictionary representing the Howler hit being constructed.

        Note:
            Link is only added if alertWebUrl is present in the Graph alert.
            Uses the same logic as implemented in xdr_incident.py for consistency.
        """
        link: dict[str, str] = {
            "icon": "https://security.microsoft.com/favicon.ico",
            "title": "Open in Microsoft XDR portal",
            "href": graph_alert.get("alertWebUrl", ""),
        }
        if graph_alert.get("alertWebUrl"):
            howler_hit["howler"]["links"] = howler_hit["howler"].get("links", [])
            howler_hit["howler"]["links"].append(link)

    def _populate_event_provider(self, howler_hit: dict[str, Any]) -> None:
        """Ensure the event provider field is populated with a default value.

        Sets a default provider name if the event.provider field is missing or empty.
        This ensures consistent provider identification across all processed alerts.

        Args:
            howler_hit: Dictionary representing the Howler hit being constructed.

        Note:
            Defaults to "MSGraphAlertCollector" when no provider is specified.
        """
        if "provider" not in howler_hit["event"] or not howler_hit["event"]["provider"]:
            howler_hit["event"]["provider"] = "MSGraphAlertCollector"

    def _populate_comments(self, graph_alert: dict[str, Any], howler_hit: dict[str, Any]) -> None:
        """Extract and convert Graph alert comments to Howler hit comment format.

        Processes comments from the Graph alert and converts them to the Howler
        comment structure, handling various comment field name variations and
        adding import attribution.

        Args:
            graph_alert: Dictionary containing the Graph API alert data.
            howler_hit: Dictionary representing the Howler hit being constructed.

        Note:
            Handles field name variations (comment/Comment, createdBy/createdByDisplayName,
            createdTime/createdDateTime). Invalid comments are logged and skipped.
            All imported comments are marked with Microsoft XDR attribution.
        """
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
                    {
                        "value": values[0],
                        "user": f"{values[1]}\n\n---\n\n*(Imported from Microsoft XDR)",
                        "timestamp": values[2],
                    }
                )
            if "comment" not in howler_hit["howler"]:
                howler_hit["howler"]["comment"] = []
            howler_hit["howler"]["comment"].extend(comments)

    def _map_evidence(self, graph_alert: dict[str, Any], howler_hit: dict[str, Any]) -> None:
        """Process and map evidence objects from Graph alert to Howler evidence format.

        Extracts evidence items from the Graph alert and converts them using
        specialized evidence mapping functions based on the evidence type.
        Requires the evidence plugin to be enabled in Howler configuration.

        Args:
            graph_alert: Dictionary containing the Graph API alert data.
            howler_hit: Dictionary representing the Howler hit being constructed.

        Raises:
            NonRecoverableError: If the evidence plugin is not enabled in configuration.

        Note:
            Uses evidence type from @odata.type field to determine appropriate
            mapping function. Falls back to default_unknown_evidence for unmapped
            or failed evidence types.
        """
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
