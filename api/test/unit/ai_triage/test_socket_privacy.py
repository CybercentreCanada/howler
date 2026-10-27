import json
from unittest.mock import Mock

import pytest
from flask import Flask

from howler.api import socket as socket_api
from howler.security import socket as socket_auth
from howler.services import ai_triage_service, hit_service

from .support import make_hit, make_user


@pytest.mark.parametrize("recipient,expected", [("analyst", 1), ("other-user", 0), (None, 0)])
def test_authenticated_socket_filters_ai_recipient_and_strips_private_metadata(monkeypatch, recipient, expected):
    callbacks = {}
    ws = Mock(connected=False)
    ws.receive.return_value = "qa-token"
    monkeypatch.setattr(socket_auth, "Server", lambda *_args, **_kwargs: ws)
    user = make_user()
    record = make_hit()
    storage = Mock()
    storage.user.get.return_value = user
    storage.hit.get_if_exists.return_value = (record, "0")
    monkeypatch.setattr(ai_triage_service, "datastore", lambda: storage)
    monkeypatch.setattr(hit_service, "datastore", lambda: storage)
    monkeypatch.setattr(
        ai_triage_service.ai_triage_queue,
        "read_run",
        lambda _: {"run_id": "run-qa", "_owner": user.uname, "results": [{"hit_id": record.howler.id}]},
    )
    auth = Mock(return_value=(user, ["R"]))
    monkeypatch.setattr(socket_auth.auth_service, "bearer_auth", auth)
    monkeypatch.setattr(socket_api.comms_service, "on", lambda event, callback: callbacks.update({event: callback}))
    monkeypatch.setattr(socket_api.comms_service, "off", Mock())
    app = Flask(__name__)
    app.config.update(SECRET_KEY="qa-not-secret", TESTING=True)
    with app.test_request_context("/socket/v1/connect"):
        socket_api.connect()
    auth.assert_called_once_with("qa-token")
    ws.send.reset_mock()
    callbacks["action"](
        {
            "operation_id": "ai_triage",
            "run_id": "run-qa",
            "request_id": "request-qa",
            "revision": 2,
            "state": "running",
            "processed": 1,
            "total": 3,
            "recipient": recipient,
            "results": [{"hit_id": "classified-hit", "reason": "private error"}],
            "token": "secret-token",
            "_owner": "private-owner",
        }
    )
    assert ws.send.call_count == expected
    if expected:
        payload = json.loads(ws.send.call_args.args[0])
        assert set(payload) == {
            "type",
            "error",
            "status",
            "message",
            "operation_id",
            "run_id",
            "request_id",
            "revision",
            "state",
            "processed",
            "total",
        }
        assert "private" not in json.dumps(payload) and "classified-hit" not in json.dumps(payload)
    ws.send.reset_mock()
    legacy = {"operation_id": "add_label", "request_id": "legacy", "message": "label changed"}
    callbacks["action"](legacy)
    assert ws.send.call_count == 1
    assert json.loads(ws.send.call_args.args[0])["message"] == "label changed"
