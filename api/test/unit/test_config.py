from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from howler.odm.models.config import Config

yml_config_good = Path(__file__).parent / "config.yml"
yml_config_good_mapping = Path(__file__).parent / "mappings.yml"
yml_config_bad = Path(__file__).parent / "config-broken.yml"
yml_config_bad_mapping = Path(__file__).parent / "config-broken-mappings.yml"


def test_builtin_config():
    from howler.config import config

    assert config.auth

def test_builtin_config_mapping():
    from howler.config import config

    assert config.mapping


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
