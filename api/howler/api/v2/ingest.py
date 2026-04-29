import json
from typing import Any, cast

from flask import request
from mergedeep import Strategy, merge

from howler.api import bad_request, created, forbidden, internal_error, make_subapi_blueprint, no_content, not_found, ok
from howler.api.v1.utils.etag import add_etag
from howler.common.exceptions import HowlerException, HowlerValueError
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.config import config
from howler.datastore.collection import ESCollection
from howler.datastore.exceptions import DataStoreException
from howler.datastore.howler_store import INDEXES
from howler.datastore.operations import OdmHelper, OdmUpdateOperation
from howler.odm.models.hit import Hit
from howler.odm.models.observable import Observable
from howler.odm.models.user import User
from howler.remote.datatypes.queues.named import NamedQueue
from howler.security import api_login
from howler.services import hit_service, observable_service
from howler.utils.dict_utils import flatten

MAX_COMMENT_LEN = 5000

SUB_API = "ingest"
ingest_api = make_subapi_blueprint(SUB_API, api_version=2)
ingest_api._doc = "Manage the different records across indexes"  # type: ignore

FIELDS = Hit.flat_fields()

logger = get_logger(__file__)

hit_helper = OdmHelper(Hit)

# Persistent queue for the correlation worker to consume newly ingested hit IDs.
_ingestion_queue: NamedQueue[str] | None = None


def _get_ingestion_queue() -> NamedQueue[str]:
    """Return the shared ingestion queue, creating it on first use."""
    global _ingestion_queue

    if _ingestion_queue is None:
        _ingestion_queue = NamedQueue(
            "howler.ingestion_queue",
            host=config.core.redis.persistent.host,
            port=config.core.redis.persistent.port,
            private=False,
        )

    return _ingestion_queue


@generate_swagger_docs()
@ingest_api.route("/<index>", methods=["POST"])
@api_login(required_priv=["W"])
def create(index: str, user: User, **kwargs):
    """Create new records in a given index.

    Variables:
    index   => Index to ingest the records into

    Arguments:
    ignore_extra_values => Whether to ignore extra values not defined in the Hit model

    Data Block:
    [
        {
            ...hit
        },
        {
            ...hit
        }
    ]

    Result Example:
    {
        "ids": ["id1", "id2"],
        "warnings": []
    }
    """
    if "," in index:
        return bad_request(err="You cannot create in multiple indexes.")

    hits = request.json

    if hits is None:
        return bad_request(err="No records were sent.")

    if not isinstance(hits, list):
        return bad_request(err="JSON Payload must be a list of records.")
    ignore_extra_values = request.args.get("ignore_extra_values", False, type=lambda v: v.lower() == "true")

    ids: list[str] = []
    warnings = []
    for i, hit in enumerate(hits):
        try:
            odm: Hit | Observable
            if index == "observable":
                odm, _warnings = observable_service.convert_observable(
                    hit, unique=True, ignore_extra_values=ignore_extra_values
                )
                observable_service.create_observable(odm.howler.id, odm, user.uname, skip_exists=True)
            else:
                odm, _warnings = hit_service.convert_hit(hit, unique=True, ignore_extra_values=ignore_extra_values)
                hit_service.create_hit(odm.howler.id, odm, user.uname, skip_exists=True)

            ids.append(odm.howler.id)
            warnings.extend(_warnings)
        except HowlerException as e:
            logger.exception("Ingestion failed.")
            return bad_request(err=f"Ingestion failure on record at index {i}: {e}")

    # Enqueue newly created hit IDs for the correlation worker.
    if ids:
        try:
            _get_ingestion_queue().push(*ids)
        except Exception:
            logger.exception("Failed to enqueue hit IDs for correlation")

    return created(ids, warnings=warnings)


@generate_swagger_docs()
@ingest_api.route("/<indexes>", methods=["DELETE"])
@api_login(required_priv=["W"])
def delete(indexes: str, user: User, **kwargs):
    """Delete records, optionally across multiple indexes.

    Variables:
    indexes   => Comma-separated list of indexes to remove the records from

    Arguments:
    None

    Data Block:
    {
        [
            hitId, hitId, hitId
        ]
    }

    Result Example:
    {
     "success": True             # Deleting the hits succeded
    }
    """
    ids = request.json

    if ids is None:
        return bad_request(err="No hit ids were sent.")

    if "admin" not in user["type"]:
        return forbidden(err="Cannot delete hit, only administrators are permitted to delete.")

    index_list = indexes.split(",")

    ds = datastore()

    if non_existing_hit_ids := [id for id in ids if all(not ds[index].exists(id) for index in index_list)]:
        return not_found(err=f"Record ids [{','.join(non_existing_hit_ids)}] do not exist.")

    try:
        remaining = set(ids)
        for index in index_list:
            if not remaining:
                break

            existing = [record_id for record_id in remaining if ds[index].exists(record_id)]
            if not existing:
                continue

            for record_id in existing:
                ds[index].delete(record_id)

            remaining -= set(existing)
            ds[index].commit()
    except DataStoreException as e:
        return internal_error(err=str(e))

    return no_content()


