import functools
import sys
from typing import Optional

import elasticapm
import requests
from flask import request
from flask import session as flsk_session
from jwt import ExpiredSignatureError
from prometheus_client import Counter

import howler.services.auth_service as auth_service
from howler.api import bad_request, forbidden, internal_error, not_found, too_many_requests, unauthorized
from howler.common.exceptions import (
    AccessDeniedException,
    AuthenticationException,
    HowlerAttributeError,
    HowlerRuntimeError,
    InvalidDataException,
    NotFoundException,
)
from howler.common.loader import APP_NAME
from howler.common.logging import get_logger
from howler.common.logging.audit import audit
from howler.config import AUDIT, QUOTA_TRACKER, config
from howler.odm.models.user import User

logger = get_logger(__file__)

SUCCESSFUL_ATTEMPTS = Counter(
    f"{APP_NAME.replace('-', '_')}_auth_success_total",
    "Successful Authentication Attempts",
)

FAILED_ATTEMPTS = Counter(
    f"{APP_NAME.replace('-', '_')}_auth_fail_total",
    "Failed Authentication Attempts",
    ["status"],
)

XSRF_ENABLED = True


####################################
# API Helper func and decorators
# noinspection PyPep8Naming
class api_login(object):  # noqa: D101, N801
    def __init__(
        self,
        required_type: Optional[list[str]] = None,
        username_key: str = "username",
        audit: bool = True,
        required_priv: Optional[list[str]] = None,
        required_method: Optional[list[str]] = None,
        check_xsrf_token: bool = XSRF_ENABLED,
        enforce_quota: bool = True,
    ):
        if required_priv is None:
            required_priv = ["E"]

        if required_type is None:
            required_type = ["admin", "user"]

        required_method_set: set[str]
        if required_method is None:
            required_method_set = {"userpass", "apikey", "internal", "oauth"}
        else:
            required_method_set = set(required_method)

        if len(required_method_set - {"userpass", "apikey", "internal", "oauth"}) > 0:
            raise HowlerAttributeError("required_method must be a subset of {userpass, apikey, internal, oauth}")

        self.required_type = required_type
        self.audit = audit and AUDIT
        self.required_priv = required_priv
        self.required_method = required_method_set
        self.username_key = username_key
        self.check_xsrf_token = check_xsrf_token
        self.enforce_quota = enforce_quota

    def __call__(self, func):  # noqa: C901, D102
        @functools.wraps(func)
        def base(*args, **kwargs):  # noqa: C901
            try:
                # All authorization (except impersonation) must go through the Authorization header, in one of
                # four formats:
                # 1. Basic user/pass authentication
                #       Authorization: Basic username:password (but in base64)
                # 2. Basic user/apikey authentication
                #       Authorization: Basic username:keyname:keydata (but in base64)
                # 3. Bearer internal token authentication (obtained from the login endpoint)
                #       Authorization: Bearer username:token
                # 4. Bearer OAuth authentication (obtained from external authentication provider i.e. azure, keycloak)
                #       Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjMifQ (example)
                authorization = request.headers.get("Authorization", None)
                if not authorization:
                    raise AuthenticationException("No Authorization header present")
                elif " " not in authorization or len(authorization.split(" ")) > 2:
                    raise InvalidDataException("Incorrectly formatted Authorization header")

                logger.debug("Authenticating user for path %s", request.path)

                [auth_type, data] = authorization.split(" ")

                user = None
                if auth_type == "Basic" and len(self.required_method & {"userpass", "apikey"}) > 0:
                    # Authenticate case (1) and (2) above
                    user, priv = auth_service.basic_auth(
                        data,
                        skip_apikey="apikey" not in self.required_method,
                        skip_password="userpass" not in self.required_method,
                    )
                elif auth_type == "Bearer" and len(self.required_method & {"internal", "oauth"}) > 0:
                    # Authenticate case (3) and (4) above
                    try:
                        user, priv = auth_service.bearer_auth(
                            data,
                            skip_jwt="oauth" not in self.required_method,
                            skip_internal="internal" not in self.required_method,
                        )
                    except ExpiredSignatureError as e:
                        raise AuthenticationException("Token Expired") from e
                    except (requests.exceptions.ConnectionError, ConnectionError) as e:
                        raise HowlerRuntimeError("Failed to connect to OAuth Provider") from e
                else:
                    raise InvalidDataException("Not a valid authentication type for this endpoint.")

                if not user:
                    raise AuthenticationException("No authenticated user found")

                # User impersonation. Basically, we want to allow a user (read: a service account) to authenticate as
                # another user. A use case for this would be, for example, writing alerts to howler on behalf of a
                # user, so they don't have to do it themselves.
                #
                # In order to do this, you provide two headers instead of one. The first header, Authorization,
                # authenticates the user as usual. The second, X-Impersonating, authenticates the first user's access
                # to the second user. The login format must be of type (2) above, with the added caveat that the apikey
                # provided MUST be authorized for impersonation (i.e. "I" in priv == True). See validate_apikey for more
                # on this.
                impersonator: Optional[User] = None
                impersonated_user: Optional[User] = None
                impersonation = request.headers.get("X-Impersonating", None)
                if impersonation:
                    [auth_type, data] = impersonation.split(" ")

                    if auth_type == "Basic":
                        try:
                            username, apikey = auth_service.decode_b64(data).split(":", 1)

                            (
                                impersonated_user,
                                impersonated_priv,
                            ) = auth_service.validate_apikey(username, apikey, user)
                        except AuthenticationException:
                            impersonated_user = None
                    else:
                        raise InvalidDataException("Not a valid authentication type for impersonation.")

                    # Either the they are trying to impersonate doesn't exist, or they don't have a valid key for them
                    if not impersonated_user:
                        raise AuthenticationException("No impersonated user found")

                    # Success!
                    logger.warning(
                        "%s is impersonating %s",
                        user["uname"],
                        impersonated_user["uname"],
                    )
                    impersonator = user
                    user, priv = impersonated_user, impersonated_priv

                # Ensure that the provided api key allows access to this API
                if not priv or not set(self.required_priv) & set(priv):
                    raise AccessDeniedException("You do not have access to this API.")

                # Make sure the user has the correct type for this endpoint
                if not set(self.required_type) & set(user["type"]):
                    logger.warning(
                        f"{user['uname']} is missing one of the types: {', '.join(self.required_type)}. "
                        "Cannot access {request.path}"
                    )
                    raise AccessDeniedException(
                        f"{request.path} requires one of the following user types: {', '.join(self.required_type)}"
                    )

                ip = request.headers.get("X-Forwarded-For", request.remote_addr)
                if "pytest" not in sys.modules:
                    logger.info(f"Logged in as {user['uname']} from {ip} for path {request.path}")

                # If auditing is enabled, write this successful access to the audit logs
                if self.audit:
                    audit(
                        args,
                        kwargs,
                        user["uname"],
                        user,
                        func,
                        impersonator=impersonator["uname"] if impersonator else None,
                    )
            except InvalidDataException as e:
                FAILED_ATTEMPTS.labels("400").inc()
                return bad_request(err=e.message)
            except AuthenticationException as e:
                FAILED_ATTEMPTS.labels("401").inc()
                return unauthorized(err=e.message)
            except AccessDeniedException as e:
                FAILED_ATTEMPTS.labels("403").inc()
                return forbidden(err=e.message)
            except NotFoundException as e:
                FAILED_ATTEMPTS.labels("404").inc()
                return not_found(err=e.message)
            except HowlerRuntimeError as e:
                FAILED_ATTEMPTS.labels("500").inc()
                return internal_error(err=e.message)

            if config.core.metrics.apm_server.server_url is not None:
                elasticapm.set_user_context(
                    username=user.get("name", None),
                    email=user.get("email", None),
                    user_id=user.get("uname", None),
                )

            if request.path.startswith("/api/v1/borealis"):
                logger.debug("Bypassing quota limits for borealis enrichment")
            elif self.enforce_quota:
                # Check current user quota
                flsk_session["quota_user"] = user["uname"]
                flsk_session["quota_set"] = True

                quota = user.get("api_quota", 25)
                if not QUOTA_TRACKER.begin(user["uname"], quota):
                    if config.ui.enforce_quota:
                        logger.info(f"{user['uname']} was prevented from using the api due to exceeded quota.")
                        FAILED_ATTEMPTS.labels("429").inc()
                        return too_many_requests(err=f"You've exceeded your maximum quota of {quota}")
                    else:
                        logger.debug(f"Quota of {quota} exceeded for user {user['uname']}.")
                else:
                    logger.debug(f"{user['uname']}'s quota is under or equal its limit of {quota}")
            else:
                logger.debug(f"Quota not enforced for {user['uname']}")

            # Save user data in kwargs for future reference in the wrapped method
            kwargs["user"] = user

            SUCCESSFUL_ATTEMPTS.inc()
            return func(*args, **kwargs)

        base.protected = True
        base.required_type = self.required_type
        base.audit = self.audit
        base.required_priv = self.required_priv
        base.required_method = self.required_method
        base.check_xsrf_token = self.check_xsrf_token
        return base
