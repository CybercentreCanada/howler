import re
from typing import Any

from flask import request
from howler.api import bad_request, created, internal_error, make_subapi_blueprint, ok, unauthorized
from howler.common.exceptions import HowlerException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.services import action_service, analytic_service, hit_service

from sentinel.mapping.sentinel_incident import SentinelIncident
from sentinel.mapping.xdr_alert import XDRAlert

SUB_API = "sentinel"
sentinel_api = make_subapi_blueprint(SUB_API, api_version=1)
sentinel_api._doc = "Ingest Microsoft Sentinel XDR incidents into Howler"

logger = get_logger(__file__)


@generate_swagger_docs()
@sentinel_api.route("/ingest", methods=["POST"])
def ingest_xdr_incident(**kwargs) -> tuple[dict[str, Any], int]:  # noqa C901
    """Ingest a Microsoft Sentinel XDR incident into Howler.

    Variables:
        None

    Arguments:
        None

    Data Block:
        {
            ...Sentinel XDR incident JSON...
        }

    Headers:
        Authorization: API in the format "Basic <key>"

    Result Example (201 Created):
        {
            "success": True,
            "bundle_hit_id": "howler-bundle-id",
            "bundle_id": "sentinel-incident-id",
            "individual_hit_ids": ["alert-hit-id-1", "alert-hit-id-2"],
            "total_hits_created": 3,
            "bundle_size": 2,
            "organization": "Acme Corporation"
        }

    Result Example (200 OK, update):
        {
            "success": True,
            "bundle_hit_id": "howler-bundle-id",
            "bundle_id": "sentinel-incident-id",
            "individual_hit_ids": ["alert-hit-id-1", "alert-hit-id-2"],
            "total_hits_updated": 3,
            "bundle_size": 2,
            "organization": "Acme Corporation",
            "updated": True
        }

    Error Codes:
        400 - Bad request (e.g., missing JSON)
        401 - Unauthorized (invalid API key)
        500 - Internal server error

    Description:
        Receives a Microsoft Sentinel XDR incident as JSON, maps it to Howler format, and creates or updates a bundle
        and its underlying alerts in Howler. Returns details about the created or updated bundle and alerts.
    """
    from sentinel.config import config

    # API Key authentication
    apikey = request.headers.get("Authorization", "Basic ", type=str).split(" ")[1]

    link_key = config.auth.link_key

    if not apikey or apikey != link_key:
        return unauthorized(err="API Key does not match expected value.")

    logger.info("Received authorization header with value %s", re.sub(r"^(.{3}).+(.{3})$", r"\1...\2", apikey))

    xdr_incident = request.json
    if not xdr_incident:
        return bad_request(err="No JSON data provided in request body")

    try:
        # TODO needs to be replaced with actual tenant mapping logic
        tenant_mapping = {"020cd98f-1002-45b7-90ff-69fc68bdd027": "Acme Corporation"}
        incident_mapper = SentinelIncident(tid_mapping=tenant_mapping)
        bundle_hit = incident_mapper.map_incident_to_bundle(xdr_incident)
        if bundle_hit is None:
            return internal_error(err="Failed to map XDR incident to Howler bundle format")

        sentinel_id = xdr_incident.get("id")
        if sentinel_id:
            existing_bundles = datastore().hit.search(f"sentinel.id:{sentinel_id}", as_obj=True)["items"]
            if existing_bundles:
                return _update_existing_incident(existing_bundles[0], xdr_incident, incident_mapper)

        return _create_new_incident(bundle_hit, xdr_incident, tenant_mapping)

    except HowlerException as e:
        logger.exception("Failed to process XDR incident")
        return internal_error(err=f"Failed to process XDR incident: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during XDR incident ingestion")
        return internal_error(err=f"Internal error occurred during ingestion: {str(e)}")


def _update_existing_incident(
    existing_bundle: Any, xdr_incident: dict[str, Any], incident_mapper: SentinelIncident
) -> tuple[dict[str, Any], int]:
    """Update an existing incident and its underlying alerts in Howler.

    Args:
        existing_bundle: The existing Howler bundle object.
        xdr_incident: The incoming XDR incident data.
        incident_mapper: The incident mapper instance.

    Returns:
        Tuple containing response dictionary and HTTP status code.
    """
    new_status = xdr_incident.get("status")
    if new_status:
        existing_bundle.howler.status = incident_mapper.map_sentinel_status_to_howler(new_status)
        datastore().hit.save(existing_bundle.howler.id, existing_bundle)
    for child_id in getattr(existing_bundle.howler, "hits", []):
        child_hit = datastore().hit.get(child_id, as_obj=True)
        if child_hit:
            child_hit.howler.status = incident_mapper.map_sentinel_status_to_howler(new_status)
            datastore().hit.save(child_id, child_hit)
    datastore().hit.commit()
    logger.info("Updated status for existing bundle %s and its child hits", existing_bundle.howler.id)
    return ok(
        {
            "success": True,
            "bundle_hit_id": existing_bundle.howler.id,
            "bundle_id": existing_bundle.sentinel.id if hasattr(existing_bundle, "sentinel") else None,
            "individual_hit_ids": getattr(existing_bundle.howler, "hits", []),
            "total_hits_updated": 1 + len(getattr(existing_bundle.howler, "hits", [])),
            "bundle_size": len(getattr(existing_bundle.howler, "hits", [])),
            "organization": getattr(existing_bundle, "organization", {}).get("name", ""),
            "updated": True,
        }
    )


