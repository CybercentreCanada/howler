"""Migrate legacy bundle hits to cases."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from howler.datastore.migrations.base import Migration
from howler.services import case_service

if TYPE_CHECKING:
    from howler.datastore.howler_store import HowlerDatastore


logger = logging.getLogger("howler.datastore.migrations")


class BundleToCaseMigration(Migration):
    """Create cases for hits that were previously stored as bundles."""

    migration_id = "bundles-to-cases"
    batch_size = 100

    @staticmethod
    def _related_case(datastore: "HowlerDatastore", bundle_hit: Any):
        """Return an existing case referenced by a legacy bundle hit, if any."""
        related = getattr(bundle_hit.howler, "related", None) or []
        for case_id in related:
            case = datastore.case.get(case_id)
            if case is not None:
                return case

        return None

    @staticmethod
    def _child_ids(datastore: "HowlerDatastore", bundle_hit: Any, bundle_id: str) -> list[str]:
        """Read child IDs from the unmapped legacy field when it is still present."""
        raw_document = datastore.hit.get(bundle_id, as_obj=False)
        if isinstance(raw_document, dict):
            howler_data = raw_document.get("howler", {})
            if isinstance(howler_data, dict):
                child_ids = howler_data.get("hits", [])
                if isinstance(child_ids, (list, tuple, set)):
                    return list(dict.fromkeys(child_id for child_id in child_ids if isinstance(child_id, str)))

        # This fallback supports indexes/models where the legacy field is still
        # exposed by the ODM, while keeping the raw-document path as the source
        # of truth after the bundle fields were removed from the model.
        child_ids = getattr(bundle_hit.howler, "hits", [])
        if isinstance(child_ids, (list, tuple, set)):
            return list(dict.fromkeys(child_id for child_id in child_ids if isinstance(child_id, str)))

        return []

    def _migrate_bundle(self, datastore: "HowlerDatastore", bundle_hit: Any) -> bool:
        bundle_id = bundle_hit.howler.id
        analytic = getattr(bundle_hit.howler, "analytic", None) or "Unknown"
        detection = getattr(bundle_hit.howler, "detection", None) or "Alert"

        case = self._related_case(datastore, bundle_hit)
        if case is not None:
            logger.info("Skipping bundle %s; already has case %s", bundle_id, case.case_id)
            return False

        case = case_service.create_case(
            {
                "title": f"{analytic} - {detection}",
                "summary": f"Migrated from bundle {bundle_id}",
            }
        )
        case_service.append_case_item(case, item_type="hit", item_value=bundle_id)
        changed = True

        child_ids = self._child_ids(datastore, bundle_hit, bundle_id)
        existing_hit_ids = {bundle_id}
        for child_id in child_ids:
            if child_id == bundle_id or child_id in existing_hit_ids:
                continue
            if not datastore.hit.exists(child_id):
                logger.warning("Child hit %s does not exist, skipping", child_id)
                continue

            try:
                case_service.append_case_item(case, item_type="hit", item_value=child_id)
            except Exception as error:  # noqa: BLE001
                logger.warning("Could not add child hit %s: %s", child_id, error)
                continue

            existing_hit_ids.add(child_id)
            changed = True

        if changed:
            case.save()
            logger.info("Migrated bundle %s to case %s (%d children)", bundle_id, case.case_id, len(child_ids))

        return changed

    def run(self, datastore: "HowlerDatastore") -> int:
        """Migrate all legacy bundle hits and return the number changed."""
        affected_documents = 0
        offset = 0

        while True:
            results = datastore.hit.search("howler.is_bundle:true", rows=self.batch_size, offset=offset)
            bundle_hits = results["items"]
            if not bundle_hits:
                break

            offset += len(bundle_hits)
            for bundle_hit in bundle_hits:
                if self._migrate_bundle(datastore, bundle_hit):
                    affected_documents += 1

            datastore.hit.commit()
            datastore.case.commit()

        return affected_documents
