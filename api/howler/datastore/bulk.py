"""Build newline-delimited JSON payloads for Elasticsearch bulk requests.

``ElasticBulkPlan`` accumulates Elasticsearch bulk operations and renders them
as NDJSON suitable for the ``_bulk`` endpoint. Documents can be serialized
through an ODM model, and update operations can be limited to selected fields
to avoid overwriting unrelated stored data.
"""

import json
import warnings
from copy import deepcopy
from typing import List, Optional

from howler import odm
from howler.config import config
from howler.datastore.utils import expand_field_patterns, prune_to_paths

_OPERATION_GROUP = tuple[str] | tuple[str, str]

ELASTIC_MAX_REQUEST_SIZE = config.datastore.max_request_size
DEFAULT_BATCH_SIZE = config.datastore.request_batch_size


class ElasticBulkPlan(object):
    """Accumulate and render Elasticsearch bulk API operations.

    Unless an operation supplies an explicit ``index``, insert, index, and
    upsert operations target the first configured index. Delete and update
    operations target every configured index, which supports collections that
    span multiple physical indices.

    Args:
        indexes: Elasticsearch indices available to the plan. The first index
            is the default target for single-index operations.
        model: Optional ODM model used to serialize document values before
            they are added to the request.
    """

    def __init__(self, indexes: List[str], model: Optional[type[odm.Model]] = None):
        self.indexes = indexes
        self.model = model
        self.operations: list[_OPERATION_GROUP] = []

    @property
    def empty(self):
        """Whether the plan has no queued operations.

        Returns:
            ``True`` when no bulk operation has been added; otherwise,
            ``False``.
        """
        return len(self.operations) == 0

    def add_delete_operation(self, doc_id, index=None):
        """Queue a document delete operation.

        Args:
            doc_id: Identifier of the document to delete.
            index: Explicit index to target. When omitted, queues one delete
                operation for each configured index.
        """
        if index:
            self.operations.append((json.dumps({"delete": {"_index": index, "_id": doc_id}}),))
        else:
            for cur_index in self.indexes:
                self.operations.append((json.dumps({"delete": {"_index": cur_index, "_id": doc_id}}),))

    def add_insert_operation(self, doc_id: str, doc, index=None):
        """Queue a create-only document insert operation.

        The Elasticsearch ``create`` action fails if a document with ``doc_id``
        already exists. The document's ``id`` field is set to ``doc_id`` in the
        serialized request body.

        Args:
            doc_id: Identifier to assign to the new document.
            doc: Document data or an instance of the configured ODM model.
            index: Explicit index to target. When omitted, uses the first
                configured index.
        """
        if self.model and isinstance(doc, self.model):
            saved_doc = doc.as_primitives(hidden_fields=True)
        elif self.model:
            saved_doc = self.model(doc).as_primitives(hidden_fields=True)
        else:
            if not isinstance(doc, dict):
                saved_doc = {"__non_doc_raw__": doc}
            else:
                saved_doc = deepcopy(doc)
        saved_doc["id"] = doc_id

        self.operations.append(
            (
                json.dumps({"create": {"_index": index or self.indexes[0], "_id": doc_id}}),
                json.dumps(saved_doc),
            )
        )

    def add_index_operation(self, doc_id, doc, index=None):
        """Queue a document index operation.

        The Elasticsearch ``index`` action creates the document or replaces an
        existing document with the same identifier. The serialized request body
        always includes ``id`` set to ``doc_id``.

        Args:
            doc_id: Identifier of the document to create or replace.
            doc: Document data or an instance of the configured ODM model.
            index: Explicit index to target. When omitted, uses the first
                configured index.
        """
        if self.model and isinstance(doc, self.model):
            saved_doc = doc.as_primitives(hidden_fields=True)
        elif self.model:
            saved_doc = self.model(doc).as_primitives(hidden_fields=True)
        else:
            if not isinstance(doc, dict):
                saved_doc = {"__non_doc_raw__": doc}
            else:
                saved_doc = deepcopy(doc)
        saved_doc["id"] = doc_id

        self.operations.append(
            (
                json.dumps({"index": {"_index": index or self.indexes[0], "_id": doc_id}}),
                json.dumps(saved_doc),
            )
        )

    def add_upsert_operation(self, doc_id, doc, index=None):
        """Queue an update operation that creates the document when absent.

        The operation uses Elasticsearch's ``doc_as_upsert`` option. Its
        serialized document includes ``id`` set to ``doc_id``.

        Args:
            doc_id: Identifier of the document to update or create.
            doc: Document data or an instance of the configured ODM model.
            index: Explicit index to target. When omitted, uses the first
                configured index.
        """
        if self.model and isinstance(doc, self.model):
            saved_doc = doc.as_primitives(hidden_fields=True)
        elif self.model:
            saved_doc = self.model(doc).as_primitives(hidden_fields=True)
        else:
            if not isinstance(doc, dict):
                saved_doc = {"__non_doc_raw__": doc}
            else:
                saved_doc = deepcopy(doc)
        saved_doc["id"] = doc_id

        self.operations.append(
            (
                json.dumps({"update": {"_index": index or self.indexes[0], "_id": doc_id}}),
                json.dumps({"doc": saved_doc, "doc_as_upsert": True}),
            )
        )

    def add_update_operation(self, doc_id, doc, index=None, fields: Optional[List[str]] = None):
        """Queue a partial-merge Elasticsearch ``update`` operation.

        Args:
            doc_id: Identifier of the document to update.
            doc: Document data or an instance of the configured ODM model.
            index: Explicit index to target. When omitted, queues one update
                operation for each configured index.

            fields: When provided, restricts the update body to just these dotted field
                paths (any valid key from :meth:`ESCollection.fields`/`Model.flat_fields`),
                dropping everything else so unrelated concurrent edits to the stored
                document aren't clobbered. Entries may contain ``*`` wildcards, expanded
                against the model's known field paths (e.g. ``"items.*"`` selects every
                subfield of the ``items`` list without touching ``title``, ``summary``,
                etc.). A path with no wildcard is kept wholesale, including any nested
                subfields, e.g. ``"items"`` alone also keeps every subfield of ``items``.
        """
        if self.model and isinstance(doc, self.model):
            saved_doc = doc.as_primitives(hidden_fields=True)
        elif self.model:
            saved_doc = self.model(doc, mask=list(doc.keys())).as_primitives(hidden_fields=True)
        else:
            if not isinstance(doc, dict):
                saved_doc = {"__non_doc_raw__": doc}
            else:
                saved_doc = deepcopy(doc)

        if fields is not None:
            saved_doc = prune_to_paths(saved_doc, allowed=expand_field_patterns(self.model, fields))

        if index:
            self.operations.append(
                (
                    json.dumps({"update": {"_index": index, "_id": doc_id}}),
                    json.dumps({"doc": saved_doc}),
                )
            )
        else:
            for cur_index in self.indexes:
                self.operations.append(
                    (
                        json.dumps({"update": {"_index": cur_index, "_id": doc_id}}),
                        json.dumps({"doc": saved_doc}),
                    )
                )

    def get_plan_data(self):
        """Render all queued operations as an Elasticsearch bulk request.

        Returns:
            Newline-delimited JSON with a final trailing newline, ready to send
            to Elasticsearch's ``_bulk`` endpoint.
        """
        return self._get_plan_for_operations()

    def get_plan_batches(self, batch_size: int | None = DEFAULT_BATCH_SIZE):
        """Yield queued operations as separate Elasticsearch bulk payloads.

        Args:
            batch_size: Maximum number of queued operations in each payload.
                Pass ``None`` to produce one payload containing all operations.

        Yields:
            Newline-delimited JSON payloads, each with a trailing newline.
        """
        if batch_size is None:
            batch_size = len(self.operations)
        for ptr in range(0, len(self.operations), batch_size):
            yield self._get_plan_for_operations(self.operations[ptr : ptr + batch_size])

    def _flatten_operations(self, batch: List[_OPERATION_GROUP] | None = None) -> List[str]:
        """Flatten queued action/body groups into their NDJSON lines.

        Args:
            batch: Operation groups to flatten. Uses every queued operation
                when omitted or empty.

        Returns:
            JSON action and document lines in bulk API order.
        """
        if not batch:
            batch = self.operations

        flattened: list[str] = []
        for op in batch:
            flattened.extend(op)

        return flattened

    def _get_plan_for_operations(self, batch: List[_OPERATION_GROUP] | None = None) -> str:
        """Render operation groups as a newline-delimited JSON payload.

        Args:
            batch: Operation groups to render. Uses every queued operation when
                omitted or empty.

        Returns:
            The rendered payload with a final trailing newline.

        Warns:
            UserWarning: If the encoded payload exceeds the configured maximum
                Elasticsearch request size.
        """
        plan = "\n".join(self._flatten_operations(batch)) + "\n"

        if ELASTIC_MAX_REQUEST_SIZE and len(plan.encode("utf-8")) > ELASTIC_MAX_REQUEST_SIZE:
            warnings.warn(
                f"Bulk plan exceeds maximum request size of {ELASTIC_MAX_REQUEST_SIZE} bytes. "
                f"Current size: {len(plan.encode('utf-8'))} bytes."
            )

        return plan
