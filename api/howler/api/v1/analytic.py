import typing
from typing import Any, Optional

from flask import Response, request

from howler.api import (
    bad_request,
    forbidden,
    make_subapi_blueprint,
    no_content,
    not_found,
    ok,
)
from howler.common.exceptions import HowlerException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.cronjobs.rules import register_rules
from howler.datastore.exceptions import DataStoreException
from howler.datastore.operations import OdmHelper
from howler.odm.models.analytic import Analytic, Comment, Notebook, TriageOptions
from howler.odm.models.template import Template
from howler.odm.models.user import User
from howler.security import api_login
from howler.services import analytic_service, user_service

MAX_COMMENT_LEN = 5000
SUB_API = "analytic"
analytic_api = make_subapi_blueprint(SUB_API, api_version=1)
analytic_api._doc = "Manage the analytics that create hits"

logger = get_logger(__file__)

analytic_helper = OdmHelper(Analytic)


@generate_swagger_docs()
@analytic_api.route("/", methods=["GET"])
@api_login(required_priv=["R"])
def get_analytics(**kwargs: Any) -> Response:
    """Get a list of analytics used to create hits in howler

    Variables:
    None

    Optional Arguments:
    None

    Result Example:
    [
        ...analytics    # A list of analytics
    ]
    """
    return ok(datastore().analytic.search("*:*", as_obj=False, rows=1000)["items"])


@generate_swagger_docs()
@analytic_api.route("/<id>", methods=["GET"])
@api_login(required_priv=["R"])
def get_analytic(id, **kwargs):
    """Get a specific analytic

    Variables:
    id => The id of the analytic to retrieve

    Optional Arguments:
    None

    Result Example:
    {
        ...analytic     # The requested analytic
    }
    """
    try:
        if not analytic_service.does_analytic_exist(id):
            return not_found(err="Analytic does not exist")

        return ok(analytic_service.get_analytic(id, as_obj=False))
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@analytic_api.route("/<id>", methods=["PUT"])
@api_login(required_priv=["R", "W"])
def update_analytic(id: str, user: User, **kwargs):
    """Update an analytic

    Variables:
    id => The id of the analytic to modify

    Optional Arguments:
    None

    Data Block:
    {
        ...analytic     # The new data to add
    }

    Result Example:
    {
        ...analytic     # The updated analytic data
    }
    """
    storage = datastore()

    if not storage.analytic.exists(id):
        return not_found(err="This analytic does not exist")

    new_data = request.json

    if not new_data:
        return bad_request(err="You must provide updated data.")

    try:
        existing_analytic: Analytic = storage.analytic.get_if_exists(id)

        existing_analytic.description = new_data.get("description", existing_analytic.description)

        if existing_analytic.triage_settings is not None:
            existing_triage_data = existing_analytic.triage_settings.as_primitives()
        else:
            existing_triage_data = {}

        existing_analytic.triage_settings = TriageOptions(
            {**existing_triage_data, **new_data.get("triage_settings", {})}
        )

        updated_rule = False
        if existing_analytic.rule_type:
            updated_rule = existing_analytic.rule != new_data.get(
                "rule", existing_analytic.rule
            ) or existing_analytic.rule_crontab != new_data.get("rule_crontab", existing_analytic.rule_crontab)

            existing_analytic.rule = new_data.get("rule", existing_analytic.rule)
            existing_analytic.rule_crontab = new_data.get("rule_crontab", existing_analytic.rule_crontab)

        storage.analytic.save(existing_analytic.analytic_id, existing_analytic)

        if updated_rule:
            # The registration process automatically deletes and resets the rule cronjob
            register_rules(existing_analytic)

        return ok(existing_analytic)
    except HowlerException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@analytic_api.route("/rules", methods=["POST"])
