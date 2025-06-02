import base64
import json as jsonUtils
import sys
import time
import warnings

import requests

from howler_client.common.utils import ClientError
from howler_client.logger import get_logger

SUPPORTED_APIS = {"v1"}

LOGGER = get_logger("connection")


def convert_api_output(response):
    if response.status_code != 204:
        return response.json()["api_response"]
    return None


class Connection(object):
    def __init__(  # pylint: disable=R0913
        self,
        server,
        auth,
        cert,
        debug,
        headers,
        retries,
        silence_warnings,
        apikey,
        verify,
        timeout,
        throw_on_bad_request,
        throw_on_max_retries,
        token,
    ):
        self.auth = auth
        self.apikey = apikey
        self.debug = debug
        self.max_retries = retries
        self.server = server
        self.silence_warnings = silence_warnings
        self.verify = verify
        self.default_timeout = timeout
        self.throw_on_bad_request = throw_on_bad_request
        self.throw_on_max_retries = throw_on_max_retries
        self.token = token

        session = requests.Session()

        session.headers.update({"Content-Type": "application/json"})

        if auth:
            LOGGER.info("Using Password Authentication")
            session.headers.update(
                {
                    "Authorization": f"Basic {base64.b64encode(':'.join(auth).encode('utf-8')).decode('utf-8')}"
                }
            )
        elif apikey:
            LOGGER.info("Using API Key Authentication")
            session.headers.update(
                {
                    "Authorization": f"Basic {base64.b64encode(':'.join(apikey).encode('utf-8')).decode('utf-8')}"
                }
            )

        session.verify = verify

        if cert:
            session.cert = cert
        if headers:
            session.headers.update(headers)

        self.session = session

        if "pytest" in sys.modules:
            LOGGER.info("Skipping API validation, running in a test environment")
        else:
            r = self.request(self.session.get, "api/", convert_api_output)
            if not isinstance(r, list) or not set(r).intersection(SUPPORTED_APIS):
                raise ClientError(
                    "Supported APIS (%s) are not available" % SUPPORTED_APIS, 400
                )

    def delete(self, path, **kw):
        return self.request(self.session.delete, path, convert_api_output, **kw)

    def download(self, path, process, **kw):
        return self.request(self.session.get, path, process, **kw)

    def get(self, path, **kw):
        return self.request(self.session.get, path, convert_api_output, **kw)

    def post(self, path, **kw):
        return self.request(self.session.post, path, convert_api_output, **kw)

    def put(self, path, **kw):
        return self.request(self.session.put, path, convert_api_output, **kw)

    def request(self, func, path, process, **kw):
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
                    stream = kw.get("files", {}).get("bin", None)
                    if stream and "seek" in dir(stream):
                        stream.seek(0)

                try:
                    response = func("/".join((self.server, path)), **kw)
                    if "XSRF-TOKEN" in response.cookies:
                        self.session.headers.update(
                            {"X-XSRF-TOKEN": response.cookies["XSRF-TOKEN"]}
                        )

                    if response.text:
                        _warnings = jsonUtils.loads(response.text).get(
                            "api_warning", None
                        )
                        if _warnings:
                            for warning in _warnings:
                                LOGGER.warning(warning)

                    if response.ok:
                        return process(response)
                    elif response.status_code not in (502, 503, 504):
                        try:
                            resp_data = response.json()

                            message = "\n".join(
                                [
                                    item["error"]
                                    for item in resp_data["api_response"]
                                    if "error" in item
                                ]
                            )

                            err_msg = resp_data["api_error_message"]

                            if message:
                                err_msg = f"{err_msg}\n{message}"

                            LOGGER.error("%s: %s", response.status_code, err_msg)

                            if response.status_code != 400 or self.throw_on_bad_request:
                                raise ClientError(
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
                                raise ClientError(
                                    response.content, response.status_code
                                )
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
                raise ClientError(
                    "Max retry reached, could not perform the request.", None
                )
            else:
                LOGGER.error("Max retry reached, could not perform the request.")
