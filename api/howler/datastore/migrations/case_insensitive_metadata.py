from __future__ import annotations

import re
from typing import TYPE_CHECKING

from elasticsearch.exceptions import NotFoundError

from howler.common.loader import DATASTORE_INDEX_PREFIX
from howler.datastore.collection import TRANSPORT_TIMEOUT
from howler.datastore.exceptions import DataStoreException
from howler.datastore.migrations.base import Migration

if TYPE_CHECKING:
    from howler.datastore.howler_store import HowlerDatastore


COLLECTION_NAMES = ("view", "action", "dossier", "template", "overview")


class CaseInsensitiveMetadataMigration(Migration):
    """Reindex user-facing metadata fields with case-insensitive keyword mappings."""

    migration_id = "metadata-case-insensitive-search"

    def _leftover_reindex_indices(self, datastore: HowlerDatastore) -> list[str]:
        """Find temporary indexes before lazy collection access can recreate a missing source."""
        indices = datastore.ds.client.indices
        leftovers: set[str] = set()

        for collection_name in COLLECTION_NAMES:
            index_prefix = f"{DATASTORE_INDEX_PREFIX}-{collection_name}"
            pattern = f"{index_prefix}*__reindex"
            try:
                matching_indices = indices.get(
                    index=pattern,
                    allow_no_indices=True,
                    ignore_unavailable=True,
                )
            except NotFoundError:
                continue

            expected_name = re.compile(rf"^{re.escape(index_prefix)}(?:_hot|-\d{{6}})__reindex$")
            leftovers.update(index for index in matching_indices if expected_name.fullmatch(index))

        return sorted(leftovers)

    def preflight(self, datastore: HowlerDatastore) -> None:
        """Refuse interrupted temporary indexes before any selected migration initializes a collection."""
        leftovers = self._leftover_reindex_indices(datastore)
        if leftovers:
            indexes = ", ".join(leftovers)
            raise DataStoreException(
                "Found leftover temporary reindex index(es): "
                f"{indexes}. Refusing to initialize collections or continue. Confirm that no reindex is still "
                "active; wait for it to finish or investigate before cleanup. If the source still exists, use the "
                "existing reindex cleanup operation to reconcile the index. If a source is missing, manually recover "
                "the temporary index before retrying this migration. No temporary index was deleted."
            )

    def run(self, datastore: HowlerDatastore) -> int:
        """Reindex the five metadata collections without permitting document loss."""
        # Keep a second read-only guard for direct run() callers and state changes after batch preflight.
        self.preflight(datastore)

        affected_documents = 0
        for collection_name in COLLECTION_NAMES:
            original_validation = datastore.ds.validate
            try:
                # Lazily create an uncached collection so legacy mappings do not block the migration.
                # The collection still uses its registered ODM model and ILM configuration to build mappings.
                datastore.ds.validate = False
                collection = getattr(datastore, collection_name)
            finally:
                datastore.ds.validate = original_validation

            reindex_result = collection.reindex(allow_failures=False, request_timeout=TRANSPORT_TIMEOUT)
            if reindex_result is not True:
                raise DataStoreException(
                    f"Metadata case-insensitive migration did not confirm a successful reindex for "
                    f"collection {collection_name!r}: {reindex_result!r}."
                )

            for index in collection.index_list_full:
                if index.endswith("__reindex"):
                    continue

                existence_response = collection.datastore.client.indices.exists(index=index)
                exists = getattr(existence_response, "body", existence_response)
                if not isinstance(exists, bool):
                    raise DataStoreException(
                        f"Metadata case-insensitive migration received an invalid existence result for "
                        f"index {index!r}: {exists!r}."
                    )
                if not exists:
                    continue

                document_count = collection._index_doc_count(index)
                if isinstance(document_count, bool) or not isinstance(document_count, int) or document_count < 0:
                    raise DataStoreException(
                        "Metadata case-insensitive migration received an invalid document count for "
                        f"index {index!r}: {document_count!r}."
                    )
                affected_documents += document_count

        return affected_documents
