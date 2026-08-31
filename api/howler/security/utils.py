import base64
import os
import re
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Union
from urllib.parse import urlparse

from opentelemetry import trace
from passlib.hash import bcrypt

from howler.common.exceptions import HowlerValueError, InvalidClassification
from howler.config import CLASSIFICATION, config

if TYPE_CHECKING:
    from howler.odm.models.user import User

tracer = trace.get_tracer(__name__)


def is_classification_accessible(
    user: Union["User", dict[str, Any]],
    classification: Optional[str],
) -> bool:
    """Check whether a user can access a document at the given classification.

    This is the per-document counterpart of the ``access_control`` Lucene filter
    applied by search endpoints: documents on access-controlled indexes (hit,
    event, case) must have their classification checked against the requesting
    user's clearance whenever they are fetched or modified directly by ID.

    Admin-type users bypass classification access control entirely, mirroring
    the behaviour of the search filtering path.

    Args:
        user: The requesting user (User ODM object or its primitive dict).
        classification: The classification of the document being accessed.

    Returns:
        True if the user can access the document, False otherwise.
    """
    if not classification:
        return True

    if isinstance(user, dict):
        user_type = user.get("type", [])
        user_classification: Any = user.get("classification")
    else:
        user_type = user["type"]
        user_classification = user["classification"]

    if "admin" in user_type:
        return True

    try:
        return CLASSIFICATION.is_accessible(
            user_classification if user_classification is not None else CLASSIFICATION.UNRESTRICTED,
            classification,
        )
    except InvalidClassification:
        return False


# Fields that must never be modified through bulk/script-based update endpoints.
# ``classification`` is protected because script updates bypass ODM serialization,
# so the derived access-control bookkeeping fields (``__access_lvl__``, etc.) would
# silently diverge from the new classification string. The bookkeeping fields
# themselves are protected because the search-time access filter is built directly
# on them (``__access_lvl__:[0 TO <user_lvl>]``); rewriting them rewrites who can
# see a document.
PROTECTED_UPDATE_FIELDS = frozenset(
    {
        "classification",
        "__access_lvl__",
        "__access_req__",
        "__access_grp1__",
        "__access_grp2__",
    }
)


def validate_bulk_operation_targets(operations: Iterable[tuple[str, str, Any]]) -> None:
    """Reject bulk update operations that target protected fields.

    Bulk update endpoints execute operations as datastore scripts, which bypass
    ODM serialization. Operations on ``classification`` or its derived
    ``__access_*`` bookkeeping fields cannot be applied safely through this path
    and would allow users to alter document visibility (their own or others').

    Args:
        operations: List of ``(operation, key, value)`` tuples from the request.

    Raises:
        HowlerValueError: If any operation targets a protected field.
    """
    for _, key, _ in operations:
        if key in PROTECTED_UPDATE_FIELDS:
            raise HowlerValueError(f"Cannot modify protected field {key} through bulk updates")


UPPERCASE = r"[A-Z]"
LOWERCASE = r"[a-z]"
NUMBER = r"[0-9]"
SPECIAL = r'[ !#$@%&\'()*+,-./[\\\]^_`{|}~"]'
PASS_BASIC = (
    [chr(x + 65) for x in range(26)]
    + [chr(x + 97) for x in range(26)]
    + [str(x) for x in range(10)]
    + ["!", "@", "$", "^", "?", "&", "*", "(", ")"]
)


def generate_random_secret(length: int = 25) -> str:
    """Generate a random secret

    Args:
        length (int, optional): The length of the secret. Defaults to 25.

    Returns:
        str: The random secret
    """
    return base64.b32encode(os.urandom(length)).decode("UTF-8")


def get_password_hash(password: Optional[str]) -> Optional[str]:
    """Get a bcrypt hash of the password

    Args:
        password (Optional[str]): The password to hash

    Returns:
        str: The hash of the password
    """
    if password is None or len(password) == 0:
        return None

    return bcrypt.hash(password)


