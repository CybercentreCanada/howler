import json
from datetime import datetime, timedelta
from typing import Any, cast
from unittest.mock import patch

import pytest
from flask import Flask
from requests import Response

from howler.common.exceptions import (
    AuthenticationException,
    HowlerRuntimeError,
    HowlerValueError,
)
from howler.config import cache, config
from howler.odm.base import Model
from howler.odm.models.analytic import Analytic
from howler.odm.models.hit import Hit
from howler.odm.randomizer import random_model_obj

time = datetime.now() + timedelta(seconds=10)


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")
    cache.init_app(app)

    app.config.update(SECRET_KEY="test test")

    with app.test_request_context(
        headers={"Authorization": "Bearer access_token", "Content-Type": "application/json"},
    ):
        yield app


@pytest.fixture(scope="module")
def mocked_requests_get():
    with patch("requests.get") as getter:
        yield getter


def test_get_nbgallery_nb(request_context, mocked_requests_get):
    notebook = {"metadata": {"gallery": {"title": "notebook_title"}}}

    ret_val = Response()
    ret_val.status_code = 200
    ret_val._content = json.dumps(notebook).encode()
    mocked_requests_get.return_value = ret_val

    from howler.services import notebook_service

    nb, name = notebook_service.get_nbgallery_nb("/notebooks/12-notebook")

    assert nb == notebook
    assert name == "notebook_title"

    mocked_requests_get.assert_called_with(
        f"{config.core.notebook.url}/notebooks/12/download.json",
        headers={"accept": "application/json", "Authorization": "Bearer access_token"},
        timeout=5,
    )


def test_get_nbgallery_nb_no_auth():
    app = Flask("test_app")
    cache.init_app(app)

    app.config.update(SECRET_KEY="test test")

    with app.test_request_context(
        headers={"Content-Type": "application/json"},
    ):
        from howler.services import notebook_service

        with pytest.raises(AuthenticationException):
            notebook_service.get_user_envs()


def test_get_user_envs(request_context, mocked_requests_get):
    ret_val = Response()
    ret_val.status_code = 200
    ret_val._content = json.dumps({"blah": "test"}).encode()
    mocked_requests_get.return_value = ret_val

    from howler.services import notebook_service

    result = notebook_service.get_user_envs()

    mocked_requests_get.assert_called_with(
        f"{config.core.notebook.url}/environments.json",
        headers={"accept": "application/json", "Authorization": "Bearer access_token"},
        timeout=5,
    )

    assert result["blah"] == "test"


def test_get_user_envs_no_auth():
    app = Flask("test_app")
    cache.init_app(app)

    app.config.update(SECRET_KEY="test test")

    with app.test_request_context(
        headers={"Content-Type": "application/json"},
    ):
        from howler.services import notebook_service

        with pytest.raises(AuthenticationException):
            notebook_service.get_user_envs()


def test_get_user_envs_error(request_context, mocked_requests_get):
    ret_val = Response()
    ret_val.status_code = 400
    mocked_requests_get.return_value = ret_val

    from howler.services import notebook_service

    with pytest.raises(HowlerRuntimeError):
        notebook_service.get_user_envs()


def test_get_nb_information(request_context, mocked_requests_get):
    notebook = {
        "metadata": {"gallery": {"title": "notebook_title"}},
        "cells": [
            {
                "cell_type": "code",
                "source": 'howlerHitId = "{{hit.howler.id}}"\nhowlerAnalyticId = "{{analytic.analytic_id}}"',
            }
        ],
    }

    ret_val = Response()
    ret_val.status_code = 200
    ret_val._content = json.dumps(notebook).encode()
    mocked_requests_get.return_value = ret_val

    from howler.services import notebook_service

    analytic = random_model_obj(cast(Model, Analytic))
    hit = random_model_obj(cast(Model, Hit))

    json_result, name = notebook_service.get_nb_information(
        "https://nbgallery.dev.analysis.cyber.gc.ca/notebooks/12-notebook",
        analytic=analytic,
        hit=hit,
    )

    assert name == "notebook_title"

    assert hit.howler.id in json_result["cells"][0]["source"]
    assert analytic.analytic_id in json_result["cells"][0]["source"]


def test_get_nb_information_error(request_context, mocked_requests_get):
    ret_val = Response()
    ret_val.status_code = 400
    mocked_requests_get.return_value = ret_val

    from howler.services import notebook_service

    analytic = random_model_obj(cast(Model, Analytic))
    hit = random_model_obj(cast(Model, Hit))

    with pytest.raises(HowlerValueError):
        notebook_service.get_nb_information(
            "https://dev.analysis.cyber.gc.ca/notebooks/12-notebook",
            analytic=analytic,
            hit=hit,
        )

    with pytest.raises(HowlerRuntimeError):
        notebook_service.get_nb_information(
            "https://nbgallery.dev.analysis.cyber.gc.ca/notebooks/12-notebook",
            analytic=analytic,
            hit=hit,
        )

    notebook: dict[str, Any] = {"metadata": {"gallery": {"title": "notebook_title"}}}

    ret_val = Response()
    ret_val.status_code = 200
    ret_val._content = json.dumps(notebook).encode()
    mocked_requests_get.return_value = ret_val

    with pytest.raises(HowlerRuntimeError):
        notebook_service.get_nb_information(
            "https://nbgallery.dev.analysis.cyber.gc.ca/notebooks/12-notebook",
            analytic=analytic,
            hit=hit,
        )

    notebook = {"metadata": {"gallery": {"title": "notebook_title"}}, "cells": []}

    ret_val = Response()
    ret_val.status_code = 200
    ret_val._content = json.dumps(notebook).encode()
    mocked_requests_get.return_value = ret_val

    with pytest.raises(HowlerValueError):
        notebook_service.get_nb_information(
            "https://nbgallery.dev.analysis.cyber.gc.ca/notebooks/12-notebook",
            analytic=analytic,
            hit=hit,
        )
