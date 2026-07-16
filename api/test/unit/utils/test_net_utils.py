"""Unit tests for howler.utils.net_utils."""

import pytest
from flask import Flask


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")
    app.config.update(SECRET_KEY="test test")
    return app


class TestGenerateParams:
    """Tests for the generate_params helper."""

    def test_post_extracts_fields_and_multi_fields(self, request_context: Flask):
        """POST requests merge selected fields from JSON payloads."""
        with request_context.test_request_context(
            method="POST",
            json={"query": "howler.id:*", "offset": 10, "filters": ["f1", "f2"]},
            headers={"Content-Type": "application/json"},
        ):
            from flask import request as flask_request

            from howler.utils.net_utils import generate_params

            params, req_data = generate_params(flask_request, ["query", "offset"], ["filters"])

            assert params == {"query": "howler.id:*", "offset": 10, "filters": ["f1", "f2"]}
            assert req_data["query"] == "howler.id:*"

    def test_post_uses_default_query_when_json_is_missing(self, request_context: Flask):
        """POST requests fall back to a wildcard query when no JSON body is present."""
        with request_context.test_request_context(
            method="POST",
            data=b"not-json",
            content_type="text/plain",
        ):
            from flask import request as flask_request

            from howler.utils.net_utils import generate_params

            params, req_data = generate_params(flask_request, ["query"], [])

            assert params == {"query": "*:*"}
            assert req_data == {"query": "*:*"}

    def test_get_extracts_fields_and_multi_fields(self, request_context: Flask):
        """GET requests use query parameters and preserve repeated values."""
        with request_context.test_request_context(
            method="GET",
            query_string=[("query", "howler.id:*"), ("filters", "f1"), ("filters", "f2")],
        ):
            from flask import request as flask_request

            from howler.utils.net_utils import generate_params

            params, req_data = generate_params(flask_request, ["query"], ["filters"])

            assert params == {"query": "howler.id:*", "filters": ["f1", "f2"]}
            assert req_data.getlist("filters") == ["f1", "f2"]

    def test_existing_params_are_preserved(self, request_context: Flask):
        """Existing params are merged without losing prior values."""
        with request_context.test_request_context(
            method="GET",
            query_string={"query": "howler.id:*", "rows": "25"},
        ):
            from flask import request as flask_request

            from howler.utils.net_utils import generate_params

            params, req_data = generate_params(flask_request, ["rows"], [], params={"offset": 5})

            assert params == {"offset": 5, "rows": "25"}
            assert req_data["rows"] == "25"
