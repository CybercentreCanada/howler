import hashlib
import json
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.config import CLASSIFICATION
from howler.datastore.exceptions import VersionConflictException
from howler.odm.models.case import Case, CaseItem
from howler.odm.models.user import User
from howler.remote.datatypes.lock import Lock as RedisLock
from howler.services import action_service, analytic_service, case_service, hit_service

from sentinel.mapping.sentinel_incident import SentinelIncident
from sentinel.mapping.xdr_alert import XDRAlert

logger = get_logger(__file__)

SYSTEM_USER = User(
    {
        "uname": "system",
        "name": "system",
        "type": ["admin", "user"],
        "classification": CLASSIFICATION.RESTRICTED,
        "password": "__NO_PASSWORD__",
    }
)

_EVIDENCE_LIFECYCLE_FIELDS = {
    "createdDateTime",
    "lastModified",
    "verdict",
    "remediationStatus",
    "remediationStatusDetails",
    "detectionStatus",
}
_DEVICE_IDENTITY_FIELDS = ("mdeDeviceId", "azureAdDeviceId", "deviceId")
_EVIDENCE_IDENTITY_PATHS: dict[str, tuple[str, ...]] = {
    "analyzedMessageEvidence": ("networkMessageId",),
    "cloudApplicationEvidence": ("appId",),
    "containerEvidence": ("containerId", "name"),
    "containerImageEvidence": ("digestImage",),
    "deviceEvidence": ("mdeDeviceId", "azureAdDeviceId", "deviceDnsName", "hostName"),
    "ipEvidence": ("ipAddress",),
    "urlEvidence": ("url",),
    "userEvidence": ("userAccount.azureAdUserId", "userAccount.userPrincipalName", "userAccount.accountName"),
}
_INGEST_LOCK_TIMEOUT_SECONDS = 600
_CASE_RECONCILIATION_ATTEMPTS = 3


class SentinelIngestMappingError(Exception):
    """A Sentinel incident could not be represented as a Howler hit."""


def ingest_incident(xdr_incident: dict[str, Any], tenant_mapping: dict[str, str]) -> tuple[dict[str, Any], int]:
    """Create or reconcile one incident case and all source/evidence hits."""
    tenant_id = xdr_incident["tenantId"]
    incident_mapper = SentinelIncident(tid_mapping=tenant_mapping)
    incident_hit = incident_mapper.map_incident_to_hit(xdr_incident)
    if incident_hit is None:
        raise SentinelIngestMappingError("Failed to map XDR incident to Howler hit format")

    incident_source_id = _source_id(xdr_incident.get("id"))
    identity_payload = {
        key: value
        for key, value in xdr_incident.items()
        if key not in {"alerts", "status", "lastUpdateDateTime", "comments", "customTags", "systemTags"}
    }
    incident_identity = incident_source_id or f"payload:{_content_digest(identity_payload)}"
    root_hit_id = _stable_hit_id(tenant_id, incident_identity, "incident")
    hit_collection = datastore().hit
    lock_name = f"sentinel-ingest:{hit_collection.name}:{root_hit_id}"
    with RedisLock(lock_name, _INGEST_LOCK_TIMEOUT_SECONDS):
        # Direct ID reads bypass Elasticsearch search visibility, but ILM rollover can
        # leave older writes invisible through the collection alias. Flush the complete
        # alias before making the authoritative create-or-update decision.
        _refresh_hit_alias()
        existing_hit = _find_existing_incident(tenant_id, incident_identity)
        if existing_hit is not None:
            return _update_existing_incident(
                existing_hit,
                xdr_incident,
                incident_mapper,
                tenant_id,
                incident_identity,
                incident_source_id,
                tenant_mapping,
            )

        return _create_new_incident(
            incident_hit,
            xdr_incident,
            tenant_id,
            incident_identity,
            incident_source_id,
            tenant_mapping,
        )


def _refresh_hit_alias() -> None:
    """Refresh every physical hit index once, including historical ILM indexes."""
    collection = datastore().hit
    collection.with_retries(collection.datastore.client.indices.refresh, index=collection.name)


