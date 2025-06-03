import re
from hashlib import sha256
from typing import Any, Optional

from flask import request

import howler.services.user_service as user_service
from howler.api import bad_request, forbidden, internal_error, make_subapi_blueprint, no_content, not_found, ok
from howler.api.v1.utils.etag import add_etag
from howler.common.exceptions import (
    AccessDeniedException,
    AuthenticationException,
    HowlerException,
    HowlerValueError,
    InvalidDataException,
)
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.config import config
from howler.helper.oauth import fetch_groups
from howler.odm.models.user import User
from howler.security import api_login
from howler.security.utils import check_password_requirements, get_password_hash, get_password_requirement_message

SUB_API = "user"
user_api = make_subapi_blueprint(SUB_API, api_version=1)
user_api._doc = "Manage the different users of the system"

logger = get_logger(__file__)


@generate_swagger_docs()
@user_api.route("/whoami", methods=["GET"])
@api_login(required_priv=["R"], enforce_quota=False)
def who_am_i(**kwargs):
    """Return the currently logged in user as well as the system configuration

    Variables:
    None

    Arguments:
    None

    Result Example:
    {
      "avatar": "data:image/jpg...",                 # Avatar data block
      "classification": "TLP:W",                     # Classification of the user
      "configuration": {                             # Configuration block
        "auth": {                                    # Authentication Configuration
          "allow_apikeys": True,                     # Are APIKeys allowed for the user
          "allow_extended_apikeys": True,            # Allow user to generate extended access API Keys
        },
        "system": {                                  # System Configuration
          "type": "production",                      # Type of deployment
          "version": "4.1"                           # Howler version
        },
        "ui": {                                      # UI Configuration
          "apps": [],                                # List of apps shown in the apps switcher
          "banner": None,                            # Banner displayed on the submit page
          "banner_level": True,                      # Banner color (info, success, warning, error)
        }
      },
      "email": "basic.user@assemblyline.local",      # Email of the user
      "groups": ["USERS"],                           # Groups the user if member of
      "is_active": True,                             # Is the user active
      "name": "Basic user",                          # Name of the user
      "type": ["user", "admin"],                     # Roles the user is member of
      "username": "sgaron-cyber"                     # Username of the current user
    }

    """
    return ok(user_service.convert_user(kwargs["user"]))


@generate_swagger_docs()
@user_api.route("/<username>", methods=["POST"])
@api_login(required_type=["admin"])
def add_user_account(username, **_):
    """Add a user to the system

    Variables:
    username    => Name of the user to add

    Arguments:
    None

    Data Block:
    {
     "name": "Test user",        # Name of the user
     "is_active": true,          # Is the user active?
     "classification": "",       # Max classification for user
     "uname": "usertest",        # Username
     "type": ['user'],           # List of all types the user is member of
     "avatar": null,             # Avatar of the user
     "groups": ["TEST"]          # Groups the user is member of
    }

    Result Example:
    {
     "success": true             # Saving the user info succeded
    }
    """
    data = request.json
    if not isinstance(data, dict):
        return bad_request(err="Invalid data format")

    if "{" in username or "}" in username:
        return bad_request(err="You can't use '{}' in the username")

    storage = datastore()
    if storage.user.get_if_exists(username):
        return bad_request(err="The username you are trying to add already exists.")

    new_pass = data.pop("new_pass", None)
    if new_pass:
        password_requirements = config.auth.internal.password_requirements.model_dump()
        if not check_password_requirements(new_pass, **password_requirements):
            error_msg = get_password_requirement_message(**password_requirements)
            return bad_request(err=error_msg)
        data["password"] = get_password_hash(new_pass)
    else:
        data["password"] = data.get("password", "__NO_PASSWORD__") or "__NO_PASSWORD__"

    # Data's username has to match the API call username
    data["uname"] = username
    if not data["name"]:
        data["name"] = data["uname"]

    # Add dynamic classification group
    data["classification"] = user_service.get_dynamic_classification(data.get("classification", None), data["email"])

    # Clear non user account data
    avatar = data.pop("avatar", None)

    if avatar is not None:
        storage.user_avatar.save(username, avatar)

    try:
        return ok({"success": storage.user.save(username, User(data))})
    except ValueError as e:
        return bad_request(err=str(e))


