from types import SimpleNamespace
from typing import Protocol, cast

import pytest
import requests

from howler.odm.models.config import AITriage
from howler.services import ai_transport

from .support import Clock, ScriptedSession


class _HasClock(Protocol):
    clock: Clock


@pytest.fixture(autouse=True)
def forbid_unscripted_http(monkeypatch):
    def fail_request(_self, method, url, **_kwargs):
        pytest.fail(f"Unit test attempted unscripted HTTP: {method} {url}")

    monkeypatch.setattr(requests.sessions.Session, "request", fail_request)


@pytest.fixture
def transport_error():
    return ai_transport.AITransportError


@pytest.fixture
def invoke_transport(monkeypatch):
    clock = Clock()
    monkeypatch.setattr(ai_transport, "time", SimpleNamespace(monotonic=clock, sleep=clock.sleep))

    def invoke(provider, responses, *, remaining=60, checkpoints=None, overrides=None, **resume):
        session = ScriptedSession(*responses)
        monkeypatch.setattr(ai_transport.requests, "Session", lambda: session)
        checkpoints = checkpoints if checkpoints is not None else []
        settings = AITriage(
            enabled=True,
            provider=provider,
            endpoint="https://ai.invalid/triage",
            model="qa-model",
            **(overrides or {}),
        )
        text = ai_transport.generate(
            settings,
            "qa-access-token",
            settings.system_prompt,
            {"event": {"original": "untrusted alert data"}},
            deadline=clock() + remaining,
            checkpoint=lambda task_id, context_id: checkpoints.append((task_id, context_id)),
            **resume,
        )
        return text, session, checkpoints

    cast(_HasClock, invoke).clock = clock
    return invoke
