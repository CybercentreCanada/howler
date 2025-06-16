"""Sentinel Incident mapper for converting Microsoft Sentinel Incidents to Howler bundles."""

import json
import logging
from typing import Any, Optional

from dateutil import parser

# Use standard logging for now
logger = logging.getLogger(__name__)


class SentinelIncident:
    """Class to handle mapping of Sentiel Incidents to Howler bundles."""

    DEFAULT_CUSTOMER_NAME = "Unknown Customer"

    def __init__(self, tid_mapping: Optional[dict[str, str]] = None):
        """Initialize the Sentiel Incident mapper.

        Args:
            tid_mapping: Mapping of tenant IDs to customer names
        """
        self.tid_mapping = tid_mapping or {}

    # --- Public mapping methods ---

    def map_incident_to_bundle(self, sentinel_incident: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Map an Sentiel Incident to a Howler bundle.

        Args:
            sentinel_incident (dict[str, Any]): The Sentiel Incident data from Microsoft Graph.

        Returns:
            Optional[dict[str, Any]]: Mapped bundle dictionary or None if mapping fails.

        Example:
            >>> mapper = SentinelIncident()
            >>> bundle = mapper.map_incident_to_bundle(sentinel_incident)
        """
        try:
            if not sentinel_incident:
                logger.error("Empty incident data provided")
                return None

            required_fields = ["id", "tenantId", "createdDateTime"]
            for field in required_fields:
                if not sentinel_incident.get(field):
                    logger.warning("Missing required field '%s' in incident: %s", field, sentinel_incident)

            tenant_id: str = sentinel_incident.get("tenantId", "")
            customer_name: str = self.get_customer_name(tenant_id)

            incident_id: Optional[str] = sentinel_incident.get("id")
            status: str = sentinel_incident.get("status", "active")
            display_name: str = sentinel_incident.get("displayName", "")
            created_datetime: Optional[str] = sentinel_incident.get("createdDateTime")
            assigned_to: Optional[str] = sentinel_incident.get("assignedTo")
            classification: str = sentinel_incident.get("classification", "unknown")
            severity: str = sentinel_incident.get("severity", "medium")
            custom_tags: list[str] = sentinel_incident.get("customTags") or []
            system_tags: list[str] = sentinel_incident.get("systemTags") or []
            description: str = sentinel_incident.get("description", "")
            resolving_comment: str = sentinel_incident.get("resolvingComment", "")
            if not isinstance(custom_tags, list):
                logger.warning("customTags is not a list: %s", custom_tags)
                custom_tags = []
            if not isinstance(system_tags, list):
                logger.warning("systemTags is not a list: %s", system_tags)
                system_tags = []

            bundle: dict[str, Any] = {
                "howler": {
                    "status": self.map_sentinel_status_to_howler(status),
                    "detection": display_name,
                    "assignment": self.map_sentinel_user_to_howler(assigned_to),
                    "score": self.map_severity_to_score(severity),
                    "outline.summary": description,
                    "rationale": resolving_comment,
                    "analytic": "Sentinel",
                    "is_bundle": True,
                    "bundle_size": 0,
                    "hits": [],
                    "labels.generic": self._build_labels(custom_tags, system_tags),
                    "data": [json.dumps(sentinel_incident)],
                },
                "organization": {"name": customer_name, "id": tenant_id},
                "sentinel": {
                    "id": incident_id,
                },
                "evidence": {"cloud": {"account": {"id": tenant_id}}},
                "event": {
                    "created": created_datetime,
                    "start": created_datetime,
                    "end": created_datetime,
                },
            }
            self._map_graph_host_link(sentinel_incident, bundle)
            self._map_timestamps(sentinel_incident, bundle)
            # Add assessment conditionally if classification is not null
            if classification is not None:
                bundle["howler"]["assessment"] = self.map_classification(classification)
            logger.info("Successfully mapped Sentinel Incident %s", incident_id)
            return bundle

        except Exception as exc:
            logger.error("Failed to map Sentiel Incident: %s", exc, exc_info=True)
            return None

    def get_customer_name(self, tid: str) -> str:
        """Get customer name from tenant ID, return default if not found.

        Args:
            tid (str): Tenant ID.
        Returns:
            str: Customer name or default.
        """
        return self.tid_mapping.get(tid, self.DEFAULT_CUSTOMER_NAME)

    def map_sentinel_status_to_howler(self, sentinel_status: Optional[str]) -> str:
        """Map Sentinel Incident status to Howler status.

        Args:
            sentinel_status (str | None): Sentinel status string or None.

        Returns:
            str: Howler status string.
        """
        if not isinstance(sentinel_status, str) or not sentinel_status:
            return "open"

        status_mapping: dict[str, str] = {
            "new": "open",
            "active": "in-progress",
            "inProgress": "in-progress",
            "resolved": "resolved",
            "closed": "resolved",
        }
        return status_mapping.get(sentinel_status, "open")

    def map_sentinel_user_to_howler(self, sentinel_user: Optional[str]) -> str:
        """Map Sentinel user assignment to Howler format.

        Args:
            sentinel_user (Optional[str]): Sentinel user assignment.
        Returns:
            str: Howler assignment string.
        """
        if not sentinel_user or sentinel_user in ["null", "None"]:
            return "unassigned"
        return sentinel_user

    def map_severity_to_score(self, severity: str) -> int:
        """Map string severity to numeric score.

        Args:
            severity (str): Severity string.
        Returns:
            int: Numeric score.
        """
        severity_mapping: dict[str, int] = {"low": 25, "medium": 50, "high": 75, "critical": 100}
        return severity_mapping.get(severity.lower() if severity else "medium", 50)

    def map_classification(self, classification: str) -> str:
        """Map Sentinel classification to Howler assessment.

        Args:
            classification (str): Sentinel classification string.
        Returns:
            str: Howler assessment string.
        """
        classification_mapping: dict[str, str] = {
            "unknown": "ambiguous",
            "truePositive": "compromise",
            "falsePositive": "false-positive",
            "informationalExpectedActivity": "legitimate",
            "benignPositive": "legitimate",
        }
        return classification_mapping.get(classification, "")

    # --- Private helper methods ---

    def _map_graph_host_link(self, graph_alert: dict[str, Any], howler_hit: dict[str, Any]) -> None:
        """Map Graph host link from Graph alert to Howler hit.

        Args:
            graph_alert (dict[str, Any]): Graph alert data.
            howler_hit (dict[str, Any]): Howler hit/bundle to update.
        """
        link: dict[str, str] = {
            "icon": "https://security.microsoft.com/favicon.ico",
            "title": "Open in Microsoft Sentinel portal",
            "href": graph_alert.get("incidentWebUrl", ""),
        }
        if graph_alert.get("incidentWebUrl"):
            howler_hit["howler"]["links"] = howler_hit["howler"].get("links", [])
            howler_hit["howler"]["links"].append(link)

    def _map_timestamps(self, graph_alert: dict[str, Any], howler_hit: dict[str, Any]) -> None:
        """Map timestamps from Graph alert to Howler hit.

        Args:
            graph_alert (dict[str, Any]): Graph alert data.
            howler_hit (dict[str, Any]): Howler hit/bundle to update.
        """
        for time_field in [
            "createdDateTime",
            "lastUpdateDateTime",
            "firstActivityDateTime",
            "lastActivityDateTime",
        ]:
            timestamp: Optional[str] = graph_alert.get(time_field)
            if timestamp:
                try:
                    dt_obj = parser.isoparse(timestamp)
                    if time_field == "createdDateTime":
                        howler_hit["event"]["created"] = dt_obj.isoformat()
                    elif time_field == "firstActivityDateTime":
                        howler_hit["event"]["start"] = dt_obj.isoformat()
                    elif time_field == "lastActivityDateTime":
                        howler_hit["event"]["end"] = dt_obj.isoformat()
                except Exception as exc:
                    logger.warning("Invalid timestamp format for %s: %s (%s)", time_field, timestamp, exc)

    def _build_labels(self, custom_tags: list[str], system_tags: list[str]) -> list[str]:
        """Build combined labels from custom and system tags.

        Args:
            custom_tags (list[str]): Custom tags.
            system_tags (list[str]): System tags.
        Returns:
            list[str]: Combined label list.
        """
        labels: list[str] = []
        if custom_tags:
            labels.extend(custom_tags)
        if system_tags:
            labels.extend(["system_%s" % tag for tag in system_tags])
        labels.append("sentinel_incident")
        return labels
