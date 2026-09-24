import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from howler.config_models import Config

yml_config_good = Path(__file__).parent / "config.yml"
yml_config_good_mapping = Path(__file__).parent / "mappings.yml"
yml_config_bad = Path(__file__).parent / "config-broken.yml"
yml_config_bad_mapping = Path(__file__).parent / "config-broken-mappings.yml"


def test_builtin_config():
    from howler.config import config

    assert config.auth


def test_config_models_cold_import_does_not_load_legacy_odm():
    """Configuration must import in a fresh process without a loader cycle or ODM dependency."""
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from howler.config_models import Config, config; "
            "assert isinstance(config, Config); "
            "assert not any(k == 'howler.odm' or k.startswith('howler.odm.') for k in sys.modules)",
        ],
        check=True,
    )


def test_legacy_config_import_reexports_application_singleton():
    from howler.config_models import Config as ApplicationConfig
    from howler.config_models import config as application_config
    from howler.odm.models.config import config as legacy_config

    assert Config is ApplicationConfig
    assert legacy_config is application_config


def test_builtin_config_mapping():
    from howler.config import config

    assert isinstance(config.mapping, dict)


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
