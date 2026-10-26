import json
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from sentinel.config import SentinelConfig


def _config_with_yaml(yaml_path: Path) -> type[SentinelConfig]:
    class YamlSentinelConfig(SentinelConfig):
        model_config = SettingsConfigDict(**{**SentinelConfig.model_config, "env_file": None, "yaml_file": yaml_path})

    return YamlSentinelConfig


def test_tenant_mapping_defaults_to_independent_empty_dicts(monkeypatch):
    monkeypatch.delenv("SENTINEL_TENANT_MAPPING", raising=False)

    first = SentinelConfig(_env_file=None)
    second = SentinelConfig(_env_file=None)

    assert first.tenant_mapping == {}
    assert second.tenant_mapping == {}
    first.tenant_mapping["tenant-a"] = "Example Organization"
    assert second.tenant_mapping == {}


def test_tenant_mapping_loads_from_yaml(tmp_path, monkeypatch):
    monkeypatch.delenv("SENTINEL_TENANT_MAPPING", raising=False)
    yaml_path = tmp_path / "sentinel.yml"
    yaml_path.write_text('name: sentinel\ntenant_mapping:\n  "tenant-a": "Example Organization"\n', encoding="utf-8")

    config = _config_with_yaml(yaml_path)(_env_file=None)

    assert config.tenant_mapping == {"tenant-a": "Example Organization"}


def test_tenant_mapping_loads_from_environment(monkeypatch):
    mapping = {"tenant-a": "Example Organization", "tenant-b": "Second Organization"}
    monkeypatch.setenv("SENTINEL_TENANT_MAPPING", json.dumps(mapping))

    config = SentinelConfig(_env_file=None)

    assert config.tenant_mapping == mapping


@pytest.mark.parametrize(
    "tenant_mapping",
    [
        pytest.param('{"tenant-a": 7}', id="non-string-environment-value"),
        pytest.param('{"tenant-a": true}', id="boolean-environment-value"),
    ],
)
def test_tenant_mapping_environment_values_must_be_strings(monkeypatch, tenant_mapping):
    monkeypatch.setenv("SENTINEL_TENANT_MAPPING", tenant_mapping)

    with pytest.raises(ValidationError):
        SentinelConfig(_env_file=None)


@pytest.mark.parametrize(
    "mapping_line",
    [
        pytest.param('  123: "Example Organization"', id="non-string-key"),
        pytest.param("  tenant-a: 123", id="non-string-value"),
    ],
)
def test_tenant_mapping_yaml_keys_and_values_must_be_strings(tmp_path, monkeypatch, mapping_line):
    monkeypatch.delenv("SENTINEL_TENANT_MAPPING", raising=False)
    yaml_path = tmp_path / "sentinel.yml"
    yaml_path.write_text(f"name: sentinel\ntenant_mapping:\n{mapping_line}\n", encoding="utf-8")

    with pytest.raises(ValidationError):
        _config_with_yaml(yaml_path)(_env_file=None)
