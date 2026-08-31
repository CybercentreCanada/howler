"""Build newline-delimited JSON payloads for Elasticsearch bulk requests.

``ElasticBulkPlan`` accumulates Elasticsearch bulk operations and renders them
as NDJSON suitable for the ``_bulk`` endpoint. Documents can be serialized
through a finalized Pydantic/DSL model, and update operations can be limited to selected fields
to avoid overwriting unrelated stored data.
"""

import json
import logging
import warnings
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, cast

from pydantic import BaseModel

from howler.config import config
from howler.datastore.exceptions import DataStoreException
from howler.datastore.utils import expand_field_patterns, prune_to_paths
from howler.models import partial_primitives, validate_field_value

_OPERATION_GROUP = tuple[str] | tuple[str, str]


@dataclass(frozen=True)
class _PendingRoute:
    action: str
    doc_id: str
    mode: str


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
logger = logging.getLogger("howler.api.datastore")


class ElasticBulkPlan(object):
    """Accumulate and render Elasticsearch bulk API operations.

    Non-ILM plans retain the configured-index behavior. ILM-aware plans send new
    documents to the write alias and resolve replacements, upserts, updates, and
    deletes to the concrete backing index containing the logical document ID.

    Args:
        indexes: Elasticsearch indices available to the plan. The first index
            is the default target for single-index operations.
        model: Optional finalized Pydantic/DSL model used to serialize document values before
            they are added to the request.
        write_index: Logical write target. ILM collections pass their write alias.
        document_locations: Optional logical-ID resolver returning concrete backing indices,
            newest first.
        valid_indexes: Optional physical-index loader. Its result is cached for the plan.
    """

    def __init__(
        self,
        indexes: List[str],
        model: Optional[type] = None,
        *,
        write_index: str | None = None,
        document_locations: Callable[[list[str]], dict[str, list[str]]] | None = None,
        valid_indexes: Callable[[], list[str]] | None = None,
    ):
        self.indexes = indexes
        self.model = model
        self.write_index = write_index or indexes[0]
        self.document_locations = document_locations
        self.valid_indexes = valid_indexes
        self._valid_indexes_cache: frozenset[str] | None = None
        self._pending_routes: dict[int, _PendingRoute] = {}
        self.operations: list[_OPERATION_GROUP] = []

    def _is_valid_index(self, index: str) -> bool:
        if self.valid_indexes is None:
            return True
        if self._valid_indexes_cache is None:
            self._valid_indexes_cache = frozenset(self.valid_indexes())
        return index in self._valid_indexes_cache

    def _validate_explicit_index(self, index: str, *, allow_write_index: bool = False) -> str:
        if self.valid_indexes is None:
            return index
        if allow_write_index and index == self.write_index:
            return index
        if not self._is_valid_index(index):
            raise DataStoreException(f"Index {index!r} is not a physical member of this collection.")
        return index

    def _model_index(self, doc: Any) -> str | None:
        if not isinstance(doc, BaseModel):
            return None
        index = getattr(getattr(doc, "meta", None), "index", None)
        if not isinstance(index, str) or not index:
            return None
        if self.valid_indexes is not None and not self._is_valid_index(index):
            logger.warning("Ignoring invalid model index metadata %s for bulk document routing.", index)
            return None
        return index

    def _known_existing_indices(self, doc: Any = None) -> list[str] | None:
        model_index = self._model_index(doc)
        if model_index is not None:
            return [model_index]
        if self.document_locations is None:
            return list(self.indexes)
        return None

    def _queue_pending_operation(
        self,
        action: str,
        doc_id: str,
        body: str | None,
        *,
        mode: str,
    ) -> None:
        position = len(self.operations)
        header = json.dumps({action: {"_index": self.write_index, "_id": doc_id}})
        self.operations.append((header,) if body is None else (header, body))
        self._pending_routes[position] = _PendingRoute(action=action, doc_id=doc_id, mode=mode)

    def _resolve_pending_routes(self) -> None:
        if not self._pending_routes:
            return
        if self.document_locations is None:
            raise DataStoreException("Bulk plan has unresolved routes without a document location resolver.")

        doc_ids = list(dict.fromkeys(route.doc_id for route in self._pending_routes.values()))
        locations = self.document_locations(doc_ids)
        resolved_operations: list[_OPERATION_GROUP] = []
        for position, operation in enumerate(self.operations):
            route = self._pending_routes.get(position)
            if route is None:
                resolved_operations.append(operation)
                continue

            existing = locations.get(route.doc_id, [])
            targets = existing if route.mode == "all" else existing[:1]
            if not targets:
                # Preserve the operation so Elasticsearch reports a missing/ambiguous alias target
                # instead of silently treating a dropped update/delete as a successful bulk plan.
                targets = [self.write_index]

            for target in targets:
                header = json.dumps({route.action: {"_index": target, "_id": route.doc_id}})
                resolved_operations.append((header,) if len(operation) == 1 else (header, operation[1]))

        self.operations = resolved_operations
        self._pending_routes.clear()

    @staticmethod
    def _input_primitives(doc: Any) -> Any:
        if isinstance(doc, BaseModel):
            return doc.model_dump(by_alias=True)
        if hasattr(doc, "as_primitives"):
            return doc.as_primitives()
        return doc

    def _serialize_full(self, doc: Any) -> dict[str, Any]:
        if self.model:
            model_type = cast(Any, self.model)
            if issubclass(model_type, BaseModel):
                raw = self._input_primitives(doc)
                if isinstance(raw, dict):
                    raw = {key: value for key, value in raw.items() if key not in _MODEL_HELPER_FIELDS}
                model = model_type.validate_howler(raw)
            elif isinstance(doc, model_type):
                model = doc
            else:
                model = model_type(self._input_primitives(doc))
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
            if issubclass(model_type, BaseModel):
                raw = {key: value for key, value in raw.items() if key not in _MODEL_HELPER_FIELDS}
                return partial_primitives(model_type, raw)
            return model_type(raw, mask=list(raw)).as_primitives(hidden_fields=True)
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
        if index:
            self.operations.append(
                (json.dumps({"delete": {"_index": self._validate_explicit_index(index), "_id": doc_id}}),)
            )
        else:
            existing = self._known_existing_indices()
            if existing is None:
                self._queue_pending_operation("delete", doc_id, None, mode="all")
                return
            for cur_index in existing:
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
        saved_doc = self._serialize_full(doc)
        saved_doc["id"] = doc_id

        self.operations.append(
            (
                json.dumps(
                    {
                        "create": {
                            "_index": (
                                self._validate_explicit_index(index, allow_write_index=True)
                                if index
                                else self.write_index
                            ),
                            "_id": doc_id,
                        }
                    }
                ),
                json.dumps(saved_doc),
            )
        )

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

        if not index:
            existing = self._known_existing_indices(doc)
            if existing is None:
                self._queue_pending_operation("index", doc_id, body, mode="newest")
                return
            target = existing[0] if existing else self.write_index
        else:
            target = self._validate_explicit_index(index)

        self.operations.append(
            (
                json.dumps({"index": {"_index": target, "_id": doc_id}}),
                body,
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
        saved_doc = self._serialize_full(doc)
        saved_doc["id"] = doc_id
        body = json.dumps({"doc": saved_doc, "doc_as_upsert": True})

        if not index:
            existing = self._known_existing_indices(doc)
            if existing is None:
                self._queue_pending_operation("update", doc_id, body, mode="newest")
                return
            target = existing[0] if existing else self.write_index
        else:
            target = self._validate_explicit_index(index)

        self.operations.append(
            (
                json.dumps({"update": {"_index": target, "_id": doc_id}}),
                body,
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
        if fields is not None:
            allowed = expand_field_patterns(self.model, fields)
            raw = self._input_primitives(doc)
            if isinstance(raw, dict):
                raw = prune_to_paths(raw, allowed=allowed)
                if self.model and issubclass(cast(Any, self.model), BaseModel):
                    for path in fields:
                        if "*" not in path:
                            raw = self._validate_complete_path(raw, path, path.split("."))
            saved_doc = self._serialize_partial(raw)
            saved_doc.pop("__index", None)
        else:
            saved_doc = self._serialize_partial(doc)

        if index:
            self.operations.append(
                (
                    json.dumps({"update": {"_index": self._validate_explicit_index(index), "_id": doc_id}}),
                    json.dumps({"doc": saved_doc}),
                )
            )
        else:
            existing = self._known_existing_indices(doc)
            if existing is None:
                self._queue_pending_operation(
                    "update",
                    doc_id,
                    json.dumps({"doc": saved_doc}),
                    mode="newest",
                )
                return
            for cur_index in existing:
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
        self._resolve_pending_routes()
        return self._get_plan_for_operations()

    def get_plan_batches(self, batch_size: int | None = DEFAULT_BATCH_SIZE):
        """Yield queued operations as separate Elasticsearch bulk payloads.

        Args:
            batch_size: Maximum number of queued operations in each payload.
                Pass ``None`` to produce one payload containing all operations.

        Yields:
            Newline-delimited JSON payloads, each with a trailing newline.
        """
        self._resolve_pending_routes()
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