def _source_id(value: Any) -> str | None:
    """Return a nonblank external ID as text, if one was supplied."""
    if value is None:
        return None
    identifier = str(value)
    return identifier if identifier.strip() else None


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str)


def _content_digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _evidence_identity(evidence: Any) -> dict[str, Any]:
    """Use a known entity key, falling back to source fields without lifecycle state."""
    if not isinstance(evidence, dict):
        return {"payload": evidence}
    raw_type = evidence.get("@odata.type")
    evidence_type = raw_type.rsplit(".", 1)[-1] if isinstance(raw_type, str) else "unknown"
    if evidence_type in {"fileEvidence", "processEvidence"}:
        composite = _composite_evidence_identity(evidence, evidence_type)
        if composite is not None:
            return composite

    for path in _EVIDENCE_IDENTITY_PATHS.get(evidence_type, ()):
        value: Any = evidence
        for part in path.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if value is not None and value != "":
            return {"type": evidence_type, "entity": {path: value}}
    return {
        "type": evidence_type,
        "payload": {k: v for k, v in evidence.items() if k not in _EVIDENCE_LIFECYCLE_FIELDS},
    }


def _is_populated_identity(value: Any) -> bool:
    return value is not None and (not isinstance(value, str) or bool(value.strip()))


def _composite_evidence_identity(evidence: dict[str, Any], evidence_type: str) -> dict[str, Any] | None:
    """Build stable, order-independent file/process identities from entity context."""
    device = next(
        (
            {field: evidence[field]}
            for field in _DEVICE_IDENTITY_FIELDS
            if field in evidence and _is_populated_identity(evidence[field])
        ),
        None,
    )
    if device is None:
        return None

    if evidence_type == "fileEvidence":
        details = evidence.get("fileDetails")
        if not isinstance(details, dict):
            return None
        file_identity = {
            field: details[field]
            for field in ("filePath", "fileName", "sha256", "sha1")
            if field in details and _is_populated_identity(details[field])
        }
        if not {"filePath", "fileName"}.issubset(file_identity) or not {"sha256", "sha1"}.intersection(file_identity):
            return None
        return {"type": evidence_type, "entity": {"device": device, "file": file_identity}}

    image_file = evidence.get("imageFile")
    process_id = evidence.get("processId")
    process_created = evidence.get("processCreationDateTime")
    if (
        not isinstance(image_file, dict)
        or not _is_populated_identity(process_id)
        or not _is_populated_identity(process_created)
    ):
        return None
    image_identity = {
        field: image_file[field]
        for field in ("filePath", "fileName", "sha256", "sha1")
        if field in image_file and _is_populated_identity(image_file[field])
    }
    if not {"filePath", "fileName"}.issubset(image_identity) or not {"sha256", "sha1"}.intersection(image_identity):
        return None
    return {
        "type": evidence_type,
        "entity": {
            "device": device,
            "process": {"processId": process_id, "processCreationDateTime": process_created},
            "image": image_identity,
        },
    }


def _stable_hit_id(*parts: str) -> str:
    """Create a stable UUID scoped to this tenant and Sentinel record identity."""
    return str(uuid5(NAMESPACE_URL, f"howler-sentinel:{_canonical_json(parts)}"))


def _find_existing_incident(tenant_id: str, incident_identity: str) -> Any | None:
    """Load the tenant-scoped stable incident hit directly, including unrefreshed writes."""
    stable_id = _stable_hit_id(tenant_id, incident_identity, "incident")
    hit = datastore().hit.get(stable_id, as_obj=True)
    if hit is None:
        return None

    sentinel = getattr(hit, "sentinel", None)
    if (
        getattr(sentinel, "incident_id", None) != incident_identity
        or getattr(sentinel, "tenant_id", None) != tenant_id
        or getattr(sentinel, "record_type", None) != "incident"
    ):
        raise ValueError(f"Stable Sentinel incident ID {stable_id} is already used by another record")
    return hit


