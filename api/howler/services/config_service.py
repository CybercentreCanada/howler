import importlib
from datetime import datetime
from math import ceil
from typing import Optional

from flask import request

import howler.services.hit_service as hit_service
from howler.common.exceptions import ForbiddenException, HowlerException
from howler.common.loader import get_lookups
from howler.common.logging import get_logger
from howler.config import CLASSIFICATION, config, get_branch, get_commit, get_version
from howler.helper.discover import get_apps_list
from howler.helper.search import list_all_fields
from howler.odm.models.howler_data import Assessment, Escalation, HitStatus, Scrutiny
from howler.odm.models.user import User
from howler.services import jwt_service
from howler.utils.str_utils import default_string_value

classification_definition = CLASSIFICATION.get_parsed_classification_definition()

lookups = get_lookups()

logger = get_logger()


def _get_apikey_max_duration():
    "Configure the maximum duration of a created API key"
    amount, unit = (
        config.auth.max_apikey_duration_amount,
        config.auth.max_apikey_duration_unit,
    )

    if not config.auth.oauth.strict_apikeys:
        return amount, unit

    auth_header: Optional[str] = request.headers.get("Authorization", None)

    if not auth_header:
        return amount, unit

    if not auth_header.startswith("Bearer") or "." not in auth_header:
        return amount, unit

    oauth_token = auth_header.split(" ")[1]
    try:
        data = jwt_service.decode(
            oauth_token,
            validate_audience=False,
            options={"verify_signature": False},
        )
        amount, unit = (
            ceil((datetime.fromtimestamp(data["exp"]) - datetime.now()).total_seconds()),
            "seconds",
        )
    except ForbiddenException:
        logger.warning("Access token is expired.")
    except HowlerException:
        logger.exception("Error occurred when decoding access token.")
    finally:
        return amount, unit


def get_configuration(user: User, **kwargs):
    """Get system configration data for the Howler API

    Args:
        user (User): The user making the request
    """
    apps = get_apps_list(discovery_url=kwargs.get("discovery_url", None))

    amount, unit = _get_apikey_max_duration()

    plugin_features: dict[str, bool] = {}

    for plugin in config.core.plugins:
        try:
            plugin_features = {**plugin_features, **importlib.import_module(f"{plugin}.features").features()}
        except (ImportError, AttributeError):
            pass

    return {
        "lookups": {
            "howler.status": HitStatus.list(),
            "howler.scrutiny": Scrutiny.list(),
            "howler.escalation": Escalation.list(),
            "howler.assessment": Assessment.list(),
            "transitions": {status: hit_service.get_transitions(status) for status in HitStatus.list()},
            **lookups,
        },
        "configuration": {
            "auth": {
                "allow_apikeys": config.auth.allow_apikeys,
                "allow_extended_apikeys": config.auth.allow_extended_apikeys,
                "max_apikey_duration_amount": amount,
                "max_apikey_duration_unit": unit,
                "oauth_providers": [
                    name
                    for name, p in config.auth.oauth.providers.items()
                    if default_string_value(p.client_secret, env_name=f"{name.upper()}_CLIENT_SECRET")
                ],
                "internal": {"enabled": config.auth.internal.enabled},
            },
            "system": {
                "type": config.system.type,
                "version": get_version(),
                "branch": get_branch(),
                "commit": get_commit(),
                "retention": {
                    "enabled": config.system.retention.enabled,
                    "limit_unit": config.system.retention.limit_unit,
                    "limit_amount": config.system.retention.limit_amount,
                },
            },
            "ui": {
                "apps": apps,
            },
            "features": {
                "borealis": config.core.borealis.enabled,
                "notebook": config.core.notebook.enabled,
                **plugin_features,
            },
            "borealis": {"status_checks": config.core.borealis.status_checks},
        },
        "c12nDef": classification_definition,
        "indexes": list_all_fields("admin" in user["type"] if user is not None else False),
    }
