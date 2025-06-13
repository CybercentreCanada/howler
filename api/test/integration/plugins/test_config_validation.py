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
