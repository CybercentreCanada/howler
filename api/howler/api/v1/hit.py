import difflib
import json
from typing import Any, Optional, cast

from flask import request
from mergedeep import Strategy, merge

from howler.api import (
    bad_request,
    conflict,
    created,
    forbidden,
    internal_error,
    make_subapi_blueprint,
    no_content,
    not_found,
    ok,
)
from howler.api.v1.utils.etag import add_etag
from howler.common.exceptions import (
    HowlerException,
    HowlerValueError,
    InvalidDataException,
)
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.collection import ESCollection
from howler.datastore.exceptions import DataStoreException, VersionConflictException
from howler.datastore.operations import OdmHelper, OdmUpdateOperation
from howler.helper.workflow import WorkflowException
from howler.odm.models.hit import Hit
from howler.odm.models.howler_data import Comment, HitOperationType, HitStatusTransition
from howler.odm.models.user import User
from howler.security import api_login
from howler.services import action_service, analytic_service, event_service, hit_service
from howler.utils.str_utils import sanitize_lucene_query

MAX_COMMENT_LEN = 5000

SUB_API = "hit"
hit_api = make_subapi_blueprint(SUB_API, api_version=1)
hit_api._doc = "Manage the different hits in the system"

FIELDS = Hit.flat_fields()

logger = get_logger(__file__)

hit_helper = OdmHelper(Hit)


@generate_swagger_docs()
@hit_api.route("/", methods=["POST"])
@api_login(required_priv=["W"])
def create_hits(user: User, **kwargs):
    """Create hits.

    Variables:
    None

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

    if hits is None:
        return bad_request(err="No hits were sent.")

    response_body: dict[str, list[Any]] = {"valid": [], "invalid": []}
    odms = []
    ignore_extra_values: bool = bool(request.args.get("ignore_extra_values", False, type=lambda v: v.lower() == "true"))
    logger.debug(f"ignore_extra_values = {ignore_extra_values}")
    warnings = []
    for hit in hits:
        try:
            odm, _warnings = hit_service.convert_hit(hit, unique=True, ignore_extra_values=ignore_extra_values)
            response_body["valid"].append(odm.as_primitives())
            odms.append(odm)
            warnings.extend(_warnings)
        except HowlerException as e:
            logger.warning(f"{type(e).__name__} when saving new hit!")
            logger.warning(e)
            response_body["invalid"].append({"input": hit, "error": str(e)})

    if len(response_body["invalid"]) == 0:
        if len(odms) > 0:
            for odm in odms:
                # Ensure all ids are consistent
                if odm.event is not None:
                    odm.event.id = odm.howler.id
                hit_service.create_hit(odm.howler.id, odm, user=user["uname"])
                analytic_service.save_from_hit(odm, user)

            datastore().hit.commit()

            action_service.bulk_execute_on_query(f"howler.id:({' OR '.join(odm.howler.id for odm in odms)})", user=user)

        response_body["warnings"] = warnings

        return created(response_body, warnings=warnings)
    else:
        err_msg = ", ".join(item["error"] for item in response_body["invalid"])

        return bad_request(response_body, err=err_msg, warnings=warnings)


@generate_swagger_docs()
@hit_api.route("/", methods=["DELETE"])
@api_login(required_priv=["W"])
def delete_hits(user: User, **kwargs):
    """Delete hits.

    Variables:
    None

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
    hit_ids = request.json

    if hit_ids is None:
        return bad_request(err="No hit ids were sent.")

    if "admin" not in user["type"]:
        return forbidden(err="Cannot delete hit, only admin is allowed to delete")

    non_existing_hit_ids = [hit_id for hit_id in hit_ids if not hit_service.exists(hit_id)]

    if len(non_existing_hit_ids) == 1:
        return not_found(err=f"Hit id {non_existing_hit_ids[0]} does not exist.")

    if len(non_existing_hit_ids) > 1:
        return not_found(err=f"Hit ids {', '.join(non_existing_hit_ids)} do not exist.")

    for hit_id in hit_ids:
        if not hit_service.exists(hit_id):
            return not_found(err=f"Hit id {hit_id} does not exist.")

    hit_service.delete_hits(hit_ids)

    return no_content()


