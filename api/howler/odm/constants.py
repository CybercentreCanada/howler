import re

from dateutil.tz import tzutc  # type: ignore

from howler.odm.howler_enum import HowlerEnum

BANNED_FIELDS = {
    "_id",
    "__access_grp1__",
    "__access_lvl__",
    "__access_req__",
    "__access_grp2__",
}
DATEFORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
FIELD_SANITIZER = re.compile("^[a-z][a-z0-9_-]*$")
FLATTENED_OBJECT_SANITIZER = re.compile("^[a-z][a-z0-9_.]*$")
NOT_INDEXED_SANITIZER = re.compile("^[A-Za-z0-9_ -]*$")


UTC_TZ = tzutc()

DOMAIN_REGEX = (
    r"(?:(?:[A-Za-z0-9\u00a1-\uffff][A-Za-z0-9\u00a1-\uffff_-]{0,62})?[A-Za-z0-9\u00a1-\uffff]\.)+"
    r"(?:xn--)?(?:[A-Za-z0-9\u00a1-\uffff]{2,}\.?)"
)
DOMAIN_ONLY_REGEX = f"^{DOMAIN_REGEX}$"
EMAIL_REGEX = f"^[a-zA-Z0-9!#$%&'*+/=?^_‘{{|}}~-]+(?:\\.[a-zA-Z0-9!#$%&'*+/=?^_‘{{|}}~-]+)*@({DOMAIN_REGEX})$"
IPV4_REGEX = r"(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)"
IPV6_REGEX = (
    r"(?:(?:[0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,7}:|"
    r"(?:[0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|(?:[0-9a-fA-F]{1,4}:){1,5}(?::[0-9a-fA-F]{1,4}){1,2}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,4}(?::[0-9a-fA-F]{1,4}){1,3}|(?:[0-9a-fA-F]{1,4}:){1,3}(?::[0-9a-fA-F]{1,4}){1,4}|"
    r"(?:[0-9a-fA-F]{1,4}:){1,2}(?::[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:(?:(?::[0-9a-fA-F]{1,4}){1,6})|"
    r":(?:(?::[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(?::[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|"
    r"::(?:ffff(?::0{1,4}){0,1}:){0,1}(?:(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|"
    r"(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])|(?:[0-9a-fA-F]{1,4}:){1,4}:(?:(?:25[0-5]|"
    r"(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(?:25[0-5]|(?:2[0-4]|1{0,1}[0-9]){0,1}[0-9]))"
)
IP_REGEX = f"(?:{IPV4_REGEX}|{IPV6_REGEX})"
IP_ONLY_REGEX = f"^{IP_REGEX}$"
PRIVATE_IP = (
    r"(?:(?:127|10)(?:\.(?:[2](?:[0-5][0-5]|[01234][6-9])|[1][0-9][0-9]|[1-9][0-9]|[0-9])){3})|"
    r"(?:172\.(?:1[6-9]|2[0-9]|3[0-1])(?:\.(?:2[0-4][0-9]|25[0-5]|[1][0-9][0-9]|[1-9][0-9]|[0-9])){2}|"
    r"(?:192\.168(?:\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])){2}))"
)
PHONE_REGEX = r"^(\+?\d{1,2})?[ .-]?(\(\d{3}\)|\d{3})[ .-](\d{3})[ .-](\d{4})$"
SSDEEP_REGEX = r"^[0-9]{1,18}:[a-zA-Z0-9/+]{0,64}:[a-zA-Z0-9/+]{0,64}$"
MD5_REGEX = r"^[a-f0-9]{32}$"
SHA1_REGEX = r"^[a-f0-9]{40}$"
SHA256_REGEX = r"^[a-f0-9]{64}$"
HOWLER_HASH_REGEX = r"^[a-f0-9]{1,64}$"
MAC_REGEX = r"^(?:(?:[0-9a-f]{2}-){5}[0-9a-f]{2}|(?:[0-9a-f]{2}:){5}[0-9a-f]{2})$"
URI_PATH = r"(?:[/?#]\S*)"
FULL_URI = f"^((?:(?:[A-Za-z]*:)?//)?(?:\\S+(?::\\S*)?@)?({IP_REGEX}|{DOMAIN_REGEX})(?::\\d{{2,5}})?){URI_PATH}?$"
PLATFORM_REGEX = r"^(Windows|Linux|MacOS|Android|iOS)$"
PROCESSOR_REGEX = r"^x(64|86)$"


class Status(str, HowlerEnum):
    """Enum representing the status of a record in howler.

    Args:
      OPEN (str): Record is open and unresolved.
      IN_PROGRESS (str): Record is currently being investigated.
      ON_HOLD (str): Record processing is on hold.
      RESOLVED (str): Record has been resolved.
    """

    OPEN = "open"
    IN_PROGRESS = "in-progress"
    ON_HOLD = "on-hold"
    RESOLVED = "resolved"


class CaseEscalation(str, HowlerEnum):
    """Enum representing the escalation of a case in Howler.

    Args:
      NORMAL (str): Default escalation level.
      FOCUS (str): Elevated escalation level requiring extra attention.
      CRISIS (str): Highest escalation level requiring urgent response.
    """

    NORMAL = "normal"
    FOCUS = "focus"
    CRISIS = "crisis"
