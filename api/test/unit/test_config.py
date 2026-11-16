from pathlib import Path

import pytest
import yaml
from pydantic import ImportString, ValidationError

from howler.config_models import Config, System
from howler.plugins.config import BasePluginConfig, ModelModules

yml_config_good = Path(__file__).parent / "config.yml"
yml_config_good_mapping = Path(__file__).parent / "mappings.yml"
yml_config_bad = Path(__file__).parent / "config-broken.yml"
yml_config_bad_mapping = Path(__file__).parent / "config-broken-mappings.yml"


def test_builtin_config():
    from howler.config import config

    assert config.auth


def test_application_config_is_the_config_models_singleton():
    from howler.config_models import Config as ApplicationConfig
    from howler.config_models import config as application_config

    assert Config is ApplicationConfig
    assert isinstance(application_config, ApplicationConfig)


def test_builtin_config_mapping():
    from howler.config import config

    assert isinstance(config.mapping, dict)


def test_encryption_key_requires_32_bytes():
    secret_key = "0123456789abcdef0123456789abcdef"

    assert System(encryption_key=secret_key).encryption_key == secret_key
    with pytest.raises(ValidationError, match="exactly 32 bytes"):
        System(encryption_key="too-short")


def test_custom_config():
    with yml_config_good.open() as _yaml:
        _conf = yaml.safe_load(_yaml)

    config = Config.model_validate(_conf)

    assert config.auth.oauth.enabled


def test_custom_config_mapping():
    with yml_config_good_mapping.open() as _yaml:
        _conf = yaml.safe_load(_yaml)

    config = Config.model_validate(_conf)

    assert config.mapping


def test_custom_bad_config():
    with pytest.raises(ValidationError) as err:
        with yml_config_bad.open() as _yaml:
            _conf = yaml.safe_load(_yaml)

        Config.model_validate(_conf)

    assert "random-key" in str(err)


def test_custom_bad_config_mapping():
    with pytest.raises(ValidationError) as err:
        with yml_config_bad_mapping.open() as _yaml:
            _conf = yaml.safe_load(_yaml)

        Config.model_validate(_conf)

    assert "random-key" in str(err)


_FAKE_PLUGIN = "_howler_test_nonexistent_plugin_"


@pytest.mark.parametrize(
    ("target", "expected_path"),
    [
        ("hit", f"{_FAKE_PLUGIN}.models.hit:declare_hit_extension"),
        ("clue", f"{_FAKE_PLUGIN}.models.clue:declare_clue_extension"),
    ],
)
def test_extension_shorthand_resolves_to_conventional_import_path(target: str, expected_path: str):
    manifest = {"name": _FAKE_PLUGIN, "modules": {"models": {"declare_extensions": {target: True}}}}

    with pytest.raises(ValidationError) as error:
        BasePluginConfig.model_validate(manifest)

    assert error.value.errors()[0]["input"] == expected_path


def test_extension_manifest_preserves_explicit_import_path():
    import_path = f"{_FAKE_PLUGIN}.custom.path:custom_declare"
    manifest = {"name": _FAKE_PLUGIN, "modules": {"models": {"declare_extensions": {"hit": import_path}}}}

    with pytest.raises(ValidationError) as error:
        BasePluginConfig.model_validate(manifest)

    assert error.value.errors()[0]["input"] == import_path


def test_extension_manifest_can_disable_a_target():
    config = BasePluginConfig.model_validate(
        {"name": _FAKE_PLUGIN, "modules": {"models": {"declare_extensions": {"hit": False}}}}
    )

    assert config.modules.models.declare_extensions == {}


def test_plugin_without_model_extensions_uses_an_empty_declaration_map():
    config = BasePluginConfig.model_validate({"name": _FAKE_PLUGIN, "modules": {}})

    assert config.modules.models.declare_extensions == {}


def test_model_extension_declarations_use_import_strings():
    assert ModelModules.model_fields["declare_extensions"].annotation == dict[str, ImportString]
