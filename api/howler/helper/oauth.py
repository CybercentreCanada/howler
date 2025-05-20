import base64
import hashlib
import re
from typing import Any, Optional

import elasticapm
import requests

from howler.common.exceptions import HowlerException, HowlerValueError
from howler.common.loader import USER_TYPES
from howler.common.logging import get_logger
from howler.common.random_user import random_user
from howler.config import CLASSIFICATION as CLASSIFICATION_ENGINE
from howler.config import config
from howler.helper.azure import azure_obo
from howler.odm.models.config import OAuthProvider
from howler.services import jwt_service

VALID_CHARS = [str(x) for x in range(10)] + [chr(x + 65) for x in range(26)] + [chr(x + 97) for x in range(26)] + ["-"]

logger = get_logger(__file__)


def reorder_name(name: Optional[str]) -> Optional[str]:
    """Reorder the name from Doe, John to John Doe"""
    if name is None:
        return name

    return " ".join(name.split(", ", 1)[::-1])


@elasticapm.capture_span(span_type="authentication")
def parse_profile(profile: dict[str, Any], provider_config: OAuthProvider) -> dict[str, Any]:  # noqa: C901
    """Parse a raw profile dict into a useful user data dict"""
    # Find email address and normalize it for further processing
    email_adr = profile.get(
        "email",
        profile.get("emails", profile.get("preferred_username", profile.get("upn", None))),
    )

    if isinstance(email_adr, list):
        email_adr = email_adr[0]

    if email_adr:
        email_adr = email_adr.lower()
        if "@" not in email_adr:
            email_adr = None

    # Find the name of the user
    name = reorder_name(profile.get("name", profile.get("displayName", None)))

    # Generate a username
    if provider_config.uid_randomize:
        # Use randomizer
        uname = random_user(
            digits=provider_config.uid_randomize_digits,
            delimiter=provider_config.uid_randomize_delimiter,
        )
    else:
        # Try and find the username
        uname = profile.get("uname", profile.get("preferred_username", email_adr))

        # Did we default to email?
        if uname is not None and uname.lower() == email_adr.lower():
            # 1. Use provided regex matcher
            if provider_config.uid_regex:
                match = re.match(provider_config.uid_regex, uname)
                if match:
                    if provider_config.uid_format:
                        uname = provider_config.uid_format.format(*[x or "" for x in match.groups()]).lower()
                    else:
                        uname = "".join([x for x in match.groups() if x]).lower()

            # 2. Parse name and domain from email if regex failed or missing
            if uname is not None and uname == email_adr:
                e_name, e_dom = uname.split("@", 1)
                uname = f"{e_name}-{e_dom.split('.')[0]}"

        # 3. Use name as username if there are no username found yet
        if uname is None and name is not None:
            uname = name.replace(" ", "-")

        # Cleanup username
        if uname:
            uname = "".join([c for c in uname if c in VALID_CHARS])

    # Get avatar from gravatar
    if config.auth.oauth.gravatar_enabled and email_adr:
        email_hash = hashlib.md5(email_adr.encode("utf-8")).hexdigest()  # noqa: S324
        alternate = f"https://www.gravatar.com/avatar/{email_hash}?s=256&d=404&r=pg"
    else:
        alternate = None

    # Compute access, roles and classification using auto_properties
    access = True
    roles = ["user"]
    classification = CLASSIFICATION_ENGINE.UNRESTRICTED
    if provider_config.auto_properties:
        for auto_prop in provider_config.auto_properties:
            if auto_prop.type == "access":
                # Set default access value for access pattern
                access = auto_prop.value != "True"

            # Get values for field
            field_data = profile.get(auto_prop.field, None)
            if not isinstance(field_data, list):
                field_data = [field_data]

            # Analyse field values
            for value in field_data:
                # If there is no value, no need to do any tests
                if value is None:
                    continue

                # Check access
                if auto_prop.type == "access":
                    if re.match(auto_prop.pattern, value) is not None:
                        access = auto_prop.value == "True"
                        break

                # Append roles from matching patterns
                elif auto_prop.type == "role":
                    if re.match(auto_prop.pattern, value):
                        roles.append(auto_prop.value)
                        break

                # Compute classification from matching patterns
                elif auto_prop.type == "classification":
                    if re.match(auto_prop.pattern, value):
                        classification = CLASSIFICATION_ENGINE.build_user_classification(
                            classification, auto_prop.value
                        )
                        break

    # Infer roles from groups
    if profile.get("groups") and provider_config.role_map:
        for user_type in USER_TYPES:
            if (
                user_type in provider_config.role_map
                and provider_config.role_map[user_type] in profile.get("groups", [])
                and user_type not in roles
            ):
                roles.append(user_type)

    return dict(
        access=access,
        type=roles,
        classification=classification,
        uname=uname,
        name=name,
        email=email_adr,
        password="__NO_PASSWORD__",  # noqa: S106
        avatar=profile.get("picture", provider_config.picture_url or alternate),
        groups=profile.get("groups", []),
    )


