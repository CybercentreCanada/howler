import json
import warnings
from copy import deepcopy
from typing import List, Optional

from howler import odm
from howler.config import config

_OPERATION_GROUP = tuple[str] | tuple[str, str]

ELASTIC_HOST_CONFIG = next((host for host in config.datastore.hosts if host.name == "elastic"), None)
ELASTIC_MAX_REQUEST_SIZE = ELASTIC_HOST_CONFIG.max_request_size if ELASTIC_HOST_CONFIG else None
DEFAULT_BATCH_SIZE = ELASTIC_HOST_CONFIG.request_batch_size if ELASTIC_HOST_CONFIG else None

class ElasticBulkPlan(object):

    def __init__(self, indexes: List[str], model: Optional[type[odm.Model]] = None):
        self.indexes = indexes
        self.model = model
        self.operations: list[_OPERATION_GROUP] = []

    @property
    def empty(self):
        return len(self.operations) == 0

    def add_delete_operation(self, doc_id, index=None):
        if index:
            self.operations.append((json.dumps({"delete": {"_index": index, "_id": doc_id}}),))
        else:
            for cur_index in self.indexes:
                self.operations.append((json.dumps({"delete": {"_index": cur_index, "_id": doc_id}}),))

    def add_insert_operation(self, doc_id: str, doc, index=None):
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

    def add_update_operation(self, doc_id, doc, index=None):
        if self.model and isinstance(doc, self.model):
            saved_doc = doc.as_primitives(hidden_fields=True)
        elif self.model:
            saved_doc = self.model(doc, mask=list(doc.keys())).as_primitives(hidden_fields=True)
        else:
            if not isinstance(doc, dict):
                saved_doc = {"__non_doc_raw__": doc}
            else:
                saved_doc = deepcopy(doc)

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
        """Construct the bulk request from the current operations"""
        return self._get_plan_for_operations()

    def get_plan_batches(self, batch_size: int | None = DEFAULT_BATCH_SIZE):
        """Yield plan data in batches"""
        if batch_size is None:
            batch_size = len(self.operations)
        for ptr in range(0, len(self.operations), batch_size):
            yield self._get_plan_for_operations(self.operations[ptr : ptr + batch_size])

    def _flatten_operations(self, batch: List[_OPERATION_GROUP] | None = None) -> List[str]:
        """Flatten the (operation, data) tuples for a batch or the full list of operations if no batch provided"""
        if not batch:
            batch = self.operations

        flattened: list[str] = []
        for op in batch:
            flattened.extend(op)

        return flattened

    def _get_plan_for_operations(self, batch: List[_OPERATION_GROUP] | None = None) -> str:
        """Get the bulk plan string for a batch or the full list of operations if no batch provided"""
        plan = "\n".join(self._flatten_operations(batch)) + "\n"

        if ELASTIC_MAX_REQUEST_SIZE and len(plan.encode("utf-8")) > ELASTIC_MAX_REQUEST_SIZE:
            warnings.warn(
                f"Bulk plan exceeds maximum request size of {ELASTIC_MAX_REQUEST_SIZE} bytes. "
                f"Current size: {len(plan.encode('utf-8'))} bytes."
            )

        return plan
