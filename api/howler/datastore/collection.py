from __future__ import annotations

import json
import logging
import re
import sys
import time
import typing
import warnings
from copy import deepcopy
from datetime import datetime
from os import environ
from random import random
from typing import Any, Callable, Dict, Generic, Literal, Optional, TypeVar, Union, cast, overload

import elasticsearch
from datemath import dm
from datemath.helpers import DateMathException
from elastic_transport import ApiResponseMeta
from elasticsearch import dsl
from opentelemetry import trace
from pydantic import BaseModel, TypeAdapter, ValidationError

from howler import odm
from howler.common.exceptions import HowlerRuntimeError, HowlerValueError, NonRecoverableError
from howler.common.loader import DATASTORE_INDEX_PREFIX
from howler.common.logging.format import HWL_DATE_FORMAT, HWL_LOG_FORMAT
from howler.datastore.bulk import ElasticBulkPlan
from howler.datastore.constants import BACK_MAPPING, TYPE_MAPPING
from howler.datastore.exceptions import (
    DataStoreException,
    HowlerScanError,
    MultiKeyError,
    SearchException,
    SearchRetryException,
    VersionConflictException,
)
from howler.datastore.support.build import build_mapping
from howler.datastore.support.elastic import error_message, error_status, error_type, response_body, total_hits_value
from howler.datastore.support.schemas import (
    default_dynamic_strings,
    default_dynamic_templates,
    default_index,
    default_mapping,
)
from howler.datastore.types import AggSearchResult, SearchResult
from howler.datastore.utils import expand_field_patterns
from howler.models import (
    construct_partial,
    flat_to_nested,
    partial_primitives,
    strip_unknown_fields,
    validate_field_value,
)
from howler.models import schema as new_schema
from howler.models.fields import FIELD_SANITIZER as MODEL_FIELD_SANITIZER
from howler.models.fields import NOT_INDEXED_SANITIZER as MODEL_NOT_INDEXED_SANITIZER
from howler.models.registry import BANNED_FIELDS as MODEL_BANNED_FIELDS
from howler.models.registry import field_metadata, model_registry
from howler.odm.base import FIELD_SANITIZER as LEGACY_FIELD_SANITIZER
from howler.odm.base import (
    IP,
    ClassificationObject,
    Enum,
    Integer,
    Keyword,
    List,
    Mapping,
    Model,
    ValidatedKeyword,
    _Field,
)
from howler.odm.base import NOT_INDEXED_SANITIZER as LEGACY_NOT_INDEXED_SANITIZER
from howler.utils.dict_utils import prune, recursive_update

if typing.TYPE_CHECKING:
    from .store import ESStore


TRANSPORT_TIMEOUT = int(environ.get("HWL_DATASTORE_TRANSPORT_TIMEOUT", "10"))

logger = logging.getLogger("howler.api.datastore")
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
logger.addHandler(console)

tracer = trace.get_tracer(__name__)

ModelType = TypeVar("ModelType")
_R = TypeVar("_R")


write_block_settings = {"index.blocks.write": True}
write_unblock_settings = {"index.blocks.write": None}

# A token value to represent a document not existing. Its a string to match the
# type used for version values. Any string will do as long as it never matches
# a real version string.
CREATE_TOKEN = "create"  # noqa: S105
ACCESS_FIELDS = (
    "__access_lvl__",
    "__access_req__",
    "__access_grp1__",
    "__access_grp2__",
)


class _SourceDocument(dict[str, Any]):
    """Internal source mapping carrying Elasticsearch hit metadata."""

    def __init__(self, data: dict[str, Any], metadata: dict[str, Any]):
        super().__init__(data)
        self.metadata = metadata


def _response_metadata(result: dict[str, Any], *, doc_id: str | None = None) -> dict[str, Any]:
    return {
        name: value
        for name, value in {
            "id": doc_id if doc_id is not None else result.get("_id"),
            "index": result.get("_index"),
            "primary_term": result.get("_primary_term"),
            "seq_no": result.get("_seq_no"),
            "version": result.get("_version"),
            "score": result.get("_score"),
        }.items()
        if value is not None
    }


def _strip_lists(model: type, data: dict[str, Any]) -> dict[str, Any]:
    """Elasticsearch returns everything as lists, regardless of whether
    we want the field to be multi-valued or not. This method uses the model's
    knowledge of what should or should not have multiple values to fix the data.
    """
    if not issubclass(model, BaseModel):
        fields = cast(Any, model).fields()
        out = {}
        for key, value in odm.flat_to_nested(data).items():
            doc_type = fields.get(key, fields.get("", model))
            if isinstance(doc_type, odm.Optional):
                doc_type = doc_type.child_type

            if isinstance(doc_type, odm.List):
                out[key] = value
            elif isinstance(doc_type, (odm.Compound, odm.Mapping)):
                out[key] = _strip_lists(doc_type.child_type, value)
            elif isinstance(value, list):
                out[key] = value[0]
            else:
                out[key] = value
        return out

    fields = model_registry.flat_fields(model)
    normalized: dict[str, Any] = {}
    for key, value in data.items():
        definition = fields.get(key)
        if isinstance(value, list) and not (definition is not None and definition.multivalued):
            normalized[key] = value[0] if value else None
        else:
            normalized[key] = value
    return flat_to_nested(normalized)


def sort_str(sort_dicts):
    if sort_dicts is None:
        return sort_dicts

    sort_list = [f"{key}:{val}" for d in sort_dicts for key, val in d.items()]
    return ",".join(sort_list)


def parse_sort(sort, ret_list=True):
    """This function tries to do two things at once:
    - convert AL sort syntax to elastic,
    - convert any sorts on the key _id to _id_
    """
    if sort is None:
        return sort

    if isinstance(sort, list):
        return [parse_sort(row, ret_list=False) for row in sort]
    elif isinstance(sort, dict):
        return {("id" if key == "_id" else key): value for key, value in sort.items()}

    parts = sort.split(" ")
    if len(parts) == 1:
        if parts == "_id":
            if ret_list:
                return ["id"]
            return "id"
        if ret_list:
            return [parts]
        return parts
    elif len(parts) == 2:
        if parts[1] not in ["asc", "desc"]:
            raise SearchException("Unknown sort parameter " + sort)
        if parts[0] == "_id":
            if ret_list:
                return [{"id": parts[1]}]
            return {"id": parts[1]}
        if ret_list:
            return [{parts[0]: parts[1]}]
        return {parts[0]: parts[1]}
    raise SearchException("Unknown sort parameter " + sort)


def _complete_eql_response(response: Any) -> dict[str, Any]:
    """Normalize an EQL response and reject running/partial result sets."""
    result = response_body(response)
    shards = result.get("_shards")
    failed_shards = (
        bool(shards.get("failed", 0))
        or bool(shards.get("failures"))
        or (
            bool(shards.get("total"))
            and int(shards.get("successful", 0) or 0) + int(shards.get("skipped", 0) or 0)
            < int(shards.get("total", 0) or 0)
        )
        if isinstance(shards, typing.Mapping)
        else False
    )
    if (
        result.get("is_running")
        or result.get("is_partial")
        or result.get("timed_out")
        or result.get("shard_failures")
        or failed_shards
    ):
        raise SearchException("Elasticsearch returned an incomplete EQL result.")
    return result


