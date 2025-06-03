import json
from datetime import datetime, timezone

from howler_client.logger import get_logger

logger = get_logger("json.encoding")


class DatetimeEncoder(json.JSONEncoder):
    "JSON Encoder that supports encoding datetime objects into iso format"

    def default(self, o):
        "Default encoder function"
        if isinstance(o, datetime):
            logger.debug("Encoding %s to ISO Format", repr(o))

            return o.astimezone(timezone.utc).isoformat()
        else:
            return super().default(o)


class BytesDatetimeEncoder(DatetimeEncoder):
    "JSON Encoder that supports encoding datetime objects into iso format, and decoding bytes objects"

    def default(self, o):
        "Default encoder function"
        if isinstance(o, bytes):
            logger.debug("Decoding bytes object")

            return o.decode("utf-8")
        elif isinstance(o, bytearray):
            logger.debug("Decoding bytearray object")

            return bytes(o).decode("utf-8", errors="replace")
        else:
            return super().default(o)
