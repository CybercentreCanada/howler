import re
from collections.abc import Callable
from copy import deepcopy
from typing import Any

from elasticsearch import BadRequestError
from elasticsearch._sync.client.indices import IndicesClient
from flask import request

from howler.api import bad_request, forbidden, internal_error, make_subapi_blueprint, ok
from howler.api.search_utils import prune_scroll_items, select_safe_scroll_fields
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.logging.audit import audit
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import SearchException
from howler.helper.search import get_collection, has_access_control
from howler.odm.models.user import User
from howler.security.login import api_login
from howler.services import hit_service, lucene_service, search_service
from howler.services.search_service import SENSITIVE_USER_FIELDS, SensitiveUserFieldsException
from howler.utils.net_utils import generate_params

SUB_API = "search"
search_api = make_subapi_blueprint(SUB_API, api_version=2)
search_api._doc = "Perform search queries"  # type: ignore

logger = get_logger(__file__)


def _audit_request(user: User, func: Callable[..., Any], **fields):
    """Emit an audit event with search-specific request details."""
    audit([], fields, user["uname"], user, func)


def _search_with_scroll(
    indexes: str,
    index_list: list[str],
    query: str,
    user: User,
    params: dict[str, Any],
    scroll: Any,
    metadata: list[str],
) -> Any:
    """Run a scroll search with per-index stored-field projections."""
    requested_fl = params.get("fl")
    if (
        "user" in index_list
        and requested_fl is not None
        and any(sensitive_field in requested_fl for sensitive_field in SENSITIVE_USER_FIELDS)
    ):
        return forbidden(err="Invalid fields to retrieve.")

    scroll_collections: dict[str, Any] = {}
    for index in index_list:
        collection = get_collection(index, user)
        if collection is None:
            return bad_request(err=f"Not a valid index to search in: {index}")
        scroll_collections[index] = collection()

    scroll_params = params.copy()
    scroll_params["fl"], scroll_fields, include_scroll_id = select_safe_scroll_fields(scroll_collections, requested_fl)
    scroll_params["include_id"] = include_scroll_id

    result = search_service.search(indexes, query, user=user, scroll=scroll, **scroll_params)
    result["items"] = prune_scroll_items(result["items"], scroll_fields, include_scroll_id)
    if metadata and "hit" in index_list:
        hit_service.augment_metadata(result["items"], metadata, user)

    return ok(result)


