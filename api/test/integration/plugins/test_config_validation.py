import logging

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict

from howler.plugins.config import BasePluginConfig, Modules


class CustomTestConfig(BasePluginConfig):
    model_config = SettingsConfigDict(strict=True, env_prefix="TEST_TEST_TEST")


def test_validation(caplog):
    with pytest.raises(ValidationError):
        CustomTestConfig.model_validate("not a dict")

    with pytest.raises(ValidationError), caplog.at_level(logging.WARNING):
        CustomTestConfig.model_validate({})

    assert "Name is missing from configuration" in caplog.text

    assert CustomTestConfig.model_validate({"name": "test"}).modules == Modules()

    result = CustomTestConfig.initialize_plugin_configuration(  # type: ignore[operator]
        {"name": "test", "modules": {"routes": ["example", "custom.module.example"]}}
    )

    assert result["modules"]["routes"][0] == "test.routes.example"
    assert result["modules"]["routes"][1] == "custom.module.example"

    result = CustomTestConfig.initialize_plugin_configuration(  # type: ignore[operator]
        {"name": "test", "modules": {"operations": ["example", "custom.module.example"]}}
    )

    assert result["modules"]["operations"][0] == "test.actions.example"
    assert result["modules"]["operations"][1] == "custom.module.example"

    result = CustomTestConfig.initialize_plugin_configuration(  # type: ignore[operator]
        {
            "name": "test",
            "modules": {"token_functions": {"borealis": True, "other": "custom.module.example", "false": False}},
        }
    )

    assert result["modules"]["token_functions"]["borealis"] == "test.token.borealis:get_token"
    assert result["modules"]["token_functions"]["other"] == "custom.module.example"
    assert "false" not in result["modules"]["token_functions"]

    assert {"name": "test", "modules": {"odm": True}} == CustomTestConfig.initialize_plugin_configuration(  # type: ignore[operator]
        {"name": "test", "modules": {"odm": True}}
    )

    result = CustomTestConfig.initialize_plugin_configuration(  # type: ignore[operator]
        {
            "name": "test",
            "modules": {"odm": {"modify_odm": {"hit": True, "user": "custom.module.example", "dossier": False}}},
        }
    )

    assert result["modules"]["odm"]["modify_odm"]["hit"] == "test.odm.hit:modify_odm"
    assert result["modules"]["odm"]["modify_odm"]["user"] == "custom.module.example"
    assert "dossier" not in result["modules"]["odm"]["modify_odm"]

    result = CustomTestConfig.initialize_plugin_configuration(  # type: ignore[operator]
        {
            "name": "test",
            "modules": {"odm": {"generation": {"hit": True, "user": "custom.module.example", "dossier": False}}},
        }
    )

    assert result["modules"]["odm"]["generation"]["hit"] == "test.odm.hit:generate"
    assert result["modules"]["odm"]["generation"]["user"] == "custom.module.example"
    assert "dossier" not in result["modules"]["odm"]["generation"]
