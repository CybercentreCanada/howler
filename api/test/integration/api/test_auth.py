import base64
import re
from datetime import datetime, timedelta
from urllib.parse import urlsplit

import pytest
import requests
from conftest import APIError, get_api_data
from flask import json
from utils.oauth_credentials import get_token

from howler.odm.models.config import Config
from howler.security.utils import get_random_password

ALPHABET = [chr(x + 65) for x in range(26)] + [str(x) for x in range(10)]


@pytest.fixture(scope="function")
def host(host, auth_fail_queue, datastore_connection):
    auth_admin_fail_queue, auth_user_fail_queue = auth_fail_queue
    auth_admin_fail_queue.pop_batch(auth_admin_fail_queue.length())
    auth_user_fail_queue.pop_batch(auth_user_fail_queue.length())
    return host


# noinspection PyUnusedLocal
def test_basic_apikey(host):
    data = requests.get(f"{host}/api/v1/auth/login", params={"user": "admin", "apikey": "devkey:admin"}).json()

    assert not data["api_error_message"]

    token = data["api_response"]["app_token"]
    assert not data["api_response"].get("access_token", None)
    assert not data["api_response"].get("refresh_token", None)

    result = requests.get(f"{host}/api/v1/user/whoami", headers={"Authorization": f"Bearer {token}"})

    assert result.ok


def test_basic_userpass(host):
    data = requests.get(f"{host}/api/v1/auth/login", params={"user": "admin", "password": "admin"}).json()

    assert not data["api_error_message"]

    token = data["api_response"]["app_token"]
    assert not data["api_response"].get("access_token", None)
    assert not data["api_response"].get("refresh_token", None)

    result = requests.get(f"{host}/api/v1/user/whoami", headers={"Authorization": f"Bearer {token}"})

    assert result.ok


def test_basic_userpass_fail(host, config: Config):
    for _ in range(config.auth.internal.max_failures):
        data = requests.get(
            f"{host}/api/v1/auth/login",
            params={"user": "admin", "password": "wrong password"},
        ).json()

        assert data["api_error_message"] == "Invalid login information"
        assert data["api_status_code"] == 401

    data = requests.get(
        f"{host}/api/v1/auth/login",
        params={"user": "admin", "password": "wrong password"},
    ).json()

    assert (
        data["api_error_message"]
        == f"Maximum password retry of {config.auth.internal.max_failures} was reached. "
        + "This account is locked for the next 60 seconds..."
    )
    assert data["api_status_code"] == 401


def test_basic_apikey_fail(host):
    data = requests.get(
        f"{host}/api/v1/auth/login",
        params={"user": "admin", "apikey": "potato:potato"},
    ).json()

    assert data["api_error_message"] == "API Key does not exist"
    assert data["api_status_code"] == 401


def test_basic_both_methods_fail(host):
    data = requests.get(
        f"{host}/api/v1/auth/login",
        params={"user": "potato", "apikey": "potato:potato", "password": "potato"},
    ).json()

    assert data["api_error_message"] == "Cannot specify password and API key."
    assert data["api_status_code"] == 400


def test_basic_empty_fail(host):
    data = requests.get(
        f"{host}/api/v1/auth/login/",
        params={},
    ).json()

    assert data["api_error_message"] == "Not enough information to proceed with authentication"
    assert data["api_status_code"] == 401


def test_oauth_flow(host):
    session = requests.Session()

    res = session.get(f"{host}/api/v1/auth/login/?provider=keycloak")

    for past in res.history:
        assert past.ok and past.status_code >= 300

    assert res.ok
    assert res.url.startswith("http://localhost:9100/realms/HogwartsMini/protocol/openid-connect/auth")

    url = re.sub(r'[\s\S]+<form.+action="(.+?)".+>[\s\S]+', r"\1", res.text).replace("&amp;", "&")

    thing = session.post(url, data={"username": "goose", "password": "goose"}, allow_redirects=False)

    final_data = session.get(
        f"{host}/api/v1/auth/login/?{urlsplit(thing.headers['Location']).query}",
        cookies={
            # No clue why this is necessary tbh
            "session": session.cookies["session"]
        },
    ).json()

    assert final_data["api_status_code"] == 200
    app_token = final_data["api_response"]["app_token"]

    result = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={"Authorization": f"Bearer {app_token}"},
    )

    assert result.ok


