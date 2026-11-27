"""Build newline-delimited JSON payloads for Elasticsearch bulk requests.

``ElasticBulkPlan`` accumulates Elasticsearch bulk operations and renders them
as NDJSON suitable for the ``_bulk`` endpoint. Documents can be serialized
through a finalized Pydantic/DSL model, and update operations can be limited to selected fields
to avoid overwriting unrelated stored data.
"""

from __future__ import annotations

import json
import warnings
from copy import deepcopy
from typing import Any, Callable, List, Optional, cast

from pydantic import BaseModel

from howler.config import config
from howler.datastore.utils import expand_field_patterns, prune_to_paths
from howler.models import partial_primitives, validate_field_value

_OPERATION_GROUP = tuple[str] | tuple[str, str]


_MODEL_HELPER_FIELDS = {
    "meta",
    "id",
    "__index",
    "__access_lvl__",
    "__access_req__",
    "__access_grp1__",
    "__access_grp2__",
}

ELASTIC_MAX_REQUEST_SIZE = config.datastore.max_request_size
DEFAULT_BATCH_SIZE = config.datastore.request_batch_size


class ElasticBulkPlan(object):
    """Accumulate and render Elasticsearch bulk API operations.

    When ``document_locations`` is provided (ILM collections), operations without an
    explicit index are resolved at render time: replacements, upserts and updates target
    the newest rollover index containing the document, deletes target every index
    containing it, and documents that do not exist yet go through the write alias.

    Args:
        indexes: Elasticsearch indices available to the plan. The first index
            is the default target for single-index operations.
        model: Optional finalized Pydantic/DSL model used to serialize document values before
            they are added to the request.
        document_locations: Map document IDs to the indexes containing them, newest first.
    """

    def __init__(
        self,
        indexes: List[str],
        model: Optional[type] = None,
        *,
        document_locations: Callable[[list[str]], dict[str, list[str]]] | None = None,
    ):
        self.indexes = indexes
        self.model = model
        self.document_locations = document_locations
        # Operation position -> (action, doc_id) awaiting location resolution
        self._pending: dict[int, tuple[str, str]] = {}
        self.operations: list[_OPERATION_GROUP] = []

    @staticmethod
    def _operation(action: str, index: str, doc_id: str, body: str | None = None) -> _OPERATION_GROUP:
        header = json.dumps({action: {"_index": index, "_id": doc_id}})
        return (header,) if body is None else (header, body)

    def _add_operation(
        self, action: str, doc_id: str, body: str | None = None, *, index: str | None = None, every: bool = False
    ) -> None:
        if self.document_locations is not None and index in (None, self.indexes[0]):
            self._pending[len(self.operations)] = (action, doc_id)
            self.operations.append(self._operation(action, self.indexes[0], doc_id, body))
            return
        for target in [index] if index else self.indexes if every else self.indexes[:1]:
            self.operations.append(self._operation(action, target, doc_id, body))

    def _resolve_pending(self) -> None:
        if not self._pending or self.document_locations is None:
            return

        locations = self.document_locations(list(dict.fromkeys(doc_id for _, doc_id in self._pending.values())))
        resolved: list[_OPERATION_GROUP] = []
        for position, operation in enumerate(self.operations):
            if position not in self._pending:
                resolved.append(operation)
                continue

            action, doc_id = self._pending[position]
            targets = locations.get(doc_id) or self.indexes[:1]
            if action != "delete":
                targets = targets[:1]
            body = operation[1] if len(operation) == 2 else None
            resolved.extend(self._operation(action, index, doc_id, body) for index in targets)

        self.operations = resolved
        self._pending.clear()

    @staticmethod
    def _input_primitives(doc: Any) -> Any:
        if isinstance(doc, BaseModel):
            return doc.model_dump(by_alias=True)
        return doc

    def _serialize_full(self, doc: Any) -> dict[str, Any]:
        if self.model:
            model_type = cast(Any, self.model)
            raw = self._input_primitives(doc)
            if isinstance(raw, dict):
                raw = {key: value for key, value in raw.items() if key not in _MODEL_HELPER_FIELDS}
            model = model_type.model_validate(raw)
            return model.as_primitives(hidden_fields=True)
        if not isinstance(doc, dict):
            return {"__non_doc_raw__": doc}
        return deepcopy(doc)

    def _serialize_partial(self, doc: Any) -> dict[str, Any]:
        if self.model:
            model_type = cast(Any, self.model)
            if isinstance(doc, model_type):
                return doc.as_primitives(hidden_fields=True)
            raw = self._input_primitives(doc)
            if not isinstance(raw, dict):
                raise TypeError(f"Expected partial document mapping, got {type(raw).__name__}")
            raw = {key: value for key, value in raw.items() if key not in _MODEL_HELPER_FIELDS}
            return partial_primitives(model_type, raw)
        if not isinstance(doc, dict):
            return {"__non_doc_raw__": doc}
        return deepcopy(doc)

    def _validate_complete_path(self, value: Any, path: str, components: list[str]) -> Any:
        """Fully validate an exact selected field while traversing compound lists."""
        if not components:
            return validate_field_value(cast(Any, self.model), path, value)
        if isinstance(value, list):
            return [self._validate_complete_path(item, path, components) for item in value]
        if not isinstance(value, dict) or components[0] not in value:
            return value

        output = dict(value)
        component = components[0]
        output[component] = self._validate_complete_path(output[component], path, components[1:])
        return output

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
        self._add_operation("delete", doc_id, index=index, every=True)

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
        saved_doc = self._serialize_full(doc)
        saved_doc["id"] = doc_id
        self.operations.append(self._operation("create", index or self.indexes[0], doc_id, json.dumps(saved_doc)))

    def add_index_operation(self, doc_id, doc, index=None):
        """Queue a document index operation.

        The Elasticsearch ``index`` action creates the document or replaces an
        existing document with the same identifier. The document's id field is
        set to doc_id in the serialized request body.

        Args:
            doc_id: Identifier of the document to create or replace.
            doc: Document data or an instance of the configured ODM model.
            index: Explicit index to target. When omitted, uses the first
                configured index.
        """
        saved_doc = self._serialize_full(doc)
        saved_doc["id"] = doc_id
        body = json.dumps(saved_doc)

        self._add_operation("index", doc_id, body, index=index)

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
        saved_doc = self._serialize_full(doc)
        saved_doc["id"] = doc_id
        body = json.dumps({"doc": saved_doc, "doc_as_upsert": True})

        self._add_operation("update", doc_id, body, index=index)

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
        if fields is not None:
            allowed = expand_field_patterns(self.model, fields)
            raw = self._input_primitives(doc)
            if isinstance(raw, dict):
                raw = prune_to_paths(raw, allowed=allowed)
                if self.model:
                    for path in fields:
                        if "*" not in path:
                            raw = self._validate_complete_path(raw, path, path.split("."))
            saved_doc = self._serialize_partial(raw)
            saved_doc.pop("__index", None)
        else:
            saved_doc = self._serialize_partial(doc)

        self._add_operation("update", doc_id, json.dumps({"doc": saved_doc}), index=index, every=True)

    def get_plan_data(self):
        """Render all queued operations as an Elasticsearch bulk request.

        Returns:
            Newline-delimited JSON with a final trailing newline, ready to send
            to Elasticsearch's ``_bulk`` endpoint.
        """
        self._resolve_pending()
        return self._get_plan_for_operations()

    def get_plan_batches(self, batch_size: int | None = DEFAULT_BATCH_SIZE):
        """Yield queued operations as separate Elasticsearch bulk payloads.

        Args:
            batch_size: Maximum number of queued operations in each payload.
                Pass ``None`` to produce one payload containing all operations.

        Yields:
            Newline-delimited JSON payloads, each with a trailing newline.
        """
        self._resolve_pending()
        write_size = batch_size or max(1, len(self.operations))
        for ptr in range(0, len(self.operations), write_size):
            yield self._get_plan_for_operations(self.operations[ptr : ptr + write_size])

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
