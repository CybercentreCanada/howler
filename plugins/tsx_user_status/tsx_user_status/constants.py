"""Constants for the tsx_user_status plugin."""

from enum import StrEnum


class UserStatus(StrEnum):
    """Valid user status values.

    Numeric statuses (1-15) represent shift/availability codes.
    Named statuses support alert assignment workflows.
    """

    STATUS_1 = "1"
    STATUS_2 = "2"
    STATUS_3 = "3"
    STATUS_4 = "4"
    STATUS_5 = "5"
    STATUS_6 = "6"
    STATUS_7 = "7"
    STATUS_8 = "8"
    STATUS_9 = "9"
    STATUS_10 = "10"
    STATUS_11 = "11"
    STATUS_12 = "12"
    STATUS_13 = "13"
    STATUS_14 = "14"
    STATUS_15 = "15"

    # Assignment statuses
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
