from typing import Any, Optional, Union

import elasticapm
from authlib.integrations.flask_client import OAuth
from flask import current_app, request

from howler.common.exceptions import AccessDeniedException, HowlerValueError, InvalidDataException
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.config import CLASSIFICATION, config
from howler.helper.oauth import fetch_avatar, parse_profile
from howler.odm.models.user import User
from howler.odm.models.view import View
from howler.utils.str_utils import safe_str

ACCOUNT_USER_MODIFIABLE = ["name", "email", "avatar", "password", "dashboard"]

logger = get_logger(__file__)


def get_user(
    id: str,
    as_odm: bool = False,
    version: bool = False,
) -> Union[User, dict[str, Any]]:
    """Return hit object as either an ODM or Dict"""
    return datastore().user.get_if_exists(key=id, as_obj=as_odm, version=version)


def convert_user(user: User) -> dict[str, Any]:
    """Converts a User ODM into a dict for frontend usage, stripping out private or irrelevant fields.

    Args:
        user (User): The user object to parse

    Returns:
        dict: The parsed user data object
    """
    user_data = {
        k: v
        for k, v in user.as_primitives().items()
        if k
        in [
            "classification",
            "email",
            "groups",
            "is_active",
            "name",
            "type",
            "uname",
            "api_quota",
            "favourite_views",
            "favourite_analytics",
            "dashboard",
        ]
    }

    user_data["apikeys"] = [
        (key, value["acl"], value["expiry_date"])
        for key, value in datastore().user.get_if_exists(user["uname"]).apikeys.items()
    ]

    user_data["avatar"] = datastore().user_avatar.get_if_exists(user["uname"])
    user_data["username"] = user_data.pop("uname")
    user_data["is_admin"] = "admin" in user_data["type"]
    user_data["roles"] = list(set(user_data.pop("type")))

    return user_data


@elasticapm.capture_span(span_type="authentication")
def parse_user_data(  # noqa: C901
    data: dict,
    oauth_provider: str,
    skip_setup: bool = True,
    access_token: Optional[str] = None,
) -> User:
    """Convert a JSON Web Token into a Howler User.

    Args:
        data (dict): The JWT to parse
        oauth_provider (str): The provider of the JWT
        skip_setup (bool, optional): Skip the extra setup steps we run at login, for performance reasons.
            Defaults to True.
        access_token (str, optional): The access token to use when fetching the user's avatar. Defaults to None.

    Raises:
        InvalidDataException: Some required data was missing.
        AccessDeniedException: The user is not permitted to access the application, or user auto-creation is disabled
            and the user doesn't exist in the database.

    Returns:
        User: The parsed User ODM
    """
    if not data or not oauth_provider:
        raise InvalidDataException("Both the JWT and OAuth provider must be supplied")

    oauth = current_app.extensions.get("authlib.integrations.flask_client")
    if not oauth:  # pragma: no cover
        logger.critical("Authlib integration missing!")
        raise HowlerValueError("Authlib integration missing!")

    provider: OAuth = oauth.create_client(oauth_provider)

    if "id_token" in data:
        data = provider.parse_id_token(
            data, nonce=request.args.get("nonce", data.get("userinfo", {}).get("nonce", None))
        )

    oauth_provider_config = config.auth.oauth.providers[oauth_provider]

    if not data and oauth_provider_config.user_get:
        response = provider.get(oauth_provider_config.user_get)
        if response.ok:
            data = response.json()

    user_data = parse_profile(data, oauth_provider_config)

    if len(oauth_provider_config.required_groups) > 0:
        required_groups = set(oauth_provider_config.required_groups)
        if len(required_groups) != len(required_groups & set(user_data["groups"])):
            logger.warning(
                f"User {user_data['uname']} is missing groups from their JWT:"
                f" {', '.join(required_groups - (required_groups & set(user_data['groups'])))}"
            )
            raise AccessDeniedException("This user is not allowed access to the system")

    has_access = user_data.pop("access", False)
    storage = datastore()
    current_user: Optional[dict[str, Any]] = None
    if has_access and user_data["email"] is not None:
        # Find if user already exists
        users: list[dict[str, Any]] = storage.user.search(f"email:{user_data['email']}", fl="*", as_obj=False)["items"]

        if users:
            current_user = users[0]
            # Do not update username and password from the current user
            user_data["uname"] = current_user.get("uname", user_data["uname"])
            user_data.pop("password", None)
        else:
            if user_data["uname"] != user_data["email"]:
                # Username was computed using a regular expression, lets make sure we don't
                # assign the same username to two users
                exists = storage.user.exists(user_data["uname"])
                if exists:
                    count = 1
                    new_uname = f"{user_data['uname']}{count}"
                    while storage.user.exists(new_uname):
                        count += 1
                        new_uname = f"{user_data['uname']}{count}"
                    user_data["uname"] = new_uname
            current_user = {}

        username = user_data["uname"]

        # Add add dynamic classification group
        user_data["classification"] = get_dynamic_classification(user_data["classification"], user_data["email"])

        # Make sure the user exists in howler and is in sync
        if (not current_user and oauth_provider_config.auto_create) or (
            current_user and oauth_provider_config.auto_sync
        ):
            old_user = {**current_user}
            old_user.pop("id", None)
            old_user.pop("avatar", None)

            # Update the current user
            current_user.update(user_data)

            user_id = current_user.pop("id", None)
            avatar = current_user.pop("avatar", None)

            # Save updated user if there are changes to sync or it doesn't exist
            if old_user != current_user:
                if user_id:
                    logger.info("Updating %s with new data", user_id if not isinstance(user_id, list) else user_id[0])
                else:
                    logger.info("Creating new user %s", username)

                if user_id:
                    current_user["id"] = user_id

                if avatar:
                    current_user["avatar"] = avatar

                storage.user.save(username, current_user)
                storage.user.commit()
            else:
                logger.debug("User is up to date!")

            if not skip_setup:
                if avatar:
                    logger.info("Updating avatar for %s", username)

                    avatar = fetch_avatar(
                        avatar,
                        provider,
                        oauth_provider,
                        access_token=access_token,
                    )

                    if avatar:
                        storage.user_avatar.save(username, avatar)

                view_query = f"owner:{current_user['uname']} AND title:view.assigned_to_me AND type:readonly"
                if len(storage.view.search(view_query)["items"]) == 0:
                    new_assigned_view = View(
                        {
                            "title": "view.assigned_to_me",
                            "query": f"howler.assignment:{current_user['uname']}",
                            "type": "readonly",
                            "owner": current_user["uname"],
                        }
                    )

                    current_user["favourite_views"] = [
                        *current_user.get("favourite_views", []),
                        new_assigned_view.view_id,
                    ]

                    storage.view.save(new_assigned_view.view_id, new_assigned_view)
                    storage.user.save(username, current_user)
                    storage.user.commit()

        if not current_user:
            raise AccessDeniedException("User auto-creation is disabled")
    else:
        raise AccessDeniedException("This user is not allowed access to the system")

    return User(current_user)


