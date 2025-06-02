from howler_client.common.utils import SEARCHABLE, ClientError, api_path


class Fields(object):
    def __init__(self, connection):
        self._connection = connection

    def _do_fields(self, index):
        if index not in SEARCHABLE:
            raise ClientError("Index %s is not searchable" % index, 400)

        path = api_path("search", "fields", index)
        return self._connection.get(path)

    def hit(self):
        """List all fields details for the hit collection."""
        return self._do_fields("hit")
