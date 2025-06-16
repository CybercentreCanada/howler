import logging
from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from howler.common.loader import config
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

    conf.modules.odm.modify_odm["hit"] = generate

    PLUGINS["test-plugin"] = conf


def test_odm_mods(caplog):
    with caplog.at_level(logging.INFO):
        HowlerDatastore(ESStore(config=config))

    assert "Modifying hit odm with function from plugin test-plugin" in caplog.text