def test_bearer_token_direct(host):
    access_token = get_token()

    if not access_token:
        pytest.skip("Could not connect to keycloak - is Hogwarts Mini running?")

    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert res.ok
    assert res.json()["api_response"]["username"] == "goose"


def test_internal_token_priv(host):
    res = requests.get(
        f"{host}/api/v1/auth/login",
        params={"user": "admin", "apikey": "readonly:admin"},
    )

    assert res.ok
    priv = res.json()["api_response"]["privileges"]
    token = res.json()["api_response"]["app_token"]
    assert not res.json()["api_response"].get("access_token", None)
    assert not res.json()["api_response"].get("refresh_token", None)
    assert priv == ["R"]

    res = requests.post(
        f"{host}/api/v1/hit/",
        headers={"Authorization": f"Bearer {token}"},
        data={},
    )

    assert res.status_code == 403

    res = requests.get(
        f"{host}/api/v1/user/whoami/",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert res.ok


def test_basic_userpass_direct(host):
    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={"Authorization": f"Basic {base64.b64encode(b'admin:admin').decode('utf-8')}"},
    )

    assert res.ok
    assert res.json()["api_response"]["username"] == "admin"


def test_basic_apikey_direct(host):
    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={"Authorization": f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}"},
    )

    assert res.ok
    assert res.json()["api_response"]["username"] == "admin"


def test_basic_apikey_direct_nonexistent_fail(host):
    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={"Authorization": f"Basic {base64.b64encode(b'admin:devkey_DOESNTEXIST:admin').decode('utf-8')}"},
    )

    assert not res.ok
    assert res.status_code == 401
    assert res.json()["api_error_message"] == "API Key does not exist"


def test_impersonation(host):
    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}",
            "X-Impersonating": f"Basic {base64.b64encode(b'user:impersonate_admin:user').decode('utf-8')}",
        },
    )

    assert res.status_code == 200
    assert res.json()["api_response"]["username"] == "user"

    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Basic {base64.b64encode(b'admin:admin').decode('utf-8')}",
            "X-Impersonating": f"Basic {base64.b64encode(b'user:impersonate_admin:user').decode('utf-8')}",
        },
    )

    assert res.status_code == 200
    assert res.json()["api_response"]["username"] == "user"

    token = get_token(user="admin")
    if token:
        res = requests.get(
            f"{host}/api/v1/user/whoami",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Impersonating": f"Basic {base64.b64encode(b'user:impersonate_admin:user').decode('utf-8')}",
            },
        )

        assert res.status_code == 200
        assert res.json()["api_response"]["username"] == "user"


def test_impersonation_key_in_authorization(host):
    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Basic {base64.b64encode(b'user:impersonate_admin:user').decode('utf-8')}",
        },
    )

    assert not res.ok
    assert res.json()["api_error_message"].startswith("Cannot use impersonation key in normal Authorization Header!")


def test_malicious_impersonation(host):
    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}",
            "X-Impersonating": f"Basic {base64.b64encode(b'user:impersonate_potato:user').decode('utf-8')}",
        },
    )

    assert res.status_code == 403
    assert res.json()["api_error_message"] == "Not a valid impersonation api key"

    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Basic {base64.b64encode(b'admin:admin').decode('utf-8')}",
            "X-Impersonating": f"Basic {base64.b64encode(b'user:impersonate_potato:user').decode('utf-8')}",
        },
    )

    assert res.status_code == 403
    assert res.json()["api_error_message"] == "Not a valid impersonation api key"

    token = get_token()
    if token:
        res = requests.get(
            f"{host}/api/v1/user/whoami",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Impersonating": f"Basic {base64.b64encode(b'user:impersonate_potato:user').decode('utf-8')}",
            },
        )

        assert res.status_code == 403
    assert res.json()["api_error_message"] == "Not a valid impersonation api key"