@tracer.start_as_current_span("verify_password")
def verify_password(password: str, pw_hash: str):
    """Use bcrypt to verify a user's password against the hash"""
    try:
        return bcrypt.verify(password, pw_hash)
    except ValueError:
        return False
    except TypeError:
        return False


def get_password_requirement_message(
    lower: bool = True,
    upper: bool = True,
    number: bool = False,
    special: bool = False,
    min_length: int = 12,
) -> str:
    """Get a custom password requirement message based on the configuration values

    Args:
        lower (bool, optional): Must include lowercase? Defaults to True.
        upper (bool, optional): Must include uppercase? Defaults to True.
        number (bool, optional): Must include number? Defaults to False.
        special (bool, optional): Must include special characters? Defaults to False.
        min_length (int, optional): What is the minimum length? Defaults to 12.

    Returns:
        str: The formatted password requirement message
    """
    msg = f"Password needs to be at least {min_length} characters"

    if lower or upper or number or special:
        msg += " with the following characteristics: "
        specs = []
        if lower:
            specs.append("lowercase letters")
        if upper:
            specs.append("uppercase letters")
        if number:
            specs.append("numbers")
        if special:
            specs.append("special characters")

        msg += ", ".join(specs)

    return msg


def check_password_requirements(
    password: str,
    lower: bool = True,
    upper: bool = True,
    number: bool = False,
    special: bool = False,
    min_length: int = 12,
) -> bool:
    """Validate the given password based on the password requirements

    Args:
        password (str): The password to check
        lower (bool, optional): Must include lowercase? Defaults to True.
        upper (bool, optional): Must include uppercase? Defaults to True.
        number (bool, optional): Must include number? Defaults to False.
        special (bool, optional): Must include special characters? Defaults to False.
        min_length (int, optional): What is the minimum length? Defaults to 12.

    Returns:
        bool: Does the password meet the requirements?
    """
    check_upper = re.compile(UPPERCASE)
    check_lower = re.compile(LOWERCASE)
    check_number = re.compile(NUMBER)
    check_special = re.compile(SPECIAL)

    if get_password_hash(password) is None:
        return True

    if len(password) < min_length:
        return False

    if upper and len(check_upper.findall(password)) == 0:
        return False

    if lower and len(check_lower.findall(password)) == 0:
        return False

    if number and len(check_number.findall(password)) == 0:
        return False

    if special and len(check_special.findall(password)) == 0:
        return False

    return True


def get_random_password(alphabet: Optional[List] = None, length: int = 24) -> str:
    """Get a random password

    Args:
        alphabet (Optional[List], optional): The alphabet to base the password on. Defaults to None.
        length (int, optional): The length of the password. Defaults to 24.

    Returns:
        str: The generated password
    """
    if alphabet is None:
        alphabet = PASS_BASIC
    r_bytes = bytearray(os.urandom(length))
    a_list = []

    for byte in r_bytes:
        while byte >= (256 - (256 % len(alphabet))):
            byte = ord(os.urandom(1))
        a_list.append(alphabet[byte % len(alphabet)])

    return "".join(a_list)


def get_disco_url(host_url: Optional[str]):
    """Get the discovery URL based on the current host"""
    if type(host_url) is str and "localhost" not in host_url:
        if not host_url.startswith("http"):
            host_url = f"https://{host_url}"

        original_hostname = urlparse(host_url).hostname

        if original_hostname:
            hostname = re.sub(r"^(.*?)howler(-stg)?(.+)$", r"\1discover\3", original_hostname)

            return f"https://{hostname}/eureka/apps"
        else:
            return config.discovery.url
    else:
        return config.discovery.url


def encryption_key() -> bytes:
    """Return the configured encryption key for JWE payloads."""
    secret_key = config.system.encryption_key
    if secret_key is None:
        raise HowlerValueError("System encryption_key must be configured before encrypting tokens")

    return secret_key.encode("utf-8")
