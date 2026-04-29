import re
from copy import deepcopy
from typing import Any

from elasticsearch import BadRequestError
from elasticsearch._sync.client.indices import IndicesClient
from flask import Request, request

from howler.api import bad_request, make_subapi_blueprint, ok
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import SearchException
from howler.helper.search import get_collection, has_access_control
from howler.security import api_login
from howler.services import hit_service, lucene_service, search_service

SUB_API = "search"
search_api = make_subapi_blueprint(SUB_API, api_version=2)
search_api._doc = "Perform search queries"  # type: ignore

logger = get_logger(__file__)


def generate_params(request: Request, fields: list[str], multi_fields: list[str], params: dict[str, Any] | None = None):
    """Generate a list of parameters, combining the request data and the query arguments"""
    # I hate you, python
    if params is None:
        params = {}

    if request.method == "POST":
        req_data = request.get_json(silent=True) or {"query": "*:*"}

        params = {
            **params,
            **{k: req_data[k] for k in fields if k in req_data},
            **{k: req_data[k] for k in multi_fields if k in req_data},
        }

    else:
        req_data = request.args
        params = {
            **params,
            **{k: req_data[k] for k in fields if k in req_data},
            **{k: req_data.getlist(k) for k in multi_fields if k in req_data},
        }

    return params, req_data


@generate_swagger_docs()
@search_api.route("/<indexes>", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def search(indexes: str, **kwargs):
    """Search through specified index for a given query. Uses lucene search syntax for query.

    Variables:
    indexes  =>   Comma-separated list of indexes to search in (hit, observable,...)

    Arguments:
    query   =>   Query to search for

    Optional Arguments:
    deep_paging_id      =>   ID of the next page or * to start deep paging
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
    user = kwargs["user"]

    index_list = indexes.split(",")

    fields = [
        "offset",
        "rows",
        "sort",
        "fl",
        "timeout",
        "deep_paging_id",
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

    if has_access_control(index_list):
        params["access_control"] = user["access_control"]

    params["sort"] = [entry for entry in params.get("sort", "").split(",") if entry] or search_service.DEFAULT_SORT

    query = req_data.get("query", None)
    if not query:
        return bad_request(err="There was no search query.")

    metadata = params.pop("metadata", [])
    access_control = params.pop("access_control", None)
    result = search_service.search(indexes, query, access_control=access_control, **params)

    if metadata and any(idx in index_list for idx in ["hit"]):
        hit_service.augment_metadata(result["items"], metadata, user)

    return ok(result)


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
    except Exception as e:
        logger.exception("Exception on query explanation")
        return bad_request(err=f"Exception: {e}")


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

    filters = params.pop("filters", [])
    try:
        return ok(collection().count(query, filters, access_control=access_control))
    except (SearchException, BadRequestError) as e:
        return bad_request(err=f"SearchException: {e}")


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

    try:
        fields = params.pop("fields")
        facet_result: dict[str, dict[str, Any]] = {}
        index_list = indexes.split(",")

        # TODO: rewrite this to facet acess all indices at the same time instead of separate network calls
        for index in index_list:
            collection = get_collection(index, user)
            if collection is None:
                return bad_request(err=f"Not a valid index to search in: {index}")

            if has_access_control(index):
                params.update({"access_control": user["access_control"]})
            for field in fields:
                facet_result.setdefault(field, {})

                if field not in collection().fields():
                    logger.warning("Invalid field %s requested for faceting, skipping", field)
                    continue

                facet_result[field].update(collection().facet(field, **params))

        return ok(facet_result)
    except (SearchException, BadRequestError) as e:
        logger.error("SearchException: %s", str(e), exc_info=True)
        return bad_request(err=f"SearchException: {e}")