def _create_alert_hits(alerts: list[dict[str, Any]], tenant_id: str, alert_mapper: XDRAlert) -> list[str]:
    """Create alert hits from the provided alerts and return their IDs.

    Args:
        alerts: List of alert dictionaries.
        tenant_id: The tenant ID string.
        alert_mapper: The alert mapper instance.

    Returns:
        List of created alert hit IDs.
    """
    child_hit_ids = []
    for i, alert in enumerate(alerts):
        try:
            mapped_hit = alert_mapper.map_alert(alert, tenant_id)
            if mapped_hit:
                alert_hit_odm, _ = hit_service.convert_hit(mapped_hit, unique=True, ignore_extra_values=True)
                if alert_hit_odm.event is not None:
                    alert_hit_odm.event.id = alert_hit_odm.howler.id
                logger.info("Creating individual alert hit %s with ID %s", i, alert_hit_odm.howler.id)
                hit_service.create_hit(alert_hit_odm.howler.id, alert_hit_odm, user="system")
                analytic_service.save_from_hit(alert_hit_odm, {"uname": "system"})
                child_hit_ids.append(alert_hit_odm.howler.id)
                logger.debug("Successfully created alert hit %s: %s", i, alert_hit_odm.howler.id)
            else:
                logger.warning("Alert mapper returned None for alert %s: %s", i, alert.get("id", "unknown"))
        except Exception:
            logger.exception("Failed to create individual alert hit %s", i)
            continue
    return child_hit_ids


def _link_child_hits_to_bundle(bundle_odm: Any, child_hit_ids: list[str]) -> None:
    """Link child hits to the bundle and update their bundle references.

    Args:
        bundle_odm: The bundle ODM object.
        child_hit_ids: List of child hit IDs to link.
    """
    for hit_id in bundle_odm.howler.hits:
        child_hit = hit_service.get_hit(hit_id, as_odm=True)

        if child_hit.howler.is_bundle:
            logger.warning("Child hit %s is a bundle - skipping bundle assignment", child_hit.howler.id)
            continue

        new_bundle_list = child_hit.howler.get("bundles", [])
        new_bundle_list.append(bundle_odm.howler.id)
        child_hit.howler.bundles = new_bundle_list
        datastore().hit.save(child_hit.howler.id, child_hit)


def _create_new_incident(
    bundle_hit: dict[str, Any], xdr_incident: dict[str, Any], tenant_mapping: dict[str, str]
) -> tuple[dict[str, Any], int]:
    """Create a new incident bundle and its underlying alerts in Howler.

    Args:
        bundle_hit: The mapped Howler bundle data.
        xdr_incident: The incoming XDR incident data.
        tenant_mapping: The tenant mapping dictionary.

    Returns:
        Tuple containing response dictionary and HTTP status code.
    """
    alerts = xdr_incident.get("alerts", [])
    tenant_id = xdr_incident.get("tenantId", "")
    alert_mapper = XDRAlert(tid_mapping=tenant_mapping)
    child_hit_ids = _create_alert_hits(alerts, tenant_id, alert_mapper)
    try:
        bundle_odm, _ = hit_service.convert_hit(bundle_hit, unique=True)
        # If there are no alerts, do not treat as bundle
        if child_hit_ids:
            bundle_odm.howler.is_bundle = True
            if not hasattr(bundle_odm.howler, "hits") or not isinstance(bundle_odm.howler.hits, list):
                bundle_odm.howler.hits = []
            for hit_id in child_hit_ids:
                if hit_id not in bundle_odm.howler.hits:
                    bundle_odm.howler.hits.append(hit_id)
            bundle_odm.howler.bundle_size = len(bundle_odm.howler.hits)
        else:
            bundle_odm.howler.is_bundle = False
            bundle_odm.howler.hits = []
            bundle_odm.howler.bundle_size = 0

        if bundle_odm.event is not None:
            bundle_odm.event.id = bundle_odm.howler.id

        logger.info("Creating incident hit with ID %s", bundle_odm.howler.id)
        hit_service.create_hit(bundle_odm.howler.id, bundle_odm, user="system")
        analytic_service.save_from_hit(bundle_odm, {"uname": "system"})
        if child_hit_ids:
            _link_child_hits_to_bundle(bundle_odm, child_hit_ids)
        datastore().hit.commit()
        if child_hit_ids:
            action_service.bulk_execute_on_query(f"howler.id:{bundle_odm.howler.id}", user={"uname": "system"})
        logger.info("Successfully completed XDR incident ingestion")
        response_body = {
            "success": True,
            "bundle_hit_id": bundle_odm.howler.id,
            "bundle_id": bundle_hit["howler"].get("xdr.incident.id"),
            "individual_hit_ids": child_hit_ids,
            "total_hits_created": len(child_hit_ids) + 1,
            "bundle_size": len(child_hit_ids),
            "organization": bundle_hit["organization"]["name"],
        }
        return created(response_body)
    except HowlerException as e:
        logger.exception("Failed to create bundle")
        return internal_error(err=f"Failed to create bundle: {str(e)}")
