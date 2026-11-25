import inspect
from unittest.mock import MagicMock, patch

from flask import Flask, Response

from howler.api.v1 import analytic as analytic_api
from howler.models.analytic import Analytic


def _analytic() -> Analytic:
    return Analytic.model_validate({"analytic_id": "c09c3f16-53ef-47c2-8f22-6f6584713bd4", "name": "Test Analytic"})


def _app() -> Flask:
    app = Flask("test_analytic_endpoint")
    app.config["SECRET_KEY"] = "test secret"
    return app


def test_update_analytic_saves_triage_settings():
    app = _app()
    analytic = _analytic()
    storage = MagicMock()
    storage.analytic.get.return_value = analytic

    with (
        patch.object(analytic_api, "datastore", return_value=storage),
        app.test_request_context(json={"triage_settings": {"skip_rationale": True}}),
    ):
        response: Response = inspect.unwrap(analytic_api.update_analytic)("analytic-1", user=MagicMock())

    assert response.status_code == 200
    assert analytic.triage_settings.skip_rationale is True
    storage.analytic.save.assert_called_once_with(analytic.analytic_id, analytic, refresh=None)


def test_add_comment_saves_the_author_and_comment_text():
    app = _app()
    analytic = _analytic()
    storage = MagicMock()

    with (
        patch.object(analytic_api.analytic_service, "does_analytic_exist", return_value=True),
        patch.object(analytic_api.analytic_service, "get_analytic", return_value=analytic),
        patch.object(analytic_api, "datastore", return_value=storage),
        app.test_request_context(json={"value": "Investigation note"}),
    ):
        response: Response = inspect.unwrap(analytic_api.add_comment)("analytic-1", user={"uname": "analyst"})

    assert response.status_code == 200
    assert analytic.comment[-1].user == "analyst"
    assert analytic.comment[-1].value == "Investigation note"
    storage.analytic.save.assert_called_once_with(analytic.analytic_id, analytic)


def test_add_notebook_saves_the_name_and_link():
    app = _app()
    analytic = _analytic()
    storage = MagicMock()

    with (
        patch.object(analytic_api.analytic_service, "does_analytic_exist", return_value=True),
        patch.object(analytic_api.analytic_service, "get_analytic", return_value=analytic),
        patch.object(analytic_api, "datastore", return_value=storage),
        app.test_request_context(json={"value": "https://nbgallery.example/notebook/1", "name": "Investigation"}),
    ):
        response: Response = inspect.unwrap(analytic_api.add_notebook)("analytic-1", user={"uname": "analyst"})

    assert response.status_code == 200
    assert analytic.notebooks[-1].name == "Investigation"
    assert analytic.notebooks[-1].value == "https://nbgallery.example/notebook/1"
    assert analytic.notebooks[-1].user == "analyst"
    storage.analytic.save.assert_called_once_with(analytic.analytic_id, analytic)
