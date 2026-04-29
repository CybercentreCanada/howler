import pytest
from flask import Flask, Response

from howler.api.v1.utils.etag import add_etag
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.random_data import create_users, wipe_hits
from test.conftest import get_api_data

hit = {
    "howler": {
        "id": "test",
        "analytic": "test",
        "assignment": "user",
        "hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bc",
        "score": "0",
        "status": "on-hold",
        "labels": {"assignments": []},
    },
}


@pytest.fixture(scope="module")
def datastore(datastore_connection: HowlerDatastore):
    try:
        wipe_hits(datastore_connection)
        create_users(datastore_connection)

        datastore_connection.hit.save(hit["howler"]["id"], hit)

        # Commit changes to DataStore
        datastore_connection.hit.commit()

        yield datastore_connection
    finally:
        wipe_hits(datastore_connection)


def test_get_hit(datastore: HowlerDatastore, login_session):
    """Test that etags work as expected when getting a hit"""
    session, host = login_session

    res = get_api_data(session, f"{host}/api/v1/hit/{hit['howler']['id']}/", raw=True)

    assert res and "Etag" in res.headers

    res = get_api_data(
        session,
        f"{host}/api/v1/hit/{hit['howler']['id']}/",
        headers={
            "If-Match": res.headers["ETag"],
            "content-type": "application/json",
        },
        raw=True,
    )

    assert res and res.status_code == 304


def test_get_user(datastore: HowlerDatastore, login_session):
    """Test that etags work as expected when getting a user"""
    session, host = login_session

    res = get_api_data(session, f"{host}/api/v1/user/user/", raw=True)

    assert res and "Etag" in res.headers

    res = get_api_data(
        session,
        f"{host}/api/v1/user/user/",
        headers={
            "If-Match": res.headers["ETag"],
            "content-type": "application/json",
        },
        raw=True,
    )

    assert res and res.status_code == 304


# ===================================================================
# Unit tests for the add_etag decorator
# ===================================================================


@pytest.fixture()
def app():
    """Minimal Flask app for testing the decorator in isolation."""
    _app = Flask("test_etag")
    _app.config.update(SECRET_KEY="test")
    return _app


class TestAddEtagWithGetter:
    """Tests for add_etag(getter=...) — the full pre-fetch path."""

    def test_sets_etag_header_on_single_response(self, app):
        """When the wrapped function returns a single Response, the getter's version is used as ETag."""
        mock_getter = lambda id, as_odm, version: ({"id": id}, "v1")  # noqa: E731

        @add_etag(getter=mock_getter)
        def endpoint(id, **kwargs):
            return Response("ok", status=200)

        with app.test_request_context("/api/v1/hit/123", method="POST"):
            resp = endpoint(id="123")

        assert resp.headers["ETag"] == "v1"
        assert resp.status_code == 200

    def test_sets_etag_from_tuple_with_new_version(self, app):
        """When the wrapped function returns (Response, new_version), the new_version is used as ETag."""
        mock_getter = lambda id, as_odm, version: ({"id": id}, "v1")  # noqa: E731

        @add_etag(getter=mock_getter)
        def endpoint(id, **kwargs):
            return Response("updated", status=200), "v2"

        with app.test_request_context("/api/v1/hit/123", method="PATCH"):
            resp = endpoint(id="123")

        assert resp.headers["ETag"] == "v2"
        assert resp.status_code == 200

    def test_injects_server_version_kwarg(self, app):
        """The decorator passes server_version from the getter into the wrapped function."""
        mock_getter = lambda id, as_odm, version: ({"id": id}, "v42")  # noqa: E731
        captured = {}

        @add_etag(getter=mock_getter)
        def endpoint(id, **kwargs):
            captured["server_version"] = kwargs.get("server_version")
            return Response("ok", status=200)

        with app.test_request_context("/api/v1/hit/123", method="POST"):
            endpoint(id="123")

        assert captured["server_version"] == "v42"

    def test_caches_object_in_kwargs(self, app):
        """The decorator caches the fetched object under a key derived from the URL path."""
        obj = {"id": "123", "name": "test"}
        mock_getter = lambda id, as_odm, version: (obj, "v1")  # noqa: E731
        captured = {}

        @add_etag(getter=mock_getter)
        def endpoint(id, **kwargs):
            captured.update(kwargs)
            return Response("ok", status=200)

        with app.test_request_context("/api/v1/hit/123", method="POST"):
            endpoint(id="123")

        assert captured.get("cached_hit") is obj

    def test_if_match_returns_304(self, app):
        """GET with If-Match matching the current version returns 304 Not Modified."""
        mock_getter = lambda id, as_odm, version: ({"id": id}, "v1")  # noqa: E731

        @add_etag(getter=mock_getter)
        def endpoint(id, **kwargs):
            return Response("ok", status=200)

        with app.test_request_context(
            "/api/v1/hit/123",
            method="GET",
            headers={"If-Match": "v1"},
        ):
            resp = endpoint(id="123")

        assert resp.status_code == 304

    def test_if_match_mismatch_does_not_304(self, app):
        """GET with If-Match not matching the current version proceeds normally."""
        mock_getter = lambda id, as_odm, version: ({"id": id}, "v2")  # noqa: E731

        @add_etag(getter=mock_getter)
        def endpoint(id, **kwargs):
            return Response("ok", status=200)

        with app.test_request_context(
            "/api/v1/hit/123",
            method="GET",
            headers={"If-Match": "v1"},
        ):
            resp = endpoint(id="123")

        assert resp.status_code == 200
        assert resp.headers["ETag"] == "v2"

    def test_check_if_match_false_skips_304(self, app):
        """When check_if_match=False, matching If-Match does not return 304."""
        mock_getter = lambda id, as_odm, version: ({"id": id}, "v1")  # noqa: E731

        @add_etag(getter=mock_getter, check_if_match=False)
        def endpoint(id, **kwargs):
            return Response("ok", status=200)

        with app.test_request_context(
            "/api/v1/hit/123",
            method="GET",
            headers={"If-Match": "v1"},
        ):
            resp = endpoint(id="123")

        assert resp.status_code == 200

    def test_no_etag_on_409_response(self, app):
        """ETag header is not set on 409 Conflict responses."""
        mock_getter = lambda id, as_odm, version: ({"id": id}, "v1")  # noqa: E731

        @add_etag(getter=mock_getter)
        def endpoint(id, **kwargs):
            return Response("conflict", status=409)

        with app.test_request_context("/api/v1/hit/123", method="POST"):
            resp = endpoint(id="123")

        assert "ETag" not in resp.headers

    def test_no_etag_on_400_response(self, app):
        """ETag header is not set on 400 Bad Request responses."""
        mock_getter = lambda id, as_odm, version: ({"id": id}, "v1")  # noqa: E731

        @add_etag(getter=mock_getter)
        def endpoint(id, **kwargs):
            return Response("bad", status=400)

        with app.test_request_context("/api/v1/hit/123", method="POST"):
            resp = endpoint(id="123")

        assert "ETag" not in resp.headers

    def test_no_etag_on_409_tuple_response(self, app):
        """ETag header is not set on 409 tuple responses."""
        mock_getter = lambda id, as_odm, version: ({"id": id}, "v1")  # noqa: E731

        @add_etag(getter=mock_getter)
        def endpoint(id, **kwargs):
            return Response("conflict", status=409), "v2"

        with app.test_request_context("/api/v1/hit/123", method="POST"):
            resp = endpoint(id="123")

        assert "ETag" not in resp.headers


