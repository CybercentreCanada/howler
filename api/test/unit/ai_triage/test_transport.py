"""Protocol vectors use scripted HTTP, but execute the complete production parser."""

import json

import pytest
import requests

from .support import response, sse


def completion(text="Conservative opinion", finish_reason="stop"):
    return response({"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": finish_reason}]})


def task(state="working", text=None):
    result = {"kind": "task", "id": "task-qa", "contextId": "context-qa", "status": {"state": state}}
    if text is not None:
        result["artifacts"] = [{"artifactId": "opinion", "parts": [{"kind": "text", "text": text}]}]
    return result


def artifact(text, *, append=False, artifact_id="opinion"):
    return {
        "kind": "artifact-update",
        "taskId": "task-qa",
        "contextId": "context-qa",
        "artifact": {"artifactId": artifact_id, "parts": [{"kind": "text", "text": text}]},
        "append": append,
        "lastChunk": False,
    }


def status(state="completed", final=True):
    return {
        "kind": "status-update",
        "taskId": "task-qa",
        "contextId": "context-qa",
        "status": {"state": state},
        "final": final,
    }


def stream(*results):
    def build(kwargs):
        request_id = kwargs["json"]["id"]
        return sse(*[{"jsonrpc": "2.0", "id": request_id, "result": result} for result in results])

    return build


def rpc(result=None, *, error=None):
    def build(kwargs):
        return response(
            {
                "jsonrpc": "2.0",
                "id": kwargs["json"]["id"],
                **({"error": error} if error else {"result": result}),
            }
        )

    return build


def test_openai_complete_text_and_secure_http_options(invoke_transport):
    text, session, _ = invoke_transport("openai", [completion()])
    assert text == "Conservative opinion"
    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["json"]["stream"] is False
    assert call["headers"]["Authorization"] == "Bearer qa-access-token"
    assert call["allow_redirects"] is False
    assert call.get("verify", True) is True
    assert session.trust_env is False
    assert "qa-access-token" not in json.dumps(call["json"])
    assert call["timeout"]


@pytest.mark.parametrize("finish_reason", ["length", "content_filter", "tool_calls", None])
def test_openai_rejects_incomplete_or_tool_only_results(invoke_transport, transport_error, finish_reason):
    with pytest.raises(transport_error):
        invoke_transport("openai", [completion("partial", finish_reason)])


@pytest.mark.parametrize("text", ["", " \n\t", None, [], {"text": "not text"}])
def test_openai_requires_nonempty_plain_text(invoke_transport, transport_error, text):
    with pytest.raises(transport_error):
        invoke_transport("openai", [completion(text)])


def test_stream_appends_replaces_and_keeps_separate_artifacts(invoke_transport):
    text, session, checkpoints = invoke_transport(
        "a2a",
        [
            stream(
                task(),
                artifact("obsolete"),
                artifact("replacement"),
                artifact(" plus", append=True),
                artifact("limitations", artifact_id="second"),
                status(),
            )
        ],
    )
    assert "replacement plus" in text
    assert "limitations" in text
    assert "obsolete" not in text
    assert len(session.calls) == 1
    assert checkpoints
    assert "task-qa" in repr(checkpoints)
    assert "context-qa" in repr(checkpoints)


@pytest.mark.parametrize("state", ["failed", "canceled", "rejected", "input-required", "auth-required", "working"])
def test_stream_final_does_not_imply_success(invoke_transport, transport_error, state):
    with pytest.raises(transport_error):
        invoke_transport("a2a", [stream(task(), artifact("must not be saved"), status(state))])


def test_completed_empty_task_does_not_succeed(invoke_transport, transport_error):
    with pytest.raises(transport_error):
        invoke_transport("a2a", [stream(task(), status())])


def test_sse_end_of_file_is_not_completion(invoke_transport, transport_error):
    with pytest.raises(transport_error):
        invoke_transport("a2a", [stream(task(), artifact("partial text"))])


@pytest.mark.parametrize("http_status", [401, 403, 429, 500, 503])
def test_http_errors_never_switch_protocol(invoke_transport, transport_error, http_status):
    with pytest.raises(transport_error):
        # A second request fails the scripted transport assertion, not the expected domain exception.
        invoke_transport("a2a", [response({"error": "private upstream detail"}, status=http_status)])


