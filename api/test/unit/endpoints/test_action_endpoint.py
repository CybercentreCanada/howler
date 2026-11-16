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
    ("updates", "omitted", "message"),
    [
        ({}, "name", "You must specify a name."),
        ({"name": ""}, None, "Name cannot be empty."),
        ({"name": None}, None, "Name cannot be empty."),
        ({}, "query", "You must specify a query."),
        ({"query": ""}, None, "Query cannot be empty."),
        ({"query": None}, None, "Query cannot be empty."),
        ({}, "operations", "You must specify a list of operations."),
        ({"operations": None}, None, "You must specify a list of operations."),
        ({"operations": "banana"}, None, "'operations' must be a list of operations."),
        ({"operations": []}, None, "You must specify at least one operation."),
        (
            {"operations": [{"operation_id": "add_label"}, {"operation_id": "add_label"}]},
            None,
            "You must have a maximum of one operation of each type in the action.",
        ),
        ({"triggers": ["invalid"]}, None, "Invalid trigger provided."),
    ],
)
def test_validate_action_preserves_legacy_messages(updates, omitted, message, request_context: Flask):
    from howler.services.action_service import validate_action

    action = {
        "name": "Test action",
        "query": "howler.id:*",
        "operations": [{"operation_id": "add_label"}],
        **updates,
    }
    if omitted is not None:
        del action[omitted]

    with request_context.test_request_context():
        response = validate_action(action)

    assert response is not None
    assert response.status_code == 400
    assert response.get_json()["api_error_message"] == message


@pytest.mark.parametrize(
    ("action", "message"),
    [
        (None, "Incorrect data structure!"),
        ([], "Incorrect data structure!"),
        ("invalid", "Incorrect data structure!"),
        (42, "Incorrect data structure!"),
        ({}, "You must specify a name."),
        ({"name": ""}, "Name cannot be empty."),
        ({"name": "Test action"}, "You must specify a query."),
        ({"name": "Test action", "query": ""}, "Query cannot be empty."),
        ({"name": "Test action", "query": "howler.id:*"}, "You must specify a list of operations."),
    ],
)
def test_validate_action_rejects_incomplete_payloads(action, message, request_context: Flask):
    from howler.services.action_service import validate_action

    with request_context.test_request_context():
        response = validate_action(action)

    assert response is not None
    assert response.status_code == 400
    assert response.get_json()["api_error_message"] == message


@pytest.mark.parametrize("operation", [{}, None, "invalid", {"operation_id": []}])
def test_validate_action_reports_malformed_operations(operation, request_context: Flask):
    from howler.services.action_service import validate_action

    with request_context.test_request_context():
        response = validate_action({"name": "Test action", "query": "howler.id:*", "operations": [operation]})

    assert response is not None
    assert response.status_code == 400
    assert "operations.0" in response.get_json()["api_error_message"]


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
    "extra",
    [{"obsolete_argument": "legacy"}, *[{key: "spoofed"} for key in sorted(DISPATCHER_ARGUMENTS)]],
)
@patch("howler.security.login.audit")
@patch("howler.security.login.QUOTA_TRACKER")
@patch("howler.security.login.auth_service")
@patch("howler.services.action_service.audit")
@patch("howler.actions.add_label.execute")
@patch("howler.actions.datastore")
def test_execute_operations_rejects_extra_and_reserved_arguments(
    mock_datastore,
    mock_add_label_execute,
    mock_action_audit,
    mock_auth_service,
    mock_quota_tracker,
    mock_login_audit,
    extra: dict[str, str],
    request_context: Flask,
):
    _configure_auth(mock_auth_service, mock_quota_tracker)
    request_data = {
        "query": "howler.id:*",
        "request_id": "request-1",
        "operations": [
            {
                "operation_id": "add_label",
                "data_json": json.dumps(
                    {
                        "category": "generic",
                        "label": "kept",
                        **extra,
                    }
                ),
            }
        ],
    }

    with request_context.test_request_context(
        "/api/v1/action/execute",
        method="POST",
        json=request_data,
        headers={"Authorization": "Bearer ."},
    ):
        from howler.api.v1.action import execute_operations

        result: Response = execute_operations()

    assert result.status_code == 200
    report = result.get_json()["api_response"]["add_label"][0]
    assert report["title"] == "Invalid Arguments"
    assert next(iter(extra)) in report["message"]
    mock_add_label_execute.assert_not_called()
    mock_datastore.assert_not_called()
    audit_record = mock_action_audit.call_args.args[1]
    assert audit_record["query"] == "howler.id:*"
    assert audit_record["operation_id"] == "add_label"
    assert audit_record["user"]["uname"] == "test"
    assert mock_action_audit.call_args.args[4] is execute_operations


