import logging
from pathlib import Path

from pydantic_settings import SettingsConfigDict

from howler.plugins import BasePluginConfig


class HowlerTestPluginConfig(BasePluginConfig):
    model_config = SettingsConfigDict(
        yaml_file=Path(__file__).parent / "test-plugin.yml", yaml_file_encoding="utf-8", strict=True
    )


def test_get_plugins(caplog):
    from howler.plugins import _config, get_plugins

    assert len(get_plugins()) == 0

    _config.core.plugins.add("no-existy")

    with caplog.at_level(logging.ERROR):
        assert len(get_plugins()) == 0

    assert "Exception when loading plugin no-existy" in caplog.text

    from howler.plugins import PLUGINS

    assert "no-existy" in PLUGINS

    _config.core.plugins.add("test-plugin")

    PLUGINS["test-plugin"] = HowlerTestPluginConfig(name="test-plugin")

    assert len(get_plugins()) == 1

    del PLUGINS["test-plugin"]

    _config.core.plugins.remove("no-existy")
    _config.core.plugins.remove("test-plugin")