def test_only_explicit_stream_unsupported_falls_back_to_send_then_poll(invoke_transport):
    text, session, checkpoints = invoke_transport(
        "a2a",
        [
            rpc(error={"code": -32601, "message": "method not found"}),
            rpc(task()),
            rpc(task("completed", "polled opinion")),
        ],
    )
    assert text == "polled opinion"
    assert [call["json"]["method"] for call in session.calls] == ["message/stream", "message/send", "tasks/get"]
    assert session.calls[-1]["json"]["params"]["id"] == "task-qa"
    assert checkpoints


@pytest.mark.parametrize("error_code", [-32600, -32602, -32603, -32001])
def test_unrelated_rpc_errors_do_not_resubmit(invoke_transport, transport_error, error_code):
    with pytest.raises(transport_error):
        invoke_transport("a2a", [rpc(error={"code": error_code, "message": "must not be replayed"})])


def test_malformed_sse_does_not_fall_back(invoke_transport, transport_error):
    with pytest.raises(transport_error):
        invoke_transport("a2a", [response(lines=["data: {not-json", ""], content_type="text/event-stream")])


def test_interrupted_stream_records_task_before_failure(invoke_transport, transport_error):
    def interrupted(kwargs):
        event = {"jsonrpc": "2.0", "id": kwargs["json"]["id"], "result": task()}
        return response(
            lines=["data: " + json.dumps(event), "", requests.exceptions.ChunkedEncodingError("disconnect")],
            content_type="text/event-stream",
        )

    checkpoints = []
    with pytest.raises(transport_error):
        invoke_transport("a2a", [interrupted], checkpoints=checkpoints)
    assert "task-qa" in repr(checkpoints)


def test_jsonrpc_response_id_mismatch_is_rejected(invoke_transport, transport_error):
    with pytest.raises(transport_error):
        invoke_transport("a2a", [sse({"jsonrpc": "2.0", "id": "other-request", "result": task("completed", "wrong")})])


def test_expired_deadline_never_contacts_provider(invoke_transport, transport_error):
    with pytest.raises(transport_error):
        invoke_transport("openai", [], remaining=-1)


def test_unsupported_after_task_acceptance_cannot_resubmit(invoke_transport, transport_error):
    def partial_then_error(kwargs):
        request_id = kwargs["json"]["id"]
        return sse(
            {"jsonrpc": "2.0", "id": request_id, "result": task()},
            {"jsonrpc": "2.0", "id": request_id, "result": artifact("partial")},
            {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "unsupported"}},
        )

    with pytest.raises(transport_error):
        invoke_transport("a2a", [partial_then_error])


@pytest.mark.parametrize("http_status", [301, 302, 307, 308])
def test_redirects_fail_closed(invoke_transport, transport_error, http_status):
    with pytest.raises(transport_error):
        invoke_transport("openai", [response({}, status=http_status)])


@pytest.mark.parametrize("provider", ["openai", "a2a"])
def test_output_bounds(invoke_transport, transport_error, provider):
    scripted = completion("x" * 5000) if provider == "openai" else stream(task("completed", "x" * 5000))
    with pytest.raises(transport_error):
        invoke_transport(provider, [scripted], overrides={"max_output_bytes": 1024})


def test_sse_line_bound_without_newline(invoke_transport, transport_error):
    result = response()
    result.headers["Content-Type"] = "text/event-stream"
    result.iter_content = lambda **_: iter([b"data: " + b"x" * 2000])
    with pytest.raises(transport_error):
        invoke_transport("a2a", [result], overrides={"max_sse_line_bytes": 1024})


@pytest.mark.parametrize("overrides", [{"headers": {"Authorization": "secret"}}, {"extra_body": {"stream": True}}])
def test_reserved_config_cannot_override_protocol_or_auth(invoke_transport, transport_error, overrides):
    with pytest.raises(transport_error):
        invoke_transport("openai", [], overrides=overrides)


@pytest.mark.parametrize("version", [None, "1.0"])
def test_a2a_requires_jsonrpc_two_envelope(invoke_transport, transport_error, version):
    def invalid_envelope(kwargs):
        payload = {"id": kwargs["json"]["id"], "result": task("completed", "must not accept")}
        if version:
            payload["jsonrpc"] = version
        return sse(payload)

    with pytest.raises(transport_error):
        invoke_transport("a2a", [invalid_envelope])


