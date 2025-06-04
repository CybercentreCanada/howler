from importlib.metadata import PackageNotFoundError, version

from howler_client.client import Client
from howler_client.connection import Connection

try:
    __version__ = version("howler-client")
except PackageNotFoundError:
    __version__ = "0.0.0.unknown"

RETRY_FOREVER = 0
SUPPORTED_APIS = {"v1"}


def get_client(
    server,
    auth=None,
    cert=None,
    debug=lambda x: None,
    headers=None,
    retries=RETRY_FOREVER,
    silence_requests_warnings=True,
    apikey=None,
    verify=True,
    timeout=None,
    throw_on_bad_request=True,
    throw_on_max_retries=True,
    token=None,
):
    "Initialize a howler client object"
    connection = Connection(
        server,
        auth,
        cert,
        debug,
        headers,
        retries,
        silence_requests_warnings,
        apikey,
        verify,
        timeout,
        throw_on_bad_request,
        throw_on_max_retries,
        token,
    )
    return Client(connection)