@pytest.mark.parametrize("reserved", [{key: "spoofed"} for key in sorted(DISPATCHER_ARGUMENTS)])
@patch("howler.security.login.audit")
@patch("howler.security.login.QUOTA_TRACKER")
@patch("howler.security.login.auth_service")
@patch("howler.services.action_service.datastore")
@patch("howler.services.action_service.audit")
@patch("howler.actions.add_label.execute")
def test_execute_action_rejects_reserved_stored_arguments(
    mock_add_label_execute,
    mock_action_audit,
    mock_datastore,
    mock_auth_service,
    mock_quota_tracker,
    mock_login_audit,
    reserved: dict[str, str],
    request_context: Flask,
):
    _configure_auth(mock_auth_service, mock_quota_tracker)
    mock_datastore.return_value.action.get.return_value = SimpleNamespace(
        query="howler.id:*",
        operations=[
            SimpleNamespace(
                operation_id="add_label",
                data_json=json.dumps({"category": "generic", "label": "stored", **reserved}),
            )
        ],
    )

    with request_context.test_request_context(
        "/api/v1/action/action-id/execute",
        method="POST",
        json={"request_id": "request-1"},
        headers={"Authorization": "Bearer ."},
    ):
        from howler.api.v1.action import execute_action

        result: Response = execute_action(id="action-id")

    assert result.status_code == 200
    report = result.get_json()["api_response"]["add_label"][0]
    assert report["title"] == "Invalid Arguments"
    assert next(iter(reserved)) in report["message"]
    mock_add_label_execute.assert_not_called()
    audit_record = mock_action_audit.call_args.args[1]
    assert audit_record["query"] == "howler.id:*"
    assert audit_record["operation_id"] == "add_label"
    assert audit_record["user"]["uname"] == "test"
    assert mock_action_audit.call_args.args[4] is execute_action


@pytest.mark.parametrize("data_json", ["{", "[]", 42])
@patch("howler.security.login.audit")
@patch("howler.security.login.QUOTA_TRACKER")
@patch("howler.security.login.auth_service")
@patch("howler.services.action_service.audit")
@patch("howler.services.action_service.actions.execute", return_value=[])
def test_execute_operations_reports_bad_data_json_and_continues(
    mock_execute,
    mock_action_audit,
    mock_auth_service,
    mock_quota_tracker,
    mock_login_audit,
    data_json,
    request_context: Flask,
):
    _configure_auth(mock_auth_service, mock_quota_tracker)
    request_data = {
        "query": "howler.id:*",
        "request_id": "request-1",
        "operations": [
            {"operation_id": "add_label", "data_json": data_json},
            {"operation_id": "remove_label", "data_json": "{}"},
        ],
    }

    with request_context.test_request_context(
        "/api/v1/action/execute",
        method="POST",
        json=request_data,
        headers={"Authorization": "Bearer ."},
    ):
        from howler.api.v1.action import execute_operations

        result: Response = execute_operations()

    reports = result.get_json()["api_response"]
    assert reports["add_label"][0]["title"] == "Invalid Arguments"
    assert reports["remove_label"] == []
    mock_execute.assert_called_once_with(
        operation_id="remove_label",
        request_id="request-1",
        query="howler.id:*",
        user=mock_action_audit.call_args.args[1]["user"],
    )


@pytest.mark.parametrize("data_json", ["{", "[]", 42])
@patch("howler.security.login.audit")
@patch("howler.security.login.QUOTA_TRACKER")
@patch("howler.security.login.auth_service")
@patch("howler.services.action_service.datastore")
@patch("howler.services.action_service.audit")
@patch("howler.services.action_service.actions.execute", return_value=[])
def test_execute_action_reports_bad_data_json_and_continues(
    mock_execute,
    mock_action_audit,
    mock_datastore,
    mock_auth_service,
    mock_quota_tracker,
    mock_login_audit,
    data_json,
    request_context: Flask,
):
    _configure_auth(mock_auth_service, mock_quota_tracker)
    mock_datastore.return_value.action.get.return_value = SimpleNamespace(
        query="howler.id:*",
        operations=[
            SimpleNamespace(operation_id="add_label", data_json=data_json),
            SimpleNamespace(operation_id="remove_label", data_json="{}"),
        ],
    )

    with request_context.test_request_context(
        "/api/v1/action/action-id/execute",
        method="POST",
        json={"request_id": "request-1"},
        headers={"Authorization": "Bearer ."},
    ):
        from howler.api.v1.action import execute_action

        result: Response = execute_action(id="action-id")

    reports = result.get_json()["api_response"]
    assert reports["add_label"][0]["title"] == "Invalid Arguments"
    assert reports["remove_label"] == []
    mock_execute.assert_called_once_with(
        operation_id="remove_label",
        request_id="request-1",
        query="howler.id:*",
        user=mock_action_audit.call_args.args[1]["user"],
    )
