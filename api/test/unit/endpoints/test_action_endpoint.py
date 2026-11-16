import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from flask import Flask, Response

from howler.actions.models import DISPATCHER_ARGUMENTS
from howler.odm.models.action import Action


@pytest.fixture(scope="module")
def request_context():
    app = Flask("test_action_endpoint")
    app.config.update(SECRET_KEY="test test", TESTING=True)
    return app


def _build_action() -> Action:
    return Action(
        {
            "action_id": "11111111-1111-4111-8111-111111111111",
            "owner": "test",
            "name": "Test action",
            "query": "howler.id:*",
            "triggers": [],
            "operations": [],
        }
    )


def _configure_auth(mock_auth_service, mock_quota_tracker):
    mock_auth_service.bearer_auth.return_value = (
        {"uname": "test", "type": ["admin"], "api_quota": 1000},
        ["R", "E"],
    )
    mock_quota_tracker.begin.return_value = True


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (None, "Incorrect data structure!"),
        ({"name": None, "query": "howler.id:*", "operations": []}, "Name cannot be empty."),
        ({"name": "Test", "query": None, "operations": []}, "Query cannot be empty."),
        ({"name": "Test", "query": "howler.id:*", "operations": None}, "You must specify a list of operations."),
        (
            {"name": "Test", "query": "howler.id:*", "operations": [{"operation_id": []}]},
            "Every operation must specify an operation_id.",
        ),
        (
            {
                "name": "Test",
                "query": "howler.id:*",
                "operations": [{"operation_id": "add_label"}, {"operation_id": "add_label"}],
            },
            "You must have a maximum of one operation of each type in the action.",
        ),
    ],
)
def test_validate_action_structure(payload, expected_error, request_context: Flask):
    from howler.services.action_service import validate_action

    with request_context.test_request_context():
        response = validate_action(payload)

    assert response is not None
    assert response.status_code == 400
    assert response.get_json()["api_error_message"] == expected_error


@pytest.mark.parametrize(
    ("operation_id", "data_json", "expected_error"),
    [
        ("unknown", "{}", "does not match any enabled operations"),
        ("add_label", "{", "data_json must be valid JSON"),
        ("add_label", "[]", "data_json must be a JSON object"),
        ("add_label", '{"category":"generic","label":"ok","extra":1}', "extra"),
        ("add_label", '{"category":"generic","label":"ok","query":"x"}', "query"),
        ("promote", '{"escalation":"evidence"}', "must provide an assessment"),
        ("promote", '{"escalation":"evidence","assessment":"development"}', "not an evidence assessment"),
        ("demote", '{"escalation":"miss"}', "must provide an assessment value when demoting to miss"),
        ("demote", '{"escalation":"miss","assessment":"attempt"}', "not a miss assessment"),
        ("promote", '{"escalation":"evidence","assessment":"attempt"}', None),
        ("demote", '{"escalation":"miss","assessment":"false-positive"}', None),
    ],
)
def test_validate_action_operation_arguments(operation_id, data_json, expected_error, request_context: Flask):
    from howler.services.action_service import validate_action

    payload = {
        "name": "Test",
        "query": "howler.id:*",
        "operations": [{"operation_id": operation_id, "data_json": data_json}],
    }
    with request_context.test_request_context():
        response = validate_action(payload)

    if expected_error is None:
        assert response is None
    else:
        assert response is not None
        assert response.status_code == 400
        assert expected_error in response.get_json()["api_error_message"]


@pytest.mark.parametrize(
    ("payload", "expected_error"),
    [
        (None, "Incorrect data structure!"),
        ({}, "You must specify a list of operations."),
        ({"operations": [{}]}, "Every operation must specify an operation_id."),
        (
            {"operations": [{"operation_id": "add_label"}, {"operation_id": "add_label"}]},
            "You must have a maximum of one operation of each type in request.",
        ),
        ({"operations": [{"operation_id": "add_label"}]}, "You must specify a query."),
        ({"operations": [{"operation_id": "add_label"}], "query": ""}, "You must specify a query."),
        ({"operations": [{"operation_id": "add_label"}], "query": "howler.id:*"}, None),
    ],
)
def test_validate_execute_request(payload, expected_error, request_context: Flask):
    from howler.services.action_service import validate_execute_request

    with request_context.test_request_context():
        response = validate_execute_request(payload)

    if expected_error is None:
        assert response is None
    else:
        assert response is not None
        assert response.status_code == 400
        assert response.get_json()["api_error_message"] == expected_error


