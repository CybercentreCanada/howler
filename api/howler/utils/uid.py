import hashlib
import uuid
from typing import Any, Optional

import baseconv

from howler.common.exceptions import HowlerValueError

TINY = 8
SHORT = 16
MEDIUM = NORMAL = 32
LONG = 64


def get_random_id() -> str:
    """Get a random id in base 62

    Returns:
        str: A random base62 id
    """
    return baseconv.base62.encode(uuid.uuid4().int)


def get_id_from_data(data: Any, prefix: Optional[str] = None, length: int = MEDIUM) -> str:
    """Get an ID of a particular length, with an optional prefix, based on the provided data.

    Args:
        data (Any): The data to generate an ID from
        prefix (str, optional): The prefix to append to the generated ID. Defaults to None.
        length (int, optional): The length of the random ID. Defaults to MEDIUM.

    Raises:
        HowlerValueError: An invalid length was provided.

    Returns:
        str: A unique hash generated from the provided data
    """
    possible_len = [TINY, SHORT, MEDIUM, LONG]
    if length not in possible_len:
        raise HowlerValueError(f"Invalid hash length of {length}. Possible values are: {str(possible_len)}.")
    sha256_hash = hashlib.sha256(str(data).encode()).hexdigest()[:length]
    _hash = baseconv.base62.encode(int(sha256_hash, 16))

    if isinstance(prefix, str):
        _hash = f"{prefix}_{_hash}"

    return _hash
