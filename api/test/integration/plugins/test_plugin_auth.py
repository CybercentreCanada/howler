import logging
from pathlib import Path
from typing import cast

import pytest
from pydantic_settings import SettingsConfigDict

from howler.app import app
from howler.plugins.config import BasePluginConfig


class HowlerTestPluginConfig(BasePluginConfig):
    model_config = SettingsConfigDict(
        yaml_file=Path(__file__).parent / "test-plugin.yml", yaml_file_encoding="utf-8", strict=True
    )


def mock_get_token(token: str):
    return "access_token"


@pytest.fixture(autouse=True, scope="module")
def mock_plugin():
    from howler.plugins import PLUGINS

    conf = HowlerTestPluginConfig(name="test-plugin")

    PLUGINS["test-plugin"] = conf


def test_auth_hooks(caplog):
    with app.test_request_context():
        from howler.api.v1.clue import get_token

        with caplog.at_level(logging.INFO):
            assert get_token("bad_token") == "bad_token"

        assert "No custom clue token logic provided, continuing with howler credentials" in caplog.text

        caplog.clear()

        from howler.plugins import PLUGINS

        cast(BasePluginConfig, PLUGINS["test-plugin"]).modules.token_functions["clue"] = mock_get_token

        with caplog.at_level(logging.INFO):
            assert get_token("bad_token") == "access_token"

        assert "No custom clue token logic provided, continuing with howler credentials" not in caplog.text
