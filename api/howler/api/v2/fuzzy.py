from flask import request

from howler.api import bad_request, make_subapi_blueprint, ok
from howler.common.logging import get_logger
from howler.common.logging.audit import audit
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import SearchException
from howler.helper.search import has_access_control
from howler.security import api_login
from howler.services import fuzzy_service

SUB_API = "fuzzy"
fuzzy_api = make_subapi_blueprint(SUB_API, api_version=2)
fuzzy_api._doc = "Perform fuzzy plain-text searches across indexes"  # type: ignore

logger = get_logger(__file__)


@generate_swagger_docs()
@fuzzy_api.route("/search", methods=["POST"])
@api_login(audit=False, required_priv=["R"])
def fuzzy_search(**kwargs):  # noqa: C901
    """Perform a plain-text fuzzy search across hits, events, and cases.

    Accepts a plain string (word, IP, domain, URL, username, email, hash) and
    returns ranked results across specified indexes.

    Variables:
    None

    Arguments:
    None

    Data Block:
    {
        "query": "192.168.1.1",             # Plain text search query (required)
        "indexes": ["hit", "event", "case"],  # Indexes to search (optional, defaults to all)
        "filters": ["howler.status:open"],          # Additional filters (optional)
        "offset": 0,                                # Offset into results (optional, default 0)
        "rows": 100,                                # Number of results (optional, default 100)
        "track_total_hits": false                   # Track total hits (optional, default false)
    }

    Result Example:
    {
        "total": 42,
        "offset": 0,
        "rows": 42,
        "items": [
            {
                "__index": "hit",
                "_score": 12.5,
                "howler": {"id": "abc123", ...},
                ...
            }
        ]
    }
    """
    user = kwargs["user"]

    req_data = request.get_json(silent=True)
    if not req_data:
        return bad_request(err="Request body is required.")

    query = req_data.get("query", "").strip()
    if not query:
        return bad_request(err="Search query is required and cannot be empty.")

    # Parse indexes
    indexes = req_data.get("indexes", ["hit", "event", "case"])
    if isinstance(indexes, str):
        indexes = [idx.strip() for idx in indexes.split(",") if idx.strip()]

    # Validate indexes
    for idx in indexes:
        if idx not in fuzzy_service.VALID_INDEXES:
            return bad_request(err=f"Invalid index: {idx}. Must be one of: hit, event, case")

    if not indexes:
        return bad_request(err="At least one index must be specified.")

    audit(
        [],
        {**kwargs, "index": ",".join(indexes), "query": query},
        user["uname"],
        user,
        fuzzy_search,
    )

    filters = req_data.get("filters", None)
    if isinstance(filters, str):
        filters = [filters]

    try:
        offset = int(req_data.get("offset", 0))
        rows = int(req_data.get("rows", 100))
    except (TypeError, ValueError):
        return bad_request(err="'offset' and 'rows' must be integers.")
    track_total_hits = bool(req_data.get("track_total_hits", False))

    # Apply access control if indexes are access controlled
    access_control = None
    if has_access_control(indexes):
        access_control = user["access_control"]

    logger.info("%s: %s", ", ".join(indexes), query)

    try:
        result = fuzzy_service.fuzzy_search(
            indexes=indexes,
            query=query,
            filters=filters,
            offset=offset,
            rows=rows,
            track_total_hits=track_total_hits,
            access_control=access_control,
        )
    except SearchException as e:  # pragma: no cover
        return bad_request(err=str(e))

    return ok(result)
