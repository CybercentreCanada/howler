import os
import re
from typing import Any

from flask import request
from howler.api import bad_request, created, make_subapi_blueprint, ok, unauthorized
from howler.common.exceptions import HowlerException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.services import action_service, analytic_service, hit_service

from ..mapping.sentinel_incident import SentinelIncident
from ..mapping.xdr_alert import XDRAlert

SUB_API = "sentinel"
sentinel_api = make_subapi_blueprint(SUB_API, api_version=1)
sentinel_api._doc = "Ingest Microsoft Sentinel XDR incidents into Howler"

logger = get_logger(__file__)

# For testing purposes, replace with actual secret in production
SECRET = os.environ.get("SENTINEL_LINK_KEY", "abcdefghijklmnopqrstuvwxyz1234567890")

if SECRET.startswith("abcdef"):
    logger.warning("Default secret used!")


@generate_swagger_docs()
@sentinel_api.route("/ingest", methods=["POST"])
def ingest_xdr_incident(**kwargs) -> tuple[dict[str, Any], int]:  # noqa C901
    """Ingest a Microsoft Sentinel XDR incident into Howler.

    This endpoint receives an XDR incident as JSON, maps it to Howler format using XDRIncidentMapper,
    and creates a bundle following the same pattern as the create_bundle endpoint.

    Uses API key authentication via Authorization header.

    Variables:
    None

    Data Body:
    XDR incident JSON data to be ingested

    Result Example:
    {
        "success": true,
        "bundle_id": "generated_bundle_id",
        "hit_count": 1
    }
    """
    # TODO this endpoint need to be refactored to make it more readable and maintainable
    apikey = request.headers.get("Authorization", "Basic ", type=str).split(" ")[1]

    if not apikey or apikey != SECRET:
        return unauthorized(err="API Key does not match expected value.")

    logger.info("Received authorization header with value %s", re.sub(r"^(.{3}).+(.{3})$", r"\1...\2", apikey))

    xdr_incident = request.json
    if not xdr_incident:
        return bad_request(err="No JSON data provided in request body")

    logger.info("XDR Incident received")

    try:
        tenant_mapping = {"020cd98f-1002-45b7-90ff-69fc68bdd027": "Acme Corporation"}

        incident_mapper = SentinelIncident(tid_mapping=tenant_mapping)
        bundle_hit = incident_mapper.map_incident_to_bundle(xdr_incident)

        if bundle_hit is None:
            return bad_request(err="Failed to map XDR incident to Howler bundle format")

        sentinel_id = xdr_incident.get("id")
        if sentinel_id:
            existing_bundles = datastore().hit.search(f"sentinel.id:{sentinel_id}", as_obj=True)["items"]
            if existing_bundles:
                existing_bundle = existing_bundles[0]
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

        logger.info("Successfully mapped XDR incident to bundle")

        alerts = xdr_incident.get("alerts", [])
        tenant_id = xdr_incident.get("tenantId", "")

        alert_mapper = XDRAlert(tid_mapping=tenant_mapping)

        # Create individual hits from alerts first
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

        try:
            bundle_odm, _ = hit_service.convert_hit(bundle_hit, unique=True)
            bundle_odm.howler.is_bundle = True

            if not hasattr(bundle_odm.howler, "hits") or not isinstance(bundle_odm.howler.hits, list):
                bundle_odm.howler.hits = []
            for hit_id in child_hit_ids:
                if hit_id not in bundle_odm.howler.hits:
                    bundle_odm.howler.hits.append(hit_id)

            if len(bundle_odm.howler.hits) < 1:
                # TODO figure out how to handle incidens without alerts
                logger.info("No valid child hits were created from the XDR incident alerts")
                return ok("Incident contains no valid alerts to create hits from")

            bundle_odm.howler.bundle_size = len(bundle_odm.howler.hits)

            if bundle_odm.event is not None:
                bundle_odm.event.id = bundle_odm.howler.id

            logger.info("Creating bundle hit with ID %s", bundle_odm.howler.id)
            hit_service.create_hit(bundle_odm.howler.id, bundle_odm, user="system")
            analytic_service.save_from_hit(bundle_odm, {"uname": "system"})

            # Link child hits to bundle (same as create_bundle)
            for hit_id in bundle_odm.howler.hits:
                child_hit = hit_service.get_hit(hit_id, as_odm=True)

                if child_hit.howler.is_bundle:
                    logger.warning("Child hit %s is a bundle - skipping bundle assignment", child_hit.howler.id)
                    continue

                new_bundle_list = child_hit.howler.get("bundles", [])
                new_bundle_list.append(bundle_odm.howler.id)
                child_hit.howler.bundles = new_bundle_list
                datastore().hit.save(child_hit.howler.id, child_hit)

            datastore().hit.commit()
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
            return bad_request(err=f"Failed to create bundle: {str(e)}")

    except HowlerException as e:
        logger.exception("Failed to process XDR incident")
        return bad_request(err=f"Failed to process XDR incident: {str(e)}")

    except Exception as e:
        logger.exception("Unexpected error during XDR incident ingestion")
        return bad_request(err=f"Internal error occurred during ingestion: {str(e)}")