def test_invalid_impersonation_methods(
    host,
):
    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Basic {base64.b64encode(b'admin:admin').decode('utf-8')}",
            "X-Impersonating": f"Basic {base64.b64encode(b'user:user').decode('utf-8')}",
        },
    )

    assert res.status_code == 401
    assert res.json()["api_error_message"] == "No impersonated user found"

    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Basic {base64.b64encode(b'admin:devkey:admin').decode('utf-8')}",
            "X-Impersonating": f"Basic {base64.b64encode(b'user:user').decode('utf-8')}",
        },
    )

    assert res.status_code == 401
    assert res.json()["api_error_message"] == "No impersonated user found"

    data = requests.get(f"{host}/api/v1/auth/login", params={"user": "admin", "password": "admin"}).json()

    assert not data["api_error_message"]
    token = data["api_response"]["app_token"]

    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Impersonating": f"Basic {base64.b64encode(b'user:user').decode('utf-8')}",
        },
    )

    assert res.status_code == 401
    assert res.json()["api_error_message"] == "No impersonated user found"

    token = get_token()
    if token:
        res = requests.get(
            f"{host}/api/v1/user/whoami",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Impersonating": f"Basic {base64.b64encode(b'user:user').decode('utf-8')}",
            },
        )

        assert res.status_code == 401
        assert res.json()["api_error_message"] == "No impersonated user found"


def test_invalid_impersonation_auth_type(host):
    data = requests.get(f"{host}/api/v1/auth/login", params={"user": "admin", "password": "admin"}).json()

    assert not data["api_error_message"]
    token = data["api_response"]["app_token"]

    data2 = requests.get(f"{host}/api/v1/auth/login", params={"user": "user", "password": "user"}).json()

    assert not data2["api_error_message"]
    token2 = data2["api_response"]["app_token"]

    res = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Bearer {token}",
            "X-Impersonating": f"Bearer user:{token2}",
        },
    )

    assert res.status_code == 400
    assert res.json()["api_error_message"] == "Not a valid authentication type for impersonation."


# noinspection PyUnusedLocal
def test_read_api_key(login_session):
    session, host = login_session
    key_name = f"apikey_{get_random_password(alphabet=ALPHABET, length=6)}"

    # Added a read apikey
    resp = get_api_data(
        session,
        f"{host}/api/v1/auth/apikey/",
        data=json.dumps(
            {
                "name": key_name,
                "priv": "R",
                "expiry_date": (datetime.now() + timedelta(days=1)).isoformat(),
            }
        ),
        method="POST",
    )
    read_pass = resp.get("apikey", None)
    assert read_pass is not None

    # Cannot reuse apikey names
    with pytest.raises(APIError):
        resp = get_api_data(
            session,
            f"{host}/api/v1/auth/apikey/",
            data=json.dumps(
                {
                    "name": key_name,
                    "priv": "RW",
                    "expiry_date": (datetime.now() + timedelta(days=1)).isoformat(),
                }
            ),
            method="POST",
        )

    # Try to login with the read key
    resp = get_api_data(
        session,
        f"{host}/api/v1/auth/login/",
        params={"user": "admin", "apikey": read_pass},
    )

    assert resp.get("privileges", []) == ["R"]

    # Delete the read key
    assert not get_api_data(session, f"{host}/api/v1/auth/apikey/{key_name}/", method="DELETE")


def test_read_write_api_key(login_session):
    session, host = login_session
    key_name = f"apikey_{get_random_password(alphabet=ALPHABET, length=6)}"

    # Added a read/write key
    resp = get_api_data(
        session,
        f"{host}/api/v1/auth/apikey/",
        data=json.dumps(
            {
                "name": key_name,
                "priv": "RW",
                "expiry_date": (datetime.now() + timedelta(days=1)).isoformat(),
            }
        ),
        method="POST",
    )
    read_write_pass = resp.get("apikey", None)
    assert read_write_pass is not None

    # Try to login with the read/write key
    resp = get_api_data(
        session,
        f"{host}/api/v1/auth/login/",
        params={"user": "admin", "apikey": read_write_pass},
    )
    assert resp.get("privileges", []) == ["R", "W"]

    # Delete the read/write key
    assert not get_api_data(session, f"{host}/api/v1/auth/apikey/{key_name}/", method="DELETE")