@generate_swagger_docs()
@hit_api.route("/validate", methods=["POST"])
def validate_hits(**kwargs):
    """Validates hits.

    Variables:
    None

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

    if hits is None:
        return bad_request(err="No hits were sent.")

    validation: dict[str, list[dict[str, Any]]] = {"valid": [], "invalid": []}

    for hit in hits:
        try:
            hit_service.convert_hit(hit, unique=True)
            validation["valid"].append(hit)
        except HowlerException as e:
            validation["invalid"].append({"input": hit, "error": str(e)})

    return ok(validation)


@generate_swagger_docs()
@hit_api.route("/<id>", methods=["GET"])
@api_login(audit=False, required_priv=["R"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def get_hit(id: str, server_version: str, **kwargs):
    """Get a hit.

    Variables:
    id       => Id of the hit you would like to get

    Arguments:
    None

    Result Example:
    https://github.com/CybercentreCanada/howler-api/blob/main/howler/odm/models/hit.py
    """
    hit = cast(Optional[Hit], kwargs.get("cached_hit"))

    if not hit:
        return not_found(err="Hit %s does not exist" % id)

    return ok(hit), server_version


@generate_swagger_docs()
@hit_api.route("/<id>/overwrite", methods=["PUT"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def overwrite_hit(id: str, server_version: str, **kwargs):
    """Overwrite a hit.

    Instead of providing a list of operations to run, provide a partial hit object to overwrite many fields at once.

    Variables:
    id       => Id of the hit you would like to update

    Arguments:
    replace => Should lists of values be replaced or merged?

    Data Block:
    {
        ...hit
    }

    Result Example:
    https://github.com/CybercentreCanada/howler-api/blob/main/howler/odm/models/hit.py
    """
    hit = cast(Optional[Hit], kwargs.get("cached_hit"))

    if not hit:
        return not_found(err="Hit %s does not exist" % id)

    new_fields = request.json

    if not isinstance(new_fields, dict):
        return bad_request(err="The JSON payload must be a subset of a valid Hit object.")

    try:
        new_hit = merge(
            hit_service.flatten(hit.as_primitives(), odm=Hit),
            hit_service.flatten(new_fields),
            strategy=Strategy.REPLACE
            if bool(request.args.get("replace", False, type=lambda v: v.lower() == "true"))
            else Strategy.ADDITIVE,
        )

        new_hit, new_version = hit_service.save_hit(Hit(new_hit), server_version)

        return ok(new_hit), new_version
    except HowlerValueError as e:
        return bad_request(err=e.message)


@generate_swagger_docs()
@hit_api.route("/<id>/update", methods=["PUT"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def update_hit(id: str, server_version: str, **kwargs):
    """Update a hit.

    Variables:
    id       => Id of the hit you would like to update

    Arguments:
    None

    Data Block:
    [
        ("SET", "howler.assignment", "user"),
        ("REMOVE", "howler.labels.generic", "some_label")
    ]

    Result Example:
    https://github.com/CybercentreCanada/howler-api/blob/main/howler/odm/models/hit.py
    """
    hit = cast(Optional[Hit], kwargs.get("cached_hit"))

    if not hit:
        return not_found(err="Hit %s does not exist" % id)

    try:
        attempted_operations = cast(list[tuple[str, str, Any]], request.json)

        operations: list[OdmUpdateOperation] = []

        explanation: list[str] = []

        for operation, key, value in attempted_operations:
            operations.append(OdmUpdateOperation(operation, key, value, silent=True))
            explanation.append(f"- `{operation}` - `{key}` - `{json.dumps(value)}`")

        operations.append(
            OdmUpdateOperation(
                ESCollection.UPDATE_APPEND,
                "howler.log",
                {
                    "timestamp": "NOW",
                    "previous_version": server_version,
                    "key": "howler.log",
                    "explanation": f"Hit updated by {kwargs['user']['uname']}\n\n" + "\n".join(explanation),
                    "new_value": "N/A",
                    "previous_value": "None",
                    "type": HitOperationType.APPENDED,
                    "user": kwargs["user"]["uname"],
                },
                silent=True,
            )
        )

        new_hit, new_version = hit_service.update_hit(
            hit.howler.id, operations, kwargs["user"]["uname"], server_version
        )

        event_service.emit("hits", {"hit": new_hit, "version": new_version})

        return ok(new_hit), new_version
    except HowlerValueError as e:
        return bad_request(err=e.message)


@generate_swagger_docs()
@hit_api.route("/update", methods=["PUT"])
@api_login(audit=False, required_priv=["W"])
def update_by_query(**kwargs):
    """Update a set of hits using a query.

    Variables:
    None

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

        datastore().hit.update_by_query(query, operations)

        return ok({"success": True})
    except (HowlerValueError, KeyError, DataStoreException) as e:
        return bad_request(err=str(e))
    except Exception as e:
        return internal_error(err=str(e))


