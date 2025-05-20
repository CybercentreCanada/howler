import json
import signal
import struct

import pytest
import requests
from requests.auth import HTTPBasicAuth
from utils.oauth_credentials import get_token
from websocket import WebSocket, create_connection

from howler.api.socket import HWL_INTERPOD_COMMS_SECRET


@pytest.fixture(scope="module")
def ws_client(host, datastore_connection):
    ws = create_connection(f'{host.replace("http", "ws")}/socket/v1/connect')

    app_token = get_token(user="goose")
    ws.send(app_token)

    data = json.loads(ws.recv())

    assert data["status"] == 200
    assert not data["error"]
    assert data["username"] == "goose"

    yield ws

    ws.close()


@pytest.fixture(scope="module")
def timeout():
    def timeout():
        raise TimeoutError("Timeout!")

    signal.signal(signal.SIGALRM, timeout)

    yield signal

    signal.alarm(0)


def test_ws_listener(ws_client: WebSocket, host: str, timeout):
    try:
        timeout.alarm(10)

        requests.post(
            f"{host}/socket/v1/emit/broadcast",
            json={"test": "hello"},
            auth=HTTPBasicAuth("user", HWL_INTERPOD_COMMS_SECRET),
        )

        data = json.loads(ws_client.recv())

        assert data["status"] == 200
        assert data["type"] == "broadcast"
        assert data["event"]["test"] == "hello"

        timeout.alarm(0)
    except TimeoutError:
        pytest.fail("Websocket connection timed out")


def test_ws_communication(ws_client: WebSocket, timeout):
    try:
        timeout.alarm(10)

        ws_client.send(json.dumps({"broadcast": True, "action": "typing", "id": "test_id"}))

        data = json.loads(ws_client.recv())

        assert data["type"] == "broadcast"
        assert data["event"]["id"] == "test_id"
        assert data["event"]["username"] == "goose"

        timeout.alarm(0)
    except TimeoutError:
        pytest.fail("Websocket connection timed out")


def test_ws_outstanding_actions(ws_client: WebSocket, timeout, host):
    app_token = get_token(user="huey")
    assert app_token is not None
    ws = create_connection(f'{host.replace("http", "ws")}/socket/v1/connect')
    ws.send(app_token)

    data = json.loads(ws.recv())

    assert data["status"] == 200
    assert not data["error"]
    assert data["username"] == "huey"

    try:
        timeout.alarm(10)

        ws.send(json.dumps({"broadcast": True, "action": "typing", "id": "test_id"}))

        data = json.loads(ws_client.recv())

        assert data["event"]["id"] == "test_id"
        assert data["event"]["action"] == "typing"

        ws.close()

        data = json.loads(ws_client.recv())

        assert data["event"]["id"] == "test_id"
        assert data["event"]["action"] == "stop_typing"

        timeout.alarm(0)
    except TimeoutError:
        pytest.fail("Websocket connection timed out")


def test_ws_communication_invalid(ws_client: WebSocket, timeout):
    try:
        timeout.alarm(10)

        ws_client.send(json.dumps({}))

        # https://websocket-client.readthedocs.io/en/latest/examples.html#receiving-connection-close-status-codes
        opcode, msg = ws_client.recv_data()

        assert not ws_client.connected

        assert opcode == 8

        assert struct.unpack("!H", msg[0:2])[0] == 1008

        data = json.loads(msg[2:].decode())

        assert data["error"]
        assert data["message"] == "Sent data is invalid."

        timeout.alarm(0)
    except TimeoutError:
        pytest.fail("Websocket connection timed out")