def fetch_avatar(  # noqa: C901
    url: str, provider: dict[str, Any], oauth_provider: str, access_token: Optional[str] = None
):
    """Fetch a user's avatar form the oauth provider"""
    provider_config = config.auth.oauth.providers[oauth_provider]

    logger.info("Fetching avatar from %s at %s", oauth_provider, url)

    try:
        # Generic picture url endpoint, i.e. MS Graph
        if url == provider_config.picture_url:
            headers = {}

            if oauth_provider == "azure":
                if not access_token:
                    raise HowlerValueError("An azure access token is necessary to retrieve the profile picture")  # noqa: TRY301

                token = azure_obo(access_token)

            if token:
                headers["Authorization"] = f"Bearer {token}"

            resp: Any = requests.get(url, headers=headers, timeout=10)

            if resp.ok and resp.headers.get("content-type") is not None:
                b64_img = base64.b64encode(resp.content).decode()
                avatar = f'data:{resp.headers.get("content-type")};base64,{b64_img}'
                return avatar

        # Url that is protected through OAuth
        elif provider_config.api_base_url and url.startswith(provider_config.api_base_url):
            resp = provider.get(url[len(provider_config.api_base_url) :])
            if resp.ok and resp.headers.get("content-type") is not None:
                b64_img = base64.b64encode(resp.content).decode()
                avatar = f'data:{resp.headers.get("content-type")};base64,{b64_img}'
                return avatar

        # Unprotected url
        elif url.startswith(("https://", "http://")):
            resp = requests.get(url, timeout=10)
            if resp.ok and resp.headers.get("content-type") is not None:
                b64_img = base64.b64encode(resp.content).decode()
                avatar = f'data:{resp.headers.get("content-type")};base64,{b64_img}'
                return avatar

    # Quietly fail, it'll use gravatar instead
    except Exception as e:
        logger.warning("Error while retrieving user profile: %s", str(e))
        return None


def fetch_groups(token: str):
    """Fetch a user's groups form an external endpoint"""
    oauth_provider = jwt_service.get_provider(token)
    oauth_provider_config = config.auth.oauth.providers[oauth_provider]

    if oauth_provider_config.groups_url:
        if oauth_provider == "azure":
            try:
                token = azure_obo(token)
            except HowlerException:
                logger.exception("Exception on fetching groups data")
                raise HowlerException("Something went wrong when getting the detailed groups data.")

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        resp = requests.get(oauth_provider_config.groups_url, headers=headers, timeout=10)

        if resp.ok and resp.headers.get("content-type") is not None:
            result = resp.json()
            if oauth_provider_config.groups_key:
                for part in oauth_provider_config.groups_key.split("."):
                    result = result[part]

            detailed_group_data = []
            for group in result:
                detailed_group_data.append(
                    {
                        "id": group.get("id", None),
                        "name": group.get("name", group.get("displayName", group.get("id", None))),
                    }
                )

            return sorted(detailed_group_data, key=lambda g: g.get("name", "").lower())

        raise HowlerException("Something went wrong when getting the detailed groups data.")
    else:
        return None