class TestAddEtagNoGetter:
    """Tests for add_etag() with no getter — only handles (Response, version) tuples."""

    def test_sets_etag_from_tuple(self, app):
        """(Response, version) tuple is unwrapped and the version becomes the ETag header."""

        @add_etag()
        def endpoint(**kwargs):
            return Response("ok", status=200), "345---1"

        with app.test_request_context("/api/v2/ingest/hit/123/overwrite", method="PATCH"):
            resp = endpoint()

        assert resp.status_code == 200
        assert resp.headers["ETag"] == "345---1"

    def test_passes_through_single_response(self, app):
        """A single Response (no tuple) is returned as-is without modification."""

        @add_etag()
        def endpoint(**kwargs):
            return Response("ok", status=200)

        with app.test_request_context("/api/v2/ingest/hit/123/overwrite", method="PATCH"):
            resp = endpoint()

        assert resp.status_code == 200
        assert "ETag" not in resp.headers

    def test_no_etag_on_409_tuple(self, app):
        """ETag is not set when the tuple response has status 409."""

        @add_etag()
        def endpoint(**kwargs):
            return Response("conflict", status=409), "v2"

        with app.test_request_context("/api/v2/ingest/hit/123/overwrite", method="PATCH"):
            resp = endpoint()

        assert resp.status_code == 409
        assert "ETag" not in resp.headers

    def test_no_etag_on_400_tuple(self, app):
        """ETag is not set when the tuple response has status 400."""

        @add_etag()
        def endpoint(**kwargs):
            return Response("bad request", status=400), "v2"

        with app.test_request_context("/api/v2/ingest/hit/123/overwrite", method="PATCH"):
            resp = endpoint()

        assert resp.status_code == 400
        assert "ETag" not in resp.headers

    def test_does_not_inject_server_version(self, app):
        """Without a getter, server_version is NOT injected into kwargs."""
        captured = {}

        @add_etag()
        def endpoint(**kwargs):
            captured.update(kwargs)
            return Response("ok", status=200)

        with app.test_request_context("/api/v2/ingest/hit/123/overwrite", method="PATCH"):
            endpoint()

        assert "server_version" not in captured

    def test_preserves_function_name(self, app):
        """The decorator preserves the wrapped function's __name__ via functools.wraps."""

        @add_etag()
        def my_endpoint(**kwargs):
            return Response("ok", status=200)

        assert my_endpoint.__name__ == "my_endpoint"

    def test_version_string_not_used_as_status_code(self, app):
        """Regression: ES version strings like '344---1' must not become HTTP status codes."""

        @add_etag()
        def endpoint(**kwargs):
            return Response("ok", status=200), "344---1"

        with app.test_request_context("/api/v2/ingest/hit/123/overwrite", method="PATCH"):
            resp = endpoint()

        assert resp.status_code == 200
        assert resp.headers["ETag"] == "344---1"
