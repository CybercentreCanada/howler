import sys
from datetime import datetime

# DO NOT REMOVE!!! THIS IS MAGIC!
# strptime Thread safe fix... yeah ...
datetime.strptime("2000", "%Y")
# END OF MAGIC


def now_as_iso() -> str:
    """Get the current time as an ISO formatted string"""
    if sys.version_info.minor < 11:
        return f"{datetime.utcnow().isoformat()}Z"
    else:
        from datetime import UTC

        return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
