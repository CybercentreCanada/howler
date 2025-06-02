import base64
import json
import sys
import time
import warnings
from typing import Any, Callable, MutableMapping, Optional, Union

import requests

from howler_client.common.utils import ClientError
from howler_client.logger import get_logger

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

SUPPORTED_APIS = {"v1"}

logger = get_logger("connection")


def convert_api_output(response: requests.Response):
    "Convert a requests response to a python object based on the returned JSON data"
    logger.debug("Converting response %s", response.text)

    if response.status_code != 204:
        return response.json()["api_response"]

    return None


class Connection(object):
    "Abstraction for executing network requests to the Howler API"

    def __init__(  # pylint: disable=R0913
        self: Self,
        server: str,
        auth: Optional[Union[str, tuple[str, str]]],
        cert: Optional[Union[str, tuple[str, str]]],
        debug: Callable[[str], None],
        headers: Optional[MutableMapping[str, Union[str, bytes]]],
        retries: int,
        silence_warnings: bool,
        apikey: Optional[tuple[str, str]],
        verify: bool,
        timeout: Optional[int],
        throw_on_bad_request: bool,
        throw_on_max_retries: bool,
        # TODO: Not sure what this argument is for (if used at all)
        token: Optional[Any],
    ):
        self.apikey = apikey
        self.debug = debug
        self.max_retries = retries
        self.server = server
        self.silence_warnings = silence_warnings
        self.default_timeout = timeout
        self.throw_on_bad_request = throw_on_bad_request
        self.throw_on_max_retries = throw_on_max_retries
        self.token = token

        session = requests.Session()

        session.headers.update({"Content-Type": "application/json"})

        if auth:
            if not isinstance(auth, str):
                auth = base64.b64encode(":".join(auth).encode("utf-8")).decode("utf-8")

            if "." in auth:
                logger.info("Using JWT Authentication")
                session.headers.update({"Authorization": f"Bearer {auth}"})
            else:
                logger.info("Using Password Authentication")
                session.headers.update({"Authorization": f"Basic {auth}"})
        elif apikey:
            logger.info("Using API Key Authentication")
            session.headers.update(
                {"Authorization": f"Basic {base64.b64encode(':'.join(apikey).encode('utf-8')).decode('utf-8')}"}
            )

        session.verify = verify

        if cert:
            session.cert = cert

        if headers:
            logger.debug("Adding additional headers")
            session.headers.update(headers)

        self.session = session

        if "pytest" in sys.modules:
            logger.info("Skipping API validation, running in a test environment")
        else:
            r = self.request(self.session.get, "api/", convert_api_output)
            if not isinstance(r, list) or not set(r).intersection(SUPPORTED_APIS):
                raise ClientError("Supported APIS (%s) are not available" % SUPPORTED_APIS, 400)

    def delete(self, path, **kw):
        "Execute a DELETE request"
        return self.request(self.session.delete, path, convert_api_output, **kw)

    def download(self, path, process, **kw):
        "Download a file from the remote server"
        return self.request(self.session.get, path, process, **kw)

    def get(self, path, **kw):
        "Execute a GET request"
        return self.request(self.session.get, path, convert_api_output, **kw)

    def post(self, path, **kw):
        "Execute a POST request"
        return self.request(self.session.post, path, convert_api_output, **kw)

    def put(self, path, **kw):
        "Execute a PUT request"
        return self.request(self.session.put, path, convert_api_output, **kw)

    def request(self, func, path, process, **kw):  # noqa: C901
        "Main request function - prepare and execute a request"
        self.debug(path)

        # Apply default timeout parameter if not passed elsewhere
        kw.setdefault("timeout", self.default_timeout)

        retries = 0
        with warnings.catch_warnings():
            if self.silence_warnings:
                warnings.simplefilter("ignore")
            while self.max_retries < 1 or retries <= self.max_retries:
                if retries:
                    time.sleep(min(2, 2 ** (retries - 7)))

                try:
                    response = func(f"{self.server}/{path}", **kw)
                    if "XSRF-TOKEN" in response.cookies:
                        self.session.headers.update({"X-XSRF-TOKEN": response.cookies["XSRF-TOKEN"]})

                    if response.text:
                        try:
                            _warnings = json.loads(response.text).get("api_warning", None)
                        except json.JSONDecodeError:
                            logger.warning(
                                "There was an error when decoding the JSON response from the server, no warnings will "
                                "be shown."
                            )
                            _warnings = None

                        if _warnings:
                            for warning in _warnings:
                                logger.warning(warning)

                    if response.ok:
                        return process(response)
                    elif response.status_code not in (502, 503, 504):
                        try:
                            resp_data = response.json()

                            message = "\n".join(
                                [item["error"] for item in resp_data["api_response"] if "error" in item]
                            )

                            err_msg = resp_data["api_error_message"]

                            if message:
                                err_msg = f"{err_msg}\n{message}"

                            logger.error("%s: %s", response.status_code, err_msg)

                            if response.status_code != 400 or self.throw_on_bad_request:
                                raise ClientError(  # noqa: TRY301
                                    err_msg,
                                    response.status_code,
                                    api_version=resp_data["api_server_version"],
                                    api_response=resp_data["api_response"],
                                    resp_data=resp_data,
                                )
                            else:
                                break

                        except Exception as e:
                            if isinstance(e, ClientError):
                                raise

                            if response.status_code != 400 or self.throw_on_bad_request:
                                raise ClientError(response.content, response.status_code) from e
                            else:
                                break
                except (requests.exceptions.SSLError, requests.exceptions.ProxyError):
                    raise
                except requests.exceptions.ConnectionError:
                    pass
                except OSError as e:
                    if "Connection aborted" not in str(e):
                        raise

                retries += 1

            if self.throw_on_max_retries:
                raise ClientError("Max retry reached, could not perform the request.", None)
            else:
                logger.error("Max retry reached, could not perform the request.")
