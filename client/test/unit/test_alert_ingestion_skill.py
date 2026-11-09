"""Offline safety tests for the public alert-ingestion helper."""

import importlib.util
import json
import logging
import stat
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "skills" / "howler-alert-ingestion" / "scripts" / "ingest.py"
SPEC = importlib.util.spec_from_file_location("alert_ingestion_skill", SCRIPT)
assert SPEC and SPEC.loader
ingest_script = importlib.util.module_from_spec(SPEC)
write_bytecode = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    SPEC.loader.exec_module(ingest_script)
finally:
    sys.dont_write_bytecode = write_bytecode


def _mock_client(ids):
    ingest = MagicMock()
    ingest.from_file.return_value = ids
    return SimpleNamespace(v2=SimpleNamespace(ingest=ingest)), ingest


def _configure(monkeypatch, token="test-jwt"):
    monkeypatch.setenv("HOWLER_API_URL", "https://howler.example")
    monkeypatch.setenv("HOWLER_JWT", token)
    monkeypatch.delenv("HOWLER_TOKEN_FILE", raising=False)


def _confirmation(index, source, report, api_url="https://howler.example"):
    return f"{api_url}|{index}|{Path(source).resolve()}|{Path(report).resolve()}"


def test_success_uses_one_bulk_from_file_and_writes_private_report(tmp_path, monkeypatch, capsys):
    _configure(monkeypatch, "private-jwt")
    source = tmp_path / "alerts.jsonl"
    source.write_text('{"private_alert":"DO_NOT_PRINT"}\n', encoding="utf-8")
    report = tmp_path / "result.json"
    client, ingest = _mock_client(["alert-id-1", "alert-id-2"])
    get_client = MagicMock(return_value=client)
    monkeypatch.setattr(ingest_script, "get_client", get_client)

    result = ingest_script.main(
        [
            "--api-url",
            "https://howler.example/",
            "--index",
            "event",
            "--input",
            str(source),
            "--report",
            str(report),
            "--confirm",
            _confirmation("event", source, report),
        ]
    )

    assert result == 0
    get_client.assert_called_once_with(
        "https://howler.example",
        auth="private-jwt",
        retries=1,
        verify=True,
        timeout=120,
        throw_on_bad_request=True,
        throw_on_max_retries=True,
    )
    ingest.from_file.assert_called_once_with(str(source.resolve()), index="event")
    ingest.validate.assert_not_called()
    saved = json.loads(report.read_text(encoding="utf-8"))
    assert saved == {
        "status": "response_received",
        "destination": "https://howler.example",
        "index": "event",
        "input": str(source.resolve()),
        "server_returned_count": 2,
        "server_returned_ids": ["alert-id-1", "alert-id-2"],
    }
    assert stat.S_IMODE(report.stat().st_mode) == 0o600
    output = capsys.readouterr()
    assert '"server_returned_count": 2' in output.out
    assert "alert-id-1" not in output.out
    assert "DO_NOT_PRINT" not in output.out
    assert "private-jwt" not in output.out


def test_sdk_defaults_input_path_to_alerts_jsonl(tmp_path, monkeypatch):
    _configure(monkeypatch)
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "alerts.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    client, ingest = _mock_client([])
    monkeypatch.setattr(ingest_script, "get_client", MagicMock(return_value=client))
    report = tmp_path / "ingest-report.json"

    assert ingest_script.main(["--index", "hit", "--confirm", _confirmation("hit", source, report)]) == 0

    ingest.from_file.assert_called_once_with(str(source.resolve()), index="hit")
    assert (tmp_path / "ingest-report.json").exists()


def test_preview_requires_confirmation_and_makes_no_request(tmp_path, monkeypatch, capsys):
    _configure(monkeypatch)
    source = tmp_path / "alerts.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    get_client = MagicMock()
    monkeypatch.setattr(ingest_script, "get_client", get_client)
    report = tmp_path / "result.json"

    result = ingest_script.main(["--index", "hit", "--input", str(source), "--report", str(report)])

    assert result == 2
    get_client.assert_not_called()
    assert not report.exists()
    preview = json.loads(capsys.readouterr().out)
    assert preview["destination"] == "https://howler.example"
    assert preview["index"] == "hit"
    assert preview["input"] == str(source.resolve())
    assert preview["status"] == "confirmation_required"
    assert preview["confirmation"] == _confirmation("hit", source, report)


