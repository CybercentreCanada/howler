"""Deterministic boundary doubles; production triage logic is never substituted."""

import json
from collections import deque
from copy import deepcopy

import requests

from howler.odm.models.hit import Hit
from howler.odm.models.user import User


class Clock:
    def __init__(self, now=1_000.0):
        self.now = now

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def make_user(name="analyst", roles=None, classification="U"):
    return User(
        {
            "uname": name,
            "name": name,
            "password": "not-a-real-password-hash",
            "type": roles or ["user", "actionrunner_basic"],
            "classification": classification,
        }
    )


def make_hit(**howler):
    return Hit(
        {
            "classification": "U",
            "howler": {"analytic": "QA detection", "hash": "123abc", **howler},
            "event": {"original": "current telemetry"},
        }
    )


def make_lead(content="Analyst note", owner=None):
    return {
        "label": {"en": "AI Triage", "fr": "Triage IA"},
        "format": "markdown",
        "content": content,
        "metadata": json.dumps({"owner": owner}) if owner else None,
    }


def response(body=None, *, status=200, lines=None, content_type="application/json"):
    """Real requests response with a scripted byte stream, including stream failures."""
    result = requests.Response()
    result.status_code = status
    result.headers["Content-Type"] = content_type
    result.encoding = "utf-8"
    result.url = "https://ai.invalid/triage"
    result._content = json.dumps(body).encode()
    result._content_consumed = True

    def chunks(*args, **kwargs):
        for line in lines or []:
            if isinstance(line, Exception):
                raise line
            if isinstance(line, str):
                yield line if kwargs.get("decode_unicode") else line.encode()
            else:
                yield line

    if lines is not None:
        result.iter_lines = chunks

        def content_chunks(*args, **kwargs):
            for line in chunks():
                yield line + b"\n"

        result.iter_content = content_chunks
    return result


def sse(*events):
    lines = []
    for event in events:
        lines.extend(["data: " + json.dumps(event), ""])
    return response(lines=lines, content_type="text/event-stream")


class ScriptedSession:
    """Reject unexpected network activity and record all security-relevant options."""

    def __init__(self, *responses):
        self.responses = deque(responses)
        self.calls = []
        self.headers = {}
        self.trust_env = True
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **deepcopy(kwargs)})
        assert self.responses, f"Unexpected additional AI request: {method} {url}"
        item = self.responses.popleft()
        if isinstance(item, Exception):
            raise item
        return item(kwargs) if callable(item) else item

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
