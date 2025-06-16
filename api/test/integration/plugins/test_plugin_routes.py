import importlib
import logging
from pathlib import Path

import pytest
import werkzeug
from pydantic_settings import SettingsConfigDict

from howler.plugins.config import BasePluginConfig

# No clue why this is necessary
werkzeug.__version__ = "1.0.0"  # type: ignore


class HowlerTestPluginConfig(BasePluginConfig):
    model_config = SettingsConfigDict(
        yaml_file=Path(__file__).parent / "test-plugin.yml", yaml_file_encoding="utf-8", strict=True
    )


@pytest.fixture(autouse=True, scope="module")
def mock_plugin():
    from howler.plugins import PLUGINS

    conf = HowlerTestPluginConfig(name="test-plugin")

    conf.modules.routes.append(importlib.import_module("utils.plugins.example_route").example_route)

    PLUGINS["test-plugin"] = conf


def test_route_hook(caplog):
    with caplog.at_level(logging.INFO):
        app = importlib.import_module("howler.app")
        importlib.reload(app)

    assert "Enabling additional endpoint: /api/v1/test" in caplog.text

    client = app.app.test_client()
    assert client.get("/api/v1/test/example").json["api_response"] == {"success": True}
