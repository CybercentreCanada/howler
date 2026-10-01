from typing import Any
from unittest.mock import MagicMock

import pytest
from flask import Flask, Response

from howler.models.hit import Hit
from howler.sample_data.randomizer import random_model_obj
from howler.services import hit_service


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test")
    return app


def _direct_overwrite_endpoint(cached_hit):
    """Wrap the endpoint body with its parameter and ETag decorators for an offline direct-call test."""
    from howler.api.v1.hit import overwrite_hit
    from howler.api.v1.utils.etag import add_etag
    from howler.api.v1.utils.params import parse_parameters, parse_refresh

    endpoint: Any = overwrite_hit
    while hasattr(endpoint, "__wrapped__"):
        endpoint = endpoint.__wrapped__

    endpoint = parse_parameters(refresh=parse_refresh)(endpoint)
    endpoint = add_etag(
        getter=lambda _id, **_kwargs: (cached_hit, "v1"),
        check_if_match=False,
    )(endpoint)
    return endpoint


def _setup_overwrite(monkeypatch, cached_hit, saved_hit):
    from howler.api.v1 import hit as hit_api

    mock_datastore = MagicMock()
    mock_datastore.return_value.hit.model_class = Hit
    monkeypatch.setattr(hit_api, "datastore", mock_datastore)

    save_hit = MagicMock(return_value=(saved_hit, "v2"))
    monkeypatch.setattr(hit_service, "save_hit", save_hit)

    return _direct_overwrite_endpoint(cached_hit), save_hit


def test_overwrite_strips_cached_synthetic_index_and_preserves_etag_and_refresh(monkeypatch, request_context: Flask):
    cached_hit: Hit = random_model_obj(Hit)
    hit_id = cached_hit.howler.id
    assert cached_hit.as_primitives()["__index"] == "hit"

    saved_hit = {
        "howler": {"id": hit_id},
        "source": {"ip": "127.0.0.1"},
    }
    endpoint, save_hit = _setup_overwrite(monkeypatch, cached_hit, saved_hit)

    with request_context.test_request_context(
        f"/api/v1/hit/{hit_id}/overwrite?refresh=wait_for",
        method="PUT",
        json={"source": {"ip": "127.0.0.1"}},
    ):
        # Supply the ID as a keyword so the getter-backed ETag wrapper resolves the expected cached record.
        result: Response = endpoint(id=hit_id)

    assert result.status_code == 200
    assert result.headers.get("ETag") == "v2"
    assert result.get_json()["api_response"] == saved_hit

    validated_hit = save_hit.call_args.args[0]
    assert isinstance(validated_hit, Hit)
    assert str(validated_hit.source.ip) == "127.0.0.1"
    save_hit.assert_called_once_with(validated_hit, "v1", refresh="wait_for")


def test_overwrite_rejects_client_supplied_synthetic_index(monkeypatch, request_context: Flask):
    cached_hit: Hit = random_model_obj(Hit)
    hit_id = cached_hit.howler.id
    endpoint, save_hit = _setup_overwrite(monkeypatch, cached_hit, {"howler": {"id": hit_id}})

    with request_context.test_request_context(
        f"/api/v1/hit/{hit_id}/overwrite",
        method="PUT",
        json={"__index": "hit"},
    ):
        result: Response = endpoint(id=hit_id)

    assert result.status_code == 400
    assert "__index" in result.get_json()["api_error_message"]
    assert "ETag" not in result.headers
    save_hit.assert_not_called()