@generate_swagger_docs()
@ingest_api.route("/<index>/validate", methods=["POST"])
def validate(index: str, **kwargs):
    """Validates records.

    Variables:
    index  => The index to validate against

    Arguments:
    None

    Data Block:
    {
        [
            {
                ...hit
            },
            {
                ...hit
            }
        ]
    }

    Result Example:
    {
        "valid": [
            {
                ...hit
            },
            {
                ...hit
            }
        ],
        "invalid": [
            {
                "input": { ...hit },
                "error": "Id already exists"
            },
            {
                "input": { ...hit },
                "error": "Object 'HowlerData' expected a parameter named: score"
            }
        ]
    }
    """
    hits = request.json

    if "," in index:
        return bad_request(err="You cannot validate across multiple indexes.")

    if hits is None:
        return bad_request(err="No hits were sent.")

    validation: dict[str, list[dict[str, Any]]] = {"valid": [], "invalid": []}

    for hit in hits:
        try:
            if index == "observable":
                observable_service.convert_observable(hit, unique=True)
            else:
                hit_service.convert_hit(hit, unique=True)
            validation["valid"].append(hit)
        except HowlerException as e:
            validation["invalid"].append({"input": hit, "error": str(e)})

    return ok(validation)


@generate_swagger_docs()
@ingest_api.route("/<index>/<id>/overwrite", methods=["PATCH"])
@api_login(audit=False, required_priv=["W"])
@add_etag()
def overwrite(index: str, id: str, **kwargs):
    """Overwrite a record.

    Variables:
    index    => Index of the record you would like to update
    id       => Id of the record you would like to update

    Arguments:
    replace => Should lists of values be replaced or merged?

    Data Block:
    {
        ...record
    }

    Result Example:
    https://github.com/CybercentreCanada/howler-api/blob/develop/howler/odm/models/hit.py
    https://github.com/CybercentreCanada/howler-api/blob/develop/howler/odm/models/observable.py
    """
    if "," in index:
        return bad_request(err="You cannot overwrite across multiple indexes.")

    ds = datastore()

    record = ds[index].get(id, as_obj=False, version=False)
    if not record:
        return not_found(err="Record %s does not exist" % id)

    new_fields = request.json
    if not isinstance(new_fields, dict):
        return bad_request(err="The JSON payload must be a subset of a valid record.")

    try:
        odm = INDEXES[index]

        # TODO: This is inefficient. We can use elastic's `update` command to just directly patch the document
        new_record = cast(
            dict[str, Any],
            merge(
                flatten(record, odm=odm),
                flatten(new_fields, odm=odm),
                strategy=Strategy.REPLACE
                if bool(request.args.get("replace", False, type=lambda v: v.lower() == "true"))
                else Strategy.ADDITIVE,
            ),
        )

        ds[index].save(id, odm(new_record) if odm else new_record, version=kwargs.get("server_version"))

        new_record, new_version = ds[index].get(id, as_obj=False, version=True)

        return ok(new_record), new_version
    except HowlerValueError as e:
        return bad_request(err=e.message)


@generate_swagger_docs()
@ingest_api.route("/<indexes>/update", methods=["PUT"])
@api_login(audit=False, required_priv=["W"])
def update_by_query(indexes: str, **kwargs):
    """Update a set of hits using a query.

    Variables:
    indexes => Comma-separated list of indexes to update

    Arguments:
    None

    Data Block:
    {
        "query": "howler.id:*",
        "operations": [
            ("SET", "howler.assignment", "user"),
            ("REMOVE", "howler.labels.generic", "some_label")
        ]
    }

    Result Example:
    {
        "success": True
    }
    """
    data = cast(dict[str, Any], request.json)

    try:
        query = cast(str, data["query"])
        operations = cast(list[tuple[str, str, Any]], data["operations"])

        explanation: list[str] = []
        for operation, key, value in operations:
            # Just using this for validation
            OdmUpdateOperation(operation, key, value)
            explanation.append(f"- `{operation}` - `{key}` - `{json.dumps(value)}`")

        operations.append(
            (
                ESCollection.UPDATE_APPEND,
                "howler.log",
                {
                    "timestamp": "NOW",
                    "explanation": f"Hit updated by {kwargs['user']['uname']}\n\n" + "\n".join(explanation),
                    "user": kwargs["user"]["uname"],
                },
            )
        )

        ds = datastore()

        return ok({"success": all(ds[index].update_by_query(query, operations) for index in indexes.split(","))})
    except (HowlerValueError, KeyError, DataStoreException) as e:
        return bad_request(err=str(e))
    except Exception as e:
        return internal_error(err=str(e))
