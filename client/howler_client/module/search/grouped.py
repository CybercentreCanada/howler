from howler_client.common.utils import SEARCHABLE, ClientError, api_path


class Grouped(object):
    "Module for grouping search results from given indexes"

    def __init__(self, connection):
        self._connection = connection

    def _do_grouped(self, index, field, **kwargs):
        if index not in SEARCHABLE:
            raise ClientError("Index %s is not searchable" % index, 400)

        filters = kwargs.pop("filters", None)
        if filters is not None:
            if isinstance(filters, str):
                filters = [filters]

            filters = [("filters", fq) for fq in filters]

        kwargs = {k: v for k, v in kwargs.items() if v is not None and k != "filters"}
        if filters is not None:
            kwargs["params_tuples"] = filters
        path = api_path("search", "grouped", index, field, **kwargs)
        return self._connection.get(path)

    def hit(
        self,
        field,
        group_sort=None,
        limit=None,
        query=None,
        filters=None,
        offset=None,
        rows=None,
        sort=None,
        fl=None,
    ):
        """Search hit collection and group result to a given field

        Required:
        field   : Field used to group the results

        Optional:
        group_sort : Field used for sorting items in the groups with direction (string: ex. 'id desc')
        limit      : Maximum number of items returned per group (integer)
        query      : lucene query (string)
        filters    : Additional lucene queries used to filter the data (list of strings)
        offset     : Offset at which the query items should start (integer)
        rows       : Number of records to return (integer)
        sort       : Field used for sorting with direction (string: ex. 'id desc')
        fl         : List of fields to return (comma separated string of fields)

        Returns a generator that transparently and efficiently pages through results.
        """
        return self._do_grouped(
            "hit",
            field,
            group_sort=group_sort,
            limit=limit,
            query=query,
            filters=filters,
            offset=offset,
            rows=rows,
            sort=sort,
            fl=fl,
        )