@generate_swagger_docs()
@user_api.route("/<username>", methods=["GET"])
@api_login(audit=False, required_priv=["R"])
@add_etag(getter=user_service.get_user, check_if_match=False)
def get_user_account(username: str, server_version: Optional[str] = None, **kwargs):
    """Load the user account information.

    Variables:
    username       => Name of the user to get the account info

    Arguments:
    load_avatar    => If exists, this will load the avatar as well

    Result Example:
    {
     "name": "Test user",        # Name of the user
     "is_active": true,          # Is the user active?
     "classification": "",            # Max classification for user
     "uname": "usertest",        # Username
     "type": ['user'],           # List of all types the user is member of
     "avatar": null,             # Avatar of the user
     "groups": ["TEST"]          # Groups the user is member of
    }
    """
    if username != kwargs["user"]["uname"] and "admin" not in kwargs["user"]["type"]:
        return forbidden(err="You are not allow to view other users then yourself.")

    user: Optional[User] = kwargs.get("cached_user")
    if not user:
        return not_found(err=f"User {username} does not exist")

    user: dict[str, Any] = user.as_primitives()
    user["apikeys"] = [(k, []) for k in user.get("apikeys", {}).keys()]
    user["has_password"] = user.pop("password", "") != ""
    user["roles"] = user.pop("type", [])
    user["username"] = user["uname"]

    if "load_avatar" in request.args:
        user["avatar"] = datastore().user_avatar.get(username)

    return ok(user), server_version


@generate_swagger_docs()
@user_api.route("/<username>", methods=["DELETE"])
@api_login(required_type=["admin"])
def remove_user_account(username, **_):
    """Remove the account specified by the username.

    Variables:
    username       => Name of the user to get the account info

    Arguments:
    None

    Result Example:
    {
     "success": true  # Was the remove successful?
    }
    """
    storage = datastore()
    user_data = storage.user.get(username)
    if user_data:
        user_deleted = storage.user.delete(username)

        if storage.user_avatar.exists(username):
            avatar_deleted = storage.user_avatar.delete(username)
        else:
            avatar_deleted = True

        if not user_deleted or not avatar_deleted:
            logger.warning("Failed to delete user")
            return internal_error(err="Failed to delete user or avatar. Contact your administrator.")

        return no_content()
    else:
        return not_found(err=f"User {username} does not exist")