def _incident_metadata(tenant_id: str, incident_identity: str, source_id: str | None) -> dict[str, Any]:
    return {
        "id": source_id,
        "tenant_id": tenant_id,
        "record_type": "incident",
        "incident_id": incident_identity,
    }


def _convert_mapped_hit(mapped_hit: dict[str, Any], stable_id: str) -> Any:
    hit, _ = hit_service.convert_hit(mapped_hit, unique=False, ignore_extra_values=True)
    hit.howler.id = stable_id
    if hit.event is not None:
        hit.event.id = stable_id
    return hit


def _persist_mapped_hit(hit: Any, stable_id: str) -> Any:
    hit_service.create_hit(stable_id, hit, user="system")
    analytic_service.save_from_hits(hit, SYSTEM_USER)
    return hit


def _create_mapped_hit(mapped_hit: dict[str, Any], stable_id: str) -> Any:
    return _persist_mapped_hit(_convert_mapped_hit(mapped_hit, stable_id), stable_id)


def _create_evidence_hit(mapped_hit: dict[str, Any], stable_id: str) -> Any:  # noqa C901
    """Convert evidence while retaining valid ECS projections if one is malformed."""
    try:
        hit = _convert_mapped_hit(mapped_hit, stable_id)
    except Exception:
        logger.warning("An ECS projection failed for Sentinel evidence %s; validating fields independently", stable_id)
        base_fields = {
            key: value
            for key, value in mapped_hit.items()
            if key in {"timestamp", "classification", "organization", "howler", "event", "sentinel"}
        }
        valid_projections: dict[str, Any] = {}
        for namespace, projection in mapped_hit.items():
            if namespace in base_fields:
                continue

            if isinstance(projection, dict):
                valid_fields = {}
                for field_name, field_value in projection.items():
                    candidate = {**base_fields, namespace: {field_name: field_value}}
                    try:
                        _convert_mapped_hit(candidate, stable_id)
                    except Exception:
                        logger.warning("Skipping invalid Sentinel evidence projection %s.%s", namespace, field_name)
                    else:
                        valid_fields[field_name] = field_value
                if valid_fields:
                    valid_projections[namespace] = valid_fields
            else:
                candidate = {**base_fields, namespace: projection}
                try:
                    _convert_mapped_hit(candidate, stable_id)
                except Exception:
                    logger.warning("Skipping invalid Sentinel evidence projection %s", namespace)
                else:
                    valid_projections[namespace] = projection

        hit = _convert_mapped_hit({**base_fields, **valid_projections}, stable_id)
    return _persist_mapped_hit(hit, stable_id)


def _find_case_for_incident(root_hit: Any) -> tuple[Case | None, str | None]:
    """Find the case and its current datastore version for this Sentinel root hit."""
    ds = datastore()
    for case_id in getattr(root_hit.howler, "related", []):
        case, version = ds.case.get(case_id, as_obj=True, version=True)
        if case is not None:
            return case, version
    return None, None