@generate_swagger_docs()
@search_api.route("/<indexes>", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def search(indexes: str, user: User, **kwargs):
    """Search through specified index for a given query. Uses lucene search syntax for query.

    Variables:
    indexes  =>   Comma-separated list of indexes to search in (hit, event,...)

    Arguments:
    query   =>   Query to search for

    Optional Arguments:
    deep_paging_id      =>   ID of the next page or * to start deep paging
    scroll              =>   Scroll keep-alive duration for deep paging (default: 5m)
    filters             =>   List of additional filter queries limit the data
    offset              =>   Offset in the results
    rows                =>   Number of results per page
    sort                =>   How to sort the results (not available in deep paging)
    fl                  =>   List of fields to return
    timeout             =>   Maximum execution time (ms)
    use_archive         =>   Allow access to the datastore achive (Default: False)
    track_total_hits    =>   Track the total number of query matches, instead of stopping at 10000 (Default: False)
    metadata            =>   A list of additional features to be added to the result alongside the raw results

    Data Block:
    # Note that the data block is for POST requests only!
    {"query": "query",          # Query to search for
     "offset": 0,               # Offset in the results
     "rows": 100,               # Max number of results
     "sort": "field asc",       # How to sort the results
     "fl": "id,score",          # List of fields to return
     "scroll": "5m",            # Scroll keep-alive duration for deep paging
     "timeout": 1000,           # Maximum execution time (ms)
     "filters": ['fq'],         # List of additional filter queries limit the data
     "metadata": ["dossiers"]}  # List of additional features to add to the search


    Result Example:
    {"total": 201,                          # Total results found
     "offset": 0,                           # Offset in the result list
     "rows": 100,                           # Number of results returned
     "next_deep_paging_id": "asX3f...342",  # ID to pass back for the next page during deep paging
     "items": []}                           # List of results
    """
    index_list = [index.strip() for index in indexes.split(",") if index.strip()]

    fields = [
        "offset",
        "rows",
        "sort",
        "fl",
        "timeout",
        "deep_paging_id",
        "scroll",
        "track_total_hits",
    ]
    multi_fields = ["filters", "metadata"]
    boolean_fields = ["use_archive"]

    params, req_data = generate_params(request, fields, multi_fields)

    params.update(
        {
            k: str(req_data.get(k, "false")).lower() in ["true", ""]
            for k in boolean_fields
            if req_data.get(k, None) is not None
        }
    )

    if params.get("sort"):
        params["sort"] = [entry for entry in params["sort"].split(",") if entry]
    else:
        params.pop("sort", None)

    query = req_data.get("query", None)
    if not query:
        return bad_request(err="There was no search query.")

    _audit_request(user, search, index=indexes, query=query)

    metadata = params.pop("metadata", [])
    scroll = params.pop("scroll", None)

    try:
        if params.get("deep_paging_id") is not None:
            return _search_with_scroll(indexes, index_list, query, user, params, scroll, metadata)

        result = search_service.search(indexes, query, user=user, **params)
    except SensitiveUserFieldsException as e:
        return forbidden(err=e.message)
    except (SearchException, BadRequestError) as e:
        logger.exception(f"SearchException on query {query}")
        return bad_request(err=f"SearchException on query {query}: {str(e)}")
    except Exception as e:
        logger.exception(f"Exception on search with query {query}")
        return internal_error(f"Exception on search with query {query}: {e}")

    if metadata and "hit" in index_list:
        hit_service.augment_metadata(result["items"], metadata, user)

    return ok(result)


@generate_swagger_docs()
@search_api.route("/scroll", methods=["DELETE"])
@api_login(required_priv=["R"])
def clear_scroll(user: User, **kwargs):
    """Clear an Elasticsearch scroll context.

    Variables:
    None

    Arguments:
    scroll_id => Scroll ID of the context to clear, provided in the request body

    Result Example:
    {"succeeded": true, "num_freed": 1}
    """
    del user, kwargs

    data = request.get_json(silent=True)
    scroll_id = data.get("scroll_id") if isinstance(data, dict) else None
    if not isinstance(scroll_id, str) or not scroll_id:
        return bad_request(err="A scroll_id must be provided.")
    if scroll_id == "_all":
        return bad_request(err="The reserved scroll ID '_all' cannot be cleared.")

    try:
        return ok(search_service.clear_scroll(scroll_id))
    except (SearchException, BadRequestError) as e:
        return bad_request(err=f"SearchException: {e}")


@generate_swagger_docs()
@search_api.route("/<index>/explain", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def explain_query(index, **kwargs):
    """Search through specified index for a given Lucene query. Uses Lucene search syntax for query.

    Variables:
    index  =>   Index to explain against (hit, user,...)

    Arguments:
    query   =>   Lucene Query to explain

    Data Block:
    # Note that the data block is for POST requests only!
    {
        "query": "id:*", # Lucene Query to explain
    }


    Result Example:
    {
        'valid': True,
        'explanations': [
            {
                'valid': True,
                'explanation': 'ConstantScore(FieldExistsQuery [field=id])'
            }
        ]
    }
    """
    user = kwargs["user"]
    collection = get_collection(index, user)

    if collection is None:
        return bad_request(err=f"Not a valid index to explain: {index}")

    fields = ["query"]
    multi_fields: list[str] = []

    params, req_data = generate_params(request, fields, multi_fields)

    params["as_obj"] = False

    query = req_data.get("query", None)
    if not query:
        return bad_request(err="There was no query.")

    _audit_request(user, explain_query, index=index, query=query)

    # This regex checks for lucene phrases (i.e. the "Example Analytic" part of howler.analytic:"Example Analytic")
    # And then escapes them.
    # https://regex101.com/r/8u5F6a/1
    escaped_lucene = re.sub(r'((:\()?(".+?")(\)?))', lucene_service.replace_lucene_phrase, query)

    try:
        indices_client = IndicesClient(datastore().hit.datastore.client)

        result = deepcopy(
            indices_client.validate_query(q=escaped_lucene, explain=True, index=collection().index_name).body
        )

        del result["_shards"]

        for explanation in result["explanations"]:
            del explanation["index"]

        return ok(result)
    except Exception as e:  # pragma: no cover
        logger.exception(f"Exception on query {query}")
        return bad_request(err=f"Exception on query {query}: {str(e)}")


@generate_swagger_docs()
@search_api.route("/count/<index>", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def count(index, **kwargs):
    """Returns number of documents matching a query. Uses lucene search syntax for query.

    Variables:
    index  =>   Index to search in (hit, user,...)

    Arguments:
    query   =>   Query to search for

    Optional Arguments:
    filters             =>   List of additional filter queries limit the data
    timeout             =>   Maximum execution time (ms)
    use_archive         =>   Allow access to the datastore achive (Default: False)

    Data Block:
    # Note that the data block is for POST requests only!
    {
        "query": "query",     # Query to search for
        "timeout": 1000,      # Maximum execution time (ms)
    }


    Result Example:
    {
        "count": 201,                          # Total results found
    }
    """
    user = kwargs["user"]
    collection = get_collection(index, user)

    if collection is None:
        return bad_request(err=f"Not a valid index to search in: {index}")

    params, req_data = generate_params(request, ["timeout"], ["filters"])

    boolean_fields = ["use_archive"]
    params.update(
        {
            k: str(req_data.get(k, "false")).lower() in ["true", ""]
            for k in boolean_fields
            if req_data.get(k, None) is not None
        }
    )

    access_control = user["access_control"] if has_access_control(index) else None

    query = req_data.get("query", None)
    if not query:
        return bad_request(err="There was no search query.")

    _audit_request(user, count, index=index, query=query)

    filters = params.pop("filters", [])
    try:
        return ok(collection().count(query, filters, access_control=access_control))
    except (SearchException, BadRequestError) as e:
        logger.exception(f"SearchException on query {query}")
        return bad_request(err=f"SearchException on query {query}: {str(e)}")


@generate_swagger_docs()
@search_api.route("/facet/<indexes>", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def facet(indexes: str, **kwargs):
    """Perform field analysis on the selected fields. (Also known as facetting in lucene).

    This essentially counts the number of instances a field is seen with each specific
    values where the documents matches the specified queries.

    Variables:
    indexes       =>   Comma-separated indexes to search in (hit, user,...)

    Optional Arguments:
    query       =>   Query to search for
    mincount    =>   Minimum item count for the fieldvalue to be returned
    rows        => The max number of fieldvalues to return
    filters     =>   Additional query to limit to output
    fields        =>   Field to analyse

    Data Block:
    # Note that the data block is for POST requests only!
    {"fields": ["howler.id", ...]
     "query": "id:*",
     "mincount": "10",
     "rows": "10",
     "filters": ['fq']}

    Result Example:
    {
        "howler.id": {                 # Facetting results
            "value_0": 2,
            ...
            "value_N": 19,
        },
        ...
    }
    """
    user = kwargs["user"]

    fields = ["query", "mincount", "rows"]
    multi_fields = ["filters", "fields"]

    params = generate_params(request, fields, multi_fields)[0]

    _audit_request(user, facet, index=indexes, query=params.get("query", ""))

    try:
        fields = params.pop("fields")
        facet_result = search_service.facet(
            indexes=indexes,
            fields=fields,
            query=params.get("query"),
            mincount=params.get("mincount") or 1,
            rows=params.get("rows") or 10,
            filters=params.get("filters"),
            user=user,
        )

        return ok(facet_result)
    except (SearchException, BadRequestError) as e:
        query = params.get("query", "id:*")
        logger.exception(f"SearchException on query {query}")
        return bad_request(err=f"SearchException on query {query}: {str(e)}")
