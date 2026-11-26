from typing import Any
from unittest.mock import MagicMock

import pytest
from flask import Flask, Response

from howler.models import keyword, mapping
from howler.models.ecs.related import Related
from howler.models.hit import Hit
from howler.models.user import User
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
    save_hit = MagicMock(return_value=(saved_hit, "v2"))
    monkeypatch.setattr(hit_service, "save_hit", save_hit)

    return _direct_overwrite_endpoint(cached_hit), save_hit


def test_overwrite_strips_stored_index_and_preserves_etag_and_refresh(monkeypatch, request_context: Flask):
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
        result: Response = endpoint(id=hit_id)

    assert result.status_code == 200
    assert result.headers.get("ETag") == "v2"
    assert result.get_json()["api_response"] == saved_hit

    validated_hit = save_hit.call_args.args[0]
    assert isinstance(validated_hit, Hit)
    assert str(validated_hit.source.ip) == "127.0.0.1"
    save_hit.assert_called_once_with(validated_hit, "v1", refresh="wait_for")


@pytest.mark.parametrize("replace, expected", [("false", ["old", "new"]), ("true", ["new"])])
def test_overwrite_merges_lists_within_hit_extension(monkeypatch, request_context, replace, expected):
    class ExtendedHit(Hit):
        plugin: Related
        groups: mapping(list[keyword()])

    cached = ExtendedHit.model_validate(
        {"howler.analytic": "Example", "howler.hash": "ab", "plugin.ids": ["old"], "groups": {"team": ["old"]}}
    )
    endpoint, save_hit = _setup_overwrite(monkeypatch, cached, {})
    with request_context.test_request_context(
        method="PUT", query_string={"replace": replace}, json={"plugin": {"ids": ["new"]}, "groups": {"team": ["new"]}}
    ):
        response = endpoint(id=cached.howler.id)

    assert response.status_code == 200
    updated = save_hit.call_args.args[0]
    assert isinstance(updated, ExtendedHit)
    assert updated.plugin.ids == expected
    # V1 treats a dynamic mapping entry as a leaf update even in additive mode.
    assert updated.groups == {"team": ["new"]}
    assert cached.plugin.ids == ["old"]


@pytest.mark.parametrize("replace", ["false", "true"])
def test_overwrite_empty_scalar_is_not_stringified(monkeypatch, request_context, replace):
    cached = Hit.model_validate({"howler.analytic": "Original", "howler.hash": "ab"})
    endpoint, save_hit = _setup_overwrite(monkeypatch, cached, {})
    with request_context.test_request_context(
        method="PUT", query_string={"replace": replace}, json={"howler.analytic": {}}
    ):
        response = endpoint(id=cached.howler.id)

    assert response.status_code == 200
    assert save_hit.call_args.args[0].howler.analytic == "Original"


def test_overwrite_denies_classification_before_validating_other_fields(monkeypatch, request_context):
    cached = Hit.model_validate({"howler.analytic": "Example", "howler.hash": "ab"})
    endpoint, save_hit = _setup_overwrite(monkeypatch, cached, {})
    user = User.model_validate({"uname": "analyst", "name": "Analyst", "password": "hash", "type": ["user"]})
    with request_context.test_request_context(method="PUT", json={"classification": "", "unknown": 1}):
        response = endpoint(id=cached.howler.id, user=user)

    assert response.status_code == 400
    assert response.get_json()["api_error_message"] == "Cannot set classification to "
    assert "ETag" not in response.headers
    save_hit.assert_not_called()


def test_overwrite_rejects_client_supplied_stored_index(monkeypatch, request_context: Flask):
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
