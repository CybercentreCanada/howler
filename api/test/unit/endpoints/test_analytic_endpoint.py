import inspect
from unittest.mock import MagicMock

import pytest
from flask import Flask, Response

from howler.api.v1 import analytic as analytic_api
from howler.models.analytic import Analytic


@pytest.fixture
def analytic_context(monkeypatch):
    app = Flask("test_analytic_endpoint")
    app.config["SECRET_KEY"] = "test secret"
    analytic = Analytic.model_validate({"analytic_id": "c09c3f16-53ef-47c2-8f22-6f6584713bd4", "name": "Test Analytic"})
    storage = MagicMock()
    storage.analytic.get.return_value = analytic
    monkeypatch.setattr(analytic_api, "datastore", lambda: storage)
    monkeypatch.setattr(analytic_api.analytic_service, "does_analytic_exist", lambda *_: True)
    monkeypatch.setattr(analytic_api.analytic_service, "get_analytic", lambda *_, **_kwargs: analytic)
    return app, analytic, storage


def test_update_analytic_saves_triage_settings(analytic_context):
    app, analytic, storage = analytic_context
    with app.test_request_context(json={"triage_settings": {"skip_rationale": True}}):
        response: Response = inspect.unwrap(analytic_api.update_analytic)("analytic-1", user=MagicMock())

    assert response.status_code == 200
    assert analytic.triage_settings.skip_rationale is True
    storage.analytic.save.assert_called_once_with(analytic.analytic_id, analytic, refresh=None)


@pytest.mark.parametrize(
    ("endpoint", "field", "payload"),
    [
        ("add_comment", "comment", {"value": "Investigation note"}),
        ("add_notebook", "notebooks", {"value": "https://nbgallery.example/notebook/1", "name": "Investigation"}),
    ],
)
def test_add_analytic_entry_saves_author_and_payload(endpoint, field, payload, analytic_context):
    app, analytic, storage = analytic_context
    with app.test_request_context(json=payload):
        response: Response = inspect.unwrap(getattr(analytic_api, endpoint))("analytic-1", user={"uname": "analyst"})

    assert response.status_code == 200
    entry = getattr(analytic, field)[-1]
    assert entry.user == "analyst"
    assert entry.value == payload["value"]
    if "name" in payload:
        assert entry.name == payload["name"]
    storage.analytic.save.assert_called_once_with(analytic.analytic_id, analytic)
