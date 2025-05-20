import pytest
from flask import Flask

import howler.api as api


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_app")

    app.config.update(SECRET_KEY="test test")

    return app


def test_http_response_functions(request_context):
    with request_context.test_request_context():
        ok_result = api.ok()
        assert ok_result.json["api_response"] == api.DEFAULT_DATA[True]
        assert ok_result.status_code == 200

        created_result = api.created()
        assert created_result.json["api_response"] == api.DEFAULT_DATA[True]
        assert created_result.status_code == 201

        accepted_result = api.accepted()
        assert accepted_result.json["api_response"] == api.DEFAULT_DATA[True]
        assert accepted_result.status_code == 202

        no_content_result = api.no_content()
        assert no_content_result.json["api_response"] == api.DEFAULT_DATA[True]
        assert no_content_result.status_code == 204

        not_modified_result = api.not_modified()
        assert not_modified_result.json["api_response"] == api.DEFAULT_DATA[True]
        assert not_modified_result.status_code == 304

        bad_request_result = api.bad_request()
        assert bad_request_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert bad_request_result.status_code == 400

        unauthorized_result = api.unauthorized()
        assert unauthorized_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert unauthorized_result.status_code == 401

        forbidden_result = api.forbidden()
        assert forbidden_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert forbidden_result.status_code == 403

        not_found_result = api.not_found()
        assert not_found_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert not_found_result.status_code == 404

        conflict_result = api.conflict()
        assert conflict_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert conflict_result.status_code == 409

        precondition_failed_result = api.precondition_failed()
        assert precondition_failed_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert precondition_failed_result.status_code == 412

        teapot_result = api.teapot()
        assert teapot_result.json["api_response"] == {"success": False, "teapot": True}
        assert teapot_result.status_code == 418

        too_many_requests_result = api.too_many_requests()
        assert too_many_requests_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert too_many_requests_result.status_code == 429

        internal_error_result = api.internal_error()
        assert internal_error_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert internal_error_result.status_code == 500

        not_implemented_result = api.not_implemented()
        assert not_implemented_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert not_implemented_result.status_code == 501

        bad_gateway_result = api.bad_gateway()
        assert bad_gateway_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert bad_gateway_result.status_code == 502

        service_unavailable_result = api.service_unavailable()
        assert service_unavailable_result.json["api_response"] == api.DEFAULT_DATA[False]
        assert service_unavailable_result.status_code == 503