@patch("howler.security.login.audit")
@patch("howler.security.login.QUOTA_TRACKER")
@patch("howler.security.login.auth_service")
@patch("howler.services.action_service.datastore")
def test_get_action_success(
    mock_datastore,
    mock_auth_service,
    mock_quota_tracker,
    mock_audit,
    request_context: Flask,
):
    action = _build_action()
    mock_datastore.return_value.action.get_if_exists.return_value = (action, "v1")
    _configure_auth(mock_auth_service, mock_quota_tracker)

    with request_context.test_request_context(
        "/api/v1/action/11111111-1111-4111-8111-111111111111",
        headers={"Authorization": "Bearer ."},
    ):
        from howler.api.v1.action import get_action

        result: Response = get_action(id="11111111-1111-4111-8111-111111111111")

    assert result.status_code == 200
    assert result.headers["ETag"] == "v1"
    assert result.get_json()["api_response"]["action_id"] == action.action_id
    mock_datastore.return_value.action.get_if_exists.assert_called_once_with(
        key=action.action_id,
        as_obj=True,
        version=True,
    )


@patch("howler.security.login.audit")
@patch("howler.security.login.QUOTA_TRACKER")
@patch("howler.security.login.auth_service")
@patch("howler.services.action_service.datastore")
def test_get_action_not_found(
    mock_datastore,
    mock_auth_service,
    mock_quota_tracker,
    mock_audit,
    request_context: Flask,
):
    mock_datastore.return_value.action.get_if_exists.return_value = (None, "create")
    _configure_auth(mock_auth_service, mock_quota_tracker)

    with request_context.test_request_context(
        "/api/v1/action/missing",
        headers={"Authorization": "Bearer ."},
    ):
        from howler.api.v1.action import get_action

        result: Response = get_action(id="missing")

    assert result.status_code == 404
    assert result.get_json()["api_error_message"] == "The specified action does not exist"


@patch("howler.security.login.audit")
@patch("howler.security.login.QUOTA_TRACKER")
@patch("howler.security.login.auth_service")
@patch("howler.api.v1.action.datastore")
def test_get_actions_caps_results(
    mock_datastore,
    mock_auth_service,
    mock_quota_tracker,
    mock_audit,
    request_context: Flask,
):
    stream_closed = False

    def action_stream():
        nonlocal stream_closed
        try:
            for index in range(300):
                yield {"action_id": str(index)}
        finally:
            stream_closed = True

    mock_datastore.return_value.action.stream_search.return_value = action_stream()
    _configure_auth(mock_auth_service, mock_quota_tracker)

    with request_context.test_request_context(
        "/api/v1/action/",
        headers={"Authorization": "Bearer ."},
    ):
        from howler.api.v1.action import get_actions

        result: Response = get_actions()

    actions = result.get_json()["api_response"]
    assert result.status_code == 200
    assert len(actions) == 250
    assert actions[-1]["action_id"] == "249"
    assert stream_closed
    mock_datastore.return_value.action.stream_search.assert_called_once_with("*:*", as_obj=False)


@pytest.mark.parametrize(
    "bad_data_json",
    [
        "{",
        "[]",
        42,
        *[json.dumps({"category": "generic", "label": "ok", key: "spoofed"}) for key in sorted(DISPATCHER_ARGUMENTS)],
    ],
)
@patch("howler.services.action_service.datastore")
@patch("howler.services.action_service.audit")
@patch("howler.services.action_service.actions.execute", return_value=[])
def test_execute_operations_and_saved_action_report_invalid_data_json_and_continue(
    mock_execute,
    mock_audit,
    mock_datastore,
    bad_data_json,
):
    from howler.services import action_service

    user = {"uname": "test", "type": ["admin"]}
    audit_fn = lambda: None  # noqa: E731
    mock_datastore.return_value.action.get.return_value = SimpleNamespace(
        query="howler.id:*",
        operations=[
            SimpleNamespace(operation_id="add_label", data_json=bad_data_json),
            SimpleNamespace(operation_id="remove_label", data_json="{}"),
        ],
    )

    reports = action_service.execute_saved_action(
        "action-id",
        query_override=None,
        request_id="request-1",
        user=user,  # type: ignore[arg-type]
        audit_fn=audit_fn,
    )

    assert reports is not None
    assert reports["add_label"][0]["title"] == "Invalid Arguments"
    assert reports["remove_label"] == []
    mock_execute.assert_called_once_with(
        operation_id="remove_label",
        request_id="request-1",
        query="howler.id:*",
        user=user,
    )
    first_audit = mock_audit.call_args_list[0].args[1]
    assert first_audit == {"user": user, "query": "howler.id:*", "operation_id": "add_label"}
    assert mock_audit.call_args_list[0].args[4] is audit_fn