def test_write_api_key(login_session):
    session, host = login_session
    key_name = f"apikey_{get_random_password(alphabet=ALPHABET, length=6)}"

    # Added a write key
    resp = get_api_data(
        session,
        f"{host}/api/v1/auth/apikey/",
        data=json.dumps(
            {
                "name": key_name,
                "priv": "W",
                "expiry_date": (datetime.now() + timedelta(days=1)).isoformat(),
            }
        ),
        method="POST",
    )
    write_pass = resp.get("apikey", None)
    assert write_pass is not None

    # Try to login with the write key
    resp = get_api_data(
        session,
        f"{host}/api/v1/auth/login/",
        params={"user": "admin", "apikey": write_pass},
    )
    assert resp.get("privileges", []) == ["W"]

    # Delete the write key
    assert not get_api_data(session, f"{host}/api/v1/auth/apikey/{key_name}/", method="DELETE")


def test_impersonate_key(login_session):
    session, host = login_session
    key_name = f"apikey_{get_random_password(alphabet=ALPHABET, length=6)}"

    resp = get_api_data(
        session,
        f"{host}/api/v1/auth/apikey/",
        data=json.dumps(
            {
                "name": key_name,
                "priv": "RI",
                "agents": ["admin", "goose"],
                "expiry_date": (datetime.now() + timedelta(days=1)).isoformat(),
            }
        ),
        headers={
            "Authorization": f"Basic {base64.b64encode(b'user:user').decode('utf-8')}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    write_pass = resp.get("apikey", None)

    assert write_pass is not None

    data = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Basic {base64.b64encode(b'admin:admin').decode('utf-8')}",
            "X-Impersonating": f"Basic {base64.b64encode(f'user:{write_pass}'.encode('utf-8')).decode('utf-8')}",
        },
    )
    assert data.ok
    assert data.json()["api_response"]["username"] == "user"

    token = get_token()
    if token:
        data = requests.get(
            f"{host}/api/v1/user/whoami",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Impersonating": f"Basic {base64.b64encode(f'user:{write_pass}'.encode('utf-8')).decode('utf-8')}",
            },
        )

        assert data.ok
        assert data.json()["api_response"]["username"] == "user"

        huey_token = get_token("huey")

        data = requests.get(
            f"{host}/api/v1/user/whoami",
            headers={
                "Authorization": f"Bearer {huey_token}",
                "X-Impersonating": f"Basic {base64.b64encode(f'user:{write_pass}'.encode('utf-8')).decode('utf-8')}",
            },
        )

        assert data.status_code == 403
        assert data.json()["api_error_message"] == "Not a valid impersonation api key"

    # Delete the key
    data = requests.delete(
        f"{host}/api/v1/auth/apikey/{write_pass.split(':')[0]}/",
        headers={"Authorization": f"Basic {base64.b64encode(b'user:user').decode('utf-8')}"},
    )

    assert data.status_code == 204

    data = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={
            "Authorization": f"Basic {base64.b64encode(b'admin:admin').decode('utf-8')}",
            "X-Impersonating": f"Basic {base64.b64encode(f'user:{write_pass}'.encode('utf-8')).decode('utf-8')}",
        },
    )

    assert data.status_code == 401
    assert data.json()["api_error_message"] == "No impersonated user found"


def test_expired_key(login_session):
    session, host = login_session

    result = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={"Authorization": f"Basic {base64.b64encode(b'admin:expired:admin').decode('utf-8')}"},
    )

    assert not result.ok

    result = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={"Authorization": f"Basic {base64.b64encode(b'admin:not_expired:admin').decode('utf-8')}"},
    )

    assert result.ok
