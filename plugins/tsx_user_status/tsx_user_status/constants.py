"""Constants for the tsx_user_status plugin."""

from enum import StrEnum


class UserStatus(StrEnum):
    """Valid user status values for alert assignment workflows."""

    AVAILABLE = "available"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"
    AWAY = "away"


DEFAULT_STATUS = None
# Default prefixes for Redis status/shift keys. Deployments can override these
# via ``TSX_USER_STATUS_KEY_PREFIX`` / ``TSX_USER_STATUS_SHIFT_KEY_PREFIX``;
# the per-user ``{...}`` hash tag is still appended at key-build time.
KEY_PREFIX = "tsx_user_status:status"
SHIFT_KEY_PREFIX = "tsx_user_status:shift"

# Empty tag structure returned for users with no tags set.
DEFAULT_TAGS = {"portfolio": [], "products": [], "primary_disciplines": []}