class ESCollection(Generic[ModelType]):
    DEFAULT_OFFSET = 0
    DEFAULT_ROW_SIZE = 25
    DEFAULT_SEARCH_FIELD = "__text__"
    DEFAULT_SORT = [{"_id": "asc"}]
    FIELD_SANITIZER = re.compile("^[a-z][a-z0-9_\\-.]+$")
    MAX_GROUP_LIMIT = 10
    MAX_FACET_LIMIT = 100
    MAX_RETRY_BACKOFF = 10
    MAX_SEARCH_ROWS = 500
    RETRY_NORMAL = 1
    RETRY_NONE = 0
    RETRY_INFINITY = -1
    SCROLL_TIMEOUT = "5m"
    UPDATE_SET = "SET"
    UPDATE_INC = "INC"
    UPDATE_DEC = "DEC"
    UPDATE_MAX = "MAX"
    UPDATE_MIN = "MIN"
    UPDATE_APPEND = "APPEND"
    UPDATE_APPEND_IF_MISSING = "APPEND_IF_MISSING"
    UPDATE_REMOVE = "REMOVE"
    UPDATE_DELETE = "DELETE"
    UPDATE_OPERATIONS = [
        UPDATE_APPEND,
        UPDATE_APPEND_IF_MISSING,
        UPDATE_DEC,
        UPDATE_INC,
        UPDATE_MAX,
        UPDATE_MIN,
        UPDATE_REMOVE,
        UPDATE_SET,
        UPDATE_DELETE,
    ]
    DEFAULT_SEARCH_VALUES: dict[str, typing.Any] = {
        "timeout": None,
        "field_list": None,
        "facet_active": False,
        "facet_mincount": 1,
        "facet_fields": [],
        "stats_active": False,
        "stats_fields": [],
        "field_script": None,
        "filters": [],
        "group_active": False,
        "group_field": None,
        "group_sort": None,
        "group_limit": 1,
        "histogram_active": False,
        "histogram_field": None,
        "histogram_type": None,
        "histogram_gap": None,
        "histogram_mincount": 1,
        "histogram_start": None,
        "histogram_end": None,
        "start": 0,
        "rows": DEFAULT_ROW_SIZE,
        "query": "*",
        "sort": DEFAULT_SORT,
        "df": None,
        "script_fields": [],
        "aggregations": None,
    }
    IGNORE_ENSURE_COLLECTION: bool = False
    ENSURE_COLLECTION_WARNED: bool = False
    CUSTOM_AGG_PREFIX: str = "_custom_agg__"

    def __init__(
        self,
        datastore: ESStore,
        name,
        model_class=None,
        validate=True,
        max_attempts=10,
        ilm_config=None,
        schema_model=None,
    ):
        self.replicas = int(
            environ.get(
                f"ELASTIC_{name.upper()}_REPLICAS",
                environ.get("ELASTIC_DEFAULT_REPLICAS", 0),
            )
        )
        self.shards = int(environ.get(f"ELASTIC_{name.upper()}_SHARDS", environ.get("ELASTIC_DEFAULT_SHARDS", 1)))
        self._index_list: list[str] = []

        self.datastore = datastore
        self.name = f"{DATASTORE_INDEX_PREFIX}-{name}"
        self.ilm_config = ilm_config
        self.index_name = f"{self.name}_hot"
        self.model_class = model_class
        self._pydantic_model = bool(isinstance(model_class, type) and issubclass(model_class, BaseModel))
        # Registered Howler collections use the same finalized Pydantic/DSL class for runtime
        # persistence and schema generation. ``None`` preserves raw schema-less collections and
        # the legacy mapping fallback for unregistered/ad hoc callers until the Step 9 cleanup.
        self.schema_model = schema_model
        self.validate = validate
        self.max_attempts = max_attempts

        if not ESCollection.IGNORE_ENSURE_COLLECTION:
            self._ensure_collection()
        elif "pytest" not in sys.modules and not ESCollection.ENSURE_COLLECTION_WARNED:
            logger.warning("Skipping ensure collection! This is dangerous. Waiting five seconds before continuing.")
            time.sleep(5)
            ESCollection.ENSURE_COLLECTION_WARNED = True

        self.stored_fields = {}
        if model_class:
            if self._pydantic_model:
                for name, definition in model_registry.flat_fields(model_class).items():
                    if definition.metadata is not None and definition.metadata.store:
                        self.stored_fields[name] = definition
            else:
                for name, field in model_class.flat_fields().items():
                    if field.store:
                        self.stored_fields[name] = field

    @property
    def index_list_full(self):
        """Return every physical index for this collection, newest ILM index first.

        Maintenance operations that must visit historical rollover indexes should use this
        property. The active index is included even when no ILM rollover index exists.
        """
        if not self._index_list:
            self._index_list = self._get_ilm_index_names()

        return list(dict.fromkeys([self.index_name, *sorted(self._index_list, reverse=True)]))

    @property
    def index_list(self):
        """Return the active physical write index for this collection.

        Historical ILM rollover indexes are intentionally excluded. ILM-aware bulk plans
        use the logical write alias plus explicit document-location resolution instead.
        """
        return [self.index_name]

    def _ilm_index_generation(self, index: str) -> int | None:
        """Return the canonical rollover generation for a physical ILM index."""
        match = re.fullmatch(rf"{re.escape(self.name)}-(\d{{6}})", index)
        return int(match.group(1)) if match else None

    def _get_ilm_index_names(self) -> list[str]:
        """Return physical ILM rollover indexes, excluding temporary maintenance indexes."""
        try:
            indices = self.datastore.client.indices.get(
                index=f"{self.name}-0*",
                ignore_unavailable=True,
                filter_path="*.aliases",
            )
        except elasticsearch.exceptions.NotFoundError:
            return []

        return sorted(
            (index for index in indices if self._ilm_index_generation(index) is not None),
            key=lambda index: cast(int, self._ilm_index_generation(index)),
        )

    def _refresh_ilm_index_name(self):
        """Set ``index_name`` to the latest existing ILM index, when one exists."""
        if not self.ilm_config:
            return

        ilm_indices = self._get_ilm_index_names()

        if ilm_indices:
            self._index_list = ilm_indices
            self.index_name = ilm_indices[-1]

    def scan_with_retry(
        self,
        query,
        sort=None,
        source=None,
        index=None,
        scroll="5m",
        size=1000,
        request_timeout=None,
    ):
        if index is None:
            index = self.index_name

        client = self.datastore.client
        if request_timeout is not None:
            client = client.options(request_timeout=request_timeout)

        # initial search
        resp = self.with_retries(
            client.search,
            index=index,
            query=query,
            scroll=scroll,
            size=size,
            sort=sort,
            _source=source,
        )
        scroll_id = resp.get("_scroll_id")

        try:
            while scroll_id and resp["hits"]["hits"]:
                for hit in resp["hits"]["hits"]:
                    yield hit

                # Default to 0 if the value isn't included in the response
                shards_successful = resp["_shards"].get("successful", 0)
                shards_skipped = resp["_shards"].get("skipped", 0)
                shards_total = resp["_shards"].get("total", 0)

                # check if we have any errors
                if (shards_successful + shards_skipped) < shards_total:
                    shards_message = (
                        f"{scroll_id}: Scroll request has only succeeded on {shards_successful} "
                        f"(+{shards_skipped} skipped) shards out of {shards_total}."
                    )
                    raise HowlerScanError(shards_message)
                resp = self.with_retries(self.datastore.client.scroll, scroll_id=scroll_id, scroll=scroll)
                scroll_id = resp.get("_scroll_id")

        finally:
            if scroll_id:
                try:
                    resp = self.with_retries(
                        self.datastore.client.clear_scroll,
                        scroll_id=[scroll_id],
                    )
                    if not resp.get("succeeded", False):
                        logger.warning(
                            f"Could not clear scroll ID {scroll_id}, there is potential "
                            "memory leak in your Elastic cluster..."
                        )
                except elasticsearch.exceptions.NotFoundError:
                    pass

    def with_retries(self, func: Callable[..., _R], *args: Any, raise_conflicts: bool = False, **kwargs: Any) -> _R:
        """This function performs the passed function with the given args and kwargs and reconnect if it fails

        :return: return the output of the function passed
        """
        retries = 0

        while True:
            if retries >= self.max_attempts:
                raise HowlerRuntimeError(f"Maximum of {self.max_attempts} retries reached. Aborting ES connection")

            try:
                ret_val = func(*args, **kwargs)

                if retries:
                    logger.info("Reconnected to elasticsearch!")

                return ret_val
            except elasticsearch.exceptions.NotFoundError as e:
                if "index_not_found_exception" in str(e):
                    time.sleep(min(retries, self.MAX_RETRY_BACKOFF))
                    logger.debug("The index does not exist. Trying to recreate it...")
                    self._ensure_collection()
                    self.datastore.connection_reset()
                    retries += 1
                else:
                    raise

            except elasticsearch.exceptions.ConflictError as ce:
                if raise_conflicts:
                    # De-sync potential treads trying to write to the index
                    time.sleep(random() * 0.1)  # noqa: S311
                    raise VersionConflictException(str(ce))

                time.sleep(min(retries, self.MAX_RETRY_BACKOFF))
                self.datastore.connection_reset()
                retries += 1

            except elasticsearch.exceptions.ConnectionTimeout:
                logger.warning(
                    f"Elasticsearch connection timeout, server(s): "
                    f"{' | '.join(self.datastore.get_hosts(safe=True))}"
                    f", retrying {func.__name__}..."
                )
                time.sleep(min(retries, self.MAX_RETRY_BACKOFF))
                self.datastore.connection_reset()
                retries += 1

            except (
                SearchRetryException,
                elasticsearch.exceptions.ConnectionError,
                elasticsearch.exceptions.AuthenticationException,
            ) as e:
                if not isinstance(e, SearchRetryException):
                    logger.exception(
                        f"No connection to Elasticsearch server(s): "
                        f"{' | '.join(self.datastore.get_hosts(safe=True))}"
                        f", because [{str(e)}] retrying {func.__name__}..."  # noqa: TRY401
                    )

                time.sleep(min(retries, self.MAX_RETRY_BACKOFF))
                self.datastore.connection_reset()
                retries += 1

            except elasticsearch.exceptions.TransportError as e:
                err_code = error_status(e)
                if err_code == 503:
                    logger.warning("Looks like index %s is not ready yet, retrying...", self.name)
                    time.sleep(min(retries, self.MAX_RETRY_BACKOFF))
                    self.datastore.connection_reset()
                    retries += 1
                elif err_code == 429:
                    logger.warning(
                        f"Elasticsearch is too busy to perform the requested task on index {self.name}, retrying..."
                    )
                    time.sleep(min(retries, self.MAX_RETRY_BACKOFF))
                    self.datastore.connection_reset()
                    retries += 1
                elif err_code == 403:
                    logger.warning(
                        "Elasticsearch cluster is preventing writing operations on index %s, retrying...",
                        self.name,
                    )
                    time.sleep(min(retries, self.MAX_RETRY_BACKOFF))
                    self.datastore.connection_reset()
                    retries += 1

                else:
                    raise

    def _get_task_results(self, task):
        # This function is only used to wait for a asynchronous task to finish in a graceful manner without
        #  timing out the elastic client. You can create an async task for long running operation like:
        #   - update_by_query
        #   - delete_by_query
        #   - reindex ...
        attempt = 0
        res = None
        while res is None:
            attempt = attempt + 1
            try:
                res = self.with_retries(
                    self.datastore.client.tasks.get,
                    task_id=task["task"],
                    wait_for_completion=True,
                    timeout="10s",
                )
            except (elasticsearch.exceptions.TransportError, elasticsearch.exceptions.ApiError) as e:
                err_code = error_status(e)
                if err_code == 500 and error_type(e) in [
                    "timeout_exception",
                    "receive_timeout_transport_exception",
                ]:
                    pass
                else:
                    logger.exception("Unexpected error on task check")
                    raise

        body = response_body(res)
        result = body["response"] if "response" in body else body["task"]["status"]

        return response_body(result)

    def _get_current_alias(self, index: str) -> typing.Optional[str]:
        if self.with_retries(self.datastore.client.indices.exists_alias, name=index):
            return next(
                iter(self.with_retries(self.datastore.client.indices.get_alias, index=index)),
                None,
            )

        return None

    def _wait_for_status(self, index, min_status="yellow"):
        status_ok = False
        while not status_ok:
            try:
                res = self.datastore.client.cluster.health(index=index, timeout="5s", wait_for_status=min_status)
                status_ok = not res["timed_out"]
            except elasticsearch.exceptions.TransportError as e:
                if error_status(e) == 408:
                    logger.warning("Waiting for index %s to get to status %s...", index, min_status)
                else:
                    raise

    def _safe_index_copy(self, copy_function, src, target, settings=None, min_status="yellow", request_timeout=60):
        options_client = self.datastore.client.options(request_timeout=request_timeout)
        timed_function = getattr(options_client.indices, copy_function.__name__)
        ret = timed_function(index=src, target=target, settings=settings)
        if not ret["acknowledged"]:
            raise DataStoreException(f"Failed to create index {target} from {src}.")

        self._wait_for_status(target, min_status=min_status)

    def _delete_async(self, index, query, max_docs=None, sort=None, refresh=None):
        deleted = 0
        while True:
            task = self.with_retries(
                self.datastore.client.delete_by_query,
                index=index,
                query=query,
                wait_for_completion=False,
                conflicts="proceed",
                sort=sort,
                max_docs=max_docs,
                refresh=refresh,
            )
            res = self._get_task_results(task)

            if res["version_conflicts"] == 0:
                res["deleted"] += deleted
                return res
            else:
                deleted += res["deleted"]

    def _update_async(self, index, script, query, max_docs=None, refresh=None):
        updated = 0
        while True:
            task = self.with_retries(
                self.datastore.client.update_by_query,
                index=index,
                script=script,
                query=query,
                wait_for_completion=False,
                conflicts="proceed",
                max_docs=max_docs,
                refresh=refresh,
            )
            res = self._get_task_results(task)

            if res["version_conflicts"] == 0:
                res["updated"] += updated
                return res
            else:
                updated += res["updated"]

    def bulk(self, operations: ElasticBulkPlan, refresh: str | None = None):
        """
        Execute a bulk plan.

        :return: True if the operation completed without errors
        """
        responses = []
        for operation_batch in operations.get_plan_batches():
            response = self.with_retries(self.datastore.client.bulk, operations=operation_batch, refresh=refresh)
            responses.append(response_body(response))

        has_errors = False
        for batch_response in responses:
            if batch_response["errors"]:
                has_errors = True
                logger.error("Errors on bulk plan: %s", batch_response["errors"])

        return not has_errors

    def get_bulk_plan(self):
        """
        Create a BulkPlan tailored for the current datastore

        :return: The BulkPlan object
        """
        if self.ilm_config:
            return ElasticBulkPlan(
                [self.name],
                self.model_class,
                write_index=self.name,
                document_locations=self._locate_ilm_documents,
                valid_indexes=self._get_ilm_index_names,
            )
        return ElasticBulkPlan(self.index_list, self.model_class)

    @tracer.start_as_current_span(f"{__name__}.commit")
    def commit(self):
        """This function should be overloaded to perform a commit of the index data of all the different hosts
        specified in self.datastore.hosts.

        :return: Should return True of the commit was successful on all hosts
        """
        self.with_retries(self.datastore.client.indices.refresh, index=self.index_name)
        self.with_retries(self.datastore.client.indices.clear_cache, index=self.index_name)
        return True

    def fix_replicas(self):
        """This function should be overloaded to fix the replica configuration of the index of all the different hosts
        specified in self.datastore.hosts.

        :return: Should return True of the fix was successful on all hosts
        """
        replicas = self._get_index_settings()["index"]["number_of_replicas"]
        settings = {"number_of_replicas": replicas}
        return self.with_retries(self.datastore.client.indices.put_settings, index=self.index_name, settings=settings)[
            "acknowledged"
        ]

    def fix_shards(self):
        """This function should be overloaded to fix the shard configuration of the index of all the different hosts
        specified in self.datastore.hosts.

        :return: Should return True of the fix was successful on all hosts
        """
        settings = self._get_index_settings()
        clone_settings = {"index.number_of_replicas": 0}
        clone_finish_settings = None
        clone_setup_settings = None
        method = None
        target_node = ""
        temp_name = f"{self.name}__fix_shards"

        indexes_settings = self.with_retries(self.datastore.client.indices.get_settings)
        current_settings = indexes_settings.get(self._get_current_alias(self.name), None)
        if not current_settings:
            raise DataStoreException(
                "Could not get current index settings. Something is wrong and requires manual intervention..."
            )

        cur_replicas = int(current_settings["settings"]["index"]["number_of_replicas"])
        cur_shards = int(current_settings["settings"]["index"]["number_of_shards"])
        target_shards = int(settings["index"]["number_of_shards"])
        clone_finish_settings = {
            "index.number_of_replicas": cur_replicas,
            "index.routing.allocation.require._name": None,
        }

        if cur_shards > target_shards:
            logger.info(
                "Current shards (%s) is bigger then target shards (%s), we will be shrinking the index.",
                cur_shards,
                target_shards,
            )
            if cur_shards % target_shards != 0:
                logger.info("The target shards is not a factor of the current shards, aborting...")
                return
            else:
                target_node = self.with_retries(self.datastore.client.cat.nodes, format="json")[0]["name"]  # type: ignore
                clone_setup_settings = {
                    "index.number_of_replicas": 0,
                    "index.routing.allocation.require._name": target_node,
                }
                method = self.datastore.client.indices.shrink
        elif cur_shards < target_shards:
            logger.info(
                "Current shards (%s) is smaller then target shards (%s), we will be splitting the index.",
                cur_shards,
                target_shards,
            )
            if target_shards % cur_shards != 0:
                logger.warning("The current shards is not a factor of the target shards, aborting...")
                return
            else:
                method = self.datastore.client.indices.split
        else:
            logger.info(
                "Current shards (%s) is equal to the target shards (%s), only housekeeping operations will be "
                "performed.",
                cur_shards,
                target_shards,
            )

        if method:
            # Before we do anything, we should make sure the source index is in a good state
            logger.info("Waiting for %s status to be GREEN.", self.name.upper())
            self._wait_for_status(self.name, min_status="green")

            # Block all indexes to be written to
            logger.info("Set a datastore wide write block on Elastic.")
            self.with_retries(self.datastore.client.indices.put_settings, settings=write_block_settings)

            # Clone it onto a temporary index
            if not self.with_retries(self.datastore.client.indices.exists, index=temp_name):
                # if there are specific settings to be applied to the index, apply them
                if clone_setup_settings:
                    logger.info("Relocating index to node %s.", target_node.upper())
                    self.with_retries(
                        self.datastore.client.indices.put_settings,
                        index=self.index_name,
                        settings=clone_setup_settings,
                    )

                    # Make sure no shard are relocating
                    while self.datastore.client.cluster.health(index=self.index_name)["relocating_shards"] != 0:
                        time.sleep(1)

                # Make a clone of the current index
                logger.info("Cloning %s into %s.", self.index_name.upper(), temp_name.upper())
                self._safe_index_copy(
                    self.datastore.client.indices.clone,
                    self.index_name,
                    temp_name,
                    settings=clone_settings,
                    min_status="green",
                )

            # Make 100% sure temporary index is ready
            logger.info("Waiting for %s status to be GREEN.", temp_name.upper())
            self._wait_for_status(temp_name, "green")

            # Make sure temporary index is the alias if not already
            if self._get_current_alias(self.name) != temp_name:
                logger.info(
                    "Make %s the current alias for %s and delete %s.",
                    temp_name.upper(),
                    self.name.upper(),
                    self.index_name.upper(),
                )
                # Make the hot index the temporary index while deleting the original index
                alias_actions = [
                    {"add": {"index": temp_name, "alias": self.name}},
                    {"remove_index": {"index": self.index_name}},
                ]
                self.with_retries(self.datastore.client.indices.update_aliases, actions=alias_actions)

            # Make sure the original index is deleted
            if self.with_retries(self.datastore.client.indices.exists, index=self.index_name):
                logger.info("Delete extra %s index.", self.index_name.upper())
                self.with_retries(self.datastore.client.indices.delete, index=self.index_name)

            # Shrink/split the temporary index into the original index
            logger.info("Perform shard fix operation from %s to %s.", temp_name.upper(), self.index_name.upper())
            self._safe_index_copy(method, temp_name, self.index_name, settings=settings)

            # Make the original index the new alias
            logger.info(
                "Make %s the current alias for %s and delete %s.",
                self.index_name.upper(),
                self.name.upper(),
                temp_name.upper(),
            )
            alias_actions = [
                {"add": {"index": self.index_name, "alias": self.name}},
                {"remove_index": {"index": temp_name}},
            ]
            self.with_retries(self.datastore.client.indices.update_aliases, actions=alias_actions)

        # Restore writes
        logger.debug("Restore datastore wide write operation on Elastic.")
        self.with_retries(self.datastore.client.indices.put_settings, settings=write_unblock_settings)

        # Restore normal routing and replicas
        logger.debug("Restore original routing table for %s.", self.name.upper())
        self.with_retries(
            self.datastore.client.indices.put_settings,
            index=self.name,
            settings=clone_finish_settings,
        )

    def _index_doc_count(self, index: str) -> int:
        """Return the number of documents in a physical index.

        :param index: the name of the physical index to count documents in
        :return: the number of documents currently stored in the index
        """
        self.with_retries(self.datastore.client.indices.refresh, index=index)
        return self.with_retries(self.datastore.client.count, index=index)["count"]

    def reindex(self, allow_failures: bool = False, request_timeout: int = 60):
        """Reindex all the data of the collection into a freshly mapped index.

        For every physical index in ``self.index_list_full`` the data is copied into a temporary
        ``__reindex`` index that uses the current mappings/settings. Writes to the source
        index are blocked while the copy runs so the reindex result and document counts can
        be validated before the original index is deleted. The temporary index is only
        collapsed back onto the original name once those checks pass.

        :param allow_failures: when ``True``, proceed even if the reindex reported document
            failures or version conflicts, or if the document counts do not match. This is
            DESTRUCTIVE: documents that could not be converted to the new mappings will be
            permanently dropped. Only use this for intentional lossy migrations.
        :param request_timeout: transport timeout in seconds for synchronous index-copy
            operations. Defaults to 60 seconds.
        :return: ``True`` when the reindex (and validation) completed successfully on all
            indexes.
        :raises DataStoreException: if a reindex reported failures/conflicts, or if the
            document count of the reindexed data does not match the source, and
            ``allow_failures`` is ``False``. The ``__reindex`` index is left in place so the
            operation can be recovered with :meth:`reindex_cleanup`.
        """
        logger.warning("Beginning Reindex")
        self._refresh_ilm_index_name()
        for index in self.index_list_full:
            new_name = f"{index}__reindex"
            index_data = None
            source_count = None
            source_writes_blocked = False

            source_exists = self.with_retries(self.datastore.client.indices.exists, index=index)
            target_exists = self.with_retries(self.datastore.client.indices.exists, index=new_name)

            # Never reindex while a '__reindex' index already exists. Its presence means a previous
            # reindex was interrupted, and the leftover may be stale or incomplete. Committing it
            # could silently replace live data, so force the operator to reconcile the state with
            # --cleanup before any new reindex is attempted.
            if target_exists:
                raise DataStoreException(
                    f"A leftover reindex index '{new_name}' already exists. This usually means a previous "
                    f"reindex was interrupted. Refusing to reindex because '{new_name}' may contain stale "
                    f"or incomplete data. Run the reindex script with --cleanup to reconcile the state "
                    f"if '{index}' still exists, or manually recover '{new_name}' if the source index is "
                    f"missing, then retry the reindex."
                )

            if not source_exists:
                logger.warning("Neither %s nor %s exist, nothing to reindex.", index, new_name)
                continue

            try:
                # Get information about the index to reindex
                index_data = self.with_retries(self.datastore.client.indices.get, index=index)[index]

                logger.warning("Block writes to source index %s", index)
                self.with_retries(
                    self.datastore.client.indices.put_settings,
                    index=index,
                    settings=write_block_settings,
                )
                source_writes_blocked = True

                # Record the number of documents we expect to migrate after writes are blocked.
                source_count = self._index_doc_count(index)
                logger.warning("Source index %s contains %s document(s)", index, source_count)

                # Create reindex target
                logger.warning("Creating new index with name %s", new_name)
                self.with_retries(
                    self.datastore.client.indices.create,
                    index=new_name,
                    mappings=self._get_index_mappings(),
                    settings=self._get_reindex_settings(index_data),
                )

                # Reindex data into target
                logger.warning("Beginning reindex from %s to %s", index, new_name)
                r_task = self.with_retries(
                    self.datastore.client.reindex,
                    source={"index": index},
                    dest={"index": new_name},
                    wait_for_completion=False,
                )
                logger.warning("Reindex taskId: %s", r_task["task"])
                reindex_result = self._get_task_results(r_task)

                # Validate the reindex did not silently drop or conflict on documents before
                # we commit to deleting the source index further down.
                self._validate_reindex_result(index, new_name, reindex_result, allow_failures)

                logger.warning("Committing reindexed data in index %s", new_name)
                self.with_retries(self.datastore.client.indices.refresh, index=new_name)
                self.with_retries(self.datastore.client.indices.clear_cache, index=new_name)

                # Compare the document counts of the source and reindexed indexes before deleting
                # the source so a silent document drop is caught.
                target_count = self._index_doc_count(new_name)
                self._validate_reindex_counts(index, new_name, source_count, target_count, allow_failures)

                logger.warning("Deleting old index %s", index)
                self.with_retries(self.datastore.client.indices.delete, index=index)
                source_writes_blocked = False

                logger.warning("Block writes to reindex target %s", new_name)
                self.with_retries(
                    self.datastore.client.indices.put_settings,
                    index=new_name,
                    settings=write_block_settings,
                )

                logger.warning("Renaming reindexed index from %s to %s", new_name, index)
                try:
                    self._safe_index_copy(
                        self.datastore.client.indices.clone,
                        new_name,
                        index,
                        settings=self._get_index_settings(),
                        request_timeout=request_timeout,
                    )

                    alias_actions = []
                    aliases = index_data.get("aliases", {})
                    for alias, alias_data in aliases.items():
                        alias_action = {"index": index, "alias": alias}
                        alias_action.update(alias_data)
                        alias_actions.append({"add": alias_action})
                    alias_actions.append({"remove_index": {"index": new_name}})
                    self.with_retries(self.datastore.client.indices.update_aliases, actions=alias_actions)

                    if bool(self.with_retries(self.datastore.client.indices.exists, index=new_name)):
                        logger.warning("Deleting reindex target %s", new_name)
                        self.with_retries(self.datastore.client.indices.delete, index=new_name)
                finally:
                    if bool(self.with_retries(self.datastore.client.indices.exists, index=index)):
                        logger.warning("Unblock writes to the index")
                        self.with_retries(
                            self.datastore.client.indices.put_settings,
                            index=index,
                            settings=write_unblock_settings,
                        )
            except Exception:
                if source_writes_blocked and bool(self.with_retries(self.datastore.client.indices.exists, index=index)):
                    logger.warning("Unblock writes to source index %s after failed reindex", index)
                    self.with_retries(
                        self.datastore.client.indices.put_settings,
                        index=index,
                        settings=write_unblock_settings,
                    )
                raise

        return True

    def _get_reindex_settings(self, index_data: dict) -> dict:
        """Build settings for a reindex target without dropping ILM lifecycle metadata."""
        settings = self._get_index_settings()
        lifecycle = index_data.get("settings", {}).get("index", {}).get("lifecycle")
        if lifecycle:
            settings["index"]["lifecycle"] = deepcopy(lifecycle)
        return settings

    def _validate_reindex_result(self, index, new_name, reindex_result, allow_failures):
        """Validate the result of an Elasticsearch reindex task.

        :param index: the source index being reindexed
        :param new_name: the temporary ``__reindex`` index being written to
        :param reindex_result: the ``response``/``status`` payload returned by the reindex task
        :param allow_failures: when ``True``, log the problems but do not abort
        :raises DataStoreException: if the reindex reported failures or version conflicts and
            ``allow_failures`` is ``False``
        """
        failures = reindex_result.get("failures", []) if reindex_result else []
        version_conflicts = reindex_result.get("version_conflicts", 0) if reindex_result else 0

        if not failures and not version_conflicts:
            return

        # Summarize the failures so the operator understands what went wrong
        summary = (
            f"Reindex of {index} into {new_name} reported {len(failures)} document failure(s) "
            f"and {version_conflicts} version conflict(s)."
        )
        for failure in failures[:10]:
            cause = failure.get("cause", failure)
            logger.error(
                "Reindex failure on document %s: %s - %s",
                failure.get("id", "<unknown>"),
                cause.get("type", "<unknown>"),
                cause.get("reason", cause),
            )
        if len(failures) > 10:
            logger.error("... and %s additional failure(s) not shown.", len(failures) - 10)

        if allow_failures:
            logger.warning("%s Proceeding anyway because allow_failures is set (DESTRUCTIVE).", summary)
            return

        raise DataStoreException(
            f"{summary} Aborting before deleting the source index to prevent data loss. The '{new_name}' "
            f"index has been left in place; run the reindex script with --cleanup to remove it and restore "
            f"'{index}', then retry. Re-run with --allow-failures only if you intend to drop the "
            f"un-convertible documents."
        )

    def _validate_reindex_counts(self, index, new_name, source_count, target_count, allow_failures):
        """Validate that the reindexed index contains the same number of documents as the source.

        :param index: the source index being reindexed
        :param new_name: the temporary ``__reindex`` index being written to
        :param source_count: the number of documents in the source index
        :param target_count: the number of documents in the reindexed index
        :param allow_failures: when ``True``, log the mismatch but do not abort
        :raises DataStoreException: if the counts differ and ``allow_failures`` is ``False``
        """
        if source_count == target_count:
            logger.warning("Document count validated: %s document(s) in both %s and %s", source_count, index, new_name)
            return

        summary = (
            f"Document count mismatch reindexing {index} into {new_name}: "
            f"source has {source_count} document(s) but reindex target has {target_count}."
        )

        if allow_failures:
            logger.warning("%s Proceeding anyway because allow_failures is set (DESTRUCTIVE).", summary)
            return

        raise DataStoreException(
            f"{summary} Aborting before deleting the source index to prevent data loss. The '{new_name}' "
            f"index has been left in place; run the reindex script with --cleanup to remove it and restore "
            f"'{index}', then retry. Re-run with --allow-failures only if you intend to accept the count "
            f"mismatch."
        )

    def reindex_cleanup(self):
        """Recover from a failed or interrupted :meth:`reindex` run.

        For every physical index that still has a leftover ``__reindex`` index, restore the source
        index's original aliases and delete the orphaned ``__reindex`` index. If the source
        index is missing, raise an error instead of deleting ``__reindex`` because it may
        be the only remaining copy of the data.

        Write blocks set during reindexing are cleared so the collection is usable again.

        :return: ``True`` when cleanup completed on all indexes
        """
        logger.warning("Beginning reindex cleanup")
        self._refresh_ilm_index_name()
        for index in self.index_list_full:
            new_name = f"{index}__reindex"

            if not self.with_retries(self.datastore.client.indices.exists, index=new_name):
                logger.info("No leftover reindex index found for %s, nothing to clean up.", index)
                continue

            if not self.with_retries(self.datastore.client.indices.exists, index=index):
                raise DataStoreException(
                    f"Source index '{index}' is missing but leftover reindex index '{new_name}' exists. "
                    f"Cannot safely clean up because '{new_name}' may be the only remaining copy of the data. "
                    f"Manually recover '{new_name}' or delete it if the data is no longer needed."
                )

            logger.warning("Restoring aliases for %s and removing leftover index %s", index, new_name)
            index_data = self.with_retries(self.datastore.client.indices.get, index=index)[index]
            new_index_data = self.with_retries(self.datastore.client.indices.get, index=new_name)[new_name]
            source_aliases = index_data.get("aliases", {})
            reindex_aliases = new_index_data.get("aliases", {})

            alias_actions = []
            for alias in sorted(set(source_aliases) | set(reindex_aliases)):
                source_alias_data = source_aliases.get(alias, {})
                reindex_alias_data = reindex_aliases.get(alias, {})

                add_alias_data = {"index": index, "alias": alias}
                add_alias_data.update(source_alias_data)
                if source_alias_data.get("is_write_index", False) or reindex_alias_data.get("is_write_index", False):
                    add_alias_data["is_write_index"] = True

                alias_actions.append({"add": add_alias_data})

            for alias in reindex_aliases:
                alias_actions.append({"remove": {"index": new_name, "alias": alias}})

            if alias_actions:
                logger.warning("Restoring aliases to %s", index)
                self.with_retries(self.datastore.client.indices.update_aliases, actions=alias_actions)

            logger.warning("Deleting leftover reindex index %s", new_name)
            self.with_retries(self.datastore.client.indices.delete, index=new_name)

            logger.warning("Unblock write to the index")
            self.with_retries(
                self.datastore.client.indices.put_settings,
                index=index,
                settings=write_unblock_settings,
            )

        return True

    def multiget(self, key_list, as_dictionary=True, as_obj=True, error_on_missing=True):
        """Get a list of documents from the datastore and make sure they are normalized using
        the model class

        :param error_on_missing: Should it raise a key error when keys are missing
        :param as_dictionary: Return a disctionary of items or a list
        :param as_obj: Return objects or not
        :param key_list: list of keys of documents to get
        :return: list of instances of the model class
        """

        requested_keys = list(key_list)
        missing_keys = list(requested_keys)
        resolved: dict[str, Any] = {}

        def add_to_output(data_output, data_id, row=None):
            if "__non_doc_raw__" in data_output:
                resolved[data_id] = data_output["__non_doc_raw__"]
            else:
                metadata = _response_metadata(row or {}, doc_id=data_id)
                resolved[data_id] = self.normalize(data_output, as_obj=as_obj, metadata=metadata, read=True)

        if missing_keys:
            if self.ilm_config:
                locations = self._locate_ilm_documents(missing_keys)
                grouped_ids: dict[str, list[str]] = {}
                for data_id in missing_keys:
                    if locations.get(data_id):
                        grouped_ids.setdefault(locations[data_id][0], []).append(data_id)
            else:
                grouped_ids = {self.name: missing_keys}

            found_keys: set[str] = set()
            for index, data_ids in grouped_ids.items():
                data = response_body(self.with_retries(self.datastore.client.mget, ids=data_ids, index=index))
                for row in data.get("docs", []):
                    if "found" in row and not row["found"]:
                        continue

                    data_id = row["_id"]
                    if data_id in found_keys:
                        logger.error("MGet returned multiple documents for id: %s", data_id)
                        continue

                    found_keys.add(data_id)
                    if data_id in missing_keys:
                        missing_keys.remove(data_id)
                    add_to_output(row["_source"], data_id, row)

        out: Union[dict[str, Any], list[Any]]
        if as_dictionary:
            out = {data_id: resolved[data_id] for data_id in requested_keys if data_id in resolved}
        else:
            out = [resolved[data_id] for data_id in requested_keys if data_id in resolved]

        if missing_keys and error_on_missing:
            raise MultiKeyError(missing_keys, out)

        return out

    def _locate_ilm_documents(self, keys: list[str]) -> dict[str, list[str]]:
        """Locate logical document IDs across every physical index behind an ILM alias."""
        if not keys:
            return {}

        result = response_body(
            self.with_retries(
                self.datastore.client.search,
                index=self.name,
                query=dsl.Q("ids", values=list(keys)).to_dict(),
                size=10000,
                _source=False,
                sort=[{"_index": "desc"}],
                track_total_hits=True,
            )
        )
        hits = result.get("hits", {})
        rows = hits.get("hits", [])
        if total_hits_value(hits.get("total", 0)) > len(rows):
            raise SearchException(f"Unable to locate every requested document across ILM indices for {self.name}.")

        locations: dict[str, list[str]] = {}
        for row in rows:
            data_id = row.get("_id")
            index = row.get("_index")
            if isinstance(data_id, str) and isinstance(index, str) and self._ilm_index_generation(index) is not None:
                locations.setdefault(data_id, []).append(index)

        for data_id, indexes in locations.items():
            locations[data_id] = sorted(
                set(indexes),
                key=lambda index: cast(int, self._ilm_index_generation(index)),
                reverse=True,
            )
            if len(locations[data_id]) > 1:
                logger.warning(
                    "Found duplicate document id %s across ILM indices for %s; using newest generation %s.",
                    data_id,
                    self.name,
                    locations[data_id][0],
                )
        return locations

    @overload
    def normalize(
        self,
        data,
        *,
        partial: bool = False,
        doc_id: str | None = None,
        index: str | None = None,
        score: float | None = None,
        metadata: dict[str, Any] | None = None,
        read: bool = False,
    ) -> ModelType | None: ...

    @overload
    def normalize(
        self,
        data,
        as_obj: Literal[True],
        *,
        partial: bool = False,
        doc_id: str | None = None,
        index: str | None = None,
        score: float | None = None,
        metadata: dict[str, Any] | None = None,
        read: bool = False,
    ) -> ModelType | None: ...

    @overload
    def normalize(
        self,
        data,
        as_obj: Literal[False],
        *,
        partial: bool = False,
        doc_id: str | None = None,
        index: str | None = None,
        score: float | None = None,
        metadata: dict[str, Any] | None = None,
        read: bool = False,
    ) -> dict[str, Any] | None: ...

    def normalize(
        self,
        data,
        as_obj=True,
        *,
        partial: bool = False,
        doc_id: str | None = None,
        index: str | None = None,
        score: float | None = None,
        metadata: dict[str, Any] | None = None,
        read: bool = False,
    ):
        """Normalize the data using the model class

        :param as_obj: Return an object instead of a dictionary
        :param data: data to normalize
        :return: instance of the model class
        """
        if data is None or self.model_class is None:
            return data

        source_metadata = data.metadata if isinstance(data, _SourceDocument) else {}
        if isinstance(data, self.model_class) and hasattr(data, "meta"):
            source_metadata = {
                **data.meta.model_dump(exclude_none=True),
                **source_metadata,
            }
        resolved_metadata = {
            **source_metadata,
            **(metadata or {}),
            **{
                key: value
                for key, value in {
                    "id": doc_id,
                    "index": index,
                    "score": score,
                }.items()
                if value is not None
            },
        }

        if not self._pydantic_model:
            if as_obj and not isinstance(data, self.model_class):
                return self.model_class(data, docid=doc_id)
            if isinstance(data, dict):
                return {key: value for key, value in data.items() if key not in MODEL_BANNED_FIELDS}
            return data

        if isinstance(data, self.model_class):
            if not as_obj:
                return data.as_primitives()
            if partial:
                model = data
            else:
                raw_data = data.as_primitives(hidden_fields=True)
                model_input = {
                    key: value
                    for key, value in raw_data.items()
                    if key not in MODEL_BANNED_FIELDS and key not in {"id", "__index"}
                }
                model = self.model_class.validate_howler({"meta": resolved_metadata, **model_input})
        else:
            if isinstance(data, BaseModel):
                raw_data = data.model_dump(by_alias=True)
            elif hasattr(data, "as_primitives"):
                raw_data = data.as_primitives()
            elif isinstance(data, dict):
                raw_data = deepcopy(data)
            else:
                raw_data = data

            if not isinstance(raw_data, dict):
                return raw_data

            if not as_obj:
                raw_data.pop("id", None)
                return {key: value for key, value in raw_data.items() if key not in MODEL_BANNED_FIELDS}

            model_input = {
                key: value
                for key, value in raw_data.items()
                if key not in MODEL_BANNED_FIELDS and key not in {"id", "__index"}
            }
            if read:
                model_input = strip_unknown_fields(self.model_class, model_input)
            model = (
                construct_partial(
                    self.model_class,
                    model_input,
                    meta=resolved_metadata,
                    ignore_unknown=read,
                )
                if partial
                else self.model_class.validate_howler({"meta": resolved_metadata, **model_input})
            )

        for name, value in resolved_metadata.items():
            setattr(model.meta, name, value)
        return model

    def _search_exists(self, key) -> bool:
        """Check document existence with an alias-safe search query."""
        result = response_body(
            self.with_retries(
                self.datastore.client.search,
                index=self.name,
                query=dsl.Q("ids", values=[key]).to_dict(),
                size=0,
                track_total_hits=True,
            )
        )
        total = result["hits"]["total"]
        return total_hits_value(total) > 0

    def exists(self, key) -> bool:
        """Check if a document exists in the datastore.

        :param key: key of the document to get from the datastore
        :return: true/false depending if the document exists or not
        """
        if self.ilm_config:
            return self._search_exists(key)

        try:
            return cast(bool, self.with_retries(self.datastore.client.exists, index=self.name, id=key, _source=False))
        except elasticsearch.BadRequestError:
            logger.exception(
                "Single-document existence check failed on %s; falling back to an alias-safe search.",
                self.name,
            )
            return self._search_exists(key)

    def _raise_document_not_found(self, key: str, result: Any) -> typing.NoReturn:
        """Raise the same error shape as an Elasticsearch document lookup for an empty search."""
        meta = ApiResponseMeta(
            status=404,
            http_version="1.1",
            headers=cast(Any, {}),
            duration=0.0,
            node=cast(Any, None),
        )
        raise elasticsearch.exceptions.NotFoundError(f"Document with id {key} not found", meta, result)

    @overload
    def _get(self, key, retries, version: Literal[False]) -> dict[str, Any]: ...

    @overload
    def _get(self, key, retries, version: Literal[True]) -> tuple[dict[str, Any], str]: ...

    def _get(self, key, retries, version=False):
        """Versioned get-save for atomic update has two paths:
            1. Document doesn't exist at all. Create token will be returned for version.
               This way only the first query to try and create the document will succeed.
            2. Document exists. A version string with the info needed to do a versioned save is returned.

        The create token is needed to differentiate between "I'm saving a new
        document non-atomic (version=None)" and "I'm saving a new document
        atomically (version=CREATE_TOKEN)".
        """

        def normalize_output(data_output, result):
            if "__non_doc_raw__" in data_output:
                return data_output["__non_doc_raw__"]
            output = deepcopy(data_output)
            output.pop("id", None)
            return _SourceDocument(output, _response_metadata(result, doc_id=key))

        if retries is None:
            retries = self.RETRY_NONE

        done = False
        while not done:
            try:
                if self.ilm_config:
                    locations = self._locate_ilm_documents([key]).get(key, [])
                    if not locations:
                        self._raise_document_not_found(key, {"hits": {"hits": []}})
                    doc = response_body(
                        self.with_retries(
                            self.datastore.client.get,
                            index=locations[0],
                            id=key,
                        )
                    )
                else:
                    doc = response_body(self.with_retries(self.datastore.client.get, index=self.name, id=key))

                if version:
                    if self.ilm_config:
                        version_token = f"{doc['_index']}---{doc['_seq_no']}---{doc['_primary_term']}"
                    else:
                        version_token = f"{doc['_seq_no']}---{doc['_primary_term']}"
                    return (
                        normalize_output(doc["_source"], doc),
                        version_token,
                    )
                return normalize_output(doc["_source"], doc)
            except elasticsearch.exceptions.NotFoundError:
                pass

            if retries > 0:
                time.sleep(0.05)
                retries -= 1
            elif retries < 0:
                time.sleep(0.05)
            else:
                done = True

        if version:
            return None, CREATE_TOKEN

        return None

    def _get_version_write_target(self, version: str) -> tuple[str, str, str]:
        """Return the concrete write target and optimistic-concurrency values from a version token."""
        version_parts = version.split("---")
        if len(version_parts) == 3:
            index, seq_no, primary_term = version_parts
            return index, seq_no, primary_term

        if len(version_parts) == 2:
            seq_no, primary_term = version_parts
            return self.name, seq_no, primary_term

        raise DataStoreException(f"Invalid version token for {self.name}: {version!r}")

    @overload
    def get(self, key, as_obj: Literal[True], version: Literal[True]) -> tuple[ModelType | None, str]: ...

    @overload
    def get(self, key, as_obj: Literal[True], version: Literal[False]) -> ModelType | None: ...

    @overload
    def get(self, key, as_obj: Literal[True]) -> ModelType | None: ...

    @overload
    def get(self, key) -> ModelType | None: ...

    @overload
    def get(self, key, as_obj: Literal[False], version: Literal[True]) -> tuple[dict[str, Any] | None, str]: ...

    @overload
    def get(self, key, as_obj: Literal[False], version: Literal[False]) -> dict[str, Any] | None: ...

    @overload
    def get(self, key, as_obj: Literal[False]) -> dict[str, Any] | None: ...

    def get(self, key, as_obj=True, version=False):
        """Get a document from the datastore, retry a few times if not found and normalize the
        document with the model provided with the collection.

        This is the normal way to get data of the system.

        :param archive_access: Temporary sets access value to archive during this call
        :param as_obj: Should the data be returned as an ODM object
        :param key: key of the document to get from the datastore
        :param version: should the version number be returned by the call
        :return: an instance of the model class loaded with the document data
        """
        data = self._get(key, self.RETRY_NORMAL, version=version)
        if version:
            data, version = data
            return self.normalize(data, as_obj=as_obj, doc_id=key, read=True), version
        return self.normalize(data, as_obj=as_obj, doc_id=key, read=True)

    @overload
    def get_if_exists(self, key: str, as_obj: Literal[True], version: Literal[True]) -> tuple[ModelType, str]: ...

    @overload
    def get_if_exists(self, key: str, as_obj: Literal[True], version: Literal[False]) -> ModelType: ...

    @overload
    def get_if_exists(self, key: str, as_obj: Literal[True]) -> ModelType: ...

    @overload
    def get_if_exists(self, key: str) -> ModelType: ...

    @overload
    def get_if_exists(self, key: str, as_obj: Literal[False], version: Literal[True]) -> tuple[dict[str, Any], str]: ...

    @overload
    def get_if_exists(self, key: str, as_obj: Literal[False], version: Literal[False]) -> dict[str, Any]: ...

    @overload
    def get_if_exists(self, key: str, as_obj: Literal[False]) -> dict[str, Any]: ...

    def get_if_exists(self, key: str, as_obj=True, version=False):
        """Get a document from the datastore but do not retry if not found.

        Use this more in caching scenarios because eventually consistent database may lead
        to have document reported as missing even if they exist.

        :param archive_access: Temporary sets access value to archive during this call
        :param as_obj: Should the data be returned as an ODM object
        :param key: key of the document to get from the datastore
        :param version: should the version number be returned by the call
        :return: an instance of the model class loaded with the document data
        """
        data = self._get(key, self.RETRY_NONE, version=version)
        if version:
            data, version = data
            return self.normalize(data, as_obj=as_obj, doc_id=key, read=True), version

        return self.normalize(data, as_obj=as_obj, doc_id=key, read=True)

    def require(
        self, key, as_obj=True, version=False
    ) -> Union[
        tuple[Optional[Union[dict[str, Any], ModelType]], str],
        Optional[Union[dict[str, Any], ModelType]],
    ]:
        """Get a document from the datastore and retry forever because we know for sure
        that this document should exist. If it does not right now, this will wait for the
        document to show up in the datastore.

        :param archive_access: Temporary sets access value to archive during this call
        :param as_obj: Should the data be returned as an ODM object
        :param key: key of the document to get from the datastore
        :param version: should the version number be returned by the call
        :return: an instance of the model class loaded with the document data
        """
        data = self._get(key, self.RETRY_INFINITY, version=version)
        if version:
            data, version = data
            return self.normalize(data, as_obj=as_obj, doc_id=key, read=True), version
        return self.normalize(data, as_obj=as_obj, doc_id=key, read=True)

    def save(self, key, data, version=None, refresh: Literal["true", "false", "wait_for"] | None = None):
        """Save to document to the datastore using the key as its document id.

        The document data will be normalized before being saved in the datastore.

        :param key: ID of the document to save
        :param data: raw data or instance of the model class to save as the document
        :param version: version of the document to save over, if the version check fails this will raise an exception
        :param refresh: 'true' | 'false' | 'wait_for' | None
             Whether to refresh the datastore before returning. 'wait_for' will wait for the change to be visible
             in search.
        :return: True if the document was saved properly
        """
        if " " in key:
            raise DataStoreException("You are not allowed to use spaces in datastore keys.")

        data = self.normalize(data)

        if self.model_class and data is not None:
            saved_data = data.as_primitives(hidden_fields=True)
        else:
            if not isinstance(data, dict):
                saved_data = {"__non_doc_raw__": data}
            else:
                saved_data = deepcopy(data)

        saved_data["id"] = key
        operation = "index"
        index = self.name
        seq_no = None
        primary_term = None

        if version is None and self.ilm_config:
            _, version = self.get_if_exists(key, as_obj=False, version=True)

        if version == CREATE_TOKEN:
            operation = "create"
        elif version:
            index, seq_no, primary_term = self._get_version_write_target(version)

        if refresh == "true":
            logger.warning(
                "refresh set to true when saving %s to index %s - this is very costly for performance!", key, self.name
            )

        try:
            self.with_retries(
                self.datastore.client.index,
                index=index,
                id=key,
                document=json.dumps(saved_data),
                op_type=operation,
                if_seq_no=seq_no,
                if_primary_term=primary_term,
                raise_conflicts=True,
                refresh=refresh,
            )
        except elasticsearch.BadRequestError as e:
            raise NonRecoverableError(
                f"When saving document {key} to elasticsearch, an exception occurred:\n{repr(e)}\n\n"
                f"Data: {json.dumps(saved_data)}"
            ) from e

        return True

    def delete(self, key, refresh=None):
        """This function should delete the underlying document referenced by the key.
        It should return true if the document was in fact properly deleted.

        :param key: id of the document to delete
        :return: True is delete successful
        """
        indexes = self._locate_ilm_documents([key]).get(key, []) if self.ilm_config else [self.name]
        deleted = False
        for index in indexes:
            try:
                info = response_body(
                    self.with_retries(self.datastore.client.delete, id=key, index=index, refresh=refresh)
                )
                deleted = info["result"] == "deleted" or deleted
            except elasticsearch.NotFoundError:
                continue
        return deleted

    def delete_by_query(self, query: str, sort=None, max_docs=None, refresh=None) -> bool:
        """This function should delete the underlying documents referenced by the query.
        It should return true if the documents were in fact properly deleted.

        :param query: Query of the documents to download
        :return: True is delete successful
        """
        query_obj = {"bool": {"must": {"query_string": {"query": query}}}}
        success = self.delete_by_search_object(query=query_obj, sort=sort, max_docs=max_docs, refresh=refresh)
        return success

    def delete_by_search_object(self, query: dict, sort=None, max_docs=None, refresh=None):
        """Delete the underlying documents matching the query object.
        Returns true if the documents were in fact properly deleted.

        :param query: Query object following elasticsearch request structure
        :param workers: Number of workers used for deletion if basic currency delete is used
        :return: True is delete successful
        """
        info = self._delete_async(
            self.name, query=query, sort=sort_str(parse_sort(sort)), max_docs=max_docs, refresh=refresh
        )
        return info.get("deleted", 0) != 0

    def _create_scripts_from_operations(self, operations):
        op_sources = []
        op_params = {}
        val_id = 0
        for op, doc_key, value in operations:
            source_path = "ctx._source" + "".join(f"[{json.dumps(component)}]" for component in doc_key.split("."))
            if op == self.UPDATE_SET:
                op_sources.append(f"{source_path} = params.value{val_id}")
                op_params[f"value{val_id}"] = value
            elif op == self.UPDATE_DELETE:
                op_sources.append(f"{source_path}.remove(params.value{val_id})")
                op_params[f"value{val_id}"] = value
            elif op == self.UPDATE_APPEND:
                op_sources.append(f"{source_path}.add(params.value{val_id})")
                op_params[f"value{val_id}"] = value
            elif op == self.UPDATE_APPEND_IF_MISSING:
                script = (
                    f"if ({source_path}.indexOf(params.value{val_id}) == -1) "
                    f"{{{source_path}.add(params.value{val_id})}}"
                )
                op_sources.append(script)
                op_params[f"value{val_id}"] = value
            elif op == self.UPDATE_REMOVE:
                script = (
                    f"if ({source_path}.indexOf(params.value{val_id}) != -1) "
                    f"{{{source_path}.remove({source_path}.indexOf(params.value{val_id}))}}"
                )
                op_sources.append(script)
                op_params[f"value{val_id}"] = value
            elif op == self.UPDATE_INC:
                op_sources.append(f"{source_path} += params.value{val_id}")
                op_params[f"value{val_id}"] = value
            elif op == self.UPDATE_DEC:
                op_sources.append(f"{source_path} -= params.value{val_id}")
                op_params[f"value{val_id}"] = value
            elif op == self.UPDATE_MAX:
                script = (
                    f"if ({source_path} == null || "
                    f"{source_path}.compareTo(params.value{val_id}) < 0) "
                    f"{{{source_path} = params.value{val_id}}}"
                )
                op_sources.append(script)
                op_params[f"value{val_id}"] = value
            elif op == self.UPDATE_MIN:
                script = (
                    f"if ({source_path} == null || "
                    f"{source_path}.compareTo(params.value{val_id}) > 0) "
                    f"{{{source_path} = params.value{val_id}}}"
                )
                op_sources.append(script)
                op_params[f"value{val_id}"] = value

            val_id += 1

        joined_sources = """;\n""".join(op_sources)

        return {
            "lang": "painless",
            "source": joined_sources.replace("};\n", "}\n"),
            "params": op_params,
        }

    def _validate_operations(self, operations):
        """Validate the different operations received for a partial update

        TODO: When the field is of type Mapping, the validation/check only works for depth 1. A full recursive
              solution is needed to support multi-depth cases.

        :param operations: list of operation tuples
        :raises: DatastoreException if operation not valid
        """
        for _, doc_key, _ in operations:
            if doc_key in ACCESS_FIELDS:
                raise DataStoreException(
                    f"Hidden access field {doc_key} is derived from classification and cannot be updated directly."
                )

        if self.model_class and not self._pydantic_model:
            fields = self.model_class.flat_fields(show_compound=True)
            if "classification" in fields:
                fields.update(
                    {
                        "__access_lvl__": Integer(),
                        "__access_req__": List(Keyword()),
                        "__access_grp1__": List(Keyword()),
                        "__access_grp2__": List(Keyword()),
                    }
                )

            legacy_operations = []
            for op, doc_key, value in operations:
                access_parts = None
                if op not in self.UPDATE_OPERATIONS:
                    raise DataStoreException(f"Not a valid Update Operation: {op}")
                previous_key = None
                if doc_key not in fields:
                    if "." in doc_key:
                        previous_key = doc_key[: doc_key.rindex(".")]
                        if previous_key in fields and not isinstance(fields[previous_key], Mapping):
                            raise DataStoreException(f"Invalid field for model: {previous_key}")
                        if previous_key in fields:
                            mapping_field = fields[previous_key]
                            sanitizer = (
                                LEGACY_FIELD_SANITIZER
                                if mapping_field.index or mapping_field.store
                                else LEGACY_NOT_INDEXED_SANITIZER
                            )
                            dynamic_key = doc_key[len(previous_key) + 1 :]
                            if not sanitizer.fullmatch(dynamic_key):
                                raise DataStoreException(f"Invalid field for model: {doc_key}")
                    else:
                        raise DataStoreException(f"Invalid field for model: {doc_key}")

                field = fields[previous_key].child_type if previous_key else fields[doc_key]
                if op == self.UPDATE_DELETE:
                    if previous_key is not None or not isinstance(field, Mapping):
                        raise DataStoreException(f"Invalid field for DELETE operation: {doc_key}")
                    try:
                        value = TypeAdapter(str).validate_python(value)
                    except (TypeError, ValueError, ValidationError) as error:
                        raise DataStoreException(f"Invalid value for field {doc_key}: {value}") from error
                    sanitizer = LEGACY_FIELD_SANITIZER if field.index or field.store else LEGACY_NOT_INDEXED_SANITIZER
                    if not sanitizer.fullmatch(value):
                        raise DataStoreException(f"Invalid value for field {doc_key}: {value}")
                elif op in {
                    self.UPDATE_APPEND,
                    self.UPDATE_APPEND_IF_MISSING,
                    self.UPDATE_REMOVE,
                    self.UPDATE_SET,
                    self.UPDATE_DEC,
                    self.UPDATE_INC,
                }:
                    try:
                        value = field.check(value)
                    except (AttributeError, TypeError, ValueError) as error:
                        raise DataStoreException(f"Invalid value for field {doc_key}: {value}") from error
                    if op == self.UPDATE_SET and doc_key == "classification":
                        access_parts = value.get_access_control_parts()

                if isinstance(value, Model):
                    value = value.as_primitives()
                elif isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, ClassificationObject):
                    value = str(value)
                legacy_operations.append((op, doc_key, value))
                if access_parts is not None:
                    legacy_operations.extend((self.UPDATE_SET, name, access_parts[name]) for name in ACCESS_FIELDS)
            return legacy_operations

        ret_ops = []
        for op, doc_key, value in operations:
            classification_parts: dict[str, Any] = {}
            if op not in self.UPDATE_OPERATIONS:
                raise DataStoreException(f"Not a valid Update Operation: {op}")

            if self.model_class and op == self.UPDATE_DELETE:
                definition = model_registry.flat_fields(self.model_class, show_compound=True).get(doc_key)
                if definition is None or definition.metadata is None or definition.metadata.kind != "Mapping":
                    raise DataStoreException(f"Invalid field for DELETE operation: {doc_key}")
                try:
                    value = TypeAdapter(str).validate_python(value)
                except (TypeError, ValueError, ValidationError) as error:
                    raise DataStoreException(f"Invalid value for field {doc_key}: {value}") from error
                sanitizer = (
                    MODEL_NOT_INDEXED_SANITIZER
                    if definition.metadata.index is False and definition.metadata.store is False
                    else MODEL_FIELD_SANITIZER
                )
                if not sanitizer.fullmatch(value):
                    raise DataStoreException(f"Invalid value for field {doc_key}: {value}")
            elif self.model_class:
                try:
                    if op == self.UPDATE_SET and doc_key == "classification":
                        classification_parts = partial_primitives(self.model_class, {"classification": value})
                        value = classification_parts.pop("classification")
                    else:
                        value = validate_field_value(
                            self.model_class,
                            doc_key,
                            value,
                            list_item=op
                            in {
                                self.UPDATE_APPEND,
                                self.UPDATE_APPEND_IF_MISSING,
                                self.UPDATE_REMOVE,
                            },
                        )
                except (AttributeError, TypeError, ValueError, ValidationError) as error:
                    if str(error).startswith("Invalid field for model:"):
                        raise DataStoreException(str(error)) from error
                    raise DataStoreException(f"Invalid value for field {doc_key}: {value}") from error

            ret_ops.append((op, doc_key, value))
            if self.model_class and op == self.UPDATE_SET and doc_key == "classification":
                ret_ops.extend(
                    (self.UPDATE_SET, name, classification_parts[name])
                    for name in ACCESS_FIELDS
                    if name in classification_parts
                )

        return ret_ops

    def update(self, key, operations, version=None, refresh=None):
        """This function performs an atomic update on some fields from the
        underlying documents referenced by the id using a list of operations.

        Operations supported by the update function are the following:
        INTEGER ONLY: Increase and decreased value
        LISTS ONLY: Append and remove items
        ALL TYPES: Set value

        :param key: ID of the document to modify
        :param operations: List of tuple of operations e.q. [(SET, document_key, operation_value), ...]
        :return: True is update successful
        """
        operations = self._validate_operations(operations)
        script = self._create_scripts_from_operations(operations)
        index = self.name
        seq_no = None
        primary_term = None

        if version is None and self.ilm_config:
            _, version = self.get_if_exists(key, as_obj=False, version=True)

        if version == CREATE_TOKEN:
            return False
        if version:
            index, seq_no, primary_term = self._get_version_write_target(version)

        try:
            res = response_body(
                self.with_retries(
                    self.datastore.client.update,
                    index=index,
                    id=key,
                    script=script,
                    if_seq_no=seq_no,
                    if_primary_term=primary_term,
                    raise_conflicts=bool(seq_no and primary_term),
                    refresh=refresh,
                )
            )
            return (
                res["result"] == "updated",
                (
                    f"{res['_index']}---{res['_seq_no']}---{res['_primary_term']}"
                    if self.ilm_config
                    else f"{res['_seq_no']}---{res['_primary_term']}"
                ),
            )
        except elasticsearch.NotFoundError as e:
            logger.warning("Update - elasticsearch.NotFoundError: %s %s", e.message, e.info)
        except elasticsearch.BadRequestError as e:
            logger.warning("Update - elasticsearch.BadRequestError: %s %s", e.message, e.info)
            return False
        except VersionConflictException as e:
            logger.warning("Update - elasticsearch.ConflictError: %s", e.message)
            raise
        except Exception as e:
            logger.warning("Update - Generic Exception: %s", str(e))
            return False

        return False

    def update_by_query(self, query, operations, filters=None, access_control=None, max_docs=None, refresh=None):
        """This function performs an atomic update on some fields from the
        underlying documents matching the query and the filters using a list of operations.

        Operations supported by the update function are the following:
        INTEGER ONLY: Increase and decreased value
        LISTS ONLY: Append and remove items
        ALL TYPES: Set value

        :param access_control:
        :param filters: Filter queries to reduce the data
        :param query: Query to find the matching documents
        :param operations: List of tuple of operations e.q. [(SET, document_key, operation_value), ...]
        :return: True is update successful
        """
        operations = self._validate_operations(operations)
        if filters is None:
            filters = []

        if access_control:
            filters.append(access_control)

        script = self._create_scripts_from_operations(operations)

        try:
            res = self._update_async(
                self.name,
                script=script,
                query={
                    "bool": {
                        "must": {"query_string": {"query": query}},
                        "filter": [{"query_string": {"query": ff}} for ff in filters],
                    }
                },
                max_docs=max_docs,
                refresh=refresh,
            )
        except Exception:
            return False

        return res["updated"]

    def _expand_fl(self, fl: str) -> str:
        """Expand wildcard patterns in a field list string using the model's flat_fields.

        For each comma-separated entry in `fl`, if the entry contains a `*`, it is treated
        as a glob-style wildcard pattern and matched against all fields returned by
        ``flat_fields()``.  Entries without wildcards are kept as-is.

        Args:
            fl: Comma-separated list of field names, optionally containing ``*`` wildcards
                (e.g. ``"howler.*,event.start"``).

        Returns:
            A comma-separated string of expanded field names.  If no model class is
            associated with this collection the original ``fl`` string is returned
            unchanged.
        """
        if not self.model_class or "*" not in fl:
            return fl

        patterns = [p.strip() for p in fl.split(",") if p.strip()]
        return ",".join(sorted(expand_field_patterns(self.model_class, patterns, preserve_all=True)))

    def _format_legacy_output(self, result, fields=None, as_obj=True):
        """Temporary projection path for differential legacy collections."""
        extra_fields = deepcopy(result.get("fields", {}))
        source_data = deepcopy(result.get("_source"))
        if source_data is not None:
            for field in MODEL_BANNED_FIELDS:
                source_data.pop(field, None)

        item_id = result["_id"]
        if not fields:
            fields = [*self.stored_fields, "id"]
        elif isinstance(fields, str):
            fields = fields.split(",")

        extra_fields = _strip_lists(self.model_class, extra_fields)
        if as_obj:
            if "_index" in fields and "_index" in result:
                extra_fields["_index"] = result["_index"]
            if "*" in fields:
                fields = None
            return self.model_class(source_data, mask=fields, docid=item_id, extra_fields=extra_fields)

        source_data = recursive_update(source_data, extra_fields, allow_recursion=False)
        if "id" in fields:
            source_data["id"] = item_id
        if "_index" in fields and "_index" in result:
            source_data["_index"] = result["_index"]
        return prune(source_data, fields, cast(Any, self.stored_fields), mapping_class=Mapping)

    def _format_output(self, result, fields=None, as_obj=True):
        if self.model_class and not self._pydantic_model:
            return self._format_legacy_output(result, fields, as_obj)

        # Getting search document data
        extra_fields = deepcopy(result.get("fields", {}))
        source_data = deepcopy(result.get("_source"))

        item_id = result["_id"]

        if self.model_class:
            requested_fields = fields
            if not fields:
                fields = list(self.stored_fields.keys())
                fields.append("id")
            elif isinstance(fields, str):
                fields = fields.split(",")

            extra_fields = _strip_lists(self.model_class, extra_fields)
            source_data = source_data or {}
            source_data = recursive_update(source_data, extra_fields, allow_recursion=False)
            source_data = {
                key: value for key, value in source_data.items() if key not in MODEL_BANNED_FIELDS and key != "id"
            }

            if as_obj:
                return self.normalize(
                    source_data,
                    as_obj=True,
                    partial=requested_fields is None or "*" not in fields,
                    metadata=_response_metadata(result, doc_id=item_id),
                    read=True,
                )

            if "id" in fields:
                source_data["id"] = item_id
            if "_index" in fields and "_index" in result:
                source_data["_index"] = result["_index"]

        if isinstance(fields, str):
            fields = [fields]

        if source_data is not None and (fields is None or "*" in fields or "id" in fields):
            source_data["id"] = [item_id]

        if fields is None or "*" in fields:
            return source_data

        projection_fields = cast(dict[str, Any], dict(self.stored_fields))
        for path, definition in self.stored_fields.items():
            if definition.metadata is not None and definition.metadata.kind == "Mapping":
                projection_fields[path] = Mapping(Keyword())
        return prune(source_data, fields, projection_fields, mapping_class=Mapping)

    def _search(self, args=None, deep_paging_id=None, track_total_hits=None):
        if args is None:
            args = []

        params: dict[str, Any] = {}
        if deep_paging_id is not None:
            params = {"scroll": self.SCROLL_TIMEOUT}
        elif track_total_hits:
            params["track_total_hits"] = track_total_hits

        parsed_values = deepcopy(self.DEFAULT_SEARCH_VALUES)

        # TODO: we should validate values for max rows, group length, history length...
        for key, value in args:
            if key not in parsed_values:
                all_args = "; ".join("%s=%s" % (field_name, field_value) for field_name, field_value in args)
                raise HowlerValueError("Unknown query argument: %s %s of [%s]" % (key, value, all_args))

            parsed_values[key] = value

        # Use the public Search/Q builders for request components that preserve the existing
        # wire shape exactly. Bool ``must`` is assembled explicitly because DSL normalizes a
        # single clause into a list, which would change golden request payloads.
        search_request = (
            dsl.Search()
            .source(parsed_values["field_list"] or list(self.stored_fields.keys()))
            .sort(*(parse_sort(parsed_values["sort"]) or []))
            .extra(from_=parsed_values["start"], size=parsed_values["rows"])
        )
        query_body = search_request.to_dict()
        query_body["from_"] = query_body.pop("from")
        must_query = dsl.Q("query_string", query=parsed_values["query"]).to_dict()
        if parsed_values["df"]:
            must_query["query_string"]["default_field"] = parsed_values["df"]
        query_body["query"] = {
            "bool": {
                "must": must_query,
                "filter": [
                    dsl.Q("query_string", query=filter_query).to_dict() for filter_query in parsed_values["filters"]
                ],
            }
        }

        if parsed_values["script_fields"]:
            fields = {}
            for f_name, f_script in parsed_values["script_fields"]:
                fields[f_name] = {"script": {"lang": "painless", "source": f_script}}
            query_body["script_fields"] = fields

        # Time limit for the query
        if parsed_values["timeout"]:
            query_body["timeout"] = parsed_values["timeout"]

        # Add an histogram aggregation
        if parsed_values["histogram_active"]:
            query_body.setdefault("aggregations", {})
            if parsed_values["histogram_type"] == "date_histogram":
                interval_type = "fixed_interval"
            else:
                interval_type = "interval"
            query_body["aggregations"]["histogram"] = dsl.A(
                cast(str, parsed_values["histogram_type"]),
                **cast(
                    dict[str, Any],
                    {
                        "field": parsed_values["histogram_field"],
                        interval_type: parsed_values["histogram_gap"],
                        "min_doc_count": parsed_values["histogram_mincount"],
                        "extended_bounds": {
                            "min": parsed_values["histogram_start"],
                            "max": parsed_values["histogram_end"],
                        },
                    },
                ),
            ).to_dict()

        # Add a facet aggregation
        if parsed_values["facet_active"]:
            query_body.setdefault("aggregations", {})
            for field in parsed_values["facet_fields"]:
                field_script = parsed_values["field_script"]
                if field_script:
                    facet_body = {
                        "script": {"source": field_script},
                        "min_doc_count": parsed_values["facet_mincount"],
                    }
                else:
                    facet_body = {
                        "field": field,
                        "min_doc_count": parsed_values["facet_mincount"],
                        "size": parsed_values["rows"],
                    }
                query_body["aggregations"][field] = dsl.A("terms", **facet_body).to_dict()

        # Add a facet aggregation
        if parsed_values["stats_active"]:
            query_body.setdefault("aggregations", {})
            for field in parsed_values["stats_fields"]:
                field_script = parsed_values["field_script"]
                if field_script:
                    stats_body = {"script": {"source": field_script}}
                else:
                    stats_body = {"field": field}

                query_body["aggregations"][f"{field}_stats"] = dsl.A(
                    "stats", **cast(dict[str, Any], stats_body)
                ).to_dict()

        # Add a group aggregation
        if parsed_values["group_active"]:
            query_body["collapse"] = {
                "field": parsed_values["group_field"],
                "inner_hits": {
                    "name": "group",
                    "_source": parsed_values["field_list"] or list(self.stored_fields.keys()),
                    "size": parsed_values["group_limit"],
                    "sort": parse_sort(parsed_values["group_sort"]) or [{parsed_values["group_field"]: "asc"}],
                },
            }

        # Add any arbitrary aggregations
        if parsed_values["aggregations"]:
            query_body.setdefault("aggregations", {})
            cluster_settings = self.datastore.client.cluster.get_settings(include_defaults=True, flat_settings=True)
            flattened_settings = {
                **cluster_settings["defaults"],
                **cluster_settings["transient"],
                **cluster_settings["persistent"],
            }
            max_buckets = int(flattened_settings["search.max_buckets"])
            for agg_name, agg_args in parsed_values["aggregations"]:
                if any("size" in agg_def and agg_def["size"] > max_buckets for agg_def in agg_args.values()):
                    # verify the size of the agg query doesn't exceed the max
                    warnings.warn(
                        f"Aggregation {agg_name} has a size argument higher than the maximum allowed "
                        f"buckets of the cluster ({max_buckets}). Skipping aggregation."
                    )
                    continue
                query_body["aggregations"][f"{self.CUSTOM_AGG_PREFIX}{agg_name}"] = dsl.A(agg_args).to_dict()

        try:
            if deep_paging_id is not None and not deep_paging_id == "*":
                # Get the next page
                result = self.with_retries(
                    self.datastore.client.scroll,
                    scroll_id=deep_paging_id,
                    **params,
                )
            else:
                # Run the query
                result = self.with_retries(
                    self.datastore.client.search,
                    index=self.name,
                    **params,
                    **query_body,
                )

            return result
        except (
            elasticsearch.ConnectionError,
            elasticsearch.ConnectionTimeout,
        ) as error:
            raise SearchRetryException("collection: %s, query: %s, error: %s" % (self.name, query_body, str(error)))

        except (elasticsearch.TransportError, elasticsearch.RequestError) as e:
            raise SearchException(error_message(e)) from e

        except Exception as error:
            raise SearchException("collection: %s, query: %s, error: %s" % (self.name, query_body, str(error)))

    @overload
    def search(
        self,
        query: str | None,
        as_obj: Literal[True] = True,
        offset: int = 0,
        rows: int | None = None,
        sort: typing.Any = None,
        fl: str | None = None,
        timeout: int | None = None,
        filters: list[str] | str | None = None,
        access_control: typing.Any = None,
        deep_paging_id: str | None = None,
        track_total_hits: bool = False,
        script_fields: list[str] = [],
        *,
        aggregations: None = None,
    ) -> SearchResult[ModelType]: ...

    @overload
    def search(
        self,
        query: str | None,
        as_obj: Literal[False],
        offset: int = 0,
        rows: int | None = None,
        sort: typing.Any = None,
        fl: str | None = None,
        timeout: int | None = None,
        filters: list[str] | str | None = None,
        access_control: typing.Any = None,
        deep_paging_id: str | None = None,
        track_total_hits: bool = False,
        script_fields: list[str] = [],
        *,
        aggregations: None = None,
    ) -> SearchResult[dict[str, typing.Any]]: ...

    @overload
    def search(
        self,
        query: str | None,
        as_obj: Literal[True] = True,
        offset: int = 0,
        rows: int | None = None,
        sort: typing.Any = None,
        fl: str | None = None,
        timeout: int | None = None,
        filters: list[str] | str | None = None,
        access_control: typing.Any = None,
        deep_paging_id: str | None = None,
        track_total_hits: bool = False,
        script_fields: list[str] = [],
        *,
        aggregations: list[tuple[str, dict]],
    ) -> AggSearchResult[ModelType]: ...

    @overload
    def search(
        self,
        query: str | None,
        as_obj: Literal[False],
        offset: int = 0,
        rows: int | None = None,
        sort: typing.Any = None,
        fl: str | None = None,
        timeout: int | None = None,
        filters: list[str] | str | None = None,
        access_control: typing.Any = None,
        deep_paging_id: str | None = None,
        track_total_hits: bool = False,
        script_fields: list[str] = [],
        *,
        aggregations: list[tuple[str, dict]],
    ) -> AggSearchResult[dict[str, typing.Any]]: ...

    def search(
        self,
        query,
        as_obj=True,
        offset=0,
        rows=None,
        sort=None,
        fl=None,
        timeout=None,
        filters=None,
        access_control=None,
        deep_paging_id=None,
        track_total_hits=None,
        script_fields=[],
        *,
        aggregations=None,
    ):
        """This function should perform a search through the datastore and return a
        search result object that consist on the following::

            {
                "offset": 0,      # Offset in the search index
                "rows": 25,       # Number of document returned per page
                "total": 123456,  # Total number of documents matching the query
                "items": [        # List of dictionary where each keys are one of
                    {             #   the field list parameter specified
                        fl[0]: value,
                        ...
                        fl[x]: value
                    }, ...]
            }

        If aggregations are provided the search result will include an additional field::

            {
                "aggregations": {       # Dictionary where the keys are the keys of the `aggregations` parameter
                    "agg_name": {...}   #   and the values are the results of the aggregations
                }
            }

        :param script_fields: List of name/script tuple of fields to be evaluated at runtime
        :param track_total_hits: Return to total matching document count
        :param deep_paging_id: ID of the next page during deep paging searches
        :param as_obj: Return objects instead of dictionaries
        :param query: lucene query to search for
        :param offset: offset at which you want the results to start at (paging)
        :param rows: number of items that the search function should return
        :param sort: field to sort the data with
        :param fl: list of fields to return from the search
        :param timeout: maximum time of execution
        :param filters: additional queries to run on the original query to reduce the scope
        :param access_control: access control parameters to limiti the scope of the query
        :param aggregations: optional list of arbitrary aggregations to run alongside the query
            structured the same way as the es rest query aggs field
        :return: a search result object
        """
        if offset is None:
            offset = self.DEFAULT_OFFSET

        if rows is None:
            rows = self.DEFAULT_ROW_SIZE

        if sort is None:
            sort = self.DEFAULT_SORT

        if filters is None:
            filters = []
        elif isinstance(filters, str):
            filters = [filters]

        if access_control:
            filters.append(access_control)

        args = [
            ("query", query),
            ("start", offset),
            ("rows", rows),
            ("sort", sort),
            ("df", self.DEFAULT_SEARCH_FIELD),
        ]

        if fl:
            fl = self._expand_fl(fl)
            field_list = fl.split(",")
            args.append(("field_list", field_list))
        else:
            field_list = None

        if timeout:
            args.append(("timeout", "%sms" % timeout))

        if filters:
            args.append(("filters", filters))

        if script_fields:
            args.append(("script_fields", script_fields))

        if aggregations:
            args.append(("aggregations", aggregations))

        result = self._search(
            args,
            deep_paging_id=deep_paging_id,
            track_total_hits=track_total_hits,
        )

        ret_data: SearchResult | AggSearchResult
        ret_data = {
            "offset": int(offset),
            "rows": int(rows),
            "total": total_hits_value(result["hits"]["total"]),
            "items": [self._format_output(doc, field_list, as_obj=as_obj) for doc in result["hits"]["hits"]],
        }

        if aggregations:
            ret_data = {
                **ret_data,
                "aggregations": {
                    k[len(self.CUSTOM_AGG_PREFIX) :]: v
                    for k, v in result.get("aggregations", {}).items()
                    if k.startswith(self.CUSTOM_AGG_PREFIX)
                },
            }

        new_deep_paging_id = result.get("_scroll_id", None)

        # Check if the scroll is finished and close it
        if deep_paging_id is not None and new_deep_paging_id is None:
            try:
                self.with_retries(
                    self.datastore.client.clear_scroll,
                    scroll_id=[deep_paging_id],
                )
            except elasticsearch.exceptions.NotFoundError:
                pass

        # Check if we can tell from inspection that we have finished the scroll
        if new_deep_paging_id is not None and len(ret_data["items"]) < ret_data["rows"]:
            try:
                self.with_retries(
                    self.datastore.client.clear_scroll,
                    scroll_id=[new_deep_paging_id],
                )
            except elasticsearch.exceptions.NotFoundError:
                pass
            new_deep_paging_id = None

        if new_deep_paging_id is not None:
            ret_data["next_deep_paging_id"] = new_deep_paging_id

        return ret_data

    @overload
    def stream_search(
        self,
        query: str,
        fl: str | None = None,
        filters: list[str] | str | None = None,
        access_control: typing.Any = None,
        item_buffer_size: int = 200,
        *,
        as_obj: Literal[True] = True,
    ) -> typing.Generator[ModelType, None, None]: ...

    @overload
    def stream_search(
        self,
        query: str,
        fl: str | None = None,
        filters: list[str] | str | None = None,
        access_control: typing.Any = None,
        item_buffer_size: int = 200,
        *,
        as_obj: Literal[False],
    ) -> typing.Generator[dict[str, typing.Any], None, None]: ...

    def stream_search(
        self,
        query,
        fl=None,
        filters=None,
        access_control=None,
        item_buffer_size=200,
        as_obj=True,
    ):
        """This function should perform a search through the datastore and stream
        all related results as a dictionary of key value pair where each keys
        are one of the field specified in the field list parameter.

        >>> # noinspection PyUnresolvedReferences
        >>> {
        >>>     fl[0]: value,
        >>>     ...
        >>>     fl[x]: value
        >>> }

        :param as_obj: Return objects instead of dictionaries
        :param query: lucene query to search for
        :param fl: list of fields to return from the search
        :param filters: additional queries to run on the original query to reduce the scope
        :param access_control: access control parameters to run the query with
        :param buffer_size: number of items to buffer with each search call
        :return: a generator of dictionary of field list results
        """
        if item_buffer_size > 2000 or item_buffer_size < 50:
            raise SearchException("Variable item_buffer_size must be between 50 and 2000.")

        if filters is None:
            filters = []
        elif isinstance(filters, str):
            filters = [filters]

        if access_control:
            filters.append(access_control)

        if fl:
            fl = self._expand_fl(fl)
            fl = fl.split(",")

        query_expression = {
            "bool": {
                "must": {
                    "query_string": {
                        "query": query,
                        "default_field": self.DEFAULT_SEARCH_FIELD,
                    }
                },
                "filter": [{"query_string": {"query": ff}} for ff in filters],
            }
        }
        sort = parse_sort(self.datastore.DEFAULT_SORT)
        source = fl or list(self.stored_fields.keys())

        for value in self.scan_with_retry(
            query=query_expression,
            sort=sort,
            source=source,
            index=self.name,
            size=item_buffer_size,
        ):
            # Unpack the results, ensure the id is always set
            yield self._format_output(value, fl, as_obj=as_obj)

    def raw_eql_search(
        self,
        eql_query: str,
        fl: Optional[str] = None,
        filters: Optional[Union[list[str], str]] = None,
        rows: Optional[int] = None,
        timeout: Optional[int] = None,
        as_obj=True,
    ):
        if filters is None:
            filters = []
        elif isinstance(filters, str):
            filters = [filters]

        parsed_filters = {
            "bool": {
                "must": {"query_string": {"query": "*:*"}},
                "filter": [{"query_string": {"query": ff}} for ff in filters],
            }
        }

        if not fl:
            fl = "howler.id"
        else:
            fl = self._expand_fl(fl)

        if rows is None:
            rows = 5

        fields = [{"field": f} for f in fl.split(",")]

        try:
            response = self.with_retries(
                self.datastore.client.eql.search,
                index=self.name,
                timestamp_field="timestamp",
                query=eql_query,
                fields=fields,
                filter=parsed_filters,
                size=rows,
                wait_for_completion_timeout=(f"{timeout}ms" if timeout is not None else None),
                allow_partial_search_results=True,
                allow_partial_sequence_results=False,
            )
            result = _complete_eql_response(response)

            ret_data: dict[str, Any] = {
                "rows": int(rows),
                "total": total_hits_value(result["hits"]["total"]),
                "items": [
                    self._format_output(doc, fl.split(","), as_obj=as_obj) for doc in result["hits"].get("events", [])
                ],
                "sequences": [
                    [self._format_output(doc, fl.split(","), as_obj=as_obj) for doc in sequence.get("events", [])]
                    for sequence in result["hits"].get("sequences", [])
                ],
            }

            return ret_data

        except SearchException:
            raise
        except (elasticsearch.TransportError, elasticsearch.RequestError) as e:
            raise SearchException(error_message(e)) from e
        except Exception as error:
            raise SearchException(f"collection: {self.name}, error: {str(error)}")

    def keys(self, access_control=None):
        """This function streams the keys of all the documents of this collection.

        :param access_control: access control parameter to limit the scope of the key scan
        :return: a generator of keys
        """
        for item in self.stream_search("id:*", fl="id", access_control=access_control):
            if item is None:
                continue

            try:
                yield cast(Any, item).meta.id
            except AttributeError:
                value = cast(Any, item)["id"]
                if isinstance(value, list):
                    for v in value:
                        yield v
                else:
                    yield value

    def _validate_steps_count(self, start, end, gap):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            gaps_count = None
            ret_type: Optional[type] = None

            try:
                start = int(start)
                end = int(end)
                gap = int(gap)

                gaps_count = int((end - start) / gap)
                ret_type = int
            except ValueError:
                pass

            if not gaps_count:
                try:
                    t_gap = gap.strip("+").strip("-")

                    parsed_start = dm(self.datastore.to_pydatemath(start)).int_timestamp
                    parsed_end = dm(self.datastore.to_pydatemath(end)).int_timestamp
                    parsed_gap = dm(self.datastore.to_pydatemath(f"+{t_gap}")).int_timestamp - dm("now").int_timestamp

                    gaps_count = int((parsed_end - parsed_start) / parsed_gap)
                    ret_type = str
                except (DateMathException, AttributeError):
                    pass

            if gaps_count is None:
                raise SearchException(
                    "Could not parse histogram ranges. Either you've mix integer and dates values or you "
                    "have invalid date math values. (start='%s', end='%s', gap='%s')" % (start, end, gap)
                )

            if gaps_count > self.MAX_FACET_LIMIT:
                raise SearchException(
                    f"Histograms are limited to a maximum of {self.MAX_FACET_LIMIT} steps. "
                    f"Current settings would generate {gaps_count} steps"
                )
            return ret_type

    def count(
        self,
        query,
        filters,
        access_control=None,
    ):
        """This function should perform a count operation through the datastore and return a
        search result object that consists of the following:

            {
                "count": 123456,  # Total number of documents matching the query
            }

        :param query: lucene query to search for
        :param access_control: access control parameters to limit the scope of the query
        :return: a count result object
        """
        if filters is None:
            filters = []
        elif isinstance(filters, str):
            filters = [filters]

        query_body: dict[str, Any] = {
            "query": {
                "bool": {
                    "must": {"query_string": {"query": query}},
                    "filter": [{"query_string": {"query": ff}} for ff in filters],
                }
            }
        }

        result = self.with_retries(self.datastore.client.count, index=self.name, **query_body)

        ret_data: dict[str, Any] = {
            "count": result["count"],
        }

        return ret_data

    def histogram(
        self,
        field,
        start,
        end,
        gap,
        query="id:*",
        mincount=None,
        filters=None,
        access_control=None,
    ):
        type_modifier = self._validate_steps_count(start, end, gap)
        start = type_modifier(start)
        end = type_modifier(end)
        gap = type_modifier(gap)

        if mincount is None:
            mincount = 1

        if filters is None:
            filters = []
        elif isinstance(filters, str):
            filters = [filters]
        filters.append("{field}:[{min} TO {max}]".format(field=field, min=start, max=end))

        args = [
            ("query", query),
            ("histogram_active", True),
            ("histogram_field", field),
            (
                "histogram_type",
                "date_histogram" if isinstance(gap, str) else "histogram",
            ),
            (
                "histogram_gap",
                gap.strip("+").strip("-") if isinstance(gap, str) else gap,
            ),
            ("histogram_mincount", mincount),
            ("histogram_start", start),
            ("histogram_end", end),
        ]

        if access_control:
            filters.append(access_control)

        if filters:
            args.append(("filters", filters))

        result = self._search(args)

        # Convert the histogram into a dictionary
        return {
            type_modifier(row.get("key_as_string", row["key"])): row["doc_count"]
            for row in result["aggregations"]["histogram"]["buckets"]
        }

    def facet(
        self,
        field,
        query=None,
        prefix=None,
        contains=None,
        ignore_case=False,
        sort=None,
        rows=10,
        mincount=None,
        filters=None,
        access_control=None,
        field_script=None,
    ):
        if not query:
            query = "id:*"

        if not mincount:
            mincount = 1

        if filters is None:
            filters = []
        elif isinstance(filters, str):
            filters = [filters]

        args = [
            ("query", query),
            ("facet_active", True),
            ("facet_fields", [field]),
            ("facet_mincount", mincount),
            ("rows", rows),
        ]

        # TODO: prefix, contains, ignore_case, sort

        if access_control:
            filters.append(access_control)

        if filters:
            args.append(("filters", filters))

        if field_script:
            args.append(("field_script", field_script))

        result = self._search(args)

        # Convert the histogram into a dictionary
        return {
            row.get("key_as_string", row["key"]): row["doc_count"] for row in result["aggregations"][field]["buckets"]
        }

    def stats(
        self,
        field,
        query="id:*",
        filters=None,
        access_control=None,
        field_script=None,
    ):
        if filters is None:
            filters = []
        elif isinstance(filters, str):
            filters = [filters]

        args = [
            ("query", query),
            ("stats_active", True),
            ("stats_fields", [field]),
            ("rows", 0),
        ]

        if access_control:
            filters.append(access_control)

        if filters:
            args.append(("filters", filters))

        if field_script:
            args.append(("field_script", field_script))

        result = self._search(args)
        return result["aggregations"][f"{field}_stats"]

    def grouped_search(
        self,
        group_field,
        query="id:*",
        offset=0,
        sort=None,
        group_sort=None,
        fl=None,
        limit=1,
        rows=None,
        filters=None,
        access_control=None,
        as_obj=True,
        track_total_hits=False,
    ):
        if rows is None:
            rows = self.DEFAULT_ROW_SIZE

        if sort is None:
            sort = self.DEFAULT_SORT

        if group_sort is None:
            group_sort = self.DEFAULT_SORT

        if filters is None:
            filters = []
        elif isinstance(filters, str):
            filters = [filters]

        args = [
            ("query", query),
            ("group_active", True),
            ("group_field", group_field),
            ("group_limit", limit),
            ("group_sort", group_sort),
            ("start", offset),
            ("rows", rows),
            ("sort", sort),
        ]

        filters.append("%s:*" % group_field)

        if fl:
            fl = self._expand_fl(fl)
            field_list = fl.split(",")
            args.append(("field_list", field_list))
        else:
            field_list = None

        if access_control:
            filters.append(access_control)

        if filters:
            args.append(("filters", filters))

        result = self._search(args, track_total_hits=track_total_hits)

        return {
            "offset": offset,
            "rows": rows,
            "total": total_hits_value(result["hits"]["total"]),
            "items": [
                {
                    "value": collapsed["fields"][group_field][0],
                    "total": total_hits_value(collapsed["inner_hits"]["group"]["hits"]["total"]),
                    "items": [
                        self._format_output(row, field_list, as_obj=as_obj)
                        for row in collapsed["inner_hits"]["group"]["hits"]["hits"]
                    ],
                }
                for collapsed in result["hits"]["hits"]
            ],
        }

    @staticmethod
    def _get_odm_type(ds_type):
        try:
            return BACK_MAPPING[ds_type].__name__.lower()
        except KeyError:
            return ds_type.lower()

    @staticmethod
    def _flatten_mapping_properties(props: dict[str, Any]) -> dict[str, Any]:
        """Flatten a raw ES mapping ``properties`` tree into dotted leaf entries.

        Compound object sub-schemas (with their own ``properties``) are recursively inlined
        under dotted paths; a materialized dynamic-key entry (e.g. a live ``labels.some_key``
        created by a document) is indistinguishable from - and handled identically to - a
        statically declared compound field, matching the legacy behavior exactly.
        """
        out: dict[str, Any] = {}
        for name, value in props.items():
            if "properties" in value:
                for child, cprops in ESCollection._flatten_mapping_properties(value["properties"]).items():
                    out[name + "." + child] = cprops
            elif "type" in value:
                out[name] = value
            else:
                raise HowlerValueError("Unknown field data " + str(props))
        return out

    def fields(self, skip_mapping_children=False):
        """
        This function should return all the fields in the index with their types
        """
        if self.schema_model is not None:
            return self._fields_from_schema(skip_mapping_children)

        data = self.with_retries(self.datastore.client.indices.get, index=self.name)
        index_name = list(data.keys())[0]
        properties = self._flatten_mapping_properties(data[index_name]["mappings"].get("properties", {}))

        if self.model_class:
            model_fields = self.model_class.flat_fields()
        else:
            model_fields = {}

        collection_data = {}

        for p_name, p_val in properties.items():
            if p_name.startswith("_") or "//" in p_name:
                continue
            if not self.FIELD_SANITIZER.match(p_name):
                continue
            field_model = model_fields.get(p_name, None)

            if "." in p_name:
                parent_p_name = re.sub(r"^(.+)\..+?$", r"\1", p_name)
                if parent_p_name in model_fields and isinstance(model_fields.get(parent_p_name), Mapping):
                    if parent_p_name not in collection_data:
                        field_model = model_fields.get(parent_p_name, None)
                        f_type = self._describe_type(p_val, None)

                        collection_data[parent_p_name] = {
                            "default": self.DEFAULT_SEARCH_FIELD in p_val.get("copy_to", []),
                            "indexed": self._describe_indexed(p_val, None),
                            "list": field_model.multivalued if field_model else False,
                            "stored": field_model.store if field_model else False,
                            "type": f_type,
                            "description": (field_model.description if field_model else ""),
                            "regex": (
                                field_model.child_type.validation_regex.pattern
                                if field_model
                                and (
                                    issubclass(type(field_model.child_type), ValidatedKeyword)
                                    or issubclass(type(field_model.child_type), IP)
                                )
                                else None
                            ),
                            "values": (
                                list(field_model.child_type.values)
                                if field_model and issubclass(type(field_model.child_type), Enum)
                                else None
                            ),
                            "deprecated_description": (field_model.deprecated_description if field_model else ""),
                        }

                        if skip_mapping_children:
                            continue
                    else:
                        continue

            f_type = self._describe_type(p_val, None)
            collection_data[p_name] = {
                "default": self.DEFAULT_SEARCH_FIELD in p_val.get("copy_to", []),
                "indexed": self._describe_indexed(p_val, None),
                "list": field_model.multivalued if field_model else False,
                "stored": field_model.store if field_model else False,
                "deprecated": field_model.deprecated if field_model else False,
                "type": f_type,
                "description": field_model.description if field_model else "",
                "regex": (
                    field_model.validation_regex.pattern
                    if field_model
                    and (issubclass(type(field_model), ValidatedKeyword) or issubclass(type(field_model), IP))
                    else None
                ),
                "values": list(field_model.values) if field_model and issubclass(type(field_model), Enum) else None,
                "deprecated_description": (field_model.deprecated_description if field_model else ""),
            }

        collection_data.pop("id", None)

        return collection_data

    def _live_mapping_properties(self) -> tuple[dict[str, dict[str, Any]], set[str]]:
        """Return per-index flattened mapping properties and the union of all dotted paths."""
        data = self.with_retries(self.datastore.client.indices.get_mapping, index=self.name)
        flattened_by_index: dict[str, dict[str, Any]] = {}
        all_paths: set[str] = set()
        for index_name, index_data in data.items():
            flattened = self._flatten_mapping_properties(index_data.get("mappings", {}).get("properties", {}))
            flattened_by_index[index_name] = flattened
            all_paths.update(flattened.keys())
        return flattened_by_index, all_paths

    def _reconciled_property(self, p_name: str, flattened_by_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
        """Return a field's mapping body, raising if it conflicts across backing indices."""
        bodies = [flattened[p_name] for flattened in flattened_by_index.values() if p_name in flattened]
        if not bodies:
            return {}
        distinct = {json.dumps(body, sort_keys=True, default=str) for body in bodies}
        if len(distinct) > 1:
            raise HowlerRuntimeError(
                f"Field {p_name} has conflicting mappings across indices for collection {self.name}: {sorted(distinct)}"
            )
        return bodies[0]

    def _live_field_capabilities(self) -> dict[str, dict[str, Any]]:
        """Return the ``fields`` section of a live ``field_caps`` call across this collection."""
        response = self.with_retries(self.datastore.client.field_caps, index=self.name, fields="*")
        body = getattr(response, "body", response)
        return dict(body.get("fields", {}))

    def _reconciled_capability(self, p_name: str, caps_fields: dict[str, dict[str, Any]]) -> Optional[dict[str, Any]]:
        """Return a field's single capability body, raising if it is ambiguous/conflicting."""
        caps = caps_fields.get(p_name)
        if not caps:
            return None
        if len(caps) > 1:
            raise HowlerRuntimeError(
                f"Field {p_name} has conflicting types across indices for collection {self.name}: {sorted(caps)}"
            )
        return next(iter(caps.values()))

    @staticmethod
    def _describe_type(p_val: dict[str, Any], type_caps: Optional[dict[str, Any]]) -> str:
        source = p_val.get("analyzer") or p_val.get("type")
        if source is None and type_caps is not None:
            source = type_caps.get("type")
        return ESCollection._get_odm_type(source or "keyword")

    @staticmethod
    def _describe_indexed(p_val: dict[str, Any], type_caps: Optional[dict[str, Any]]) -> bool:
        if type_caps is not None and "searchable" in type_caps:
            return bool(type_caps["searchable"])
        return p_val.get("index", p_val.get("enabled", True))

    @staticmethod
    def _mapping_child_metadata(field_definition):
        """Return the Howler field metadata for a Mapping/FlattenedObject field's value type."""
        if field_definition is None:
            return None
        return field_metadata(new_schema.mapping_value_annotation(field_definition))

    def _fields_from_schema(self, skip_mapping_children=False):  # noqa: C901
        """``fields()`` computed from live ``field_caps``/mapping introspection + the new schema.

        Uses Elasticsearch ``field_caps`` (type/searchable/aggregatable across every backing
        alias/rollover index) as the primary signal, supplemented by a live mapping GET for
        details ``field_caps`` does not expose (``analyzer``, ``copy_to``, ``enabled``), and
        ``model_registry`` for description/list(multivalued)/stored/deprecated/regex/values.
        Multi-index/multi-type conflicts are raised explicitly rather than silently resolved by
        picking an arbitrary index. Preserves the exact legacy return shape and the legacy
        Mapping-child de-duplication quirk (only the first live dynamic key of a given ``Mapping``
        field gets its own entry, in addition to the parent-summary entry).
        """
        model_fields = model_registry.flat_fields(self.schema_model)
        flattened_by_index, all_paths = self._live_mapping_properties()
        caps_fields = self._live_field_capabilities()

        collection_data: dict[str, Any] = {}

        for p_name in sorted(all_paths):
            if p_name.startswith("_") or "//" in p_name:
                continue
            if not self.FIELD_SANITIZER.match(p_name):
                continue

            p_val = self._reconciled_property(p_name, flattened_by_index)
            type_caps = self._reconciled_capability(p_name, caps_fields)
            field_model = model_fields.get(p_name)

            if "." in p_name:
                parent_p_name = re.sub(r"^(.+)\..+?$", r"\1", p_name)
                parent_definition = model_fields.get(parent_p_name)
                parent_is_mapping = (
                    parent_definition is not None
                    and parent_definition.metadata is not None
                    and parent_definition.metadata.kind in new_schema.DYNAMIC_KEY_KINDS
                )
                if parent_is_mapping:
                    if parent_p_name not in collection_data:
                        field_model = parent_definition
                        f_type = self._describe_type(p_val, type_caps)
                        child_metadata = self._mapping_child_metadata(field_model)
                        child_options = dict(child_metadata.options) if child_metadata else {}

                        collection_data[parent_p_name] = {
                            "default": self.DEFAULT_SEARCH_FIELD in p_val.get("copy_to", []),
                            "indexed": self._describe_indexed(p_val, type_caps),
                            "list": field_model.multivalued if field_model else False,
                            "stored": bool(field_model.metadata.store)
                            if field_model and field_model.metadata
                            else False,
                            "type": f_type,
                            "description": (field_model.description if field_model else ""),
                            "regex": child_options.get("validation_regex"),
                            "values": (list(child_options["values"]) if "values" in child_options else None),
                            "deprecated_description": (
                                field_model.metadata.deprecated_description
                                if field_model and field_model.metadata
                                else ""
                            ),
                        }

                        if skip_mapping_children:
                            continue
                    else:
                        continue

            f_type = self._describe_type(p_val, type_caps)
            options = dict(field_model.metadata.options) if field_model and field_model.metadata else {}
            collection_data[p_name] = {
                "default": self.DEFAULT_SEARCH_FIELD in p_val.get("copy_to", []),
                "indexed": self._describe_indexed(p_val, type_caps),
                "list": field_model.multivalued if field_model else False,
                "stored": bool(field_model.metadata.store) if field_model and field_model.metadata else False,
                "deprecated": (
                    bool(field_model.metadata.deprecated) if field_model and field_model.metadata else False
                ),
                "type": f_type,
                "description": field_model.description if field_model else "",
                "regex": options.get("validation_regex"),
                "values": list(options["values"]) if "values" in options else None,
                "deprecated_description": (
                    field_model.metadata.deprecated_description if field_model and field_model.metadata else ""
                ),
            }

        collection_data.pop("id", None)

        return collection_data

    def _ilm_policy_exists(self):
        try:
            self.datastore.client.ilm.get_lifecycle(name=f"{self.name}_policy")
        except elasticsearch.NotFoundError:
            return False
        else:
            return True

    def _delete_ilm_policy(self):
        try:
            self.datastore.client.ilm.delete_lifecycle(name=f"{self.name}_policy")
        except elasticsearch.ApiError:
            return False
        else:
            return True

    def _create_ilm_policy(self, ilm_config):
        """Create or update the ILM policy for this collection.

        Builds an ILM policy with hot (rollover), optional warm (forcemerge),
        and optional cold phases. No delete phase — retention is handled by
        the retention cronjob.

        The ``ilm_config`` parameter (global :class:`ILMConfig`) is used **only**
        for the hot phase rollover settings (``rollover_max_age`` and
        ``rollover_max_size``). Warm and cold phase configuration is sourced
        exclusively from ``self.ilm_config`` (the per-index :class:`ILMIndexConfig`).

        :param ilm_config: The global ILMConfig with rollover settings (hot phase only).
        """
        phases: dict[str, Any] = {
            "hot": {
                "min_age": "0ms",
                "actions": {
                    "rollover": {
                        "max_age": ilm_config.rollover_max_age,
                        "max_primary_shard_size": ilm_config.rollover_max_size,
                    }
                },
            }
        }

        if self.ilm_config and self.ilm_config.warm:
            warm_actions: dict[str, Any] = {}
            if self.ilm_config.warm_forcemerge_segments is not None:
                warm_actions["forcemerge"] = {"max_num_segments": self.ilm_config.warm_forcemerge_segments}
            phases["warm"] = {
                "min_age": self.ilm_config.warm,
                "actions": warm_actions,
            }

        if self.ilm_config and self.ilm_config.cold:
            # Note: forcemerge is NOT allowed in the cold phase by ES.
            # Cold phase is typically just for storage tier allocation.
            phases["cold"] = {
                "min_age": self.ilm_config.cold,
                "actions": {},
            }

        policy = {"phases": phases}

        self.with_retries(
            self.datastore.client.ilm.put_lifecycle,
            name=f"{self.name}_policy",
            policy=policy,
        )
        logger.info("ILM policy %s_policy created/updated", self.name)

    def _create_index_template(self, ilm_config):
        """Create or update a composable index template for ILM-managed rollover.

        The template matches '{name}-*' and includes the full registered mappings
        so that rollover indices inherit the correct schema.

        :param ilm_config: The global ILMConfig (unused directly but kept for symmetry).
        """
        if self.schema_model is not None:
            template = new_schema.ilm_template_body(
                self.schema_model,
                shards=self.shards,
                replicas=self.replicas,
                policy_name=f"{self.name}_policy",
                rollover_alias=self.name,
            )
        else:
            settings = self._get_index_settings()
            settings["index"]["lifecycle.name"] = f"{self.name}_policy"
            settings["index"]["lifecycle.rollover_alias"] = self.name
            template = {
                "settings": settings,
                "mappings": self._get_index_mappings(),
            }

        self.with_retries(
            self.datastore.client.indices.put_index_template,
            name=f"{self.name}_template",
            index_patterns=[f"{self.name}-*"],
            template=template,
        )
        logger.info("Index template %s_template created/updated", self.name)

    def _get_index_settings(self) -> dict:
        if self.schema_model is not None:
            return new_schema.index_settings(self.schema_model, shards=self.shards, replicas=self.replicas)

        default_stub: dict = deepcopy(default_index)
        settings: dict = default_stub.pop("settings", {})

        if "index" not in settings:
            settings["index"] = {}
        settings["index"]["number_of_shards"] = self.shards
        settings["index"]["number_of_replicas"] = self.replicas

        if "mapping" not in settings["index"]:
            settings["index"]["mapping"] = {}

        if "total_fields" not in settings["index"]["mapping"]:
            settings["index"]["mapping"]["total_fields"] = {}

        limit = len(self.model_class.flat_fields()) + 500 if self.model_class else 1500
        if limit < 1500:
            limit = 1500
        elif limit > 1500:
            logger.warning("ODM field size is larger than 1500 - set to %s", limit)
        settings["index"]["mapping"]["total_fields"]["limit"] = limit

        return settings

    def _get_index_mappings(self) -> dict:
        if self.schema_model is not None:
            return new_schema.document_mapping(self.schema_model)

        mappings: dict = deepcopy(default_mapping)
        if self.model_class:
            mappings["properties"], mappings["dynamic_templates"] = build_mapping(self.model_class.fields().values())
            mappings["dynamic_templates"].insert(0, default_dynamic_strings)
        else:
            mappings["dynamic_templates"] = deepcopy(default_dynamic_templates)

        if not mappings["dynamic_templates"]:
            # Setting dynamic to strict prevents any documents with fields not in the properties to be added
            mappings["dynamic"] = "strict"

        mappings["properties"]["id"] = {
            "store": True,
            "doc_values": True,
            "type": "keyword",
        }

        mappings["properties"]["__text__"] = {
            "store": False,
            "type": "text",
        }

        return mappings

    def __get_possible_fields(self, field):
        field_types = [field.__name__.lower()]
        if field.__bases__[0] != _Field:
            field_types.extend(self.__get_possible_fields(field.__bases__[0]))

        if field_type := TYPE_MAPPING.get(field.__name__, None):
            field_types.append(field_type)

        return field_types

    def _check_fields(self, model=None):
        if not self.validate:
            return

        if self.schema_model is not None:
            return self._check_fields_from_schema()

        if model is None:
            if self.model_class:
                return self._check_fields(self.model_class)

            return

        if self.model_class is None:
            return

        fields = self.fields()
        model = self.model_class.flat_fields(skip_mappings=True)

        missing = set(model.keys()) - set(fields.keys())
        if missing:
            self._add_fields_with_limit_retry(
                {key: model[key] for key in missing},
                self._add_fields,
            )

        matching = set(fields.keys()) & set(model.keys())
        for field_name in matching:
            if fields[field_name]["indexed"] != model[field_name].index and model[field_name].index:
                raise HowlerRuntimeError(f"Field {field_name} should be indexed but is not.")

            possible_field_types = self.__get_possible_fields(model[field_name].__class__)

            if fields[field_name]["type"] not in possible_field_types:
                raise HowlerRuntimeError(
                    f"Field {field_name} didn't have the expected store "
                    f"type. [{fields[field_name]['type']} != "
                    f"{model[field_name].__class__.__name__.lower()}]"
                )

    def _add_fields_with_limit_retry(
        self,
        missing_fields: dict[str, Any],
        add_fields: Callable[[dict[str, Any]], None],
    ) -> None:
        """Add fields, expanding only this collection's physical-index limit when required."""
        try:
            add_fields(missing_fields)
        except elasticsearch.BadRequestError as err:
            if not (
                err.body
                and isinstance(err.body, dict)
                and "error" in err.body
                and "reason" in err.body["error"]
                and str(err.body["error"]["reason"]).startswith("Limit of total fields")
            ):
                raise

            reason = str(err.body["error"]["reason"])
            current_count = int(re.sub(r".+\[(\d+)].+", r"\1", reason))
            logger.warning("Current field cap %s is too low, increasing to %s", current_count, current_count + 500)
            self.with_retries(
                self.datastore.client.indices.put_settings,
                index=self.index_list_full,
                settings={"index.mapping.total_fields.limit": current_count + 500},
            )
            add_fields(missing_fields)

    def _live_dynamic_templates(self) -> dict[str, list[dict[str, Any]]]:
        """Return each backing index's dynamic templates in Elasticsearch precedence order."""
        data = self.with_retries(self.datastore.client.indices.get_mapping, index=self.name)
        return {
            index_name: list(index_data.get("mappings", {}).get("dynamic_templates", []))
            for index_name, index_data in data.items()
        }

    def _check_dynamic_templates(self) -> None:
        """Refuse missing/changed templates while tolerating harmless obsolete live templates.

        Adding or changing a dynamic template after documents already exist can silently change
        how *future* dynamic keys are typed without touching already-indexed data, so any expected
        template that is missing from a backing index or has changed is refused explicitly rather
        than "fixed" automatically. Extra templates left by a disabled plugin do not alter fields
        generated by the active schema and are retained with a warning.
        """
        expected_templates = new_schema.document_mapping(self.schema_model)["dynamic_templates"]
        expected_order = [next(iter(template)) for template in expected_templates]
        expected_by_key = {next(iter(template)): template[next(iter(template))] for template in expected_templates}

        unsafe: set[str] = set()
        extra: set[str] = set()
        reordered_indices: list[str] = []
        live_templates_by_index = self._live_dynamic_templates()
        if not live_templates_by_index:
            unsafe.update(expected_by_key)

        for index_name, templates in live_templates_by_index.items():
            live_order = [next(iter(template)) for template in templates]
            live_by_key = {next(iter(template)): template[next(iter(template))] for template in templates}
            unsafe.update(
                key
                for key, expected in expected_by_key.items()
                if key not in live_by_key or live_by_key[key] != expected
            )
            if [key for key in live_order if key in expected_by_key] != expected_order:
                reordered_indices.append(index_name)
            extra.update(live_by_key.keys() - expected_by_key.keys())

        if unsafe or reordered_indices:
            details = sorted(unsafe)
            if reordered_indices:
                details.append(f"order differs on {sorted(reordered_indices)}")
            raise HowlerValueError(
                f"Refusing to add or change dynamic mapping templates automatically for collection "
                f"{self.name}: {details}. Dynamic template changes require an explicit "
                "index/template migration."
            )

        if extra:
            logger.warning(
                "Collection %s retains dynamic templates not used by the active schema: %s",
                self.name,
                sorted(extra),
            )

    @staticmethod
    def _normalized_mapping_value(name: str, body: dict[str, Any], field_type: str) -> Any:
        if name == "index":
            return body.get("index", body.get("enabled", True))
        if name == "doc_values":
            return body.get("doc_values", field_type not in {"object", "nested", "text"})
        if name == "copy_to":
            copy_to = body.get("copy_to", ())
            return (copy_to,) if isinstance(copy_to, str) else tuple(copy_to)
        if name == "enabled":
            return body.get("enabled", True)
        return body.get(name)

    def _check_schema_field(
        self,
        path: str,
        expected: dict[str, Any],
        live: dict[str, Any],
        capability: Optional[dict[str, Any]],
    ) -> None:
        """Raise when an existing live field is incompatible with the generated schema."""
        expected_type = cast(str, expected.get("type"))
        live_type = cast(str, capability.get("type") if capability is not None else live.get("type"))
        if expected_type != live_type:
            raise HowlerRuntimeError(
                f"Field {path} didn't have the expected store type. [{live_type} != {expected_type}]"
            )

        expected_indexed = self._normalized_mapping_value("index", expected, expected_type)
        live_indexed = (
            bool(capability["searchable"])
            if capability is not None and "searchable" in capability
            else self._normalized_mapping_value("index", live, live_type)
        )
        if expected_indexed != live_indexed:
            raise HowlerRuntimeError(f"Field {path} has incompatible indexing. [{live_indexed} != {expected_indexed}]")

        for option in ("analyzer", "normalizer", "format", "ignore_above", "copy_to", "enabled", "doc_values"):
            expected_value = self._normalized_mapping_value(option, expected, expected_type)
            live_value = self._normalized_mapping_value(option, live, live_type)
            if expected_value != live_value:
                raise HowlerRuntimeError(
                    f"Field {path} has incompatible {option}. [{live_value!r} != {expected_value!r}]"
                )

    def _check_fields_from_schema(self) -> None:
        """``_check_fields`` computed from the finalized new schema model.

        Compares the schema's expected flat/explicit properties (and the model's expected
        dynamic templates) to the live index via :meth:`fields`/:meth:`_live_dynamic_templates`.
        Missing *safe* explicit fields (plain leaf properties, never a new/changed dynamic
        template) are added across every physical index; anything that would require a new or
        changed dynamic template is refused. Total-field-limit expansion on the existing
        Elasticsearch error path is preserved unchanged.
        """
        self._check_dynamic_templates()

        expected_properties = new_schema.document_mapping(self.schema_model)["properties"]
        flattened_by_index, live_paths = self._live_mapping_properties()
        capabilities = self._live_field_capabilities()

        for path, expected in expected_properties.items():
            if path not in live_paths:
                continue
            live = self._reconciled_property(path, flattened_by_index)
            capability = self._reconciled_capability(path, capabilities)
            self._check_schema_field(path, expected, live, capability)

        missing_static = {path: props for path, props in expected_properties.items() if path not in live_paths}
        if missing_static:
            self._add_fields_with_limit_retry(missing_static, self._add_schema_fields)

    def _ensure_collection(self):
        """This function should test if the collection that you are trying to access does indeed exist
        and should create it if it does not.

        When ILM is configured for this collection, it sets up the ILM policy,
        composable index template, and bootstraps a rollover alias instead of
        using the legacy _hot index naming.

        :return:
        """
        if self.ilm_config:
            return self._ensure_collection_ilm()

        # Create HOT index
        if not self.with_retries(self.datastore.client.indices.exists, index=self.name):
            logger.debug("Index %s does not exist. Creating it now...", self.name.upper())
            try:
                self.with_retries(
                    self.datastore.client.indices.create,
                    index=self.index_name,
                    mappings=self._get_index_mappings(),
                    settings=self._get_index_settings(),
                    aliases={self.name: {}},
                )
            except elasticsearch.exceptions.RequestError as e:
                if "resource_already_exists_exception" not in str(e):
                    raise
                logger.warning("Tried to create an index template that already exists: %s", self.name.upper())
        elif not self.with_retries(
            self.datastore.client.indices.exists, index=self.index_name
        ) and not self.with_retries(self.datastore.client.indices.exists_alias, name=self.name):
            # Turn on write block
            self.with_retries(self.datastore.client.indices.put_settings, settings=write_block_settings)

            # Create a copy on the result index
            self._safe_index_copy(self.datastore.client.indices.clone, self.name, self.index_name)

            # Make the hot index the new clone
            self.with_retries(
                self.datastore.client.indices.update_aliases,
                actions=[
                    {"add": {"index": self.index_name, "alias": self.name}},
                    {"remove_index": {"index": self.name}},
                ],
            )

            self.with_retries(self.datastore.client.indices.put_settings, settings=write_unblock_settings)

        self._check_fields()

    def _ensure_collection_ilm(self):
        """Bootstrap an ILM-managed collection with rollover alias.

        1. Create/update the ILM policy and composable index template.
        2. Bootstrap the initial index if needed:
           - If ILM indices already exist (pattern {name}-0*), skip.
           - If a legacy _hot index exists, migrate it to {name}-000001.
           - Otherwise, create {name}-000001 from scratch.
        """
        from howler.odm.models.config import config as _config

        ilm_global = _config.datastore.ilm

        # The policy must exist before lifecycle settings are applied. The template is updated
        # only after existing mappings pass reconciliation, so a refused schema change cannot
        # leave future rollover indices on a partially-applied contract.
        self._create_ilm_policy(ilm_global)

        ilm_initial_index = f"{self.name}-000001"

        # Check if any ILM-managed index already exists
        existing_ilm_indices = list(
            self.with_retries(
                self.datastore.client.indices.get, index=f"{self.name}-0*", ignore_unavailable=True
            ).keys()
        )

        if existing_ilm_indices:
            # ILM already bootstrapped — ensure the alias exists
            latest = sorted(existing_ilm_indices)[-1]
            legacy_hot_index = f"{self.name}_hot"
            if self.with_retries(self.datastore.client.indices.exists_alias, name=self.name):
                alias_indices = self.with_retries(self.datastore.client.indices.get_alias, name=self.name)
                alias_actions = []
                for alias_index, alias_index_data in alias_indices.items():
                    alias_data = alias_index_data.get("aliases", {}).get(self.name, {})
                    if alias_index == legacy_hot_index:
                        alias_actions.append({"remove": {"index": alias_index, "alias": self.name}})
                    elif alias_index != latest and alias_data.get("is_write_index", False):
                        alias_actions.append(
                            {
                                "add": {
                                    "index": alias_index,
                                    "alias": self.name,
                                    **alias_data,
                                    "is_write_index": False,
                                }
                            }
                        )

                latest_alias_data = alias_indices.get(latest, {}).get("aliases", {}).get(self.name, {})
                if not latest_alias_data.get("is_write_index", False):
                    alias_actions.append(
                        {
                            "add": {
                                "index": latest,
                                "alias": self.name,
                                **latest_alias_data,
                                "is_write_index": True,
                            }
                        }
                    )

                if alias_actions:
                    self.with_retries(self.datastore.client.indices.update_aliases, actions=alias_actions)
            else:
                # Find the latest index to set as write index
                self.with_retries(
                    self.datastore.client.indices.put_alias,
                    index=latest,
                    name=self.name,
                    is_write_index=True,
                )

            self.index_name = latest
            logger.debug("ILM collection %s already bootstrapped", self.name.upper())
        elif self.with_retries(self.datastore.client.indices.exists, index=self.index_name):
            # Legacy _hot index exists — migrate to ILM
            logger.info("Migrating %s from legacy _hot index to ILM-managed rollover", self.name.upper())

            # Block writes on the old index
            self.with_retries(
                self.datastore.client.indices.put_settings,
                index=self.index_name,
                settings=write_block_settings,
            )

            # Everything after write-block must be wrapped in try/except to ensure
            # we unblock writes if migration fails — otherwise ingestion is stuck.
            try:
                # Clone the _hot index to the new ILM initial index
                self._safe_index_copy(self.datastore.client.indices.clone, self.index_name, ilm_initial_index)

                # Apply ILM settings to the new index
                self.with_retries(
                    self.datastore.client.indices.put_settings,
                    index=ilm_initial_index,
                    settings={
                        "index.lifecycle.name": f"{self.name}_policy",
                        "index.lifecycle.rollover_alias": self.name,
                        "index.blocks.write": None,
                    },
                )

                # Swap alias: remove old _hot, add new ILM index as write index
                actions = [
                    {"add": {"index": ilm_initial_index, "alias": self.name, "is_write_index": True}},
                ]

                # Remove old alias if it points to _hot
                if self.with_retries(self.datastore.client.indices.exists_alias, index=self.index_name, name=self.name):
                    actions.append({"remove": {"index": self.index_name, "alias": self.name}})

                self.with_retries(self.datastore.client.indices.update_aliases, actions=actions)

            except Exception:
                # Migration failed — rollback to restore ingestion to the old index
                logger.exception(
                    "Migration of %s to ILM failed. Rolling back write-block on %s.",
                    self.name.upper(),
                    self.index_name,
                )

                # Unblock writes on the old index so ingestion can resume
                try:
                    self.with_retries(
                        self.datastore.client.indices.put_settings,
                        index=self.index_name,
                        settings=write_unblock_settings,
                    )
                    logger.info("Rollback successful: writes restored to %s", self.index_name)
                except Exception as rollback_err:
                    logger.critical(
                        "CRITICAL: Rollback failed for %s — index may be write-blocked! Error: %s",
                        self.index_name,
                        str(rollback_err),
                    )

                # Clean up partially-created ILM index if it exists
                try:
                    if self.with_retries(self.datastore.client.indices.exists, index=ilm_initial_index):
                        self.with_retries(self.datastore.client.indices.delete, index=ilm_initial_index)
                        logger.info("Cleaned up partial ILM index %s", ilm_initial_index)
                except Exception:
                    logger.warning(
                        "Could not clean up partial ILM index %s — manual cleanup may be needed",
                        ilm_initial_index,
                    )

                # Re-raise the original exception so startup fails clearly
                raise

            # Unblock writes on the old index (it stays around until manually removed)
            self.with_retries(
                self.datastore.client.indices.put_settings,
                index=self.index_name,
                settings=write_unblock_settings,
            )

            # Update index_name to point to the ILM initial index
            self.index_name = ilm_initial_index

            logger.info("Migration of %s to ILM complete", self.name.upper())
        else:
            # Fresh install — create the initial ILM index with alias
            logger.debug("Creating ILM-managed index %s...", ilm_initial_index)
            settings = self._get_index_settings()
            settings["index"]["lifecycle.name"] = f"{self.name}_policy"
            settings["index"]["lifecycle.rollover_alias"] = self.name

            try:
                self.with_retries(
                    self.datastore.client.indices.create,
                    index=ilm_initial_index,
                    mappings=self._get_index_mappings(),
                    settings=settings,
                    aliases={self.name: {"is_write_index": True}},
                )
            except elasticsearch.exceptions.RequestError as e:
                if "resource_already_exists_exception" not in str(e):
                    raise
                logger.warning("ILM index already exists: %s", ilm_initial_index)

            # Update index_name to point to the ILM initial index
            self.index_name = ilm_initial_index

        self._check_fields()
        self._create_index_template(ilm_global)

    def _add_fields(self, missing_fields: Dict):
        no_fix = []
        properties = {}
        for name, field in missing_fields.items():
            # Figure out the path of the field in the document, if the name is set in the field, it
            # is going to be duplicated in the path from missing_fields, so drop it
            prefix = name.split(".")
            if field.name:
                prefix = prefix[:-1]

            # Build the fields and templates for this new mapping
            sub_properties, sub_templates = build_mapping([field], prefix=prefix, allow_refuse_implicit=False)
            properties.update(sub_properties)
            if sub_templates:
                no_fix.append(name)

        # If we have collected any fields that we can't just blindly add, as they might conflict
        # with existing things, (we might have the refuse_all_implicit_mappings rule in place)
        # simply raise an exception
        if no_fix:
            raise HowlerValueError(
                f"Can't update database mapping for {self.name}, couldn't safely amend mapping for {no_fix}"
            )

        self._put_mapping_properties(properties)

    def _add_schema_fields(self, missing_fields: dict[str, Any]) -> None:
        """Add already-built, safe explicit schema properties (never dynamic-template-governed).

        Unlike :meth:`_add_fields`, ``missing_fields`` values here are already complete ES
        property bodies produced by ``howler.models.schema.build_properties``, so no further
        mapping/template construction is needed before uploading them.
        """
        self._put_mapping_properties({path: deepcopy(body) for path, body in missing_fields.items()})

    def _put_mapping_properties(self, properties: dict[str, Any]) -> None:
        # Upload the new properties to every physical index backing this collection, update the
        # legacy top-level template if one exists, and refresh the ILM composable template.
        for index in self.index_list_full:
            self.with_retries(self.datastore.client.indices.put_mapping, index=index, properties=properties)

        if self.with_retries(self.datastore.client.indices.exists_template, name=self.name):
            current_template = self.with_retries(self.datastore.client.indices.get_template, name=self.name)[self.name]
            self.with_retries(
                self.datastore.client.indices.put_template,
                name=self.name,
                **recursive_update(current_template, {"mappings": {"properties": properties}}),
            )

        # When ILM is enabled, also update the composable index template so
        # future rollover indices inherit the new field mappings.
        if self.ilm_config:
            from howler.odm.models.config import config as _config

            self._create_index_template(_config.datastore.ilm)

    def wipe(self):
        """This function should completely delete the collection

        NEVER USE THIS!

        :return:
        """
        logger.debug("Wipe operation started for collection: %s" % self.name.upper())

        for index in self.index_list:
            if self.with_retries(self.datastore.client.indices.exists, index=index):
                self.with_retries(self.datastore.client.indices.delete, index=index)

        if self.with_retries(self.datastore.client.indices.exists_template, name=self.name):
            self.with_retries(self.datastore.client.indices.delete_template, name=self.name)

        self._ensure_collection()
