"""
XDR Incident mapper for converting Microsoft Sentinel XDR incidents to Howler bundles.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

# Use standard logging for now
logger = logging.getLogger(__name__)


class XDRIncidentMapper:
    """Class to handle mapping of XDR incidents to Howler bundles."""

    DEFAULT_CUSTOMER_NAME = "Unknown Customer"

    def __init__(self, tid_mapping: Optional[Dict[str, str]] = None):
        """
        Initialize the XDR incident mapper.
        
        Args:
            tid_mapping: Mapping of tenant IDs to customer names
        """
        self.tid_mapping = tid_mapping or {}
    
    def _map_graph_host_link(self, graph_alert: Dict[str, Any], howler_hit: Dict[str, Any]) -> None:
        """Map Graph host link from Graph alert to Howler hit."""
        link = {
            "icon": "https://security.microsoft.com/favicon.ico",
            "title": "Open in Microsoft 365 Defender portal",
            "href": graph_alert.get("incidentWebUrl", "")
        }

        if "incidentWebUrl" in graph_alert:
            howler_hit["howler"]["links"] = howler_hit["howler"].get("links", [])
            howler_hit["howler"]["links"].append(link)

    def get_customer_name(self, tid: str) -> str:
        """Get customer name from tenant ID, return default if not found."""
        return self.tid_mapping.get(tid, self.DEFAULT_CUSTOMER_NAME)

    def map_xdr_status_to_howler(self, xdr_status: str) -> str:
        """Map XDR incident status to Howler status."""
        status_mapping = {
            "new": "open",
            "active": "in-progress", 
            "inProgress": "in-progress",
            "resolved": "resolved",
            "closed": "resolved"
        }
        return status_mapping.get(xdr_status, "open")
    
    def _map_timestamps(self, graph_alert: Dict[str, Any], howler_hit: Dict[str, Any]) -> None:
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
                    # TODO: check if all timestamps are in Zulu
                    if "." in timestamp:
                        timestamp = timestamp.split(".")[0] + "+00:00"

                    timestamp = datetime.fromisoformat(timestamp)

                    # Map specific timestamps to Howler fields
                    if time_field == "createdDateTime":
                        howler_hit["event"]["created"] = timestamp.isoformat()
                    elif time_field == "firstActivityDateTime":
                        howler_hit["event"]["start"] = timestamp.isoformat()
                    elif time_field == "lastActivityDateTime":
                        howler_hit["event"]["end"] = timestamp.isoformat()

                except ValueError:
                    logger.warning("Invalid timestamp format for %s: %s", time_field, graph_alert[time_field])
                    
    def map_xdr_user_to_howler(self, xdr_user: Optional[str]) -> str:
        """Map XDR user assignment to Howler format."""
        if not xdr_user or xdr_user in ["null", "None"]:
            return "unassigned"
        return xdr_user

    def map_severity_to_score(self, severity: str) -> int:
        """Map string severity to numeric score."""
        severity_mapping = {
            "low": 25,
            "medium": 50,
            "high": 75,
            "critical": 100
        }
        return severity_mapping.get(severity.lower() if severity else "medium", 50)

    def map_classification(self, classification: str) -> str:
        """Map XDR classification to Howler assessment."""
        classification_mapping = {
            "unknown": "ambiguous",
            "truePositive": "compromise",
            "falsePositive": "false-positive", 
            "informationalExpectedActivity": "legitimate",
            "benignPositive": "legitimate"
        }
        return classification_mapping.get(classification, "ambiguous")

    def map_incident_to_bundle(self, xdr_incident: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Map an XDR incident to a Howler bundle.
        
        Args:
            xdr_incident: The XDR incident data from Microsoft Graph
            
        Returns:
            Mapped bundle dictionary or None if mapping fails
        """
        try:
            # Validate required fields
            if not xdr_incident:
                logger.error("Empty incident data provided")
                return None

            # Get customer name from tenant ID mapping
            tenant_id = xdr_incident.get("tenantId", "")
            customer_name = self.get_customer_name(tenant_id)

            # Extract basic incident information
            incident_id = xdr_incident.get("id")
            tenant_id = xdr_incident.get("tenantId")
            status = xdr_incident.get("status", "active")
            display_name = xdr_incident.get("displayName", "")
            created_datetime = xdr_incident.get("createdDateTime")
            assigned_to = xdr_incident.get("assignedTo")
            classification = xdr_incident.get("classification", "unknown")
            severity = xdr_incident.get("severity", "medium")
            custom_tags = xdr_incident.get("customTags", [])
            system_tags = xdr_incident.get("systemTags", [])
            description = xdr_incident.get("description", "")
            resolving_comment = xdr_incident.get("resolvingComment", "")
#25/06/02 12:48:32 ERROR howler.api.plugins.sentinel.sentinel.routes.ingest | Failed to create bundle: [hit.howler]: object was created with invalid parameters:
#  last_updated, cloud, incident_web_url, determination, xdr, azure, event
            # Create the bundle structure
            bundle = {
                "howler": {
                    # Core Howler fields
                    "status": self.map_xdr_status_to_howler(status),
                    "detection": display_name,
                    "assignment": self.map_xdr_user_to_howler(assigned_to),
                    "assessment": self.map_classification(classification),
                    "score": self.map_severity_to_score(severity),
                    "outline.summary": description,
                    "rationale": resolving_comment,
                    "analytic": "MSGraph",
                    
                    # Bundle specific fields
                    "is_bundle": True,
                    "bundle_size": 0,  # Will be set by the ingestion process
                    "hits": [],  # Will be populated by the ingestion process
                    
                    # Labels combining custom and system tags
                    "labels.generic": self._build_labels(custom_tags, system_tags),
                },
                "organization": {
                    "name": customer_name, 
                    "id": tenant_id
                },
                "sentinel": {
                    "id": incident_id,

                },
                "evidence": {
                    "cloud" : {
                        "account": {
                            "id": tenant_id
                        }
                    }
            },
                "event": {
                    "created": created_datetime,
                    "start": created_datetime,
                    "end": created_datetime,  # Default to created time
                }
            }
            self._map_graph_host_link(xdr_incident, bundle)
            self._map_timestamps(xdr_incident, bundle)
            logger.info("Successfully mapped XDR incident %s", incident_id)
            return bundle

        except Exception as e:
            logger.error("Failed to map XDR incident: %s", e)
            return None

    def _build_labels(self, custom_tags: List[str], system_tags: List[str]) -> List[str]:
        """Build combined labels from custom and system tags."""
        labels = []
        
        # Add custom tags as-is
        labels.extend(custom_tags)
        
        # Add system tags with prefix
        labels.extend([f"system_{tag}" for tag in system_tags])
        
        # Add XDR identifier
        labels.append("xdr_incident")
        
        return labels

