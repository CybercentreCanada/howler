from howler_client.common.utils import SEARCHABLE, ClientError, api_path


class Histogram(object):
    def __init__(self, connection):
        self._connection = connection

    def _do_histogram(self, index, field, **kwargs):
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
        path = api_path("search", "histogram", index, field, **kwargs)
        return self._connection.get(path)

    def hit(
        self,
        field,
        query=None,
        mincount=None,
        filters=None,
        start=None,
        end=None,
        gap=None,
    ):
        """
        Create an histogram of data from a given field in the hit index where the frequency
        of the data is split between a given gap size.

        Required:
        field   : field to create the histograms with (only work on date or number fields)

        Optional:
        query    : Initial query to filter the data (default: 'id:*')
        filters  : Additional lucene queries used to filter the data (list of strings)
        mincount : Minimum amount of hits for the value to be returned
        start    : Beginning of the histogram range (Default: now-1d or 0)
        end      : End of the histogram range (Default: now or 1000)
        gap      : Interval in between each histogram points (Default: 1h or 100)

        Returns all results."""
        return self._do_histogram(
            "hit",
            field,
            query=query,
            mincount=mincount,
            filters=filters,
            start=start,
            end=end,
            gap=gap,
        )
