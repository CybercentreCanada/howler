import logging
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from howler.config import config
from howler.datastore.howler_store import HowlerDatastore
from howler.datastore.store import ESStore
from howler.plugins.config import BasePluginConfig


class HowlerTestPluginConfig(BasePluginConfig):
    model_config = SettingsConfigDict(
        yaml_file=Path(__file__).parent / "test-plugin.yml", yaml_file_encoding="utf-8", strict=True
    )


def generate(hit):
    "Add cccs-specific changes to hits on generation"
    return [], hit


@pytest.fixture(autouse=True, scope="module")
def mock_plugin():
    from howler.plugins import PLUGINS

    conf = HowlerTestPluginConfig(name="test-plugin")

    conf.modules.models.declare_extensions["hit"] = lambda: None

    PLUGINS["test-plugin"] = conf
    yield
    PLUGINS.pop("test-plugin", None)


def test_typed_extension_declaration(caplog):
    with caplog.at_level(logging.INFO):
        HowlerDatastore(ESStore(config=config))

    assert "Declaring hit model extension with function from plugin test-plugin" in caplog.text
