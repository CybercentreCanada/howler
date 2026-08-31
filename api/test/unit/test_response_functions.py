from typing import cast

import pytest
from flask import Flask

import howler.api as api
from howler.models.action import Action as SchemaAction
from howler.odm import Model
from howler.odm.models.user import User
from howler.odm.randomizer import random_model_obj


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


def test_internal_error_clips_traceback_to_innermost_frame(request_context):
    """API error responses should expose only the original traceback frame."""

    def _inner_failure():
        raise ValueError("boom")

    def _outer_failure():
        _inner_failure()

    with request_context.test_request_context():
        try:
            _outer_failure()
        except Exception as err:
            response = api._make_api_response(None, err=err, status_code=500)

    message = response.json["api_error_message"]

    assert "_outer_failure" not in message
    assert "test_internal_error_clips_traceback_to_innermost_frame" not in message
    assert "_inner_failure" in message
    assert "ValueError: boom" in message


def test_format_api_error_message_clips_to_innermost_frame(request_context):
    """The dedicated traceback formatter should keep only the innermost frame."""

    def _inner_failure():
        raise RuntimeError("boom")

    def _outer_failure():
        _inner_failure()

    with request_context.test_request_context():
        try:
            _outer_failure()
        except Exception as err:
            message = api._format_api_error_message(err)

    assert "_outer_failure" not in message
    assert "test_format_api_error_message_clips_to_innermost_frame" not in message
    assert "_inner_failure" in message
    assert "RuntimeError: boom" in message


def test_coerce_response_data_handles_model_instances():
    """Model instances should be converted to primitive dictionaries."""
    user = random_model_obj(cast(Model, User))

    coerced = api._coerce_response_data(user)

    assert coerced == user.as_primitives()


def test_coerce_response_data_handles_lists_of_models():
    """Lists of ODM models should be converted element by element."""
    users = [random_model_obj(cast(Model, User)), random_model_obj(cast(Model, User))]

    coerced = api._coerce_response_data(users)

    assert coerced == [user.as_primitives() for user in users]


def test_coerce_response_data_handles_pydantic_models():
    """Finalized datastore models use the same public response conversion."""
    action = SchemaAction.model_validate(
        {
            "action_id": "action-1",
            "owner_id": "user-1",
            "name": "Test",
            "query": "id:*",
        }
    )

    assert api._coerce_response_data(action) == action.as_primitives()
    assert api._coerce_response_data([action]) == [action.as_primitives()]


def test_coerce_response_data_passthrough_for_plain_values():
    """Plain JSON-serializable values should be returned unchanged."""
    payload = {"success": True, "count": 3}

    coerced = api._coerce_response_data(payload)

    assert coerced is payload
