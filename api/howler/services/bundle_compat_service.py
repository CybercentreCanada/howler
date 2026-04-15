"""Backward-compatibility shim translating legacy bundle operations into case operations.

All public functions in this module accept the same inputs as the removed bundle
endpoints and return synthesized legacy-shaped responses so that existing callers
continue to work without modification.

.. deprecated::
    Use the ``/api/v2/case/`` endpoints directly.  These shims will be removed
    in a future release.
"""

from typing import Any, Optional

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.odm.models.case import Case, CaseItemTypes
from howler.odm.models.hit import Hit
from howler.services import analytic_service, case_service, hit_service

logger = get_logger(__file__)

DEPRECATION_MESSAGE = (
    "Bundle endpoints are deprecated and will be removed in a future release. Use /api/v2/case/ endpoints instead."
)


def find_case_for_bundle(bundle_hit_id: str) -> Optional[str]:
    """Return the case_id of the case that contains *bundle_hit_id* at its root.

    The lookup relies on the ``howler.related`` back-reference that
    ``case_service.append_case_item`` automatically sets on the hit.
    """
    hit = hit_service.get_hit(bundle_hit_id, as_odm=True)
    if hit is None:
        return None

    ds = datastore()
    for related_id in hit.howler.related:
        case = ds.case.get(related_id)
        if case is not None:
            # Confirm the bundle hit is at the root path (empty string)
            if any(item.value == bundle_hit_id and item.path == "" for item in case.items):
                return case.case_id

    return None


def create_bundle(
    bundle_hit_data: dict[str, Any],
    child_hit_ids: list[str],
    user: str,
) -> dict[str, Any]:
    """Create a hit + case that together represent a legacy bundle.

    1. Ingest the root bundle hit via ``hit_service``.
    2. Create a case titled ``{analytic} - {detection}``.
    3. Append the root hit at path ``""`` (root).
    4. Append each child hit under ``hits/``.

    Returns a synthesized legacy bundle response.
    """
    # Strip bundle-specific fields the ODM no longer recognises
    bundle_hit_data.pop("howler.is_bundle", None)
    bundle_hit_data.pop("howler.hits", None)
    bundle_hit_data.pop("howler.bundle_size", None)
    bundle_hit_data.pop("howler.bundles", None)
    if isinstance(bundle_hit_data.get("howler"), dict):
        bundle_hit_data["howler"].pop("is_bundle", None)
        bundle_hit_data["howler"].pop("hits", None)
        bundle_hit_data["howler"].pop("bundle_size", None)
        bundle_hit_data["howler"].pop("bundles", None)

    odm, warnings = hit_service.convert_hit(bundle_hit_data, unique=True, ignore_extra_values=True)
    hit_service.create_hit(odm.howler.id, odm, user=user)
    analytic_service.save_from_hit(odm, {"uname": user})  # type: ignore[arg-type]

    analytic = odm.howler.analytic or "Unknown"
    detection = odm.howler.detection or "Alert"
    case_title = f"{analytic} - {detection}"

    case = case_service.create_case(
        {"title": case_title, "summary": f"Auto-created case for bundle {odm.howler.id}"},
        user=user,
    )

    # Root hit at empty path
    case_service.append_case_item(
        case.case_id,
        item_type="hit",
        item_value=odm.howler.id,
        item_path="",
    )

    for child_id in child_hit_ids:
        child_hit = hit_service.get_hit(child_id, as_odm=True)
        if child_hit is None:
            logger.warning("Child hit %s does not exist, skipping", child_id)
            continue

        child_label = f"hits/{child_hit.howler.analytic} ({child_id})"
        try:
            case_service.append_case_item(
                case.case_id,
                item_type="hit",
                item_value=child_id,
                item_path=child_label,
            )
        except (InvalidDataException, NotFoundException) as exc:
            logger.warning("Could not add child hit %s to case: %s", child_id, exc)

    datastore().hit.commit()
    datastore().case.commit()

    updated_case: Case | None = datastore().case.get(case.case_id)
    if updated_case is None:
        raise NotFoundException(f"Case {case.case_id} disappeared after creation")

    return synthesize_bundle_response(updated_case, odm, warnings=warnings)


