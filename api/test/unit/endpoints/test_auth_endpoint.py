from datetime import datetime, timedelta

import pytest
from flask import Flask, Response
from mock import MagicMock, patch

from howler.common.loader import datastore
from howler.config import config
from howler.odm.models.user import User
from howler.odm.randomizer import random_model_obj

time = datetime.now() + timedelta(seconds=10)


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")

    app.config.update(SECRET_KEY="test test")

    return app


@patch("howler.api.v1.auth.jwt_service")
@patch("howler.security.auth_service")
def test_add_apikey(mock_auth_service, mock_jwt_service, request_context: Flask):
    mock_auth_service.bearer_auth = MagicMock()
    mock_jwt_service.decode = MagicMock(return_value={"exp": (datetime.now() + timedelta(minutes=5)).timestamp()})

    user_data: User = random_model_obj(User)
    user_data.type = ["admin", "user"]

    datastore().user.save(user_data.uname, user_data)

    mock_auth_service.bearer_auth.return_value = (
        user_data,
        ["R", "W", "E"],
    )

    with request_context.test_request_context(
        headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        json={
            "name": "tester_key_name",
            "priv": "RW",
            "expiry_date": (datetime.now() + timedelta(minutes=1)).isoformat(),
        },
    ):
        from howler.api.v1.auth import add_apikey

        result: Response = add_apikey()

        assert result.status_code < 300


@patch("howler.api.v1.auth.jwt_service")
@patch("howler.security.auth_service")
def test_add_apikey_no_extended(mock_auth_service, mock_jwt_service, request_context: Flask):
    config.auth.allow_extended_apikeys = False

    mock_auth_service.bearer_auth = MagicMock()
    mock_jwt_service.decode = MagicMock(return_value={"exp": (datetime.now() + timedelta(minutes=5)).timestamp()})

    user_data: User = random_model_obj(User)
    user_data.type = ["admin", "user"]

    datastore().user.save(user_data.uname, user_data)

    mock_auth_service.bearer_auth.return_value = (
        user_data,
        ["R", "W", "E"],
    )

    with request_context.test_request_context(
        headers={"Authorization": "Bearer .", "Content-Type": "application/json"},
        json={
            "name": "tester_key_name",
            "priv": "RWE",
            "expiry_date": (datetime.now() + timedelta(minutes=1)).isoformat(),
        },
    ):
        from howler.api.v1.auth import add_apikey

        result: Response = add_apikey()

        assert result.status_code == 400


@patch("howler.api.v1.auth.jwt_service")
@patch("howler.security.auth_service")
def test_add_apikey_bad_date_format(mock_auth_service, mock_jwt_service, request_context: Flask):
    config.auth.allow_extended_apikeys = False

    mock_auth_service.basic_auth = MagicMock()
    mock_jwt_service.decode = MagicMock(return_value={"exp": (datetime.now() + timedelta(minutes=5)).timestamp()})

    user_data: User = random_model_obj(User)
    user_data.type = ["admin", "user"]

    datastore().user.save(user_data.uname, user_data)
    mock_auth_service.basic_auth.return_value = (
        user_data,
        ["R", "W", "E"],
    )

    with request_context.test_request_context(
        headers={"Authorization": "Basic potato", "Content-Type": "application/json"},
        json={
            "name": "tester_key_name",
            "priv": "RW",
            "expiry_date": "2023/09/10 12:45",
        },
    ):
        from howler.api.v1.auth import add_apikey

        result: Response = add_apikey()

        assert result.status_code == 400
        assert result.json["api_error_message"] == "Invalid expiry date format. Please use ISO format."


@patch("howler.security.auth_service")
def test_add_apikey_bad_config(mock_auth_service, request_context: Flask):
    config.auth.max_apikey_duration_amount = 10
    config.auth.max_apikey_duration_unit = "days"

    mock_auth_service.basic_auth = MagicMock()

    user_data: User = random_model_obj(User)
    user_data.type = ["admin", "user"]

    datastore().user.save(user_data.uname, user_data)
    mock_auth_service.basic_auth.return_value = (
        user_data,
        ["R", "W", "E"],
    )

    with request_context.test_request_context(
        headers={"Authorization": "Basic potato", "Content-Type": "application/json"},
        json={
            "name": "tester_key_name",
            "priv": "RW",
            "expiry_date": (datetime.now() + timedelta(days=20)).isoformat(),
        },
    ):
        from howler.api.v1.auth import add_apikey

        result: Response = add_apikey()

        assert result.status_code == 400
        assert result.json["api_error_message"].startswith("Expiry date must be before")


@patch("howler.security.auth_service")
def test_add_apikey_no_exp(mock_auth_service, request_context: Flask):
    config.auth.max_apikey_duration_amount = 10
    config.auth.max_apikey_duration_unit = "days"

    mock_auth_service.basic_auth = MagicMock()

    user_data: User = random_model_obj(User)
    user_data.type = ["admin", "user"]

    datastore().user.save(user_data.uname, user_data)
    mock_auth_service.basic_auth.return_value = (
        user_data,
        ["R", "W", "E"],
    )

    with request_context.test_request_context(
        headers={"Authorization": "Basic potato", "Content-Type": "application/json"},
        json={
            "name": "tester_key_name",
            "priv": "RW",
        },
    ):
        from howler.api.v1.auth import add_apikey

        result: Response = add_apikey()

        assert result.status_code == 400
        assert result.json["api_error_message"] == "API keys must have an expiry date."