def test_mismatched_confirmation_does_not_start_client(tmp_path, monkeypatch, capsys):
    _configure(monkeypatch)
    source = tmp_path / "alerts.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    report = tmp_path / "result.json"
    get_client = MagicMock()
    monkeypatch.setattr(ingest_script, "get_client", get_client)

    result = ingest_script.main(
        [
            "--index",
            "hit",
            "--input",
            str(source),
            "--report",
            str(report),
            "--confirm",
            "stale-confirmation",
        ]
    )

    assert result == 2
    get_client.assert_not_called()
    assert not report.exists()
    assert json.loads(capsys.readouterr().out)["status"] == "confirmation_required"


@pytest.mark.parametrize(
    "api_url",
    [
        "http://howler.example",
        "https://user:secret@howler.example",
        "https://howler.example/?token=secret",
    ],
)
def test_rejects_non_https_or_credential_bearing_url(tmp_path, monkeypatch, capsys, api_url):
    _configure(monkeypatch)
    source = tmp_path / "alerts.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    get_client = MagicMock()
    monkeypatch.setattr(ingest_script, "get_client", get_client)

    assert ingest_script.main(["--api-url", api_url, "--index", "hit"]) == 1

    get_client.assert_not_called()
    captured = capsys.readouterr()
    assert "secret" not in captured.out + captured.err
    assert not (tmp_path / "ingest-report.json").exists()


def test_token_file_takes_precedence_without_exposing_secret(tmp_path, monkeypatch, capsys):
    _configure(monkeypatch, "environment-jwt")
    token_file = tmp_path / "token.txt"
    token_file.write_text("file-jwt-secret\n", encoding="utf-8")
    monkeypatch.setenv("HOWLER_TOKEN_FILE", str(token_file))
    source = tmp_path / "alerts.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    report = tmp_path / "result.json"
    client, _ = _mock_client(["private-id"])
    get_client = MagicMock(return_value=client)
    monkeypatch.setattr(ingest_script, "get_client", get_client)

    assert (
        ingest_script.main(
            [
                "--index",
                "hit",
                "--input",
                str(source),
                "--report",
                str(report),
                "--confirm",
                _confirmation("hit", source, report),
            ]
        )
        == 0
    )

    assert get_client.call_args.kwargs["auth"] == "file-jwt-secret"
    output = capsys.readouterr()
    assert "file-jwt-secret" not in output.out + output.err
    assert "environment-jwt" not in output.out + output.err
    assert "private-id" not in output.out + output.err


def test_refuses_existing_or_input_report_before_network(tmp_path, monkeypatch, capsys):
    _configure(monkeypatch)
    source = tmp_path / "alerts.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    existing = tmp_path / "existing.json"
    existing.write_text("keep", encoding="utf-8")
    get_client = MagicMock()
    monkeypatch.setattr(ingest_script, "get_client", get_client)

    assert (
        ingest_script.main(
            [
                "--index",
                "hit",
                "--input",
                str(source),
                "--report",
                str(existing),
                "--confirm",
                _confirmation("hit", source, existing),
            ]
        )
        == 1
    )
    assert existing.read_text(encoding="utf-8") == "keep"
    assert (
        ingest_script.main(
            [
                "--index",
                "hit",
                "--input",
                str(source),
                "--report",
                str(source),
                "--confirm",
                _confirmation("hit", source, source),
            ]
        )
        == 1
    )
    get_client.assert_not_called()
    assert "keep" not in capsys.readouterr().out

    token_file = tmp_path / "token.txt"
    token_file.write_text("private-token", encoding="utf-8")
    monkeypatch.setenv("HOWLER_TOKEN_FILE", str(token_file))
    assert (
        ingest_script.main(
            [
                "--index",
                "hit",
                "--input",
                str(source),
                "--report",
                str(token_file),
                "--confirm",
                _confirmation("hit", source, token_file),
            ]
        )
        == 1
    )
    assert token_file.read_text(encoding="utf-8") == "private-token"
    get_client.assert_not_called()


