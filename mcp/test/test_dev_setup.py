import importlib
import json
import subprocess

dev_setup = importlib.import_module("dev.dev_setup")


def test_dev_credentials_match_seeded_keycloak_user():
    # api/dev/keycloak/keycloak-realm.json seeds "goose"/"goose"; using any
    # other value here silently breaks --token/--start with a 401.
    assert dev_setup._TEST_USER == "goose"
    assert dev_setup._TEST_PASS == "goose"


def test_update_mcp_json_preserves_existing_configuration(tmp_path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text(
        json.dumps(
            {
                "servers": {
                    "other": {"url": "http://example.test"},
                    "howlerMcp": {"url": "http://old.example/mcp"},
                },
                "inputs": ["existing"],
            }
        )
    )

    dev_setup.update_mcp_json("new-token", mcp_json_path=config_path)
    config = json.loads(config_path.read_text())

    assert config["servers"]["other"] == {"url": "http://example.test"}
    assert config["inputs"] == ["existing"]
    assert config["servers"]["howlerMcp"]["headers"]["Authorization"] == "Bearer new-token"


def test_update_mcp_json_starts_fresh_on_invalid_json(tmp_path):
    config_path = tmp_path / "mcp.json"
    config_path.write_text("not json")

    dev_setup.update_mcp_json("new-token", mcp_json_path=config_path)
    config = json.loads(config_path.read_text())

    assert config["servers"]["howlerMcp"]["headers"]["Authorization"] == "Bearer new-token"


def test_clear_port_only_targets_the_mcp_service(monkeypatch):
    monkeypatch.setattr(dev_setup, "_find_executable", lambda name: name)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[1:5] == ["compose", "--profile", "full", "ps"]:
            return subprocess.CompletedProcess(command, 0, stdout="howler-mcp\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dev_setup.subprocess, "run", run)
    dev_setup.clear_port(8000)

    docker_calls = [call for call in calls if call[0] == "docker"]
    assert docker_calls[-1] == ["docker", "compose", "--profile", "full", "stop", "howler-mcp"]
    # Never reference dependency services; clear_port must not touch them.
    assert not any(
        service in call for call in calls for service in ("elasticsearch", "redis", "keycloak", "howler-api")
    )


def test_clear_port_does_not_stop_compose_when_mcp_service_not_running(monkeypatch):
    monkeypatch.setattr(dev_setup, "_find_executable", lambda name: name)
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(dev_setup.subprocess, "run", run)
    dev_setup.clear_port(8000)

    assert not any(call[0] == "docker" and "stop" in call for call in calls)
