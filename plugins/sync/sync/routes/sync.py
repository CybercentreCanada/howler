from datetime import datetime
from typing import Any

from flask import request
from howler.api import make_subapi_blueprint, ok
from howler.api.v1.utils.params import parse_parameters
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.security import api_login

from sync.services import sync_service
from sync.utils.parsers import parse_datetime

SUB_API = "sync"
sync_api = make_subapi_blueprint(SUB_API, api_version=1)

logger = get_logger(__file__)


@generate_swagger_docs()
@sync_api.route("/hit_diffs", methods=["GET"])
@parse_parameters(from_date=(parse_datetime, "required"), to_date=parse_datetime)
@api_login(required_priv=["R"])
def get_upserted_hits(*, from_date: datetime, to_date: datetime | None = None, **_extra_args):
    """Get the hits that have been created or updated since the last sync.

    Arguments:
    from_date       =>   The date to check for new or updated hits since, required.

    Optional Arguments:
    to_date         =>   The date beyond which to ignore any new or updated hits.
    deep_paging_id  =>   ID of the next page or * to start deep paging
    offset          =>   Offset in the results
    rows            =>   Number of results per page
    timeout         =>   Maximum execution time (ms)

    Result Example:
    {
        "total": 201,                          # Total results found, not accurate if more than 10000
        "offset": 0,                           # Offset in the result list
        "rows": 100,                           # Number of results returned
        "next_deep_paging_id": "asX3f...342",  # ID to pass back for the next page during deep paging
        "items": [
            ...hits  # list of hits that have been created or updated since the last sync
        ]
    }
    """
    # don't use parse_parameters because we don't want to forward None if the parameter is not present
    search_params = [("deep_paging_id", str), ("offset", int), ("rows", int), ("timeout", int)]
    search_args: dict[str, Any] = {
        param: request.args.get(param, type=type_cast)
        for param, type_cast in search_params
        if request.args.get(param) is not None
    }

    res = sync_service.get_upserted_hits(data_interval_start=from_date, data_interval_end=to_date, **search_args)

    return ok(res)


@generate_swagger_docs()
@sync_api.route("/hit_schema", methods=["GET"])
def get_hit_struct_schema():
    """Get the hit schema for the current Howler version.

    Result Example:
    {  # The hit schema as a struct json
        "fields": [
            {
                "metadata": {},
                "name": "timestamp",
                "nullable": true,
                "type": "timestamp"
            },
            ...
        ],
        "type": "struct"
    }
    """
    schema = sync_service.get_hit_struct_schema()
    return ok(schema.json())