def test_report_is_reserved_before_client_network_access(tmp_path, monkeypatch):
    _configure(monkeypatch)
    source = tmp_path / "alerts.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    report = tmp_path / "result.json"
    client, _ = _mock_client(["id"])

    def construct_client(*args, **kwargs):
        assert report.exists()
        assert stat.S_IMODE(report.stat().st_mode) == 0o600
        assert json.loads(report.read_text(encoding="utf-8"))["status"] == "pending"
        assert kwargs["verify"] is True
        return client

    monkeypatch.setattr(ingest_script, "get_client", construct_client)

    assert (
        ingest_script.main(
            [
                "--index",
                "hit",
                "--input",
                str(source),
                "--report",
                str(report),
                "--confirm",
                _confirmation("hit", source, report),
            ]
        )
        == 0
    )


def test_failure_and_unknown_result_are_redacted_and_warn_not_to_rerun(tmp_path, monkeypatch, capsys, caplog):
    _configure(monkeypatch, "super-secret-token")
    source = tmp_path / "alerts.jsonl"
    source.write_text('{"private":"secret-payload"}\n', encoding="utf-8")
    report = tmp_path / "result.json"
    client, ingest = _mock_client(None)
    sdk_logger = logging.getLogger("howler.sdk")
    old_logger_level = sdk_logger.level
    old_logger_disabled = sdk_logger.disabled
    old_disable = logging.root.manager.disable
    sdk_logger.setLevel(logging.DEBUG)
    sdk_logger.disabled = False
    logging.disable(logging.DEBUG - 1)

    def unknown_result(*args, **kwargs):
        assert logging.root.manager.disable == logging.CRITICAL
        sdk_logger.debug("secret-payload super-secret-token")
        raise RuntimeError("secret-payload super-secret-token")

    ingest.from_file.side_effect = unknown_result
    monkeypatch.setattr(ingest_script, "get_client", MagicMock(return_value=client))

    try:
        with caplog.at_level(logging.DEBUG, logger=sdk_logger.name):
            assert (
                ingest_script.main(
                    [
                        "--index",
                        "hit",
                        "--input",
                        str(source),
                        "--report",
                        str(report),
                        "--confirm",
                        _confirmation("hit", source, report),
                    ]
                )
                == 1
            )
        assert logging.root.manager.disable == logging.DEBUG - 1
        assert sdk_logger.level == logging.DEBUG
        assert "secret-payload" not in caplog.text
        assert "super-secret-token" not in caplog.text
    finally:
        sdk_logger.setLevel(old_logger_level)
        sdk_logger.disabled = old_logger_disabled
        logging.disable(old_disable)

    captured = capsys.readouterr()
    assert "secret-payload" not in captured.out + captured.err
    assert "super-secret-token" not in captured.out + captured.err
    assert "manual rerun" in captured.err
    ingest.from_file.assert_called_once_with(str(source.resolve()), index="hit")
    saved = json.loads(report.read_text(encoding="utf-8"))
    assert saved["status"] == "unknown"
    assert saved["outcome_may_be_uncertain"] is True
    assert saved["server_returned_count"] is None
    assert saved["server_returned_ids"] is None


def test_rejects_unrecognized_result_without_logging_result_payload(tmp_path, monkeypatch, capsys):
    _configure(monkeypatch)
    source = tmp_path / "alerts.jsonl"
    source.write_text("{}\n", encoding="utf-8")
    report = tmp_path / "result.json"
    client, ingest = _mock_client({"private": "unknown-response"})
    monkeypatch.setattr(ingest_script, "get_client", MagicMock(return_value=client))

    assert (
        ingest_script.main(
            [
                "--index",
                "hit",
                "--input",
                str(source),
                "--report",
                str(report),
                "--confirm",
                _confirmation("hit", source, report),
            ]
        )
        == 1
    )

    captured = capsys.readouterr()
    assert "unknown-response" not in captured.out + captured.err
    assert json.loads(report.read_text(encoding="utf-8"))["status"] == "unknown"


def test_index_is_required_and_restricted():
    with pytest.raises(SystemExit) as missing:
        ingest_script.main([])
    assert missing.value.code == 2

    with pytest.raises(SystemExit) as unsupported:
        ingest_script.main(["--index", "other"])
    assert unsupported.value.code == 2
