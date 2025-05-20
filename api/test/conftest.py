import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# We append the plugin directory for howler to the python part
PLUGIN_PATH = Path(os.environ.get("HWL_PLUGIN_DIRECTORY", "/etc/howler/plugins"))
sys.path.insert(0, str(PLUGIN_PATH))
sys.path.append(str(PLUGIN_PATH / f".venv/lib/python3.{sys.version_info.minor}/site-packages"))

import base64
import os
import warnings
from json import JSONDecodeError

import pytest
import redis
import requests

from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.store import ESCollection, ESStore
from howler.odm import random_data
from howler.odm.models.config import Config
from howler.odm.models.config import config as _config
from howler.remote.datatypes.queues.named import NamedQueue

original_skip = pytest.skip

# Check if we are in an unattended build environment where skips won't be noticed
IN_CI_ENVIRONMENT = any(indicator in os.environ for indicator in ["CI", "BITBUCKET_BUILD_NUMBER", "AGENT_JOBSTATUS"])


def skip_or_fail(message):
    """Skip or fail the current test, based on the environment"""
    if IN_CI_ENVIRONMENT:
        pytest.fail(message)
    else:
        original_skip(message)


# Replace the built in skip function with our own
pytest.skip = skip_or_fail


@pytest.fixture(scope="session")
def config():
    return _config


@pytest.fixture(scope="session")
def auth_fail_queue(config: Config):
    nonpersistent_config = {
        "host": config.core.redis.nonpersistent.host,
        "port": config.core.redis.nonpersistent.port,
        "ttl": config.auth.internal.failure_ttl,
    }

    return (
        NamedQueue("ui-failed-admin", **nonpersistent_config),
        NamedQueue("ui-failed-user", **nonpersistent_config),
    )


@pytest.fixture(scope="session")
def datastore_connection(config, auth_fail_queue):
    ESCollection.MAX_RETRY_BACKOFF = 0.5
    store = ESStore(config)
    ret_val = store.ping()
    if not ret_val:
        pytest.skip("Could not connect to datastore")

    ds: HowlerDatastore = HowlerDatastore(store)
    try:
        random_data.wipe_users(ds)
        random_data.create_users(ds)
        yield ds

    finally:
        random_data.wipe_users(ds)


# Under different test setups, the host may have a different address
POSSIBLE_HOSTS = [
    "https://localhost:443",
    "https://nginx",
    "http://localhost:5000",
]


class InvalidRequestMethod(Exception):
    pass


class APIError(Exception):
    def __init__(self, msg, json=None, content=None, *args: object) -> None:
        super().__init__(msg, *args)

        self.json = json
        self.content = content


@pytest.fixture(scope="session")
def redis_connection(config):
    try:
        from howler.remote.datatypes import get_client

        c = get_client(
            config.core.redis.nonpersistent.host,
            config.core.redis.nonpersistent.port,
            False,
        )
        ret_val = c.ping()
        if ret_val:
            return c
    except redis.ConnectionError:
        pass

    pytest.skip("Connection to the Redis server failed. This test cannot be performed.")


@pytest.fixture(scope="session")
def host():
    """Figure out what hostname will reach the api server.

    We also probe for the host so that we can fail faster when it is missing.
    Request redis first, because if it is missing, the ui server can hang.

    Try three times, in an outer loop, so we try the other urls while waiting
    for the failed address to become available.
    """
    errors = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for host in POSSIBLE_HOSTS:
            try:
                result = requests.get(
                    f"{host}/api/v1/user/whoami/",
                    headers={"Authorization": f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}"},
                )
                if result.status_code in (200, 401):
                    return host
                result.raise_for_status()
                errors[host] = str(result.status_code)
            except requests.RequestException as err:
                errors[host] = str(err)

    pytest.skip(
        "Couldn't find the API server, can't test against it.\n" + "\n".join(k + " " + v for k, v in errors.items())
    )


@pytest.fixture(scope="function")
def login_session(host):
    try:
        session = requests.Session()
        session.headers.update({"Authorization": f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}"})
        return session, host
    except requests.ConnectionError as err:
        pytest.skip(str(err))


def get_api_data(  # noqa: C901
    session,
    url,
    params=None,
    data=None,
    method="GET",
    raw=False,
    headers=None,
    files=None,
):
    if headers is None:
        headers = {"content-type": "application/json"}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        if method == "GET":
            res = session.get(url, params=params, verify=False, headers=headers)
        elif method == "POST":
            res = session.post(
                url,
                data=data,
                params=params,
                verify=False,
                headers=headers,
                files=files,
            )
        elif method == "DELETE":
            res = session.delete(url, data=data, params=params, verify=False, headers=headers)
        elif method == "PUT":
            res = session.put(
                url,
                data=data,
                params=params,
                verify=False,
                headers=headers,
                files=files,
            )
        else:
            raise InvalidRequestMethod(method)

        if "XSRF-TOKEN" in res.cookies:
            session.headers.update({"X-XSRF-TOKEN": res.cookies["XSRF-TOKEN"]})

        if raw:
            return res
        else:
            if res.ok:
                if res.status_code == 204:
                    return None

                try:
                    res_data = res.json()
                    return res_data["api_response"]
                except Exception:
                    raise APIError(f"{res.status_code}: {res.content or None}")
            else:
                try:
                    res_data = res.json()

                    raise APIError(
                        f"{res.status_code}: {res_data['api_error_message']}",
                        json=res_data,
                    )
                except JSONDecodeError:
                    raise APIError(f"{res.status_code}: {res.content}", content=res.content)