def _ensure_incident_case(  # noqa: C901
    root_hit: Any, incident_identity: str, tenant_id: str
) -> tuple[Case, str, bool]:
    """Load and repair the incident's case, creating it only when absent.

    Normal replays reuse the existing case for subsequent versioned updates.
    Lookups prefer the root hit's existing association, including legacy case
    IDs, then use the deterministic tenant/incident case ID to recover a case
    whose root back-reference is missing.

    Creation is needed only for the first delivery or recovery when an earlier
    attempt persisted the root hit but not its case, even with no alerts. On a
    version conflict, bounded retries reload current records before deciding
    whether creation is still needed; they never replace an existing case.

    Returns the case, its datastore version, and whether case-item repairs need
    to be persisted by the caller. Root back-reference repairs are saved here.
    """
    ds = datastore()
    root_hit_id = root_hit.howler.id
    stable_case_id = _stable_hit_id(tenant_id, incident_identity, "case")

    for attempt in range(_CASE_RECONCILIATION_ATTEMPTS):
        root_hit, _ = ds.hit.get(root_hit_id, as_obj=True, version=True)
        if root_hit is None:
            raise ValueError("Sentinel incident hit disappeared while its case was being ensured")

        # Preserve a valid pre-existing association (including legacy random case
        # IDs), but do not depend on that back-reference to find a newly-created
        # deterministic case after a partial write.
        case, case_version = _find_case_for_incident(root_hit)
        if case is None:
            case, case_version = ds.case.get(stable_case_id, as_obj=True, version=True)

        if case is None:
            analytic = root_hit.howler.analytic or "Sentinel"
            source_label = root_hit.sentinel.id or incident_identity
            try:
                created_case = case_service.create_case(
                    {
                        "title": f"{analytic} - {root_hit.howler.detection or 'XDR Incident'}",
                        "summary": f"Sentinel incident {source_label}",
                        "classification": root_hit.classification,
                        "items": [{"type": "hit", "value": root_hit_id, "name": analytic}],
                    },
                    user=SYSTEM_USER,
                    case_id=stable_case_id,
                )
            except VersionConflictException:
                if attempt + 1 == _CASE_RECONCILIATION_ATTEMPTS:
                    raise
                continue
            if created_case.case_id != stable_case_id:
                raise ValueError("Sentinel incident case creation did not retain its deterministic ID")
            case, case_version = ds.case.get(stable_case_id, as_obj=True, version=True)
            if case is None:
                raise ValueError("Sentinel incident case disappeared after creation")

        if case_version is None:
            raise ValueError(f"Sentinel incident case {case.case_id} has no datastore version")

        changed = False
        has_root_item = any(item.type == "hit" and item.value == root_hit_id for item in case.items)
        if not has_root_item:
            try:
                case_service.append_case_item(
                    case,
                    item_type="hit",
                    item_value=root_hit_id,
                    item_name=root_hit.howler.analytic or "Sentinel",
                    user=SYSTEM_USER,
                )
            except VersionConflictException:
                if attempt + 1 == _CASE_RECONCILIATION_ATTEMPTS:
                    raise
                continue
            changed = True

        root_hit, root_hit_version = ds.hit.get(root_hit_id, as_obj=True, version=True)
        if root_hit is None or root_hit_version is None:
            raise ValueError("Sentinel incident hit disappeared while its case back-reference was being ensured")
        if case.case_id not in root_hit.howler.related:
            case_service.add_backreference(root_hit, case.case_id, user=SYSTEM_USER)
            try:
                root_hit.save(version=root_hit_version)
            except VersionConflictException:
                if attempt + 1 == _CASE_RECONCILIATION_ATTEMPTS:
                    raise
                continue

        return case, case_version, changed

    raise ValueError("Sentinel incident case could not be reconciled")


def _queue_case_hit(case: Case, pending: list[CaseItem], hit_id: str, name: str, parent_id: str | None) -> None:
    if any(item.type == "hit" and item.value == hit_id for item in case.items) or any(
        item.type == "hit" and item.value == hit_id for item in pending
    ):
        return
    pending.append(CaseItem({"type": "hit", "value": hit_id, "parent": parent_id, "name": name}))


def _record_matches_incident(hit: Any, tenant_id: str, incident_identity: str) -> bool:
    sentinel = getattr(hit, "sentinel", None)
    return (
        getattr(sentinel, "tenant_id", None) == tenant_id
        and getattr(sentinel, "incident_id", None) == incident_identity
        and getattr(sentinel, "record_type", None) in {"alert", "evidence"}
    )


def _case_descendants(case: Case, tenant_id: str, incident_identity: str) -> list[Any]:
    descendants = []
    for item in case.items:
        if item.type != "hit":
            continue
        hit = datastore().hit.get(item.value, as_obj=True)
        if hit is not None and _record_matches_incident(hit, tenant_id, incident_identity):
            descendants.append(hit)
    return descendants


