"""Unit tests for the search API endpoint (howler.api.v2.search)."""

import uuid
from typing import cast
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, Response

from howler.common.loader import datastore
from howler.odm import Model
from howler.odm.models.user import User
from howler.odm.randomizer import random_model_obj


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test")
    return app


def _build_user(user_type: list[str] | None = None) -> User:
    user_data: User = random_model_obj(cast(Model, User))
    user_data.type = user_type or ["admin", "user"]
    user_data.uname = f"test_{uuid.uuid4().hex[:12]}"
    user_data.api_quota = 1000
    return user_data


def _mock_auth(mock_auth_service, user, priv=None):
    """Configure auth mocks so api_login passes."""
    if priv is None:
        priv = ["R", "W", "E"]
    mock_auth_service.bearer_auth = MagicMock(return_value=(user, priv))
    datastore().user.save(user.uname, user)


# ---------------------------------------------------------------------------
# generate_params()
# ---------------------------------------------------------------------------


class TestGenerateParams:
    """Tests for the generate_params helper."""

    def test_generate_params_post_extracts_fields(self, request_context: Flask):
        """POST requests extract fields from JSON body."""
        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*", "offset": 10, "rows": 50},
            headers={"Content-Type": "application/json"},
        ):
            from flask import request as flask_request

            from howler.api.v2.search import generate_params

            params, req_data = generate_params(flask_request, ["query", "offset", "rows"], [])

            assert params["query"] == "howler.id:*"
            assert params["offset"] == 10
            assert params["rows"] == 50

    def test_generate_params_get_extracts_fields(self, request_context: Flask):
        """GET requests extract fields from query string."""
        with request_context.test_request_context(
            method="GET",
            query_string={"query": "howler.id:*", "rows": "25"},
        ):
            from flask import request as flask_request

            from howler.api.v2.search import generate_params

            params, req_data = generate_params(flask_request, ["query", "rows"], [])

            assert params["query"] == "howler.id:*"
            assert params["rows"] == "25"

    def test_generate_params_get_multi_fields(self, request_context: Flask):
        """GET requests use getlist for multi_fields."""
        with request_context.test_request_context(
            method="GET",
            query_string=[("filters", "f1"), ("filters", "f2")],
        ):
            from flask import request as flask_request

            from howler.api.v2.search import generate_params

            params, req_data = generate_params(flask_request, [], ["filters"])

            assert params["filters"] == ["f1", "f2"]

    def test_generate_params_post_multi_fields(self, request_context: Flask):
        """POST requests extract multi_fields from JSON body directly."""
        with request_context.test_request_context(
            method="POST",
            json={"filters": ["f1", "f2"], "metadata": ["dossiers"]},
            headers={"Content-Type": "application/json"},
        ):
            from flask import request as flask_request

            from howler.api.v2.search import generate_params

            params, req_data = generate_params(flask_request, [], ["filters", "metadata"])

            assert params["filters"] == ["f1", "f2"]
            assert params["metadata"] == ["dossiers"]

    def test_generate_params_post_bad_json_defaults(self, request_context: Flask):
        """POST with invalid JSON falls back to query=*:*."""
        with request_context.test_request_context(
            method="POST",
            data=b"not json",
            content_type="text/plain",
        ):
            from flask import request as flask_request

            from howler.api.v2.search import generate_params

            params, req_data = generate_params(flask_request, ["query"], [])

            assert req_data == {"query": "*:*"}


# ---------------------------------------------------------------------------
# GET/POST /api/v2/search/<indexes>
# ---------------------------------------------------------------------------


