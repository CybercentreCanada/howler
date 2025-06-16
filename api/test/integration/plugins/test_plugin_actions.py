import importlib
from pathlib import Path
from typing import cast

import pytest
from pydantic_settings import SettingsConfigDict

from howler.datastore.howler_store import HowlerDatastore
from howler.plugins.config import BasePluginConfig


class HowlerTestPluginConfig(BasePluginConfig):
    model_config = SettingsConfigDict(
        yaml_file=Path(__file__).parent / "test-plugin.yml", yaml_file_encoding="utf-8", strict=True
    )


@pytest.fixture(autouse=True, scope="module")
def mock_plugin():
    from howler.plugins import PLUGINS

    PLUGINS["test-plugin"] = HowlerTestPluginConfig(name="test-plugin")


def test_plugin_actions_integration(datastore_connection: HowlerDatastore):
    from howler.actions import execute, specifications

    user = datastore_connection.user.search("uname:admin")["items"][0]

    assert all(spec["id"] != "test-plugin-execute" for spec in specifications())

    result = execute("test-plugin-execute", "howler.id:*", user=user)

    assert result[0]["outcome"] == "error"
    assert (
        result[0]["message"] == "The operation ID provided (test-plugin-execute) does not match any enabled operations."
    )

    from howler.plugins import PLUGINS

    cast(BasePluginConfig, PLUGINS["test-plugin"]).modules.operations.append(
        importlib.import_module("utils.plugins.example_action")
    )

    assert any(spec["id"] == "test-plugin-execute" for spec in specifications())
    result = execute("test-plugin-execute", "howler.id:*", user=user)

    assert result[0]["outcome"] == "success"
    assert result[0]["message"] == "Example action ran successfully."

    cast(BasePluginConfig, PLUGINS["test-plugin"]).modules.operations = []