def add_to_bundle(bundle_id: str, hit_ids: list[str]) -> dict[str, Any]:
    """Add hits to an existing bundle (case).

    Finds the case associated with *bundle_id*, then appends each hit under
    ``hits/``.
    """
    case_id = find_case_for_bundle(bundle_id)
    if case_id is None:
        raise NotFoundException(f"No case found for bundle hit {bundle_id}")

    root_hit = hit_service.get_hit(bundle_id, as_odm=True)
    if root_hit is None:
        raise NotFoundException(f"Bundle hit {bundle_id} does not exist")

    for hit_id in hit_ids:
        child_hit = hit_service.get_hit(hit_id, as_odm=True)
        if child_hit is None:
            logger.warning("Hit %s does not exist, skipping", hit_id)
            continue

        child_label = f"hits/{child_hit.howler.analytic} ({hit_id})"
        try:
            case_service.append_case_item(
                case_id,
                item_type="hit",
                item_value=hit_id,
                item_path=child_label,
            )
        except (InvalidDataException, NotFoundException) as exc:
            logger.warning("Could not add hit %s to case: %s", hit_id, exc)

    updated_case: Case | None = datastore().case.get(case_id)
    if updated_case is None:
        raise NotFoundException(f"Case {case_id} not found")

    return synthesize_bundle_response(updated_case, root_hit)


def remove_from_bundle(bundle_id: str, hit_ids: list[str]) -> dict[str, Any]:
    """Remove hits from an existing bundle (case).

    If *hit_ids* is ``["*"]``, all child hits (everything except the root) are
    removed.
    """
    case_id = find_case_for_bundle(bundle_id)
    if case_id is None:
        raise NotFoundException(f"No case found for bundle hit {bundle_id}")

    root_hit = hit_service.get_hit(bundle_id, as_odm=True)
    if root_hit is None:
        raise NotFoundException(f"Bundle hit {bundle_id} does not exist")

    case: Case | None = datastore().case.get(case_id)
    if case is None:
        raise NotFoundException(f"Case {case_id} not found")

    if hit_ids == ["*"]:
        values_to_remove = [item.value for item in case.items if item.value != bundle_id]
    else:
        values_to_remove = [hid for hid in hit_ids if hid != bundle_id]

    if values_to_remove:
        # Filter to only values that actually exist in the case
        existing_values = [item.value for item in case.items]
        values_to_remove = [v for v in values_to_remove if v in existing_values]

        if values_to_remove:
            case_service.remove_case_items(case_id, values_to_remove)

    updated_case: Case | None = datastore().case.get(case_id)
    if updated_case is None:
        raise NotFoundException(f"Case {case_id} not found")

    return synthesize_bundle_response(updated_case, root_hit)


def synthesize_bundle_response(
    case: Case,
    root_hit: Hit,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a legacy bundle-shaped response from a case and its root hit.

    The returned dict looks like the old bundle hit with synthetic
    ``is_bundle``, ``hits``, and ``bundle_size`` fields injected into
    ``howler``.
    """
    child_ids = [
        item.value for item in case.items if item.type == CaseItemTypes.HIT and item.value != root_hit.howler.id
    ]

    hit_data = root_hit.as_primitives()
    hit_data["howler"]["is_bundle"] = True
    hit_data["howler"]["hits"] = child_ids
    hit_data["howler"]["bundle_size"] = len(child_ids)
    hit_data["_deprecation"] = DEPRECATION_MESSAGE
    hit_data["_case_id"] = case.case_id

    if warnings:
        hit_data["_warnings"] = warnings

    return hit_data