@api_login(required_priv=["R", "W"])
def create_rule(user: User, **kwargs):
    """Create a rule analytic

    Variables:
    None

    Optional Arguments:
    None

    Data Block:
    {
        "name": "Rule Name",
        "description": "*markdown* _description_"
    }

    Result Example:
    {
        ...analytic     # The created analytic rule
    }
    """
    storage = datastore()

    new_data: Optional[dict[str, Any]] = request.json

    if not new_data:
        return bad_request(err="You must provide rule data.")

    required_keys = {
        "name",
        "description",
        "rule",
        "rule_type",
        "rule_crontab",
    }

    for key in required_keys:
        if key not in new_data or not new_data[key]:
            return bad_request(err=f"You must provide a {key} for your rule.")

    extra_keys = set(new_data.keys()) - required_keys

    if len(extra_keys) > 0:
        return bad_request(err=f"Additional fields ({', '.join(extra_keys)}) are not permitted.")

    new_analytic = Analytic(
        {
            **new_data,
            "tags": ["rule"],
            "owner": user["uname"],
            "contributors": [user["uname"]],
            "detections": ["Rule"],
        }
    )

    new_template = Template(
        {
            "analytic": new_data["name"],
            "detection": "Rule",
            "type": "global",
            "owner": user["uname"],
            # TODO: Allow custom keys
            "keys": ["event.kind", "event.module", "event.reason", "event.type"],
        }
    )

    try:
        storage.analytic.save(new_analytic.analytic_id, new_analytic)
        # Have to commit so the analytic is available during registration
        storage.analytic.commit()
        register_rules(new_analytic)

        storage.template.save(new_template.template_id, new_template)

        return ok(new_analytic)
    except HowlerException as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@analytic_api.route("/<id>", methods=["DELETE"])
@api_login(audit=False, required_priv=["W"])
def delete_rule(id: str, user: User, **kwargs):
    """Delete a rule

    Variables:
    id  => id of the analytic whose comments we are deleting

    Optional Arguments:
    None

    Data Block:
    [
        ...comment_ids
    ]

    Result Example:
    {
    }
    """
    if not analytic_service.does_analytic_exist(id):
        return not_found(err=f"Analytic {id} does not exist")

    analytic: Analytic = analytic_service.get_analytic(id, as_obj=True)

    if not analytic.rule:
        return bad_request(err="This is not a rule analytic, and cannot be deleted.")

    if user["uname"] != analytic.owner and "admin" not in user["type"]:
        return forbidden(err="You cannot delete this analytic.")

    try:
        datastore().analytic.delete(analytic.analytic_id)
    except DataStoreException as e:
        return bad_request(err=str(e))

    return no_content()


@generate_swagger_docs()
@analytic_api.route("/<id>/comments", methods=["POST"])
@api_login(audit=False, required_priv=["W"])
def add_comment(id: str, user: dict[str, Any], **kwargs):
    """Add a comment

    Variables:
    id  => id of the analytic to add a comment to

    Optional Arguments:
    None

    Data Block:
    {
        detection: "Detection to comment on (optional)",
        value: "New comment value"
    }

    Result Example:
    {
        ...analytic            # The new data for the analytic
    }
    """
    comment = request.json
    if not isinstance(comment, dict):
        return bad_request(err="Incorrect data format!")

    comment_data = comment.get("value")
    if not comment_data:
        return bad_request(err="Value cannot be empty.")

    if len(comment_data) > MAX_COMMENT_LEN:
        return bad_request(err="Comment is too long.")

    if not analytic_service.does_analytic_exist(id):
        return not_found(err="Analytic %s does not exist" % id)

    analytic: Analytic = analytic_service.get_analytic(id, as_obj=True)

    try:
        analytic.comment.append(
            Comment(
                {
                    "user": user["uname"],
                    "value": comment_data,
                    "detection": comment.get("detection", None),
                }
            )
        )

        datastore().analytic.save(analytic.analytic_id, analytic)
    except DataStoreException as e:
        return bad_request(err=str(e))

    analytic = analytic_service.get_analytic(id)

    return ok(analytic)


@generate_swagger_docs()
@analytic_api.route("/<id>/comments/<comment_id>", methods=["PUT"])
@api_login(audit=False, required_priv=["W"])
def edit_comment(id: str, comment_id: str, user: dict[str, Any], **kwargs):
    """Edit a comment

    Variables:
    id          => id of the analytic the comment belongs to
    comment_id  => id of the comment we are editing

    Optional Arguments:
    None

    Data Block:
    {
        value: "New comment value"
    }

    Result Example:
    {
        ...analytic            # The new data for the analytic
    }
    """
    updated_comment = request.json
    if not isinstance(updated_comment, dict):
        return bad_request(err="Incorrect data format")

    if not analytic_service.does_analytic_exist(id):
        return not_found(err=f"Analytic {id} does not exist")

    comment_data: Optional[str] = updated_comment.get("value")
    if not comment_data:
        return bad_request(err="Value cannot be empty.")

    if len(comment_data) > MAX_COMMENT_LEN:
        return bad_request(err="Comment is too long.")

    analytic: Analytic = analytic_service.get_analytic(id, as_obj=True)

    comment: Optional[Comment] = next((c for c in analytic.comment if c.id == comment_id), None)

    if not comment:
        return not_found(err=f"Comment {comment_id} does not exist")

    if comment.user != user["uname"]:
        return forbidden(err="Cannot edit comment that wasn't made by you.")

    comment["value"] = comment_data
    comment["modified"] = "NOW"

    analytic.comment = [c if c.id != comment.id else comment for c in analytic.comment]

    try:
        datastore().analytic.save(analytic.analytic_id, analytic)
    except DataStoreException as e:
        return bad_request(err=str(e))

    return ok(analytic)