@generate_swagger_docs()
@hit_api.route("/user", methods=["GET"])
@api_login(audit=True, required_priv=["R"])
def get_assigned_hits(user, **kwargs):
    """Get hits assigned to the user.

    Variables:
    None

    Arguments:
    deep_paging_id   =>   ID of the next page or * to start deep paging
    offset           =>   Offset in the results
    rows             =>   Number of results per page
    sort             =>   How to sort the results (not available in deep paging)
    fl               =>   List of fields to return
    timeout          =>   Maximum execution time (ms)

    Result Example:
    {
        [
            hit1,
            hit2
        ]
    }

    https://github.com/CybercentreCanada/howler-api/blob/main/howler/odm/models/hit.py
    """
    uname = user["uname"]

    hits = hit_service.search(
        query=f"howler.assignment:{sanitize_lucene_query(uname)}",
        deep_paging_id=request.args.get("deep_paging_id", None),
        offset=request.args.get("offset", 0, type=int),  # type: ignore[union-attr]
        rows=request.args.get("rows", None, type=int),  # type: ignore[union-attr]
        sort=request.args.get("sort", None),
        fl=request.args.get("fl", None),
        timeout=request.args.get("timeout", None),
        as_obj=False,
    )["items"]

    return ok(hits)


@generate_swagger_docs()
@hit_api.route("/<id>/labels/<label_set>", methods=["PUT"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def add_label(id, label_set, user, **kwargs):
    """Add labels to a hit.

    Variables:
    id          => id of the hit to add labels to
    label_set   => the label set to add to

    Optional Arguments:
    None

    Data Block:
    {
        "value": ["label1", "label2"],        # Label values to add
    }

    Result Example:
    {
        "success": True             # Adding the label succeeded
    }
    """
    if not hit_service.does_hit_exist(id):
        return not_found(err=f"Hit {id} does not exist")

    existing_hit: Hit = hit_service.get_hit(id, as_odm=True)
    if f"howler.labels.{label_set}" not in existing_hit.flat_fields():
        return not_found(err=f"Label set {label_set} does not exist")

    label_data = request.json
    if not isinstance(label_data, dict):
        return bad_request("Invalid data format")

    labels: list[str] = label_data["value"]

    if not labels or len(labels) == 0:
        return bad_request(err="Labels were not provided")

    existing_labels = existing_hit[f"howler.labels.{label_set}"]

    if not set(labels).isdisjoint(set(existing_labels)):
        return bad_request(err=f"Cannot add duplicate labels: {set(labels) & set(existing_labels)}")

    hit_service.update_hit(
        id,
        [hit_helper.list_add(f"howler.labels.{label_set}", label) for label in labels],
        user["uname"],
    )

    datastore().hit.commit()

    action_service.bulk_execute_on_query(
        f"howler.id:{id}",
        trigger="add_label",
        user=user,
    )

    hit, version = hit_service.get_hit(id, version=True)

    return ok(hit), version


@generate_swagger_docs()
@hit_api.route("/<id>/labels/<label_set>", methods=["DELETE"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def remove_labels(id, label_set, user, **kwargs):
    """Remove labels from a hit.

    Variables:
    id          => id of the hit to remove labels from
    label_set   => label_set the label set to remove from

    Optional Arguments:
    None

    Data Block:
    {
        "value": ["label1", "label2"],        # Label values to remove
    }

    Result Example:
    {
        "success": True             # Removing the labels succeeded
    }
    """
    if not hit_service.does_hit_exist(id):
        return not_found(err=f"Hit {id} does not exist")

    if f"howler.labels.{label_set}" not in hit_service.get_hit(id, as_odm=True).flat_fields():
        return not_found(err=f"Label set {label_set} does not exist")

    label_data = request.json
    if not isinstance(label_data, dict):
        return bad_request("Invalid data format")

    labels: list[str] = label_data["value"]

    if not labels or len(labels) == 0:
        return bad_request(err="Labels were not provided")

    hit_service.update_hit(
        id,
        [hit_helper.list_remove(f"howler.labels.{label_set}", label) for label in labels],
        user["uname"],
    )

    datastore().hit.commit()

    action_service.bulk_execute_on_query(
        f"howler.id:{id}",
        trigger="remove_label",
        user=user,
    )

    hit, version = hit_service.get_hit(id, version=True)

    return ok(hit), version


@generate_swagger_docs()
@hit_api.route("/<id>/transition", methods=["POST"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=True)
def transition(id: str, user: User, **kwargs):
    """Transition a hit

    Variables:
    id          => id of the hit to transition

    Optional Arguments:
    None

    Data Block:
    {
        "transition": "release",        # Transition to execute
        "data": {},                 # Optional data used by the transition
    }

    Result Example:
    {
        ...hit            # The new data for the hit
    }
    """
    if not kwargs.get("cached_hit"):
        return not_found(err="Hit %s does not exist" % id)

    transition_data = request.json
    if not isinstance(transition_data, dict):
        return bad_request(err="Invalid data format")

    transition = transition_data["transition"]
    if "If-Match" in request.headers:
        version = request.headers["If-Match"]
    else:
        logger.warning("User is mising version - no If-Match header in request.")
        version = None

    try:
        if transition not in HitStatusTransition.list():
            return bad_request(
                (
                    f"Transition '{transition}' not supported. Please use one of the following: "
                    f"{HitStatusTransition.list()}"
                )
            )

        hit_service.transition_hit(id, transition, user, version, **kwargs, **transition_data.get("data", {}))
    except (WorkflowException, DataStoreException, InvalidDataException) as e:
        return bad_request(err=str(e))
    except VersionConflictException as e:
        return conflict(err=str(e))
    except HowlerException as e:
        return internal_error(err=str(e))

    hit, version = hit_service.get_hit(id, version=True)
    return ok(hit), version


@generate_swagger_docs()
@hit_api.route("/<id>/comments/<comment_id>", methods=["GET"])
@api_login(audit=False, required_priv=["R"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def get_comment(id: str, comment_id: str, user: User, server_version: str, **kwargs):
    """Get a comment associated with a particular hit

    Variables:
    id          => id of the hit corresponding to the comment
    comment_id  => the id of the comment to get

    Optional Arguments:
    None

    Result Example:
    See: https://github.com/CybercentreCanada/howler-api/blob/main/howler/odm/models/howler_data.py#L17
    """
    hit: Optional[Hit] = kwargs.get("cached_hit")
    if not hit:
        return not_found(err=f"Hit {id} does not exist")

    comment: Optional[Comment] = next((c for c in hit.howler.comment if c.id == comment_id), None)

    if not comment:
        return not_found(err=f"Comment {comment_id} does not exist")

    return ok(comment), server_version


@generate_swagger_docs()
@hit_api.route("/<id>/comments", methods=["POST"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def add_comment(id: str, user: dict[str, Any], **kwargs):
    """Add a comment

    Variables:
    id  => id of the hit to add a comment to

    Optional Arguments:
    None

    Data Block:
    {
        value: "New comment value"
    }

    Result Example:
    {
        ...hit            # The new data for the hit
    }
    """
    comment_data = request.json
    if not isinstance(comment_data, dict):
        return bad_request(err="Invalid data format")

    comment_value = comment_data.get("value", None)

    if not comment_value:
        return bad_request(err="Value cannot be empty.")

    if len(comment_value) > MAX_COMMENT_LEN:
        return bad_request(err="Comment is too long.")

    if not kwargs.get("cached_hit"):
        return not_found(err="Hit %s does not exist" % id)

    try:
        hit_service.update_hit(
            id,
            [
                hit_helper.list_add(
                    "howler.comment",
                    Comment({"user": user["uname"], "value": comment_value}),
                    explanation=f"Added a comment:\n\n{comment_value}",
                    if_missing=True,
                ),
            ],
            user["uname"],
        )
    except DataStoreException as e:
        return bad_request(err=str(e))

    hit, version = hit_service.get_hit(id, version=True)

    return ok(hit), version


@generate_swagger_docs()
@hit_api.route("/<id>/comments/<comment_id>", methods=["PUT"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def edit_comment(id: str, comment_id: str, user: dict[str, Any], **kwargs):
    """Edit a comment

    Variables:
    id          => id of the hit the comment belongs to
    comment_id  => id of the comment we are editing

    Optional Arguments:
    None

    Data Block:
    {
        value: "New comment value"
    }

    Result Example:
    {
        ...hit            # The new data for the hit
    }
    """
    comment_data = request.json
    if not isinstance(comment_data, dict):
        return bad_request(err="Invalid data format")

    comment_value = comment_data.get("value", None)

    if not comment_value:
        return bad_request(err="Value cannot be empty.")

    if len(comment_value) > MAX_COMMENT_LEN:
        return bad_request(err="Comment is too long.")

    if not hit_service.does_hit_exist(id):
        return not_found(err=f"Hit {id} does not exist")

    hit: Hit = kwargs["cached_hit"]

    comment: Optional[Comment] = next((c for c in hit.howler.comment if c.id == comment_id), None)

    if not comment:
        return not_found(err=f"Comment {comment_id} does not exist")

    if comment.user != user["uname"]:
        return forbidden(err="Cannot edit comment that wasn't made by you.")

    new_comment = comment.as_primitives()
    new_comment["value"] = comment_value
    new_comment["modified"] = "NOW"

    diff = []
    for line in difflib.unified_diff(comment.value.split("\n"), new_comment["value"].split("\n")):
        if line[:3] not in ("+++", "---", "@@ "):
            diff.append(line)

    (hit, version) = hit_service.update_hit(
        id,
        [
            hit_helper.list_remove("howler.comment", comment, silent=True),
            hit_helper.list_add(
                "howler.comment",
                new_comment,
                explanation="Edited a comment. Changes:\n\n````diff\n" + "\n".join(diff) + "\n````",
            ),
        ],
        user["uname"],
    )
    return ok(hit), version


@generate_swagger_docs()
@hit_api.route("/<id>/comments", methods=["DELETE"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def delete_comments(id: str, user: User, **kwargs):
    """Delete a set of comments

    Variables:
    id  => id of the hit whose comments we are deleting

    Optional Arguments:
    None

    Data Block:
    [
        ...comment_ids
    ]

    Result Example:
    {
        ...hit            # The new data for the hit
    }
    """
    if not hit_service.does_hit_exist(id):
        return not_found(err=f"Hit {id} does not exist")

    comment_ids: list[str] = request.json or []

    if len(comment_ids) == 0:
        return bad_request(err="Supply at least one comment to delete.")

    hit: Hit = kwargs["cached_hit"]
    comments = [comment for comment in hit.howler.comment if comment.id in comment_ids]

    if ("admin" not in user["type"]) and any(comment for comment in comments if comment.user != user["uname"]):
        return forbidden(err="You cannot delete the comment of someone else.")

    if len(comments) != len(comment_ids):
        missing_id = next(id for id in comment_ids if not any(comment for comment in comments if comment.id == id))
        return not_found(err=f"Comment with id {missing_id} not found")

    try:
        hit_service.update_hit(
            id,
            [
                hit_helper.list_remove(
                    "howler.comment",
                    comment,
                    "Deleted a comment",
                )
                for comment in comments
            ],
            user["uname"],
        )

    except DataStoreException as e:
        return bad_request(err=str(e))
    hit, version = hit_service.get_hit(id, version=True)
    return ok(hit), version


@generate_swagger_docs()
@hit_api.route("/<id>/comments/<comment_id>/react", methods=["PUT"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def react_comment(id: str, comment_id: str, user: dict[str, Any], **kwargs):
    """React to a comment

    Variables:
    id          => id of the hit the comment belongs to
    comment_id  => id of the comment we are editing

    Optional Arguments:
    None

    Data Block:
    {
        type: "thumbsup"
    }

    Result Example:
    {
        ...hit            # The new data for the hit
    }
    """
    react_data: Optional[str] = request.json
    if not isinstance(react_data, dict):
        return bad_request(err="Invalid data format")

    react_value = react_data.get("type", None)

    if not react_value:
        return bad_request(err="Type cannot be empty.")

    hit: Optional[Hit] = kwargs.get("cached_hit")
    if not hit:
        return not_found(err=f"Hit {id} does not exist")

    for comment in hit.howler.comment:
        if comment.id == comment_id:
            comment["reactions"] = {
                **comment.get("reactions", {}),
                user["uname"]: react_value,
            }

    new_hit, version = hit_service.save_hit(hit, version=kwargs.get("server_version"))

    return ok(new_hit), version


@generate_swagger_docs()
@hit_api.route("/<id>/comments/<comment_id>/react", methods=["DELETE"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def remove_react_comment(id: str, comment_id: str, user: dict[str, Any], **kwargs):
    """React to a comment

    Variables:
    id          => id of the hit the comment belongs to
    comment_id  => id of the comment we are editing

    Optional Arguments:
    None

    Result Example:
    {
        ...hit            # The new data for the hit
    }
    """
    hit: Optional[Hit] = kwargs.get("cached_hit")
    if not hit:
        return not_found(err=f"Hit {id} does not exist")

    for comment in hit.howler.comment:
        if comment.id == comment_id:
            reactions = comment.get("reactions", {})
            reactions.pop(user["uname"], None)
            comment["reactions"] = {**reactions}

    new_hit, version = hit_service.save_hit(hit, version=kwargs.get("server_version"))

    return ok(new_hit), version


@generate_swagger_docs()
@hit_api.route("/bundle", methods=["POST"])
@api_login(audit=False, required_priv=["W"])
def create_bundle(user: User, **kwargs):
    """Create a new bundle

    Variables:
    None

    Arguments:
    None

    Data Block:
    {
        "bundle": {
            ...hit          # A howler hit that will be used as a template for this new bundle
        },
        "hits": [...ids]    # A list of existing howler hits to add as children to the new bundle
    }

    Result Example:
    {
        ...hit      # The created bundle
    }
    """
    data = request.json
    if not isinstance(data, dict):
        return bad_request(err="Invalid data format")

    bundle_hit: Optional[dict[str, Any]] = data.get("bundle")

    if bundle_hit is None:
        return bad_request(err="You did not provide a bundle hit.")

    try:
        odm, _ = hit_service.convert_hit(bundle_hit, unique=True)
        odm.howler.is_bundle = True

        child_hits = data.get("hits", [])

        if len(odm.howler.hits) < 1 and len(child_hits) < 1:
            return bad_request(err="You did not provide any child hits.")

        for hit_id in child_hits:
            if hit_id not in odm.howler.hits:
                odm.howler.hits.append(hit_id)

        hit_service.create_hit(odm.howler.id, odm, user=user["uname"])
        analytic_service.save_from_hit(odm, user)

        for hit_id in odm.howler.hits:
            child_hit: Hit = hit_service.get_hit(hit_id, as_odm=True)

            if child_hit.howler.is_bundle:
                return bad_request(
                    err=f"You cannot specify a bundle as a child of another bundle - {child_hit.howler.id} is a bundle."
                )

            new_bundle_list = child_hit.howler.get("bundles", [])
            new_bundle_list.append(odm.howler.id)
            child_hit.howler.bundles = new_bundle_list
            datastore().hit.save(child_hit.howler.id, child_hit)

        return created(odm)
    except HowlerException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@hit_api.route("/bundle/<id>", methods=["PUT"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def update_bundle(id, **kwargs):
    """Update a hit's child hits. Can be used to convert an existing hit into a bundle, or to update an existing bundle.

    Variables:
    id  => The ID of the bundle to update

    Arguments:
    None

    Data Block:
    [
        ...ids
    ]

    Result Example:
    {
        ...hit      # The updated bundle
    }
    """
    bundle_hit: Hit = kwargs.get("cached_hit", None)
    if not bundle_hit:
        return not_found(err="This bundle does not exist.")

    hit_ids = request.json
    if not isinstance(hit_ids, list):
        return bad_request(err="Invalid data format")

    new_hit_list = bundle_hit.howler.as_primitives().get("hits", [])
    if bundle_hit.howler.is_bundle:
        for hit_id in hit_ids:
            if hit_id not in new_hit_list:
                new_hit_list.append(hit_id)
            else:
                return conflict(err=f"The hit {hit_id} is already in the bundle {bundle_hit.howler.id}.")
    else:
        new_hit_list = hit_ids

    bundle_hit.howler.hits = new_hit_list
    bundle_hit.howler.is_bundle = True

    try:
        for hit_id in new_hit_list:
            child_hit: Hit = hit_service.get_hit(hit_id, as_odm=True)

            if child_hit.howler.is_bundle:
                return bad_request(
                    err=f"You cannot specify a bundle as a child of another bundle - {child_hit.howler.id} is a bundle."
                )

            new_bundle_list = child_hit.howler.as_primitives().get("bundles", [])
            new_bundle_list.append(bundle_hit.howler.id)
            child_hit.howler.bundles = new_bundle_list
            datastore().hit.save(child_hit.howler.id, child_hit)

        datastore().hit.save(bundle_hit.howler.id, bundle_hit)

        return ok(bundle_hit)
    except HowlerException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@hit_api.route("/bundle/<id>", methods=["DELETE"])
@api_login(audit=False, required_priv=["W"])
@add_etag(getter=hit_service.get_hit, check_if_match=False)
def remove_bundle_children(id, **kwargs):
    """Remove a bundle's child hits.

    Can be used to convert an existing bundle back into a normal hit, or to remove a subset of
    existing hits from the bundle.

    Variables:
    id  => The ID of the bundle to update

    Arguments:
    None

    Data Block:
    [
        ...ids OR '*'   # A list of ids to remove, or a single '*' to remove all
    ]

    Result Example:
    {
        ...hit      # The updated hit
    }
    """
    bundle_hit = kwargs.get("cached_hit", None)
    if not bundle_hit:
        return not_found(err="This bundle does not exist.")

    hit_ids = request.json
    if not isinstance(hit_ids, list):
        return bad_request(err="Invalid data format")

    new_hit_list = bundle_hit.howler.get("hits", [])
    if bundle_hit.howler.is_bundle:
        if hit_ids == ["*"]:
            hit_ids = new_hit_list
            new_hit_list = []
        else:
            new_hit_list = [_id for _id in new_hit_list if _id not in hit_ids]
    else:
        return bad_request(err="The specified hit must be a bundle.")

    bundle_hit.howler.hits = new_hit_list
    bundle_hit.howler.is_bundle = len(new_hit_list) > 0

    try:
        for hit_id in hit_ids:
            child_hit: Hit = hit_service.get_hit(hit_id, as_odm=True)

            new_bundle_list = child_hit.howler.get("bundles", [])
            try:
                new_bundle_list.remove(bundle_hit.howler.id)
            except ValueError:
                logger.warning("Bundle isn't included in child %s!", bundle_hit.howler.id)
            child_hit.howler.bundles = new_bundle_list

            datastore().hit.save(child_hit.howler.id, child_hit)

        datastore().hit.save(bundle_hit.howler.id, bundle_hit)

        return ok(bundle_hit)
    except HowlerException as e:
        return bad_request(err=str(e))