def _case_record_ids(case: Case, tenant_id: str, incident_identity: str) -> tuple[list[str], list[str]]:
    alert_ids: list[str] = []
    evidence_ids: list[str] = []
    for hit in _case_descendants(case, tenant_id, incident_identity):
        record_type = getattr(getattr(hit, "sentinel", None), "record_type", None)
        if record_type == "alert":
            alert_ids.append(hit.howler.id)
        elif record_type == "evidence":
            evidence_ids.append(hit.howler.id)
    return alert_ids, evidence_ids


def _source_alert_metadata(tenant_id: str, incident_identity: str, alert_id: str | None) -> dict[str, Any]:
    return {
        "id": alert_id,
        "tenant_id": tenant_id,
        "record_type": "alert",
        "incident_id": incident_identity,
        "alert_id": alert_id,
    }


def _reconcile_alerts(  # noqa C901
    case: Case,
    alerts: list[Any],
    tenant_id: str,
    incident_identity: str,
    root_hit: Any,
    alert_mapper: XDRAlert,
) -> tuple[list[str], list[str], int]:
    """Create or reconcile source alerts and their Graph evidence hits."""
    alert_hit_ids: list[str] = []
    evidence_hit_ids: list[str] = []
    created_count = 0
    anonymous_alert_counts: dict[str, int] = {}
    pending_case_items: list[CaseItem] = []

    for alert in alerts:
        if not isinstance(alert, dict):
            raise TypeError("Incident alerts must be JSON objects")

        graph_alert_id = _source_id(alert.get("id"))
        identity_payload = {key: value for key, value in alert.items() if key != "evidence"}
        if graph_alert_id:
            alert_identity = graph_alert_id
        else:
            alert_digest = _content_digest(identity_payload)
            occurrence = anonymous_alert_counts.get(alert_digest, 0)
            anonymous_alert_counts[alert_digest] = occurrence + 1
            alert_identity = f"payload:{alert_digest}:{occurrence}"
        alert_hit_id = _stable_hit_id(tenant_id, incident_identity, "alert", alert_identity)
        metadata = _source_alert_metadata(tenant_id, incident_identity, graph_alert_id)

        existing_alert = datastore().hit.get(alert_hit_id, as_obj=True)
        if existing_alert is not None:
            if (
                not _record_matches_incident(existing_alert, tenant_id, incident_identity)
                or getattr(existing_alert.sentinel, "record_type", None) != "alert"
            ):
                raise ValueError(f"Stable Sentinel alert ID {alert_hit_id} is already used by another record")
            alert_hit = existing_alert
        else:
            mapped_alert = alert_mapper.map_alert(alert, tenant_id)
            if mapped_alert is None:
                raise ValueError(f"Failed to map Sentinel alert {graph_alert_id or alert_identity}")
            mapped_alert["classification"] = root_hit.classification
            mapped_alert["sentinel"] = metadata
            alert_hit = _create_mapped_hit(mapped_alert, alert_hit_id)
            created_count += 1

        actual_alert_hit_id = alert_hit.howler.id
        alert_hit_ids.append(actual_alert_hit_id)
        alert_folder = case_service.get_parent_from_path(
            case,
            f"alerts/{actual_alert_hit_id}",
            create_if_missing=True,
            user=SYSTEM_USER,
        )
        _queue_case_hit(
            case,
            pending_case_items,
            actual_alert_hit_id,
            f"{alert_hit.howler.detection or 'Sentinel Alert'} ({actual_alert_hit_id})",
            alert_folder.id if alert_folder else None,
        )

        evidence_values = alert.get("evidence", [])
        if not isinstance(evidence_values, list):
            continue
        duplicate_counts: dict[str, int] = {}
        for evidence in evidence_values:
            external_evidence_id = _source_id(evidence.get("id")) if isinstance(evidence, dict) else None
            evidence_basis = external_evidence_id or _content_digest(_evidence_identity(evidence))
            occurrence = duplicate_counts.get(evidence_basis, 0)
            duplicate_counts[evidence_basis] = occurrence + 1
            evidence_identity = evidence_basis if occurrence == 0 else f"{evidence_basis}:{occurrence}"
            evidence_key = hashlib.sha256(evidence_identity.encode("utf-8")).hexdigest()
            evidence_hit_id = _stable_hit_id(tenant_id, incident_identity, "evidence", alert_identity, evidence_key)
            evidence_metadata = {
                "tenant_id": tenant_id,
                "record_type": "evidence",
                "incident_id": incident_identity,
                "alert_id": graph_alert_id,
                "evidence_id": evidence_key,
            }

            evidence_hit = datastore().hit.get(evidence_hit_id, as_obj=True)
            if evidence_hit is None:
                mapped_evidence = alert_mapper.map_evidence_to_hit(
                    evidence,
                    tenant_id,
                    parent_status=alert_hit.howler.status,
                    classification=root_hit.classification,
                )
                mapped_evidence["sentinel"] = evidence_metadata
                evidence_hit = _create_evidence_hit(mapped_evidence, evidence_hit_id)
                created_count += 1
            elif (
                not _record_matches_incident(evidence_hit, tenant_id, incident_identity)
                or getattr(evidence_hit.sentinel, "record_type", None) != "evidence"
            ):
                raise ValueError(f"Stable Sentinel evidence ID {evidence_hit_id} is already used by another record")

            evidence_hit_ids.append(evidence_hit.howler.id)
            _queue_case_hit(
                case,
                pending_case_items,
                evidence_hit.howler.id,
                f"Evidence ({evidence_hit.howler.id})",
                alert_folder.id if alert_folder else None,
            )

    _refresh_hit_alias()
    if pending_case_items:
        case_service.append_hits(case, pending_case_items, user=SYSTEM_USER, refresh=False)

    return alert_hit_ids, evidence_hit_ids, created_count


