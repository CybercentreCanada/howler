import os

from flask_caching import Cache

from howler.common import loader
from howler.odm.models.config import config
from howler.remote.datatypes import get_client
from howler.remote.datatypes.user_quota_tracker import UserQuotaTracker

#################################################################
# Configuration

CLASSIFICATION = loader.get_classification()

AUDIT = config.ui.audit

SECRET_KEY = config.ui.secret_key
DEBUG = config.ui.debug
MAX_CLASSIFICATION = CLASSIFICATION.UNRESTRICTED

HWL_UNSECURED_UI = os.environ.get("HWL_UNSECURED_UI", "false").lower() == "true"
HWL_USE_REST_API = os.environ.get("HWL_USE_REST_API", "true").lower() == "true"
HWL_USE_WEBSOCKET_API = os.environ.get("HWL_USE_WEBSOCKET_API", "false").lower() == "true"
HWL_USE_JOB_SYSTEM = os.environ.get("HWL_USE_JOB_SYSTEM", "false").lower() == "true"
HWL_ENABLE_RULES = os.environ.get("HWL_ENABLE_RULES", "false").lower() == "true"
HWL_ENABLE_COVERAGE = os.environ.get("HWL_ENABLE_COVERAGE", "false").lower() == "true"
HWL_PLUGIN_DIRECTORY = os.environ.get("HWL_PLUGIN_DIRECTORY", "/etc/howler/plugins")


def get_version() -> str:
    """The version of the HOWLER API

    Returns:
        str: The howler version
    """
    return os.environ.get("HOWLER_VERSION", "this is not the version you are looking for")


def get_commit() -> str:
    """The commit of the currently deployed Howler API

    Returns:
        str: The commit of the currently deployed image
    """
    return os.environ.get("COMMIT_HASH", "this is not the commit you are looking for")


def get_branch() -> str:
    """The branch of the current Howler Image

    Returns:
        str: The current branch
    """
    return os.environ.get("BRANCH", "this is not the branch you are looking for")


redis_persistent = get_client(config.core.redis.persistent.host, config.core.redis.persistent.port, False)
redis = get_client(config.core.redis.nonpersistent.host, config.core.redis.nonpersistent.port, False)


cache = Cache(config={"CACHE_TYPE": "SimpleCache"})

# TRACKERS
QUOTA_TRACKER = UserQuotaTracker("quota", timeout=60 * 2, redis=redis)  # 2 Minutes timeout
