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
from dataclasses import dataclass
from typing import Any, Callable, List, Optional, TypedDict, cast

from pydantic import BaseModel

from howler.config import config
from howler.datastore.exceptions import DataStoreException
from howler.datastore.utils import expand_field_patterns, prune_to_paths
from howler.models import partial_primitives, validate_field_value

_OPERATION_GROUP = tuple[str] | tuple[str, str]


class _RoutingParams(TypedDict, total=False):
    routing: str


@dataclass(frozen=True)
class DocumentLocation:
    """The physical index and shard routing of an Elasticsearch document."""

    index: str
    routing: str | None = None

    def routing_params(self) -> _RoutingParams:
        return {"routing": self.routing} if self.routing is not None else {}

    def operation(self, action: str, doc_id: str, body: str | None = None) -> _OPERATION_GROUP:
        header = json.dumps({action: {"_index": self.index, "_id": doc_id, **self.routing_params()}})
        return (header,) if body is None else (header, body)

    @staticmethod
    def newest(matches: list[DocumentLocation]) -> DocumentLocation:
        if len(matches) > 1 and matches[0].index == matches[1].index:
            raise DataStoreException(f"Ambiguous document ID on multiple routes in {matches[0].index}")
        return matches[0]

    @staticmethod
    def all_generations(matches: list[DocumentLocation]) -> list[DocumentLocation]:
        """Delete across generations only if each ID identifies a single shard in each index."""
        seen = set()
        for target in matches:
            if target.index in seen:
                raise DataStoreException(f"Ambiguous document ID on multiple routes in {target.index}")
            seen.add(target.index)
        return matches


