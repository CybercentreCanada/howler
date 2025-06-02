from howler_client.common.utils import SEARCHABLE, ClientError, api_path


class Stats(object):
    def __init__(self, connection):
        self._connection = connection

    def _do_stats(self, index, field, **kwargs):
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
        path = api_path("search", "stats", index, field, **kwargs)
        return self._connection.get(path)

    def hit(self, field, query=None, filters=None):
        """
        Generates statistics about the distribution of an integer field of the hit index.

        Required:
        field   : field to create the stats on (only work on number fields)

        Optional:
        query    : Initial query to filter the data (default: 'id:*')
        filters  : Additional lucene queries used to filter the data (list of strings)

        Returns statistics about the field.
        """
        return self._do_stats("hit", field, query=query, filters=filters)
