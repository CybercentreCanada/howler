"""Backward-compatibility shim translating legacy bundle operations into case operations.

All public functions in this module accept the same inputs as the removed bundle
endpoints and return synthesized legacy-shaped responses so that existing callers
continue to work without modification.

.. deprecated::
    Use the ``/api/v2/case/`` endpoints directly.  These shims will be removed
    in a future release.
"""

from typing import Any, Literal

from howler.common.exceptions import HowlerException, InvalidDataException, NotFoundException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.datastore.exceptions import DataStoreException
from howler.odm.models.case import Case, CaseItem, CaseItemTypes
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.services import analytic_service, case_service, hit_service


class BundleConflictException(HowlerException):
    """Raised when a duplicate child is added to a bundle."""


logger = get_logger(__file__)

DEPRECATION_MESSAGE = (
    "Bundle endpoints are deprecated and will be removed in a future release. Use /api/v2/case/ endpoints instead."
)


def find_case_for_bundle(bundle_hit_id: str) -> Case | None:
    """Return the case_id of the case that contains *bundle_hit_id* at its root.

    The lookup relies on the ``howler.related`` back-reference that
    ``case_service.append_case_item`` automatically sets on the hit.
    """
    hit = hit_service.get_hit(bundle_hit_id, as_odm=True)
    if hit is None:
        return None

    ds = datastore()
    for case in ds.case.search(f"case_id:({' OR '.join(hit.howler.related)})")["items"]:
        if any(item.value == bundle_hit_id and item.parent is None for item in case.items):
            return case

    return None


def create_bundle(
    bundle_hit_data: dict[str, Any],
    child_hit_ids: list[str],
    user: User,
    refresh: Literal["true", "false", "wait_for"] | None = "wait_for",
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

    if not child_hit_ids:
        raise InvalidDataException("You did not provide any child hits.")

    odm, warnings = hit_service.convert_hit(bundle_hit_data, unique=True, ignore_extra_values=True)
    hit_service.create_hit(odm.howler.id, odm, user=user.uname, refresh=refresh)
    analytic_service.save_from_hits(odm, user, refresh)

    analytic = odm.howler.analytic or "Unknown"
    detection = odm.howler.detection or "Alert"
    case_title = f"{analytic} - {detection}"

    folder = CaseItem({"type": CaseItemTypes.FOLDER, "name": "hits", "parent": None, "value": ""})
    items: list[CaseItem] = [
        folder,
        case_service.make_case_item(
            item_type="hit",
            item_value=odm.howler.id,
            item_name=f"{odm.howler.analytic} ({odm.howler.id})",
        ),
    ]

    for child_id in child_hit_ids:
        child_hit = hit_service.get_hit(child_id, as_odm=True)
        if child_hit is None:
            continue

        try:
            items.append(
                case_service.make_case_item(
                    item_type="hit",
                    item_value=child_id,
                    item_name=f"{child_hit.howler.analytic} ({child_hit.howler.id})",
                    item_parent=folder.id,
                )
            )
        except (InvalidDataException, NotFoundException, DataStoreException) as exc:  # pragma: no cover
            logger.warning("Could not add child hit %s to case: %s", child_id, exc)

    case = case_service.create_case(
        {
            "title": case_title,
            "summary": f"Auto-created case for bundle {odm.howler.id}",
            "items": [item.as_primitives() for item in items],
        },
        user=user,
        refresh=refresh,
    )

    return synthesize_bundle_response(case, odm, warnings=warnings)


def add_to_bundle(  # noqa: C901
    bundle_id: str, hit_ids: list[str], refresh: Literal["true", "false", "wait_for"] | None = "wait_for"
) -> dict[str, Any]:
    """Add hits to an existing bundle (case).

    Finds the case associated with *bundle_id*, then appends each hit under
    ``hits/``.  If the hit exists but is not yet a bundle (no backing case),
    a case is created on the fly — matching develop's convert-to-bundle
    behaviour.
    """
    root_hit = hit_service.get_hit(bundle_id, as_odm=True)
    if root_hit is None:
        raise NotFoundException(f"Bundle hit {bundle_id} does not exist")

    case = find_case_for_bundle(bundle_id)

    # develop: PUT on a plain hit converts it into a bundle by creating a case
    if case is None:
        analytic = root_hit.howler.analytic or "Unknown"
        detection = root_hit.howler.detection or "Alert"
        case = case_service.create_case(
            {
                "title": f"{analytic} - {detection}",
                "summary": f"Auto-created case for bundle {bundle_id}",
                "items": [{"type": "hit", "value": bundle_id}],
            },
        )

    items: list[CaseItem] = []
    for hit_id in hit_ids:
        items.append(case_service.make_case_item("hit", hit_id))

    if items:
        case = case_service.append_case_items(case.case_id, items, refresh=refresh)

    return synthesize_bundle_response(case, root_hit)


def remove_from_bundle(
    bundle_id: str, hit_ids: list[str], refresh: Literal["true", "false", "wait_for"] | None = "wait_for"
) -> dict[str, Any]:
    """Remove hits from an existing bundle (case).

    If *hit_ids* is ``["*"]``, all child hits (everything except the root) are
    removed.
    """
    root_hit = hit_service.get_hit(bundle_id, as_odm=True)
    if root_hit is None:
        raise NotFoundException(f"Bundle hit {bundle_id} does not exist")

    _case = find_case_for_bundle(bundle_id)
    if _case is None:
        # Hit exists but is not a bundle — match develop's "must be a bundle" error
        raise InvalidDataException("The specified hit must be a bundle.")

    case: Case | None = datastore().case.get(_case.case_id)
    if case is None:
        raise NotFoundException(f"Case {_case.case_id} not found")

    if hit_ids == ["*"]:
        values_to_remove = [item.value for item in case.items if item.value != bundle_id]
    else:
        values_to_remove = [hid for hid in hit_ids if hid != bundle_id]

    if values_to_remove:
        # Filter to only values that actually exist in the case
        existing_values = [item.value for item in case.items]
        values_to_remove = [v for v in values_to_remove if v in existing_values]

        if values_to_remove:
            item_ids_to_remove = [item.id for item in case.items if item.value in values_to_remove]
            # force=True is required when removing all children via wildcard because the "hits/" folder
            # item is included in the removal set and may still have children at removal time.
            use_force = hit_ids == ["*"]
            case_service.remove_case_items(_case, item_ids_to_remove, force=use_force, refresh=refresh)

    updated_case: Case | None = datastore().case.get(_case.case_id)
    if updated_case is None:  # pragma: no cover
        raise NotFoundException(f"Case {_case.case_id} not found")

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
    hit_data["howler"]["is_bundle"] = len(child_ids) > 0
    hit_data["howler"]["hits"] = child_ids
    hit_data["howler"]["bundle_size"] = len(child_ids)
    hit_data["_deprecation"] = DEPRECATION_MESSAGE
    hit_data["_case_id"] = case.case_id

    if warnings:
        hit_data["_warnings"] = warnings

    return hit_data
