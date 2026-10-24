import re
from typing import Any

from flask import request
from howler.api import bad_request, created, internal_error, make_subapi_blueprint, ok, unauthorized
from howler.common.exceptions import HowlerException
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs

from sentinel.services import ingest_service
from sentinel.services.ingest_service import SentinelIngestMappingError

SUB_API = "sentinel"
sentinel_api = make_subapi_blueprint(SUB_API, api_version=1)
sentinel_api._doc = "Ingest Microsoft Sentinel XDR incidents into Howler"  # type: ignore

logger = get_logger(__file__)


@generate_swagger_docs()
@sentinel_api.route("/ingest", methods=["POST"])
def ingest_xdr_incident(**kwargs) -> tuple[dict[str, Any], int]:
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
            "incident_hit_id": "howler-incident-hit-id",
            "incident_id": "sentinel-incident-id",
            "source_alert_hit_ids": ["source-alert-hit-id"],
            "evidence_hit_ids": ["evidence-hit-id"],
            "case_id": "case-id",
            "total_hits_created": 3,
            "organization": "Acme Corporation"
        }

    Error Codes:
        400 - Bad request (e.g., missing JSON or invalid tenant)
        401 - Unauthorized (invalid API key)
        500 - Internal server error

    Description:
        Receives a Microsoft Sentinel XDR incident, creates or updates its
        summary hit, and represents source alerts and their evidence objects as
        hits nested in one Howler case.
    """
    from sentinel.config import config

    apikey = request.headers.get("Authorization", "Basic ", type=str).split(" ")[1]
    if not apikey or apikey != config.auth.link_key:
        return unauthorized(err="API Key does not match expected value.")

    logger.info("Received authorization header with value %s", re.sub(r"^(.{3}).+(.{3})$", r"\1...\2", apikey))

    xdr_incident = request.get_json(silent=True)
    if not isinstance(xdr_incident, dict):
        return bad_request(err="Request body must be a JSON object")

    tenant_id = xdr_incident.get("tenantId")
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        return bad_request(err="Incident must include a non-blank string tenantId")

    tenant_mapping = config.tenant_mapping
    customer_name = tenant_mapping.get(tenant_id)
    if customer_name is None:
        return bad_request(err="Tenant ID is not configured for Sentinel ingestion")
    if not isinstance(customer_name, str) or not customer_name.strip():
        return bad_request(err="Configured organization name for tenant ID must not be blank")

    try:
        response_body, status_code = ingest_service.ingest_incident(xdr_incident, tenant_mapping)
        return created(response_body) if status_code == 201 else ok(response_body)
    except SentinelIngestMappingError as e:
        logger.exception("Failed to map XDR incident")
        return internal_error(err=str(e))
    except HowlerException as e:
        logger.exception("Failed to process XDR incident")
        return internal_error(err=f"Failed to process XDR incident: {str(e)}")
    except Exception as e:
        logger.exception("Unexpected error during XDR incident ingestion")
        return internal_error(err=f"Internal error occurred during ingestion: {str(e)}")