@generate_swagger_docs()
@user_api.route("/<username>", methods=["PUT"])
@api_login(required_type=["admin", "user"], enforce_quota=False)
def set_user_account(username: str, **kwargs):  # noqa: C901
    """Save the user account information.

    Variables:
    username    => Name of the user to get the account info

    Arguments:
    None

    Data Block:
    {
     "name": "Test user",        # Name of the user
     "is_active": true,          # Is the user active?
     "classification": "",            # Max classification for user
     "uname": "usertest",        # Username
     "type": ['user'],           # List of all types the user is member of
     "avatar": null,             # Avatar of the user
     "groups": ["TEST"]          # Groups the user is member of
    }

    Result Example:
    {
     "success": true             # Saving the user info succeded
    }
    """
    try:
        new_data = request.json
        if not isinstance(new_data, dict):
            return bad_request(err="Invalid data format")

        storage = datastore()
        if not (old_user := storage.user.get_if_exists(username, as_obj=False)):
            return not_found(err=f"User {username} does not exist")

        data = {**old_user, **new_data}
        new_pass = data.pop("new_pass", None)

        # Don't allow the overwriting of api keys
        data["apikeys"] = old_user.get("apikeys", [])

        # Don't allow overwriting of api quota unless you're an admin
        if "admin" not in kwargs["user"]["type"]:
            data["api_quota"] = old_user["api_quota"]

        if not data["name"]:
            return bad_request(err="Full name of the user cannot be empty")

        if data["email"] != old_user["email"]:
            return bad_request(err="Cannot update user's email")

        if data["uname"] != old_user["uname"]:
            return bad_request(err="Cannot update user's username")

        password_requirements = config.auth.internal.password_requirements.model_dump()
        if not new_pass:
            data["password"] = old_user.get("password", "__NO_PASSWORD__") or "__NO_PASSWORD__"
        elif not check_password_requirements(new_pass, **password_requirements):
            error_msg = get_password_requirement_message(**password_requirements)
            return bad_request(err=error_msg)
        else:
            data["password"] = get_password_hash(new_pass)
            data.pop("new_pass_confirm", None)

        # Apply dynamic classification
        data["classification"] = user_service.get_dynamic_classification(data["classification"], data["email"])

        ret_val = user_service.save_user_account(username, data, kwargs["user"])
        return ok({"success": ret_val})
    except AccessDeniedException as e:
        return forbidden(err=str(e))
    except (InvalidDataException, HowlerValueError) as e:
        return bad_request(err=str(e))


######################################################
# User's Avatar
######################################################


@generate_swagger_docs()
@user_api.route("/avatar/<username>", methods=["GET"])
@api_login(audit=True, required_priv=["R"])
def get_user_avatar(username, **_):
    """Loads the user's avatar.

    Variables:
    username    => Name of the user you want to get the avatar for

    Arguments:
    None

    Result Example:
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD..."
    """
    storage = datastore()
    avatar: str = storage.user_avatar.get(username)

    if avatar:
        resp = ok(avatar)
        resp.headers["Cache-Control"] = "private, max-age=3600"
        resp.headers["ETag"] = sha256(avatar.encode("utf-8")).hexdigest()
        return resp
    else:
        return not_found(err="No avatar for specified user")


@generate_swagger_docs()
@user_api.route("/avatar/<username>", methods=["POST"])
@api_login(audit=True)
def set_user_avatar(username, **kwargs):
    """Sets the user's Avatar

    Variables:
    username    => Name of the user you want to set the avatar for

    Arguments:
    None

    Data Block:
    "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD..."

    Result Example:
    {
     "success": true    # Was saving the avatar successful ?
    }
    """
    if username != kwargs["user"]["uname"]:
        return forbidden(err="Cannot save the avatar of another user.")

    data = request.data
    storage = datastore()
    if data:
        data: str = data.decode("utf-8")
        if not isinstance(data, str) or not storage.user_avatar.save(username, data):
            bad_request(
                err="Data block should be a base64 encoded image that starts with 'data:image/<format>;base64,'"
            )
    else:
        storage.user_avatar.delete(username)

    return ok()


@generate_swagger_docs()
@user_api.route("/groups", methods=["GET"])
@api_login(audit=False)
def get_user_groups(**kwargs):
    """Gets the user's groups from an oauth provider

    Variables:
    None

    Arguments:
    None

    Result Example:
    [
        {
            "name": "Group Name",
            "id": "abc-123"
        },
        ...
    ]
    """
    auth_header = request.headers.get("Authorization", None)

    if not auth_header:
        raise AuthenticationException("No Authorization header present")

    type, token = auth_header.split(" ")

    group_data = None
    if type == "Bearer" and "." in token:
        try:
            group_data = fetch_groups(token)
        except HowlerException as e:
            return internal_error(e.message)

    if group_data is None:
        group_data = []
        for g in kwargs["user"].get("groups", []):
            name = re.sub(r"^\w", lambda m: m.group(0).upper(), g)
            name = re.sub(r"[-_]", " ", name)
            name = re.sub(r" \w", lambda m: m.group(0).upper(), name)

            group_data.append({"name": name, "id": g})

    return ok(group_data)
