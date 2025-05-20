import base64
from datetime import datetime, timedelta

import jwt
import pytest
import requests
from conftest import APIError, get_api_data
from flask import json
from utils.oauth_credentials import get_token

from howler.config import config
from howler.datastore.howler_store import HowlerDatastore

ALPHABET = [chr(x + 65) for x in range(26)] + [str(x) for x in range(10)]


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
    return datastore_connection


def test_add_delete_apikey(datastore: HowlerDatastore, login_session):
    session, host = login_session

    result: str = get_api_data(
        session,
        f"{host}/api/v1/auth/apikey",
        data=json.dumps(
            {
                "name": "tester",
                "priv": ["R"],
                "expiry_date": (datetime.now() + timedelta(days=1)).isoformat(),
            }
        ),
        method="POST",
    )["apikey"]

    req_result = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={"Authorization": f"Basic {base64.b64encode(f'admin:{result}'.encode()).decode('utf-8')}"},
    )

    assert req_result.ok

    get_api_data(
        session,
        f"{host}/api/v1/auth/apikey/tester",
        method="DELETE",
    )

    req_result = requests.get(
        f"{host}/api/v1/user/whoami",
        headers={"Authorization": f"Basic {base64.b64encode(f'admin:{result}'.encode()).decode('utf-8')}"},
    )

    assert not req_result.ok


@pytest.mark.skipif(
    not config.auth.max_apikey_duration_amount or not config.auth.max_apikey_duration_unit,
    reason="Can only be run when max expiry is set!",
)
def test_past_max_expiry(datastore: HowlerDatastore, login_session):
    session, host = login_session

    key_expiry = None
    if config.auth.max_apikey_duration_unit:
        key_expiry = (
            datetime.now()
            + timedelta(**{config.auth.max_apikey_duration_unit: (config.auth.max_apikey_duration_amount or 0) + 10})
        ).isoformat()

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/auth/apikey",
            data=json.dumps(
                {
                    "name": "tester",
                    "priv": ["R"],
                    "expiry_date": key_expiry,
                }
            ),
            method="POST",
        )

    assert str(err.value).startswith("400: Expiry date must be before")


@pytest.mark.skipif(
    not config.auth.oauth.strict_apikeys,
    reason="Can only be run when strict oauth API keys are enabled.",
)
def test_max_expiry_oauth(datastore: HowlerDatastore, login_session):
    session, host = login_session

    access_token = get_token()

    jwt_data = jwt.decode(access_token, options={"verify_signature": False})

    key_expiry = (datetime.fromtimestamp(jwt_data["exp"]) + timedelta(weeks=6)).isoformat()

    result = requests.post(
        f"{host}/api/v1/auth/apikey",
        json={
            "name": "tester",
            "priv": ["R"],
            "expiry_date": key_expiry,
        },
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert not result.ok
    assert (
        result.json()["api_error_message"]
        == f"Expiry date must be before {datetime.fromtimestamp(jwt_data['exp']).isoformat()}."
    )


def test_invalid_apikey_expiry(datastore: HowlerDatastore, login_session):
    session, host = login_session

    with pytest.raises(APIError) as err:
        get_api_data(
            session,
            f"{host}/api/v1/auth/apikey",
            data=json.dumps(
                {
                    "name": "badexpiry",
                    "priv": ["R"],
                    "expiry_date": "2023, Feb 14th 10:00am",
                }
            ),
            method="POST",
        )

    assert str(err.value).startswith("400: Invalid expiry date format")
