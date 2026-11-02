import json
import logging
from datetime import datetime
from typing import Any, Optional

from dateutil import parser

from sentinel.mapping.xdr_alert_evidence import evidence_function_map

# Configure logger
logger = logging.getLogger(__name__)

# The existing Graph evidence projections also contain plugin-specific namespaces. Only
# these top-level Howler/ECS field sets are safe to copy onto a normal hit;
# everything else remains available verbatim in howler.data.
SUPPORTED_EVIDENCE_FIELDS = {
    "aws",
    "azure",
    "cloud",
    "container",
    "email",
    "file",
    "gcp",
    "group",
    "host",
    "network",
    "process",
    "registry",
    "url",
    "user",
    "user_agent",
}


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

    def map_alert(self, graph_alert: dict[str, Any], customer_id: str) -> Optional[dict[str, Any]]:
        """Transform a Microsoft Graph alert into a Howler hit format.

        This is the main mapping function that converts a Graph API alert object
        into the Howler hit format. Evidence is ingested separately as child
        hits by the Sentinel case ingestion route.

        Args:
            graph_alert: Dictionary containing the Graph API alert data.
            customer_id: Tenant/customer identifier for organization mapping.

        Returns:
            Dictionary representing a Howler hit with all mapped fields, or None
            if the alert cannot be processed (e.g., None input, unknown customer).

        Note:
            Calls several helper methods to populate specific sections of the hit:
            _map_timestamps, _map_graph_host_link, _populate_event_provider,
            and _populate_comments.
        """
        # Handle None input gracefully
        if graph_alert is None:
            logger.warning("Received None graph_alert, cannot process")
            return None

        customer_name = self.get_customer_name(customer_id)
        if customer_name == self.DEFAULT_CUSTOMER_NAME and customer_id not in self.tid_mapping:
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

        outline = {
            "summary": graph_alert.get("description", ""),
            "indicators": [],
            "threat": graph_alert.get("threatDisplayName", ""),
        }
        computer_dns_name = graph_alert.get("computerDnsName")
        if isinstance(computer_dns_name, str) and computer_dns_name.strip():
            outline["target"] = computer_dns_name

        howler_hit = {
            "timestamp": created,
            "message": graph_alert.get("recommendedActions", ""),
            "organization": {"name": customer_name, "id": customer_id},
            "howler": {
                "analytic": "MSGraph",
                "score": severity / 100.0,
                "status": status,
                "detection": display_name,
                "outline": outline,
                "assignment": assigned_to,
                "escalation": "hit",
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

        # Call mapping helper methods
        self._map_timestamps(graph_alert, howler_hit)
        self._map_graph_host_link(graph_alert, howler_hit)
        self._populate_event_provider(howler_hit)
        self._populate_comments(graph_alert, howler_hit)

        return howler_hit

    def map_evidence_to_hit(  # noqa C901
        self,
        graph_evidence: Any,
        customer_id: str,
        *,
        parent_status: str,
        classification: str | None = None,
    ) -> dict[str, Any]:
        """Map a Graph evidence value to an ordinary Howler hit.

        Raw evidence is always retained in ``howler.data``. The evidence-field
        projections are used only for supported ECS namespaces; fields
        owned by the removed evidence plugin (or unknown Graph namespaces) are
        intentionally not emitted as top-level hit fields.
        """
        evidence = graph_evidence if isinstance(graph_evidence, dict) else {}
        odata = evidence.get("@odata.type", "")
        evidence_type = odata.split(".")[-1].lstrip("#") if isinstance(odata, str) and odata else "Unknown"
        mapper = evidence_function_map.get(evidence_type)

        mapped_fields: dict[str, Any] = {}
        if mapper is not None:
            try:
                mapped = mapper(evidence)
                if isinstance(mapped, dict):
                    mapped_fields = {key: value for key, value in mapped.items() if key in SUPPORTED_EVIDENCE_FIELDS}
            except Exception:
                logger.warning("Failed to map Sentinel evidence type %s; preserving raw evidence", evidence_type)

        host = mapped_fields.get("host")
        if isinstance(host, dict):
            # Older evidence mappings used lists for these scalar ECS fields.
            if isinstance(host.get("domain"), list):
                host["domain"] = next((value for value in host["domain"] if isinstance(value, str)), None)
            for field in ("ip", "mac"):
                value = host.get(field)
                if isinstance(value, str):
                    host[field] = [value] if value else []
                elif isinstance(value, list):
                    host[field] = [entry for entry in value if isinstance(entry, str)]

        created = evidence.get("createdDateTime")
        if not isinstance(created, str) or not created:
            created = None
        else:
            try:
                created = parser.isoparse(created).isoformat()
            except (TypeError, ValueError):
                logger.warning("Invalid evidence timestamp: %s", created)
                created = None

        raw_payload = json.dumps(graph_evidence, sort_keys=True, ensure_ascii=True)
        howler_hit: dict[str, Any] = {
            "organization": {"name": self.get_customer_name(customer_id), "id": customer_id},
            "howler": {
                "analytic": "Sentinel Evidence",
                "detection": "Sentinel Evidence",
                "status": parent_status,
                "escalation": "hit",
                "outline": {"summary": f"Evidence object from {evidence_type}"},
                "data": [raw_payload],
            },
            "event": {
                "kind": "enrichment",
                "category": ["threat"],
                "type": ["info"],
                "provider": "Microsoft Defender XDR",
            },
            **mapped_fields,
        }
        if created:
            howler_hit["timestamp"] = created
            howler_hit["event"]["created"] = created
        if classification:
            howler_hit["classification"] = classification

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
