from typing import Union

from elasticsearch import BadRequestError
from flask import request
from sigma.backends.elasticsearch import LuceneBackend
from sigma.rule import SigmaRule
from werkzeug.exceptions import BadRequest
from yaml.scanner import ScannerError

from howler.api import bad_request, make_subapi_blueprint, ok
from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.common.swagger import generate_swagger_docs
from howler.datastore.exceptions import SearchException
from howler.helper.search import (
    get_collection,
    get_default_sort,
    has_access_control,
    list_all_fields,
)
from howler.security import api_login

SUB_API = "search"
search_api = make_subapi_blueprint(SUB_API, api_version=1)
search_api._doc = "Perform search queries"

logger = get_logger(__file__)


def generate_params(request, fields, multi_fields, params=None):
    """Generate a list of parameters, combining the request data and the query arguments"""
    # I hate you, python
    if params is None:
        params = {}

    if request.method == "POST":
        try:
            req_data = request.json
        except BadRequest:
            req_data = {"query": "*:*"}

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
            **{k: req_data.getlist(k, None) for k in multi_fields if k in req_data},
        }

    return params, req_data


@generate_swagger_docs()
@search_api.route("/<index>", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def search(index, **kwargs):
    """Search through specified index for a given query. Uses lucene search syntax for query.

    Variables:
    index  =>   Index to search in (hit, user,...)

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

    Data Block:
    # Note that the data block is for POST requests only!
    {"query": "query",     # Query to search for
     "offset": 0,          # Offset in the results
     "rows": 100,          # Max number of results
     "sort": "field asc",  # How to sort the results
     "fl": "id,score",     # List of fields to return
     "timeout": 1000,      # Maximum execution time (ms)
     "filters": ['fq']}    # List of additional filter queries limit the data


    Result Example:
    {"total": 201,                          # Total results found
     "offset": 0,                           # Offset in the result list
     "rows": 100,                           # Number of results returned
     "next_deep_paging_id": "asX3f...342",  # ID to pass back for the next page during deep paging
     "items": []}                           # List of results
    """
    user = kwargs["user"]
    collection = get_collection(index, user)
    default_sort = get_default_sort(index, user)

    if collection is None or default_sort is None:
        return bad_request(err=f"Not a valid index to search in: {index}")

    fields = [
        "offset",
        "rows",
        "sort",
        "fl",
        "timeout",
        "deep_paging_id",
        "track_total_hits",
    ]
    multi_fields = ["filters"]
    boolean_fields = ["use_archive"]

    params, req_data = generate_params(request, fields, multi_fields)

    params.update(
        {
            k: str(req_data.get(k, "false")).lower() in ["true", ""]
            for k in boolean_fields
            if req_data.get(k, None) is not None
        }
    )

    if has_access_control(index):
        params.update({"access_control": user["access_control"]})

    params["as_obj"] = False
    params.update({"sort": (params.get("sort", None) or default_sort).split(",")})

    query = req_data.get("query", None)
    if not query:
        return bad_request(err="There was no search query.")

    try:
        return ok(collection().search(query, **params))
    except (SearchException, BadRequestError) as e:
        return bad_request(err=f"SearchException: {e}")


@generate_swagger_docs()
@search_api.route("/<index>/eql", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def eql_search(index, **kwargs):
    """Search through specified index for a given EQL query. Uses EQL search syntax for query.

    Variables:
    index  =>   Index to search in (hit, user,...)

    Arguments:
    eql_query   =>   EQL Query to search for

    Optional Arguments:
    filters             =>   List of additional filter queries limit the data, written in lucene
    fl                  =>   Comma-separated list of fields to return
    rows                =>   Number of results per page
    timeout             =>   Maximum execution time (ms)

    Data Block:
    # Note that the data block is for POST requests only!
    {"eql_query": "query", # EQL Query to search for
     "rows": 100,          # Max number of results
     "fl": "id,score",     # List of fields to return
     "timeout": 1000,      # Maximum execution time (ms)
     "filters": ['fq']}    # List of additional filter queries limit the data


    Result Example:
    {"total": 201,                          # Total results found
     "offset": 0,                           # Offset in the result list
     "rows": 100,                           # Number of results returned
     "items": []}                           # List of results
    """
    user = kwargs["user"]
    collection = get_collection(index, user)

    if collection is None:
        return bad_request(err=f"Not a valid index to search in: {index}")

    fields = [
        "eql_query",
        "fl",
        "rows",
        "timeout",
    ]
    multi_fields = ["filters"]

    params, req_data = generate_params(request, fields, multi_fields)

    if has_access_control(index):
        params.update({"access_control": user["access_control"]})

    params["as_obj"] = False

    eql_query = req_data.get("eql_query", None)
    if not eql_query:
        return bad_request(err="There was no EQL search query.")

    try:
        return ok(collection().raw_eql_search(**params))
    except (SearchException, BadRequestError) as e:
        logger.error("SearchException: %s", str(e), exc_info=True)
        return bad_request(err=f"SearchException: {e}")


@generate_swagger_docs()
@search_api.route("/<index>/sigma", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def sigma_search(index, **kwargs):
    """Search through specified index using a given sigma rule. Uses sigma rule syntax for query.

    Variables:
    index  =>   Index to search in (hit, user,...)

    Arguments:
    sigma   =>   Sigma rule to search on

    Optional Arguments:
    filters             =>   List of additional filter queries limit the data, written in lucene
    fl                  =>   Comma-separated list of fields to return
    rows                =>   Number of results per page
    timeout             =>   Maximum execution time (ms)

    Data Block:
    # Note that the data block is for POST requests only!
    {"sigma": "sigma yaml", # Sigma Rule to search for
     "rows": 100,           # Max number of results
     "fl": "id,score",      # List of fields to return
     "timeout": 1000,       # Maximum execution time (ms)
     "filters": ['fq']}     # List of additional filter queries limit the data


    Result Example:
    {"total": 201,                          # Total results found
     "offset": 0,                           # Offset in the result list
     "rows": 100,                           # Number of results returned
     "items": []}                           # List of results
    """
    user = kwargs["user"]
    collection = get_collection(index, user)
    default_sort = get_default_sort(index, user)

    if collection is None or default_sort is None:
        return bad_request(err=f"Not a valid index to search in: {index}")

    fields = [
        "offset",
        "rows",
        "sort",
        "fl",
        "timeout",
        "deep_paging_id",
        "track_total_hits",
    ]
    multi_fields = ["filters"]
    boolean_fields = ["use_archive"]

    params, req_data = generate_params(request, fields, multi_fields)

    params.update(
        {
            k: str(req_data.get(k, "false")).lower() in ["true", ""]
            for k in boolean_fields
            if req_data.get(k, None) is not None
        }
    )

    if has_access_control(index):
        params.update({"access_control": user["access_control"]})

    params["as_obj"] = False
    params.update({"sort": (params.get("sort", None) or default_sort).split(",")})

    sigma = req_data.get("sigma", None)
    if not sigma:
        return bad_request(err="There was no sigma rule.")

    try:
        rule = SigmaRule.from_yaml(sigma)
    except ScannerError as e:
        return bad_request(err=f"Error when parsing yaml: {e.problem} {e.problem_mark}")

    es_collection = collection()

    lucene_queries = LuceneBackend(index_names=[es_collection.index_name]).convert_rule(rule)

    try:
        return ok(es_collection.search("*:*", **params, filters=[*params.get("filters", []), *lucene_queries]))
    except (SearchException, BadRequestError) as e:
        logger.error("SearchException: %s", str(e), exc_info=True)
        return bad_request(err=f"SearchException: {e}")


@generate_swagger_docs()
@search_api.route("/grouped/<index>/<group_field>", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def group_search(index, group_field, **kwargs):
    """Search for a given query and groups the data based on a specific field. Uses lucene search syntax.

    Variables:
    index        =>   Index to search in (hit, user,...)
    group_field  =>   Field to group on

    Optional Arguments:
    group_sort   =>   How to sort the results inside the group
    limit        =>   Maximum number of results return for each groups
    query        =>   Query to search for
    filters      =>   List of additional filter queries limit the data
    offset       =>   Offset in the results
    rows         =>   Max number of results
    sort         =>   How to sort the results
    fl           =>   List of fields to return

    Data Block:
    # Note that the data block is for POST requests only!
    {"group_sort": "score desc",
     "limit": 10,
     "query": "query",
     "offset": 0,
     "rows": 100,
     "sort": "field asc",
     "fl": "id,score",
     "filters": ['fq']}


    Result Example:
    {
     "total": 201,       # Total results found
     "offset": 0,        # Offset in the result list
     "rows": 100,        # Number of results returned
     "items": [],        # List of results
     "sequences": [],    # List of matching sequences
    }
    """
    user = kwargs["user"]
    collection = get_collection(index, user)
    default_sort = get_default_sort(index, user)
    if collection is None or default_sort is None:
        return bad_request(err=f"Not a valid index to search in: {index}")

    fields = ["group_sort", "limit", "query", "offset", "rows", "sort", "fl"]
    multi_fields = ["filters"]

    params = generate_params(request, fields, multi_fields)[0]

    if has_access_control(index):
        params.update({"access_control": user["access_control"]})

    params["as_obj"] = False
    params.setdefault("sort", default_sort)

    if not group_field:
        return bad_request(err="The field to group on was not specified.")

    try:
        return ok(collection().grouped_search(group_field, **params))
    except (SearchException, BadRequestError) as e:
        logger.error("SearchException: %s", str(e), exc_info=True)
        return bad_request(err=f"SearchException: {e}")


# noinspection PyUnusedLocal
@generate_swagger_docs()
@search_api.route("/fields/<index>", methods=["GET"])
@api_login(required_priv=["R"])
def list_index_fields(index, **kwargs):
    """List all available fields for a given index

    Variables:
    index  =>     Which specific index you want to know the fields for


    Arguments:
    None

    Result Example:
    {
        "<<FIELD_NAME>>": {      # For a given field
            indexed: True,        # Is the field indexed
            stored: False,        # Is the field stored
            type: string          # What type of data in the field
            },
        ...

    }
    """
    user = kwargs["user"]
    collection = get_collection(index, user)
    if collection is not None:
        return ok(collection().fields())
    elif index == "ALL":
        return ok(list_all_fields("admin" in user["type"]))
    else:
        return bad_request(err=f"Not a valid index to search in: {index}")


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
        "total": 201,                          # Total results found
    }
    """
    user = kwargs["user"]
    collection = get_collection(index, user)

    if collection is None:
        return bad_request(err=f"Not a valid index to search in: {index}")

    params, req_data = generate_params(request, [], [])

    boolean_fields = ["use_archive"]
    params.update(
        {
            k: str(req_data.get(k, "false")).lower() in ["true", ""]
            for k in boolean_fields
            if req_data.get(k, None) is not None
        }
    )

    if has_access_control(index):
        params.update({"access_control": user["access_control"]})

    query = req_data.get("query", None)
    if not query:
        return bad_request(err="There was no search query.")

    try:
        return ok(collection().count(query, **params))
    except (SearchException, BadRequestError) as e:
        return bad_request(err=f"SearchException: {e}")


@generate_swagger_docs()
@search_api.route("/facet/<index>/<field>", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def facet(index, field, **kwargs):
    """Perform field analysis on the selected field. (Also known as facetting in lucene).

    This essentially counts the number of instances a field is seen with each specific
    values where the documents matches the specified queries.

    Variables:
    index       =>   Index to search in (hit, user,...)
    field        =>   Field to analyse

    Optional Arguments:
    query       =>   Query to search for
    mincount    =>   Minimum item count for the fieldvalue to be returned
    rows        => The max number of fieldvalues to return
    filters     =>   Additional query to limit to output

    Data Block:
    # Note that the data block is for POST requests only!
    {"query": "id:*",
     "mincount": "10",
     "rows": "10",
     "filters": ['fq']}

    Result Example:
    {                 # Facetting results
     "value_0": 2,
     ...
     "value_N": 19,
    }
    """
    user = kwargs["user"]
    collection = get_collection(index, user)
    if collection is None:
        return bad_request(err=f"Not a valid index to search in: {index}")

    field_info = collection().fields().get(field, None)
    if field_info is None:
        return bad_request(err=f"Field '{field}' is not a valid field in index: {index}")

    fields = ["query", "mincount", "rows"]
    multi_fields = ["filters"]

    params = generate_params(request, fields, multi_fields)[0]

    if has_access_control(index):
        params.update({"access_control": user["access_control"]})

    try:
        return ok(collection().facet(field, **params))
    except (SearchException, BadRequestError) as e:
        logger.error("SearchException: %s", str(e), exc_info=True)
        return bad_request(err=f"SearchException: {e}")


@generate_swagger_docs()
@search_api.route("/histogram/<index>/<field>", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def histogram(index, field, **kwargs):
    """Generate an histogram based on a time or and int field using a specific gap size

    Variables:
    index       =>   Index to search in (hit, user,...)
    field        =>   Field to generate the histogram from

    Optional Arguments:
    query        =>   Query to search for
    mincount     =>   Minimum item count for the fieldvalue to be returned
    filters      =>   Additional query to limit to output
    start        =>   Value at which to start creating the histogram
                       * Defaults: 0 or now-1d
    end          =>   Value at which to end the histogram. Defaults: 2000 or now
    gap          =>   Size of each step in the histogram. Defaults: 100 or +1h

    Data Block:
    # Note that the data block is for POST requests only!
    {"query": "id:*",
     "mincount": "10",
     "filters": ['fq'],
     "start": 0,
     "end": 100,
     "gap": 10}

    Result Example:
    {                 # Histogram results
     "step_0": 2,
     ...
     "step_N": 19,
    }
    """
    fields = ["query", "mincount", "start", "end", "gap"]
    multi_fields = ["filters"]
    user = kwargs["user"]

    collection = get_collection(index, user)
    if collection is None:
        return bad_request(err=f"Not a valid index to search in: {index}")

    # Get fields default values
    field_info = collection().fields().get(field, None)
    params: dict[str, Union[str, int]] = {}
    if field_info is None:
        return bad_request(err=f"Field '{field}' is not a valid field in index: {index}")
    elif field_info["type"] == "integer":
        params = {"start": 0, "end": 2000, "gap": 100}
    elif field_info["type"] == "date":
        storage = datastore()
        params = {
            "start": f"{storage.ds.now}-1{storage.ds.day}",
            "end": f"{storage.ds.now}",
            "gap": f"+1{storage.ds.hour}",
        }
    else:
        err_msg = f"Field '{field}' is of type '{field_info['type']}'. Only 'integer' or 'date' are acceptable."
        return bad_request(err=err_msg)

    # Load API variables
    params = generate_params(request, fields, multi_fields, params)[0]

    # Make sure access control is enforced
    if has_access_control(index):
        params.update({"access_control": user["access_control"]})

    try:
        return ok(collection().histogram(field, **params))
    except (SearchException, BadRequestError) as e:
        logger.error("SearchException: %s", str(e), exc_info=True)
        return bad_request(err=f"SearchException: {e}")


@generate_swagger_docs()
@search_api.route("/stats/<index>/<int_field>", methods=["GET", "POST"])
@api_login(required_priv=["R"])
def stats(index, int_field, **kwargs):
    """Perform statistical analysis of an integer field to get its min, max, average and count values

    Variables:
    index       =>   Index to search in (hit, user,...)
    int_field    =>   Integer field to analyse

    Optional Arguments:
    query        =>   Query to search for
    filters      =>   Additional query to limit to output

    Data Block:
    # Note that the data block is for POST requests only!
    {"query": "id:*",
     "filters": ['fq']}

    Result Example:
    {                 # Stats results
     "count": 1,        # Number of times this field is seen
     "min": 1,          # Minimum value
     "max": 1,          # Maximum value
     "avg": 1,          # Average value
     "sum": 1           # Sum of all values
    }
    """
    user = kwargs["user"]
    collection = get_collection(index, user)
    if collection is None:
        return bad_request(err=f"Not a valid index to search in: {index}")

    field_info = collection().fields().get(int_field, None)
    if field_info is None:
        return bad_request(err=f"Field '{int_field}' is not a valid field in index: {index}")

    if field_info["type"] not in ["integer", "float"]:
        return bad_request(err=f"Field '{int_field}' is not a numeric field.")

    fields = ["query"]
    multi_fields = ["filters"]

    params = generate_params(request, fields, multi_fields)[0]

    if has_access_control(index):
        params.update({"access_control": user["access_control"]})

    try:
        return ok(collection().stats(int_field, **params))
    except (SearchException, BadRequestError) as e:
        logger.error("SearchException: %s", str(e), exc_info=True)
        return bad_request(err=f"SearchException: {e}")