def test_fallback_cannot_restart_expired_request_budget(invoke_transport, transport_error):
    def slow_unsupported(kwargs):
        invoke_transport.clock.sleep(2)
        return rpc(error={"code": -32601, "message": "unsupported"})(kwargs)

    with pytest.raises(transport_error):
        invoke_transport("a2a", [slow_unsupported], remaining=1)


def test_serialized_extra_body_is_included_in_input_budget(invoke_transport, transport_error):
    with pytest.raises(transport_error):
        invoke_transport("openai", [], overrides={"max_input_bytes": 1024, "extra_body": {"metadata": "x" * 5000}})


def test_sse_total_byte_budget_covers_many_small_events(invoke_transport, transport_error):
    with pytest.raises(transport_error):
        invoke_transport(
            "a2a",
            [stream(task(), *[artifact("x" * 100, append=True) for _ in range(20)], status())],
            overrides={"max_sse_bytes": 1024},
        )


@pytest.mark.parametrize("streamed", [False, True])
def test_rpc_cannot_contain_both_result_and_error(invoke_transport, transport_error, streamed):
    def malformed(kwargs):
        envelope = {
            "jsonrpc": "2.0",
            "id": kwargs["json"]["id"],
            "result": task("completed", "bad"),
            "error": {"code": -32601, "message": "unsupported"},
        }
        return sse(envelope) if streamed else response(envelope)

    with pytest.raises(transport_error):
        invoke_transport("a2a", [malformed])


@pytest.mark.parametrize("status_code", [404, 405])
def test_http_not_found_or_method_not_allowed_is_not_rpc_unsupported(invoke_transport, transport_error, status_code):
    with pytest.raises(transport_error):
        invoke_transport("a2a", [response({}, status=status_code)])


@pytest.mark.parametrize("streamed", [False, True])
def test_task_requires_own_id_in_every_transport(invoke_transport, transport_error, streamed):
    invalid = task("completed", "not correlated")
    invalid.pop("id")
    with pytest.raises(transport_error):
        invoke_transport("a2a", [stream(invalid) if streamed else rpc(invalid)])


def test_poll_cannot_return_a_task_without_canonical_id(invoke_transport, transport_error):
    invalid = task("completed", "not correlated")
    invalid.pop("id")
    with pytest.raises(transport_error):
        invoke_transport("a2a", [rpc(invalid)], resume_task_id="task-qa", resume_context_id="context-qa")


def test_non_sse_working_task_is_checkpointed_and_polled_not_resubmitted(invoke_transport):
    text, session, checkpoints = invoke_transport("a2a", [rpc(task()), rpc(task("completed", "polled"))])
    assert text == "polled" and checkpoints
    assert [call["json"]["method"] for call in session.calls] == ["message/stream", "tasks/get"]


@pytest.mark.parametrize("streamed", [False, True])
def test_valid_direct_agent_message_needs_no_task_or_resubmission(invoke_transport, streamed):
    message = {
        "kind": "message",
        "role": "agent",
        "messageId": "message-qa",
        "parts": [{"kind": "text", "text": "direct opinion"}],
    }
    text, session, _ = invoke_transport("a2a", [stream(message) if streamed else rpc(message)])
    assert text == "direct opinion" and len(session.calls) == 1


@pytest.mark.parametrize("invalid", ["role", "messageId", "parts"])
def test_direct_message_requires_agent_identity_and_text(invoke_transport, transport_error, invalid):
    message = {
        "kind": "message",
        "role": "agent",
        "messageId": "message-qa",
        "parts": [{"kind": "text", "text": "direct"}],
    }
    message.pop(invalid)
    with pytest.raises(transport_error):
        invoke_transport("a2a", [rpc(message)])


def test_stream_task_cannot_change_context_or_switch_to_direct_message(invoke_transport, transport_error):
    changed = status()
    changed["contextId"] = "other-context"
    with pytest.raises(transport_error):
        invoke_transport("a2a", [stream(task(), artifact("opinion"), changed)])
    message = {
        "kind": "message",
        "role": "agent",
        "messageId": "message-qa",
        "parts": [{"kind": "text", "text": "wrong"}],
    }
    with pytest.raises(transport_error):
        invoke_transport("a2a", [stream(task(), message)])
