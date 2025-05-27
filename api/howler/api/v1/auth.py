import typing
from datetime import datetime, timedelta
from typing import Any, Optional
from urllib.parse import urlparse

from authlib.integrations.base_client import OAuthError
from flask import current_app, request
from passlib.hash import bcrypt

import howler.services.auth_service as auth_service
import howler.services.user_service as user_service
from howler.api import (
    bad_request,
    forbidden,
    internal_error,
    make_subapi_blueprint,
    no_content,
    not_found,
    ok,
    unauthorized,
)
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
from howler.odm.models.user import User
from howler.security import api_login
from howler.security.utils import generate_random_secret
from howler.services import jwt_service
from howler.utils.str_utils import default_string_value

logger = get_logger(__file__)


SUB_API = "auth"
auth_api = make_subapi_blueprint(SUB_API, api_version=1)
auth_api._doc = "Allow user to authenticate to the web server"

logger = get_logger(__file__)


@generate_swagger_docs()
@auth_api.route("/apikey", methods=["POST"])
@api_login(audit=False)
def add_apikey(**kwargs):  # noqa: C901
    """Add an API Key for the currently logged in user with given privileges

    Variables:
    name    => Name of the API key
    priv    => Requested privileges
    expiry_dates    => API key expiry date

    Arguments:
    None

    Data Block:
    {
        "name": "apikey",                 # The username to authenticate
        "priv": "priv",                   # The access priv of API key
        "expiry_date": "Expiry Date",     # The API key expiry date (optional)
    }

    Result Example:
    {
        "apikey": <ramdomly_generated_password>
    }
    """
    user = kwargs["user"]
    storage = datastore()
    user_data = storage.user.get_if_exists(user["uname"])
    apikey_data = request.json
    if not isinstance(apikey_data, dict):
        return bad_request(err="Invalid data format")

    if apikey_data["name"] in user_data.apikeys:
        return bad_request(err=f"APIKey '{apikey_data['name']}' already exists")

    privs: list[str] = [p for p in apikey_data["priv"]]

    if any(p for p in privs if p not in ["R", "W", "E", "I"]):
        return bad_request(
            err="APIKey contains permissions that do not exist. Please provide a subset of [R, W, E, I]."
        )

    if "E" in privs and not config.auth.allow_extended_apikeys:
        return bad_request(err="Extended permissions are disabled.")

    if "E" in privs and "I" in privs:
        return bad_request(err="Extended permission is not allowed on impersonation keys.")

    expiry_date = apikey_data.get("expiry_date", None)
    max_expiry = None
    if config.auth.max_apikey_duration_amount and config.auth.max_apikey_duration_unit:
        if not expiry_date:
            return bad_request(err="API keys must have an expiry date.")

        max_expiry = datetime.now() + timedelta(
            **{str(config.auth.max_apikey_duration_unit): config.auth.max_apikey_duration_amount}
        )

    if config.auth.oauth.strict_apikeys:
        auth_header: Optional[str] = request.headers.get("Authorization", None)

        if auth_header and auth_header.startswith("Bearer") and "." in auth_header:
            oauth_token = auth_header.split(" ")[1]
            data = jwt_service.decode(
                oauth_token,
                validate_audience=False,
                options={"verify_signature": False},
            )
            max_expiry = datetime.fromtimestamp(data["exp"])

    if expiry_date:
        try:
            expiry = datetime.fromisoformat(expiry_date.replace("Z", ""))
        except (ValueError, TypeError):
            return bad_request(err="Invalid expiry date format. Please use ISO format.")

        if max_expiry and max_expiry < expiry:
            return bad_request(err=f"Expiry date must be before {max_expiry.isoformat()}.")

    try:
        random_pass = generate_random_secret(length=50)
        key_name = apikey_data["name"] if "I" not in privs else f"impersonate_{apikey_data['name']}"

        new_key = {
            "password": bcrypt.encrypt(random_pass),
            "agents": apikey_data.get("agents", []),
            "acl": privs,
        }

        if expiry_date:
            new_key["expiry_date"] = expiry.isoformat()

        user_data.apikeys[key_name] = new_key
    except HowlerException as e:
        return bad_request(err=e.message)

    storage.user.save(user["uname"], user_data)

    return ok({"apikey": f"{key_name}:{random_pass}"})


