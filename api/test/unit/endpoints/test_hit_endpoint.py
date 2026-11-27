from inspect import unwrap
from unittest.mock import MagicMock

import pytest
from flask import Flask

from howler.models import Keyword, mapping
from howler.models.ecs.related import Related
from howler.models.hit import Hit
from howler.models.user import User
from howler.services import hit_service


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test")
    return app


def _setup_overwrite(monkeypatch, cached_hit):
    from howler.api.v1.hit import overwrite_hit
    from howler.api.v1.utils.etag import add_etag
    from howler.api.v1.utils.params import parse_parameters, parse_refresh

    save_hit = MagicMock(return_value=({}, "v2"))
    monkeypatch.setattr(hit_service, "save_hit", save_hit)
    endpoint = parse_parameters(refresh=parse_refresh)(unwrap(overwrite_hit))
    endpoint = add_etag(getter=lambda _id, **_kwargs: (cached_hit, "v1"), check_if_match=False)(endpoint)
    return endpoint, save_hit


@pytest.mark.parametrize("replace, expected", [("false", ["old", "new"]), ("true", ["new"])])
def test_overwrite_merges_lists_within_hit_extension(monkeypatch, request_context, replace, expected):
    class ExtendedHit(Hit):
        plugin: Related
        groups: mapping(list[Keyword])

    cached = ExtendedHit.model_validate(
        {"howler.analytic": "Example", "howler.hash": "ab", "plugin.ids": ["old"], "groups": {"team": ["old"]}}
    )
    endpoint, save_hit = _setup_overwrite(monkeypatch, cached)
    user = User.model_validate({"uname": "analyst", "name": "Analyst", "password": "hash", "type": ["user"]})
    with request_context.test_request_context(
        method="PUT",
        query_string={"replace": replace, "refresh": "wait_for"},
        json={"plugin": {"ids": ["new"]}, "groups": {"team": ["new"]}, "howler.analytic": {}},
    ):
        response = endpoint(id=cached.howler.id, user=user)

    assert response.status_code == 200
    updated = save_hit.call_args.args[0]
    assert isinstance(updated, ExtendedHit)
    assert updated.plugin.ids == expected
    # V1 treats a dynamic mapping entry as a leaf update even in additive mode.
    assert updated.groups == {"team": ["new"]}
    assert cached.plugin.ids == ["old"]
    assert updated.howler.analytic == "Example"
    save_hit.assert_called_once_with(updated, "v1", refresh="wait_for")


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        ({"classification": "", "unknown": 1}, "Cannot set classification to "),
        ({"__index": "hit"}, "__index"),
    ],
)
def test_overwrite_rejects_invalid_input_without_saving(monkeypatch, request_context, payload, error):
    cached = Hit.model_validate({"howler.analytic": "Example", "howler.hash": "ab"})
    endpoint, save_hit = _setup_overwrite(monkeypatch, cached)
    user = User.model_validate({"uname": "analyst", "name": "Analyst", "password": "hash", "type": ["user"]})
    kwargs = {"user": user} if "classification" in payload else {}
    with request_context.test_request_context(method="PUT", json=payload):
        response = endpoint(id=cached.howler.id, **kwargs)

    assert response.status_code == 400
    message = response.get_json()["api_error_message"]
    if "classification" in payload:
        assert message == error
    else:
        assert error in message
    assert "ETag" not in response.headers
    save_hit.assert_not_called()