def _save_reconciled_case(
    case: Case,
    case_version: str,
    root_hit: Any,
    alerts: Any,
    tenant_id: str,
    incident_identity: str,
    tenant_mapping: dict[str, str],
) -> tuple[Case, bool]:
    """Persist updates to an existing case using its loaded datastore version.

    Both first-delivery ingestion, after case creation, and ordinary replays
    use this update path rather than recreating the case. On a version conflict,
    reload the latest case and reapply missing Sentinel items once, preserving
    concurrent analyst edits and additions. Never fall back to an unconditional
    replacement save.
    """
    try:
        case.save(version=case_version)
        return case, True
    except VersionConflictException:
        case, case_version = datastore().case.get(case.case_id, as_obj=True, version=True)
        if case is None or case_version is None:
            raise ValueError("Sentinel incident case disappeared during replay reconciliation")
        case_items_before = len(case.items)
        if not any(item.type == "hit" and item.value == root_hit.howler.id for item in case.items):
            case_service.append_case_item(
                case,
                item_type="hit",
                item_value=root_hit.howler.id,
                item_name=root_hit.howler.analytic or "Sentinel",
                user=SYSTEM_USER,
            )
        if isinstance(alerts, list):
            _reconcile_alerts(
                case,
                alerts,
                tenant_id,
                incident_identity,
                root_hit,
                XDRAlert(tid_mapping=tenant_mapping),
            )
        changed = len(case.items) != case_items_before
        if changed:
            case.save(version=case_version)
        return case, changed