@dataclass(frozen=True)
class _PendingRoute:
    action: str
    doc_id: str
    mode: str
    index: str | None


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
# Even a single unbatched write payload must not require an unbounded ID query.
MAX_LOCATION_BATCH_SIZE = 500


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
        document_locations: Resolve IDs visible through the alias, newest generation first.
        index_aliases: Per-index alias metadata for validating hints and routing new documents.
    """

    def __init__(
        self,
        indexes: List[str],
        model: Optional[type] = None,
        *,
        write_index: str | None = None,
        document_locations: Callable[[list[str]], dict[str, list[DocumentLocation]]] | None = None,
        index_aliases: Callable[[], dict[str, dict[str, Any]]] | None = None,
    ):
        self.indexes = indexes
        self.model = model
        self.write_index = write_index or indexes[0]
        self.document_locations = document_locations
        self.index_aliases = index_aliases
        self._aliases: dict[str, dict[str, Any]] | None = None
        self._pending_routes: dict[int, _PendingRoute] = {}
        self.operations: list[_OPERATION_GROUP] = []

    def _physical_aliases(self) -> dict[str, dict[str, Any]]:
        if self._aliases is None:
            self._aliases = self.index_aliases() if self.index_aliases else {}
        return self._aliases

    def _index_target(self, index: str) -> DocumentLocation:
        if index == self.write_index:
            return DocumentLocation(self.write_index)
        if self.index_aliases is None:
            # A legacy single-index collection uses its alias even for a model carrying the
            # physical _hot index. Elasticsearch then applies the alias's current routing.
            return DocumentLocation(self.write_index if index == self.indexes[0] else index)
        aliases = self._physical_aliases()
        if index not in aliases:
            raise DataStoreException(f"Index {index!r} is not a physical member of this collection.")
        alias = aliases[index]
        return DocumentLocation(index, alias.get("index_routing", alias.get("routing")))

    def _missing_operation(self, route: _PendingRoute, body: str | None) -> _OPERATION_GROUP:
        # A filtered or search-routed alias can hide an existing ID. An unconditional fallback
        # in that case could overwrite/delete a different document that the lookup did not see.
        aliases = self._physical_aliases()
        candidates = [aliases[route.index]] if route.index and self.index_aliases else aliases.values()
        target = self._index_target(route.index) if route.index else DocumentLocation(self.write_index)
        if any("filter" in alias or "search_routing" in alias or "routing" in alias for alias in candidates):
            if route.action == "index":
                return target.operation("create", route.doc_id, body)
            if route.action == "update" and body and (update := json.loads(body)).get("doc_as_upsert"):
                return target.operation("create", route.doc_id, json.dumps(update["doc"]))
            raise DataStoreException(f"No visible location for {route.action} of {route.doc_id!r} through scoped alias")
        return target.operation(route.action, route.doc_id, body)

    def _model_index(self, doc: Any) -> str | None:
        if not isinstance(doc, BaseModel):
            return None
        index = getattr(getattr(doc, "meta", None), "index", None)
        if not isinstance(index, str) or not index:
            return None
        self._index_target(index)
        return index

    def _queue_pending_operation(
        self,
        action: str,
        doc_id: str,
        body: str | None,
        *,
        mode: str,
        index: str | None,
    ) -> None:
        position = len(self.operations)
        self.operations.append(DocumentLocation(self.write_index).operation(action, doc_id, body))
        self._pending_routes[position] = _PendingRoute(action=action, doc_id=doc_id, mode=mode, index=index)

    def _add_routed_operation(
        self,
        action: str,
        doc_id: str,
        body: str | None = None,
        *,
        index: str | None = None,
        doc: Any = None,
        mode: str = "newest",
        pending_mode: str | None = None,
    ) -> None:
        """Append an operation using the collection's explicit or resolved index route."""
        if index:
            self._index_target(index)
        index = index or self._model_index(doc)
        if index == self.write_index:
            index = None  # The alias selects locations, not a particular physical generation.
        if self.document_locations is not None:
            # An index hint alone does not identify a shard. Resolve the actual document route
            # even for a model read from a known physical index.
            self._queue_pending_operation(action, doc_id, body, mode=pending_mode or mode, index=index)
            return
        targets = [index] if index else (self.indexes if mode == "all" else self.indexes[:1])

        for target in targets:
            self.operations.append(self._index_target(target).operation(action, doc_id, body))

    def _resolve_pending_routes(self, batch_size: int | None = DEFAULT_BATCH_SIZE) -> None:
        if batch_size is not None and batch_size < 1:
            raise ValueError("batch_size must be positive")
        if not self._pending_routes:
            return
        if self.document_locations is None:
            raise DataStoreException("Bulk plan has unresolved routes without a document location resolver.")

        lookup_size = min(batch_size or MAX_LOCATION_BATCH_SIZE, MAX_LOCATION_BATCH_SIZE)
        doc_ids = list(dict.fromkeys(pending.doc_id for pending in self._pending_routes.values()))
        locations = {}
        for start in range(0, len(doc_ids), lookup_size):
            locations.update(self.document_locations(doc_ids[start : start + lookup_size]))
        resolved_operations: list[_OPERATION_GROUP] = []
        for position, operation in enumerate(self.operations):
            route = self._pending_routes.get(position)
            if route is None:
                resolved_operations.append(operation)
                continue

            existing = locations.get(route.doc_id, [])
            if route.index is not None:
                # An index hint narrows the alias search; it does not bypass its filter or search routing.
                existing = [target for target in existing if target.index == route.index]
            body = operation[1] if len(operation) == 2 else None
            if not existing:
                # Preserve the operation so Elasticsearch reports a missing/ambiguous alias target
                # instead of silently treating a dropped update/delete as a successful bulk plan.
                resolved_operations.append(self._missing_operation(route, body))
                continue
            targets = (
                DocumentLocation.all_generations(existing)
                if route.mode == "all"
                else [DocumentLocation.newest(existing)]
            )
            resolved_operations.extend(target.operation(route.action, route.doc_id, body) for target in targets)

        self.operations = resolved_operations
        self._pending_routes.clear()

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
            model = model_type.validate_howler(raw)
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
        self._add_routed_operation("delete", doc_id, index=index, mode="all")

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
        target = (
            self._index_target(index) if index and index != self.write_index else DocumentLocation(self.write_index)
        )
        self.operations.append(target.operation("create", doc_id, json.dumps(saved_doc)))

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

        self._add_routed_operation("index", doc_id, body, index=index, doc=doc)

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

        self._add_routed_operation("update", doc_id, body, index=index, doc=doc)

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

        self._add_routed_operation(
            "update",
            doc_id,
            json.dumps({"doc": saved_doc}),
            index=index,
            doc=doc,
            mode="all",
            pending_mode="newest",
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
        self._resolve_pending_routes(batch_size)
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
