import json
import os

APP_NAME = os.environ.get("APP_NAME", "howler")

try:
    from howler.common.net import get_hostname

    hostname = get_hostname()
except Exception:
    hostname = "unknownhost"

HWL_SYSLOG_FORMAT = f"HWL %(levelname)8s {hostname} %(process)5d %(name)40s | %(message)s"
HWL_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s | %(message)s"
HWL_DATE_FORMAT = "%y/%m/%d %H:%M:%S"
HWL_JSON_FORMAT = (
    f"{{"
    f'"@timestamp": "%(asctime)s", '
    f'"event": {{ "module": "{APP_NAME}", "dataset": "%(name)s" }}, '
    f'"host": {{ "hostname": "{hostname}" }}, '
    f'"log": {{ "level": "%(levelname)s", "logger": "%(name)s" }}, '
    f'"process": {{ "pid": "%(process)d" }}, '
    f'"message": %(message)s}}'
)
HWL_ISO_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"
HWL_AUDIT_FORMAT = json.dumps(
    {
        "date": "%(asctime)s",
        "type": "audit",
        "app_name": APP_NAME,
        "api": "howler.api.audit",
        "severity": "%(levelname)s",
        "user": "%(user)s",
        "function": "%(function)s",
        "method": "%(method)s",
        "path": "%(path)s",
    }
).replace('"msg"', "%(message)s")