@auth_api.route("/apikey/<name>", methods=["DELETE"])
@api_login(audit=False)
def delete_apikey(name, **kwargs):
    """Delete an API Key matching specified name for the currently logged in user

    Variables:
    name    => Name of the API key

    Arguments:
    None

    Result Example:
    {
     "success": True
    }
    """
    user = kwargs["user"]
    storage = datastore()
    user_data: User = storage.user.get_if_exists(user["uname"])

    if name not in user_data.apikeys:
        return not_found("Api key does not exist")

    user_data.apikeys.pop(name)
    storage.user.save(user["uname"], user_data)

    return no_content()


@auth_api.route("/login", methods=["GET", "POST"])
def login(**_):  # noqa: C901
    """Log the user into the system, in one of three ways.

    1. Username/Password Authentication
    2. Username/API Key Authentication
    3. OAuth Login flow
        (See here: https://auth0.com/docs/get-started/authentication-and-authorization-flow/authorization-code-flow)

    Variables:
    None

    Arguments:
    NOTE: The arguments are used only when completing the OAuth authorization flow.

    provider    => The provider of the OAuth code.
    state       => Random state used in the OAuth authentication flow.
    code        => The code provided by the OAuth provider used to exchange for an access token.

    Data Block:
    {
        "user": "user",                 # The username to authenticate as (optional)
        "password": "password",         # The password used to authenticate (optional)
        "apikey": "devkey:user",        # The apikey used ot authenticate (optional)
        "oauth_provider": "keycloak"    # The oauth provider initiate an OAuth Authorization Flow with (optional)
    }

    Result Example:
    {
        # Profile picture for the user
        "avatar": "data:image/png;base64, ...",
        # Username of the authenticated user
        "username": "user",
        # Different privileges that the user will get for this session
        "privileges": ["R", "W"],
        # A token generated by us the user can use to authenticate with howler
        "app_token": "asdfsd876opqwm465a89sdf4",
        # A JSON Web Access Token generated by an OAuth provider to authenticate with them
        "access_token": "<JWT>",
    }
    """
    data: dict[str, Any]
    if request.is_json and len(request.data) > 0:
        data = request.json  # type: ignore
    else:
        data = request.values

    # Get the ip the request came from - used in logging later
    ip = request.headers.get("X-Forwarded-For", request.remote_addr)

    # Get the data from the request
    # TODO: Figure out how to fix this inconsistency
    oauth_provider = data.get("provider", data.get("oauth_provider", None))
    user = data.get("user", None)
    password = data.get("password", None)
    apikey = data.get("apikey", None)

    # These variables are what will eventually be returned, if authentication is successful
    logged_in_uname = None
    access_token = None
    refresh_token = data.get("refresh_token", None)
    priv: Optional[list[str]] = []

    try:
        # First, we'll try oauth
        if oauth_provider:
            if not config.auth.oauth.enabled:
                raise InvalidDataException("OAuth is disabled.")  # noqa: TRY301

            oauth = current_app.extensions.get("authlib.integrations.flask_client")
            if not oauth:  # pragma: no cover
                logger.critical("Authlib integration missing!")
                raise HowlerValueError()

            provider = oauth.create_client(oauth_provider)

            if not provider:
                logger.critical("OAuth client failed to create!")
                raise HowlerValueError()

            # This means that they want to start the oauth process, so we'll redirect them to their chosen provider
            if "code" not in request.args and not refresh_token:
                referer = request.headers.get("Referer", None)
                uri = urlparse(referer if referer else request.host_url)
                port_portion = ":" + str(uri.port) if uri.port else ""
                redirect_uri = f"{uri.scheme}://{uri.hostname}{port_portion}/login?provider={oauth_provider}"
                return provider.authorize_redirect(redirect_uri=redirect_uri, nonce=request.args.get("nonce", None))

            # At this point we know the code exists, so we're good to use that to exchange for an JSON Web Token with
            # user data in it. token_data contains the access token, expiry, refresh token, and id token,
            # in JWT format: https://jwt.io/

            oauth_provider_config = config.auth.oauth.providers[oauth_provider]

            # We need to figure out what information the provider already has, and provide whatever it doesn't.
            # Without this step, the provider will try and send the client_id and/or secret *twice*, leading to an
            # error.
            kwargs = {}

            # Does the provider have the client id? If not provide it
            if not provider.client_id:
                kwargs["client_id"] = default_string_value(
                    oauth_provider_config.client_id,
                    env_name=f"{oauth_provider.upper()}_CLIENT_ID",
                )

                if not kwargs["client_id"]:
                    logger.critical("client id not set! Cannot complete oauth")
                    raise HowlerValueError()

            # Does the provider have the client secret? If not provide it
            if not provider.client_secret:
                kwargs["client_secret"] = default_string_value(
                    oauth_provider_config.client_secret,
                    env_name=f"{oauth_provider.upper()}_CLIENT_SECRET",
                )

                if not kwargs["client_secret"]:
                    logger.critical("client secret not set! Cannot complete oauth")
                    raise HowlerValueError()

            if refresh_token is not None:
                token_data = provider.fetch_access_token(
                    refresh_token=refresh_token,
                    grant_type="refresh_token",
                    **kwargs,
                )
            else:
                # Finally, ask for the access token with whatever info the provider needs
                token_data = provider.authorize_access_token(**kwargs)

            access_token = token_data.get("access_token", None)
            refresh_token = token_data.get("refresh_token", None)

            # Get a useful dict of user data from the web token
            cur_user = user_service.parse_user_data(
                token_data, oauth_provider, skip_setup=False, access_token=access_token
            )

            logged_in_uname = cur_user["uname"]

            priv = ["R", "W", "E"]

        # No oauth provider was specified, so we fall back to user/pass or user/apikey
        elif user and (password or apikey):
            if password and apikey:
                raise InvalidDataException("Cannot specify password and API key.")  # noqa: TRY301

            user_data, priv = auth_service.basic_auth(
                f"{user}:{password or apikey}",
                is_base64=False,
                # No need to validate for api keys if we know they provided a password, and vice versa
                skip_apikey=bool(password),
                skip_password=bool(apikey),
            )

            if not user_data:
                raise AuthenticationException("User does not exist, or authentication was invalid")  # noqa: TRY301

            logged_in_uname = user_data["uname"]

        else:
            raise AuthenticationException("Not enough information to proceed with authentication")  # noqa: TRY301

    # For sanity's sake, we throw exceptions throughout the authentication code and simply catch the exceptions here to
    # return the corresponding HTTP Code to the user
    except (OAuthError, AuthenticationException) as err:
        logger.warning(f"Authentication failure. (U:{user} - IP:{ip}) [{err}]")
        return unauthorized(err=str(err))

    except AccessDeniedException as err:
        logger.warning(f"Authorization failure. (U:{user} - IP:{ip}) [{err}]")
        return forbidden(err=err.message)

    except InvalidDataException as err:
        return bad_request(err=err.message or str(err))

    except HowlerException:
        logger.exception(f"Internal Authentication Error. (U:{user} - IP:{ip})")
        return internal_error(
            err="Unhandled exception occured while Authenticating. Contact your administrator.",
        )

    logger.info(f"Login successful. (U:{logged_in_uname} - IP:{ip})")

    xsrf_token = generate_random_secret()

    # Generate the token this user can use to authenticate from now on

    if access_token:
        app_token = access_token
    else:
        app_token = f"{logged_in_uname}:{auth_service.create_token(logged_in_uname, typing.cast(list[str], priv))}"

    return ok(
        {
            "app_token": app_token,
            "provider": oauth_provider,
            "refresh_token": refresh_token,
            "privileges": priv,
        },
        cookies={"XSRF-TOKEN": xsrf_token},
    )
