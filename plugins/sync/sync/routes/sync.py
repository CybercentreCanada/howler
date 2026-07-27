from datetime import datetime
from typing import Any

from flask import request
from howler.api import bad_request, make_subapi_blueprint, ok
from howler.api.v1.utils.params import parse_parameters
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.types import SearchResult
from howler.odm.models.hit import Hit
from howler.security import api_login

from sync.services import sync_service
from sync.utils.parsers import ip_format_type, parse_ip_format, parse_tz_datetime

SUB_API = "sync"
sync_api = make_subapi_blueprint(SUB_API, api_version=1)

logger = get_logger(__file__)


@generate_swagger_docs()
@sync_api.route("/hit_diffs", methods=["GET"])
@parse_parameters(from_date=(parse_tz_datetime, "required"), to_date=parse_tz_datetime, ip_format=parse_ip_format)
@api_login(required_priv=["R"])
def get_upserted_hits(
    *,
    from_date: datetime,
    to_date: datetime | None = None,
    ip_format: ip_format_type | None = None,
    **_extra_args,
):
    """Get the hits that have been created or updated since the last sync.

    Arguments:
    from_date       =>   The date to check for new or updated hits since, required.

    Optional Arguments:
    to_date         =>   The date beyond which to ignore any new or updated hits.
    ip_format       =>   The format of the IP addresses, default to encoded bytes, matching the schema from this api.
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
    search_args: dict[str, Any] = {}

    for param, type_cast in search_params:
        if param in request.args:
            try:
                search_args[param] = type_cast(request.args[param])
            except ValueError:
                return bad_request(f"Invalid value for {param}: {request.args[param]}")

    if to_date is not None and from_date > to_date:
        logger.warning("to_date is earlier than from_date, ignoring to_date")
        to_date = None

    if ip_format is None:
        ip_format = "encoded_bytes"

    res = sync_service.get_upserted_hits(data_interval_start=from_date, data_interval_end=to_date, **search_args)
    parsed: SearchResult[dict[str, Any]] = {
        **res,
        "items": [hit.as_primitives(ip_format=ip_format) for hit in res["items"]],
    }

    return ok(parsed)


@generate_swagger_docs()
@sync_api.route("/schema/hit", methods=["GET"])
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
    schema = sync_service.get_model_struct_schema(Hit)
    return ok(schema.jsonValue())