def add_access_control(user: dict[str, Any]):
    """Add access control to the specified user.

    Args:
        user (dict[str, Any]): The user to add access control information to.
    """
    user.update(
        CLASSIFICATION.get_access_control_parts(
            user.get("classification", CLASSIFICATION.UNRESTRICTED),
            user_classification=True,
        )
    )

    gl2_query = " OR ".join(
        [
            "__access_grp2__:__EMPTY__",
            *[f'__access_grp2__:"{x}"' for x in user["__access_grp2__"]],
        ],
    )
    gl2_query = f"({gl2_query}) AND "

    gl1_query = " OR ".join(
        [
            "__access_grp1__:__EMPTY__",
            *[f'__access_grp1__:"{x}"' for x in user["__access_grp1__"]],
        ],
    )
    gl1_query = f"({gl1_query}) AND "

    req = list(set(CLASSIFICATION.get_access_control_req()).difference(set(user["__access_req__"])))
    req_query = " OR ".join([f'__access_req__:"{r}"' for r in req])
    if req_query:
        req_query = f"-({req_query}) AND "

    lvl_query = f'__access_lvl__:[0 TO {user["__access_lvl__"]}]'

    query = f"{gl2_query}{gl1_query}{req_query}{lvl_query}"
    user["access_control"] = safe_str(query)


def save_user_account(username: str, data: dict[str, Any], user: dict[str, Any]) -> bool:
    """Create or update a user in the database

    Args:
        username (str): The username to create or update the user under
        data (dict[str, Any]): The user's data
        user (dict[str, Any]): The account that is creating this new user

    Raises:
        AccessDeniedException: Parts of the user data is overwriting fields that cannot be changed.
        InvalidDataException: The username in question doesn't match any existing users

    Returns:
        bool: If the save operation was successful
    """
    # Clear non user account data
    avatar = data.pop("avatar", None)
    data.pop("security_token_enabled", None)
    data.pop("has_password", None)

    data = User(data).as_primitives()

    if username != data["uname"]:
        raise AccessDeniedException("You are not allowed to change the username.")

    if username != user["uname"] and "admin" not in user["type"]:
        raise AccessDeniedException("You are not allowed to change another user than yourself.")

    storage = datastore()
    current = storage.user.get_if_exists(username, as_obj=False)
    if current:
        if "admin" not in user["type"]:
            for key in current.keys():
                if data[key] != current[key] and key not in ACCOUNT_USER_MODIFIABLE:
                    raise AccessDeniedException(f"Only Administrators can change the value of the field [{key}].")
    else:
        raise InvalidDataException(f"You cannot save a user that does not exists [{username}].")

    if avatar == "DELETE":
        storage.user_avatar.delete(username)
    elif avatar is not None:
        storage.user_avatar.save(username, avatar)

    return storage.user.save(username, data)


def get_dynamic_classification(current_c12n: str, email: str) -> str:
    """Get the classification of the user

    Args:
        current_c12n (str): The current classification of the user
        email (str): The user's email

    Returns:
        str: The classification
    """
    if CLASSIFICATION.dynamic_groups and email:
        dyn_group = email.upper().split("@")[1]
        return CLASSIFICATION.build_user_classification(current_c12n, f"{CLASSIFICATION.UNRESTRICTED}//{dyn_group}")
    return current_c12n
