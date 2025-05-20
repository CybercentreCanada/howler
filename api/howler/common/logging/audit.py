import logging
import os
import sys

from flask import request

from howler.common.logging.format import (
    HWL_AUDIT_FORMAT,
    HWL_DATE_FORMAT,
    HWL_ISO_DATE_FORMAT,
    HWL_LOG_FORMAT,
)
from howler.config import DEBUG, config

AUDIT = config.ui.audit

AUDIT_KW_TARGET = [
    "sid",
    "sha256",
    "copy_sid",
    "filter",
    "query",
    "username",
    "group",
    "rev",
    "wq_id",
    "index",
    "cache_key",
    "alert_key",
    "alert_id",
    "url",
    "q",
    "fq",
    "file_hash",
    "heuristic_id",
    "error_key",
    "mac",
    "vm_type",
    "vm_name",
    "config_name",
    "servicename",
    "vm",
    "transition",
    "data",
    "id",
    "comment_id",
    "label_set",
    "tool_name",
    "operation_id",
    "category",
    "label",
]

AUDIT_LOG = logging.getLogger("howler.api.audit")
AUDIT_LOG.propagate = False

if AUDIT:
    AUDIT_LOG.setLevel(logging.DEBUG)

if not os.path.exists(config.logging.log_directory):
    os.makedirs(config.logging.log_directory)

fh = logging.FileHandler(os.path.join(config.logging.log_directory, "hwl_audit.log"))
fh.setLevel(logging.DEBUG)
fh.setFormatter(
    logging.Formatter(
        HWL_LOG_FORMAT if DEBUG else HWL_AUDIT_FORMAT,
        HWL_DATE_FORMAT if DEBUG else HWL_ISO_DATE_FORMAT,
    )
)
AUDIT_LOG.addHandler(fh)

ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(
    logging.Formatter(
        HWL_LOG_FORMAT if DEBUG else HWL_AUDIT_FORMAT,
        HWL_DATE_FORMAT if DEBUG else HWL_ISO_DATE_FORMAT,
    )
)
AUDIT_LOG.addHandler(ch)

#########################
# End of prepare logger #
#########################


def audit(args, kwargs, logged_in_uname, user, func, impersonator=None):
    """Log audit information for a given function executed by a given user."""
    try:
        json_blob = request.json
        if not isinstance(json_blob, dict):
            json_blob = {}
    except Exception:
        json_blob = {}

    params_list = (
        list(args)
        + ["%s='%s'" % (k, v) for k, v in kwargs.items() if k in AUDIT_KW_TARGET]
        + ["%s='%s'" % (k, v) for k, v in request.args.items() if k in AUDIT_KW_TARGET]
        + ["%s='%s'" % (k, v) for k, v in json_blob.items() if k in AUDIT_KW_TARGET]
    )

    if impersonator:
        audit_user = f"{impersonator} on behalf of {logged_in_uname}"
    else:
        audit_user = logged_in_uname
    if DEBUG:
        # In debug mode, you'll get an output like:
        # 23/03/20 14:26:56 DEBUG howler.api.audit | goose - search(index='...', query='...')
        AUDIT_LOG.debug(
            "%s - %s(%s)",
            audit_user,
            func.__name__,
            ", ".join(params_list),
        )
    else:
        # In prod, you'll get an output like:
        # {
        #     "date": "2023-03-20T18:33:27-0400",
        #     "type": "audit",
        #     "app_name": "howler",
        #     "api": "howler.api.audit",
        #     "severity": "INFO",
        #     "user": "goose",
        #     "function": "search(index='hit', query='howler.escalation:alert AND howler.status:open')",
        #     "method": "POST",
        #     "path": "/api/v1/search/hit/"
        # }
        AUDIT_LOG.info(
            "",
            extra={
                "user": audit_user,
                "function": f"{func.__name__}({', '.join(params_list)})",
                "method": request.method,
                "path": request.path,
            },
        )