class TestSearch:
    """Tests for the search endpoint."""

    @patch("howler.api.v2.search.hit_service")
    @patch("howler.api.v2.search.search_service")
    @patch("howler.security.auth_service")
    def test_search_success(self, mock_auth_service, mock_search_svc, mock_hit_svc, request_context: Flask):
        """Returns 200 with search results for a valid query."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_search_svc.DEFAULT_SORT = "event.created desc"
        mock_search_svc.search.return_value = {"total": 1, "items": [{"howler": {"id": "hit-1"}}], "offset": 0}

        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import search

            result: Response = search(indexes="hit", user=user)

            assert result.status_code == 200
            body = result.get_json()
            assert body["api_response"]["total"] == 1
            mock_search_svc.search.assert_called_once()

    @patch("howler.api.v2.search.search_service")
    @patch("howler.security.auth_service")
    def test_search_no_query_returns_400(self, mock_auth_service, mock_search_svc, request_context: Flask):
        """Returns 400 when no query is provided."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_search_svc.DEFAULT_SORT = "event.created desc"

        with request_context.test_request_context(
            method="POST",
            json={"rows": 10},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import search

            result: Response = search(indexes="hit", user=user)

            assert result.status_code == 400
            mock_search_svc.search.assert_not_called()

    @patch("howler.api.v2.search.hit_service")
    @patch("howler.api.v2.search.search_service")
    @patch("howler.security.auth_service")
    def test_search_with_metadata_augments(
        self, mock_auth_service, mock_search_svc, mock_hit_svc, request_context: Flask
    ):
        """When metadata is requested for hit index, augment_metadata is called."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        items = [{"howler": {"id": "hit-1"}}]
        mock_search_svc.DEFAULT_SORT = "event.created desc"
        mock_search_svc.search.return_value = {"total": 1, "items": items, "offset": 0}

        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*", "metadata": ["dossiers"]},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import search

            result: Response = search(indexes="hit", user=user)

            assert result.status_code == 200
            mock_hit_svc.augment_metadata.assert_called_once_with(items, ["dossiers"], user)

    @patch("howler.api.v2.search.hit_service")
    @patch("howler.api.v2.search.search_service")
    @patch("howler.security.auth_service")
    def test_search_passes_access_control_for_hits(
        self, mock_auth_service, mock_search_svc, mock_hit_svc, request_context: Flask
    ):
        """Search on 'hit' index includes access_control in params."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_search_svc.DEFAULT_SORT = "event.created desc"
        mock_search_svc.search.return_value = {"total": 0, "items": [], "offset": 0}

        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import search

            search(indexes="hit", user=user)

            call_kwargs = mock_search_svc.search.call_args
            assert "access_control" in call_kwargs.kwargs or any("access_control" in str(a) for a in call_kwargs.args)


# ---------------------------------------------------------------------------
# GET/POST /api/v2/search/count/<index>
# ---------------------------------------------------------------------------


class TestCount:
    """Tests for the count endpoint."""

    @patch("howler.api.v2.search.get_collection")
    @patch("howler.security.auth_service")
    def test_count_success(self, mock_auth_service, mock_get_collection, request_context: Flask):
        """Returns 200 with the count for a valid query."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_collection = MagicMock()
        mock_collection.return_value.count.return_value = 42
        mock_get_collection.return_value = mock_collection

        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import count

            result: Response = count(index="hit", user=user)

            assert result.status_code == 200
            body = result.get_json()
            assert body["api_response"] == 42

    @patch("howler.api.v2.search.get_collection")
    @patch("howler.security.auth_service")
    def test_count_invalid_index_returns_400(self, mock_auth_service, mock_get_collection, request_context: Flask):
        """Returns 400 when the index is not valid."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_get_collection.return_value = None

        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import count

            result: Response = count(index="invalid_index", user=user)

            assert result.status_code == 400

    @patch("howler.api.v2.search.get_collection")
    @patch("howler.security.auth_service")
    def test_count_no_query_returns_400(self, mock_auth_service, mock_get_collection, request_context: Flask):
        """Returns 400 when no query is provided."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_get_collection.return_value = MagicMock()

        with request_context.test_request_context(
            method="POST",
            json={"rows": 10},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import count

            result: Response = count(index="hit", user=user)

            assert result.status_code == 400

    @patch("howler.api.v2.search.get_collection")
    @patch("howler.security.auth_service")
    def test_count_search_exception_returns_400(self, mock_auth_service, mock_get_collection, request_context: Flask):
        """Returns 400 when the search raises a SearchException."""
        from howler.datastore.exceptions import SearchException

        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_collection = MagicMock()
        mock_collection.return_value.count.side_effect = SearchException("bad query")
        mock_get_collection.return_value = mock_collection

        with request_context.test_request_context(
            method="POST",
            json={"query": "bad:::query"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import count

            result: Response = count(index="hit", user=user)

            assert result.status_code == 400


# ---------------------------------------------------------------------------
# GET/POST /api/v2/search/<index>/explain
# ---------------------------------------------------------------------------


class TestExplain:
    """Tests for the explain endpoint."""

    @patch("howler.api.v2.search.datastore")
    @patch("howler.api.v2.search.get_collection")
    @patch("howler.security.auth_service")
    def test_explain_success(self, mock_auth_service, mock_get_collection, mock_ds, request_context: Flask):
        """Returns 200 with query explanation on success."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_collection = MagicMock()
        mock_collection.return_value.index_name = "howler-hit"
        mock_get_collection.return_value = mock_collection

        mock_indices = MagicMock()
        mock_indices.validate_query.return_value.body = {
            "_shards": {},
            "valid": True,
            "explanations": [{"valid": True, "explanation": "MatchAll", "index": "howler-hit"}],
        }
        mock_ds.return_value.hit.datastore.client = MagicMock()

        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*"},
            headers={"Authorization": "Bearer ."},
        ):
            with patch("howler.api.v2.search.IndicesClient", return_value=mock_indices):
                from howler.api.v2.search import explain_query

                result: Response = explain_query(index="hit", user=user)

                assert result.status_code == 200
                body = result.get_json()
                assert body["api_response"]["valid"] is True
                assert "_shards" not in body["api_response"]
                assert "index" not in body["api_response"]["explanations"][0]

    @patch("howler.api.v2.search.get_collection")
    @patch("howler.security.auth_service")
    def test_explain_invalid_index_returns_400(self, mock_auth_service, mock_get_collection, request_context: Flask):
        """Returns 400 when the index is not valid."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_get_collection.return_value = None

        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*"},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import explain_query

            result: Response = explain_query(index="badindex", user=user)

            assert result.status_code == 400

    @patch("howler.api.v2.search.get_collection")
    @patch("howler.security.auth_service")
    def test_explain_no_query_returns_400(self, mock_auth_service, mock_get_collection, request_context: Flask):
        """Returns 400 when no query is provided."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_get_collection.return_value = MagicMock()

        with request_context.test_request_context(
            method="POST",
            json={"rows": 10},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import explain_query

            result: Response = explain_query(index="hit", user=user)

            assert result.status_code == 400


# ---------------------------------------------------------------------------
# GET/POST /api/v2/search/facet/<indexes>
# ---------------------------------------------------------------------------


class TestFacet:
    """Tests for the facet endpoint."""

    @patch("howler.api.v2.search.has_access_control")
    @patch("howler.api.v2.search.get_collection")
    @patch("howler.security.auth_service")
    def test_facet_success(self, mock_auth_service, mock_get_collection, mock_has_ac, request_context: Flask):
        """Returns 200 with facet results for a valid request."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_has_ac.return_value = False
        mock_collection = MagicMock()
        mock_collection.return_value.fields.return_value = {"howler.analytic": {}}
        mock_collection.return_value.facet.return_value = {"AnalyticA": 5, "AnalyticB": 3}
        mock_get_collection.return_value = mock_collection

        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*", "fields": ["howler.analytic"]},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import facet

            result: Response = facet(indexes="hit", user=user)

            assert result.status_code == 200
            body = result.get_json()
            assert body["api_response"]["howler.analytic"]["AnalyticA"] == 5

    @patch("howler.api.v2.search.has_access_control")
    @patch("howler.api.v2.search.get_collection")
    @patch("howler.security.auth_service")
    def test_facet_invalid_index_returns_400(
        self, mock_auth_service, mock_get_collection, mock_has_ac, request_context: Flask
    ):
        """Returns 400 when the index is not valid."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_has_ac.return_value = False
        mock_get_collection.return_value = None

        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*", "fields": ["howler.analytic"]},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import facet

            result: Response = facet(indexes="badindex", user=user)

            assert result.status_code == 400

    @patch("howler.api.v2.search.has_access_control")
    @patch("howler.api.v2.search.get_collection")
    @patch("howler.security.auth_service")
    def test_facet_skips_invalid_field(
        self, mock_auth_service, mock_get_collection, mock_has_ac, request_context: Flask
    ):
        """Facet skips fields that are not in the collection's field list."""
        user = _build_user()
        _mock_auth(mock_auth_service, user)

        mock_has_ac.return_value = False
        mock_collection = MagicMock()
        mock_collection.return_value.fields.return_value = {"howler.analytic": {}}
        mock_collection.return_value.facet.return_value = {"AnalyticA": 5}
        mock_get_collection.return_value = mock_collection

        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*", "fields": ["howler.analytic", "nonexistent.field"]},
            headers={"Authorization": "Bearer ."},
        ):
            from howler.api.v2.search import facet

            result: Response = facet(indexes="hit", user=user)

            assert result.status_code == 200
            body = result.get_json()
            # Valid field was faceted
            assert "howler.analytic" in body["api_response"]
            # Invalid field has empty dict (initialized but never populated)
            assert body["api_response"]["nonexistent.field"] == {}
