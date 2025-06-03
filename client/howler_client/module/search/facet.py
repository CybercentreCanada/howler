from howler_client.common.utils import SEARCHABLE, ClientError, api_path


class Facet(object):
    "List most frequent values for a field in the given collection"

    def __init__(self, connection):
        self._connection = connection

    def _do_facet(self, index, field, **kwargs):
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
        path = api_path("search", "facet", index, field, **kwargs)
        return self._connection.get(path)

    def hit(self, field, query=None, mincount=None, filters=None, rows=None):
        """List most frequent value for a field in the hit collection.

        Required:
        field   : field to extract the facets from

        Optional:
        query    : Initial query to filter the data (default: 'id:*')
        filters  : Additional lucene queries used to filter the data (list of strings)
        mincount : Minimum amount of hits for the value to be returned
        rows     : The number of different facets to return

        Returns all results.
        """
        return self._do_facet("hit", field, query=query, mincount=mincount, filters=filters, rows=rows)