def _update_existing_incident(
    existing_hit: Any,
    xdr_incident: dict[str, Any],
    incident_mapper: SentinelIncident,
    tenant_id: str,
    incident_identity: str,
    incident_source_id: str | None,
    tenant_mapping: dict[str, str],
) -> tuple[dict[str, Any], int]:
    ds = datastore()
    case, case_version, case_changed = _ensure_incident_case(existing_hit, incident_identity, tenant_id)
    existing_hit = ds.hit.get(existing_hit.howler.id, as_obj=True)
    if existing_hit is None:
        raise ValueError("Sentinel incident hit disappeared while its case was being ensured")
    if case.case_id not in existing_hit.howler.related:
        raise ValueError(f"Sentinel incident hit {existing_hit.howler.id} is missing its case back-reference")

    created_count = 0
    alerts = xdr_incident.get("alerts")
    if isinstance(alerts, list):
        case_items_before = len(case.items)
        _, _, created_count = _reconcile_alerts(
            case,
            alerts,
            tenant_id,
            incident_identity,
            existing_hit,
            XDRAlert(tid_mapping=tenant_mapping),
        )
        case_changed = case_changed or len(case.items) != case_items_before

    # append_hits writes related back-references with refresh disabled. Make all
    # physical indexes visible before reading descendants or applying status.
    _refresh_hit_alias()

    new_status = xdr_incident.get("status")
    updated_count = 0
    if new_status:
        status = incident_mapper.map_sentinel_status_to_howler(new_status)
        existing_hit.howler.status = status
        ds.hit.save(existing_hit.howler.id, existing_hit)
        updated_count = 1
        # Only Sentinel-owned descendants bearing this incident and tenant
        # metadata are managed. Analyst-added case hits are deliberately ignored.
        for descendant in _case_descendants(case, tenant_id, incident_identity):
            descendant.howler.status = status
            ds.hit.save(descendant.howler.id, descendant)
            updated_count += 1

    if case_changed:
        case, case_changed = _save_reconciled_case(
            case,
            case_version,
            existing_hit,
            alerts,
            tenant_id,
            incident_identity,
            tenant_mapping,
        )

    if case_changed:
        ds.case.commit()
    _refresh_hit_alias()
    alert_ids, evidence_ids = _case_record_ids(case, tenant_id, incident_identity)

    response_body = {
        "success": True,
        "incident_hit_id": existing_hit.howler.id,
        "incident_id": incident_source_id,
        "source_alert_hit_ids": alert_ids,
        "evidence_hit_ids": evidence_ids,
        "case_id": case.case_id,
        "total_hits_updated": updated_count,
        "total_hits_created": created_count,
        "organization": existing_hit.organization.name,
        "updated": True,
    }
    return response_body, 200


def _create_new_incident(
    incident_hit_data: dict[str, Any],
    xdr_incident: dict[str, Any],
    tenant_id: str,
    incident_identity: str,
    incident_source_id: str | None,
    tenant_mapping: dict[str, str],
) -> tuple[dict[str, Any], int]:
    incident_hit_data["sentinel"] = _incident_metadata(tenant_id, incident_identity, incident_source_id)
    root_hit_id = _stable_hit_id(tenant_id, incident_identity, "incident")
    root_hit = _create_mapped_hit(incident_hit_data, root_hit_id)
    _refresh_hit_alias()
    case, case_version, _ = _ensure_incident_case(root_hit, incident_identity, tenant_id)

    alerts = xdr_incident.get("alerts", [])
    if not isinstance(alerts, list):
        alerts = []
    _, _, child_hits_created = _reconcile_alerts(
        case,
        alerts,
        tenant_id,
        incident_identity,
        root_hit,
        XDRAlert(tid_mapping=tenant_mapping),
    )
    # Child backlink writes are deferred; refresh their physical indexes before
    # later action searches and any response-side descendant reads.
    _refresh_hit_alias()

    case, _ = _save_reconciled_case(
        case,
        case_version,
        root_hit,
        alerts,
        tenant_id,
        incident_identity,
        tenant_mapping,
    )
    datastore().case.commit()

    if alerts:
        action_service.bulk_execute_on_query(f"howler.id:{root_hit.howler.id}", user=SYSTEM_USER)

    _refresh_hit_alias()
    alert_ids, evidence_ids = _case_record_ids(case, tenant_id, incident_identity)

    logger.info("Successfully completed XDR incident ingestion")
    response_body = {
        "success": True,
        "incident_hit_id": root_hit.howler.id,
        "incident_id": incident_source_id,
        "source_alert_hit_ids": alert_ids,
        "evidence_hit_ids": evidence_ids,
        "case_id": case.case_id,
        "total_hits_created": 1 + child_hits_created,
        "organization": root_hit.organization.name,
    }
    return response_body, 201