@generate_swagger_docs()
@analytic_api.route("/<id>/comments/<comment_id>/react", methods=["PUT"])
@api_login(audit=False, required_priv=["W"])
def react_comment(id: str, comment_id: str, user: dict[str, Any], **kwargs):
    """React to a comment

    Variables:
    id          => id of the analytic the comment belongs to
    comment_id  => id of the comment we are editing

    Optional Arguments:
    None

    Data Block:
    {
        type: "thumbsup"
    }

    Result Example:
    {
        ...analytic            # The new data for the analytic
    }
    """
    data = request.json
    if not isinstance(data, dict):
        return bad_request(err="Incorrect data format")

    react_data: Optional[str] = data.get("type")
    if not react_data:
        return bad_request(err="Type cannot be empty.")

    if not analytic_service.does_analytic_exist(id):
        return not_found(err=f"Analytic {id} does not exist")

    analytic: Analytic = analytic_service.get_analytic(id, as_obj=True)

    for comment in analytic.comment:
        if comment.id == comment_id:
            comment["reactions"] = {
                **comment.get("reactions", {}),
                user["uname"]: react_data,
            }

    datastore().analytic.save(analytic.analytic_id, analytic)

    return ok(analytic)


@generate_swagger_docs()
@analytic_api.route("/<id>/comments/<comment_id>/react", methods=["DELETE"])
@api_login(audit=False, required_priv=["W"])
def remove_react_comment(id: str, comment_id: str, user: dict[str, Any], **kwargs):
    """React to a comment

    Variables:
    id          => id of the analytic the comment belongs to
    comment_id  => id of the comment we are editing

    Optional Arguments:
    None

    Result Example:
    {
        ...analytic            # The new data for the analytic
    }
    """
    if not analytic_service.does_analytic_exist(id):
        return not_found(err=f"Analytic {id} does not exist")

    analytic: Analytic = analytic_service.get_analytic(id, as_obj=True)

    for comment in analytic.comment:
        if comment.id == comment_id:
            reactions = comment.get("reactions", {})
            reactions.pop(user["uname"], None)
            comment["reactions"] = {**reactions}

    datastore().analytic.save(analytic.analytic_id, analytic)

    return ok(analytic)


@generate_swagger_docs()
@analytic_api.route("/<id>/comments", methods=["DELETE"])
@api_login(audit=False, required_priv=["W"])
def delete_comments(id: str, user: User, **kwargs):
    """Delete a set of comments

    Variables:
    id  => id of the analytic whose comments we are deleting

    Optional Arguments:
    None

    Data Block:
    [
        ...comment_ids
    ]

    Result Example:
    {
    }
    """
    if not analytic_service.does_analytic_exist(id):
        return not_found(err=f"Analytic {id} does not exist")

    comment_ids: list[str] = request.json or []

    if len(comment_ids) == 0:
        return bad_request(err="Supply at least one comment to delete.")

    analytic: Analytic = analytic_service.get_analytic(id, as_obj=True)

    new_comments = []
    for comment in analytic.comment:
        if comment.id in comment_ids:
            if ("admin" not in user["type"]) and comment.user != user["uname"]:
                return forbidden(err="You cannot delete the comment of someone else.")

            continue

        new_comments.append(comment)

    analytic.comment = new_comments

    try:
        datastore().analytic.save(analytic.analytic_id, analytic)
    except DataStoreException as e:
        return bad_request(err=str(e))

    return no_content()


@generate_swagger_docs()
@analytic_api.route("/<id>/owner", methods=["POST"])
@api_login(required_priv=["W"])
def set_analytic_owner(id: str, user: dict[str, Any], **kwargs):
    """Set the analytic's owner

    Variables:
    id  => id of the analytic to claim

    Arguments:
    None

    Data Block:
    {
        "username": "admin"     # The username to set the owner as
    }

    Result Example:
    {
        ...analytic            # The claimed analytic
    }
    """
    if not analytic_service.does_analytic_exist(id):
        return not_found(err=f"Analytic {id} does not exist")

    data: dict[str, Any] = typing.cast(dict[str, Any], request.json)
    if not user_service.get_user(data["username"]):
        return not_found(err=f"User {data['username']} does not exist")

    analytic: Analytic = analytic_service.get_analytic(id, as_obj=True)

    analytic.owner = data["username"]

    ds = datastore()
    ds.analytic.save(analytic.analytic_id, analytic)
    ds.analytic.commit()

    return ok(analytic)


@generate_swagger_docs()
@analytic_api.route("/<id>/favourite", methods=["POST"])
@api_login(required_priv=["R", "W"])
def set_as_favourite(id, **kwargs):
    """Add an analytic to a list of the user's favourites

    Variables:
    id => The id of the analytic to add as a favourite

    Optional Arguments:
    None

    Data Block:
    {}  # Empty

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    storage = datastore()

    existing_analytic: Analytic = storage.analytic.get_if_exists(id)
    if not existing_analytic:
        return not_found(err="This analytic does not exist")

    try:
        current_user = storage.user.get_if_exists(kwargs["user"]["uname"])

        current_user["favourite_analytics"] = list(set(current_user.get("favourite_analytics", []) + [id]))

        storage.user.save(current_user["uname"], current_user)

        return ok()
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@analytic_api.route("/<id>/favourite", methods=["DELETE"])
@api_login(required_priv=["R", "W"])
def remove_as_favourite(id, **kwargs):
    """Remove an analytic from a list of the user's favourites

    Variables:
    id => The id of the analytic to remove as a favourite

    Optional Arguments:
    None

    Result Example:
    {
        "success": True     # If the operation succeeded
    }
    """
    storage = datastore()

    if not storage.analytic.exists(id):
        return not_found(err="This analytic does not exist")

    try:
        current_user = storage.user.get_if_exists(kwargs["user"]["uname"])

        current_user["favourite_analytics"] = list(
            filter(lambda f: f != id, current_user.get("favourite_analytics", []))
        )

        storage.user.save(current_user["uname"], current_user)

        return no_content()
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@analytic_api.route("/<id>/notebooks", methods=["POST"])
@api_login(audit=False, required_priv=["W"])
def add_notebook(id: str, user: dict[str, Any], **kwargs):
    """Add a notebook

    Variables:
    id  => id of the analytic to add a notebook to

    Optional Arguments:
    None

    Data Block:
    {
        value: "New notebook link",
        name: "New notebook name",
        detection: "Detection to add a notebook about (optional)",
    }

    Result Example:
    {
        ...analytic            # The new data for the analytic
    }
    """
    data = request.json
    if not isinstance(data, dict):
        return bad_request(err="Incorrect data format")

    link = data.get("value")
    name = data.get("name")
    detection = data.get("detection", None)

    if not link or not name:
        return bad_request(err="Value/Name cannot be empty.")

    if "nbgallery." not in link:
        return bad_request(err="Only nbgallery is supported for now.")

    if not analytic_service.does_analytic_exist(id):
        return not_found(err="Analytic %s does not exist" % id)

    analytic: Analytic = analytic_service.get_analytic(id, as_obj=True)

    try:
        analytic.notebooks.append(
            Notebook(
                {
                    "user": user["uname"],
                    "name": name,
                    "value": link,
                    "detection": detection if detection else None,
                }
            )
        )

        datastore().analytic.save(analytic.analytic_id, analytic)
    except DataStoreException as e:
        return bad_request(err=str(e))

    analytic = analytic_service.get_analytic(id)

    return ok(analytic)


@generate_swagger_docs()
@analytic_api.route("/<id>/notebooks", methods=["DELETE"])
@api_login(audit=False, required_priv=["W"])
def delete_notebook(id: str, user: User, **kwargs):
    """Delete a notebook

    Variables:
    id  => id of the analytic whose notebook we are deleting

    Optional Arguments:
    None

    Data Block:
    [
        notebook_id
    ]

    Result Example:
    {
    }
    """
    if not analytic_service.does_analytic_exist(id):
        return not_found(err=f"Analytic {id} does not exist")

    notebook_ids: list[str] = request.json or []

    if len(notebook_ids) == 0:
        return bad_request(err="A notebook id is necessary for deletion.")

    analytic: Analytic = analytic_service.get_analytic(id, as_obj=True)

    new_notebooks = []
    for notebook in analytic.notebooks:
        if notebook.id in notebook_ids:
            if ("admin" not in user["type"]) and notebook.user != user["uname"]:
                return forbidden(err="You cannot delete the notebook of someone else.")

            continue

        new_notebooks.append(notebook)

    analytic.notebooks = new_notebooks

    try:
        datastore().analytic.save(analytic.analytic_id, analytic)
    except DataStoreException as e:
        return bad_request(err=str(e))

    return no_content()
