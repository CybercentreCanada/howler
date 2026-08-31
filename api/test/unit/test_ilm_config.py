"""Unit tests for ILM configuration models."""

from unittest.mock import MagicMock, patch

import pytest
import yaml
from pydantic import ValidationError

from howler.common.exceptions import HowlerAttributeError
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.config import Config, Datastore, ILMConfig, ILMIndexConfig


class TestILMIndexConfig:
    """Tests for per-index ILM phase configuration."""

    def test_defaults(self):
        cfg = ILMIndexConfig()
        assert cfg.enabled is True
        assert cfg.warm is None
        assert cfg.warm_forcemerge_segments == 3  # Default for warm
        assert cfg.cold is None

    def test_disabled(self):
        cfg = ILMIndexConfig(enabled=False)
        assert cfg.enabled is False

    def test_warm_only(self):
        cfg = ILMIndexConfig(warm="30d")
        assert cfg.warm == "30d"
        assert cfg.cold is None

    def test_cold_only(self):
        cfg = ILMIndexConfig(cold="90d")
        assert cfg.warm is None
        assert cfg.cold == "90d"

    def test_both_phases(self):
        cfg = ILMIndexConfig(warm="14d", cold="60d")
        assert cfg.warm == "14d"
        assert cfg.cold == "60d"

    def test_custom_forcemerge_segments(self):
        cfg = ILMIndexConfig(warm="30d", warm_forcemerge_segments=5, cold="90d")
        assert cfg.warm_forcemerge_segments == 5

    def test_skip_forcemerge_with_none(self):
        cfg = ILMIndexConfig(warm="30d", warm_forcemerge_segments=None, cold="90d")
        assert cfg.warm_forcemerge_segments is None


class TestILMConfig:
    """Tests for global ILM configuration."""

    def test_defaults(self):
        cfg = ILMConfig()
        assert cfg.enabled is False
        assert cfg.rollover_max_age == "30d"
        assert cfg.rollover_max_size == "50gb"
        assert cfg.indices == {}

    def test_enabled_with_indices(self):
        cfg = ILMConfig(
            enabled=True,
            rollover_max_age="7d",
            rollover_max_size="25gb",
            indices={
                "hit": ILMIndexConfig(warm="30d", cold="90d"),
                "analytic": ILMIndexConfig(warm="60d"),
            },
        )
        assert cfg.enabled is True
        assert cfg.rollover_max_age == "7d"
        assert cfg.rollover_max_size == "25gb"
        assert "hit" in cfg.indices
        assert cfg.indices["hit"].warm == "30d"
        assert cfg.indices["hit"].cold == "90d"
        assert "analytic" in cfg.indices
        assert cfg.indices["analytic"].cold is None

    def test_index_lookup_miss(self):
        cfg = ILMConfig(enabled=True, indices={"hit": ILMIndexConfig(warm="30d")})
        assert cfg.indices.get("nonexistent") is None

    def test_registration_uses_default_telemetry_ilm_config(self):
        cfg = Config(datastore=Datastore(ilm=ILMConfig(enabled=True)))
        datastore = MagicMock()

        with (
            patch("howler.datastore.howler_store.config", cfg),
            patch("howler.datastore.howler_store.get_plugins", return_value=[]),
        ):
            HowlerDatastore(datastore)

        registered_configs = {call.args[0]: call.kwargs["ilm_config"] for call in datastore.register.call_args_list}
        for call in datastore.register.call_args_list:
            assert call.args[1] is call.kwargs["schema_model"]
        for name in ("hit", "event", "case"):
            assert registered_configs[name] is not None
            assert registered_configs[name].enabled is True
        for name in ("template", "overview", "analytic", "action", "user", "view", "dossier", "user_avatar"):
            assert registered_configs[name] is None

    def test_registration_skips_disabled_indices(self):
        cfg = Config(datastore=Datastore(ilm=ILMConfig(enabled=True)))
        cfg.datastore.ilm.indices["event"] = ILMIndexConfig(enabled=False)
        datastore = MagicMock()

        with (
            patch("howler.datastore.howler_store.config", cfg),
            patch("howler.datastore.howler_store.get_plugins", return_value=[]),
        ):
            HowlerDatastore(datastore)

        registered_configs = {call.args[0]: call.kwargs["ilm_config"] for call in datastore.register.call_args_list}
        for name in ("hit", "case"):
            assert registered_configs[name] is not None
            assert registered_configs[name].enabled is True
        for name in ("event", "template", "overview", "analytic", "action", "user", "view", "dossier", "user_avatar"):
            assert registered_configs[name] is None

    def test_registration_rejects_legacy_only_plugin_model_extensions(self):
        plugin = MagicMock()
        plugin.name = "legacy-plugin"
        plugin.modules.odm.modify_odm = {"hit": MagicMock()}
        plugin.modules.models.declare_extensions = {}

        with patch("howler.datastore.howler_store.get_plugins", return_value=[plugin]):
            with pytest.raises(HowlerAttributeError, match="without matching typed model extensions"):
                HowlerDatastore(MagicMock())


class TestDatastoreILMIntegration:
    """Tests that ILM config is properly nested in Datastore config."""

    def test_datastore_default_ilm(self):
        ds = Datastore()
        assert ds.ilm is not None
        assert ds.ilm.enabled is False
        assert ds.ilm.indices == {}

    def test_datastore_with_ilm(self):
        ds = Datastore(
            ilm=ILMConfig(
                enabled=True,
                indices={"hit": ILMIndexConfig(warm="30d", cold="90d")},
            )
        )
        assert ds.ilm.enabled is True
        assert ds.ilm.indices["hit"].warm == "30d"

    def test_full_config_from_yaml(self):
        yaml_str = """
auth:
  internal:
    enabled: true
datastore:
  ilm:
    enabled: true
    rollover_max_age: "14d"
    rollover_max_size: "30gb"
    indices:
      hit:
        warm: "30d"
        cold: "90d"
      analytic:
        warm: "60d"
logging:
  log_level: INFO
system:
  type: development
"""
        data = yaml.safe_load(yaml_str)
        config = Config.model_validate(data)
        assert config.datastore.ilm.enabled is True
        assert config.datastore.ilm.rollover_max_age == "14d"
        assert config.datastore.ilm.rollover_max_size == "30gb"
        assert config.datastore.ilm.indices["hit"].warm == "30d"
        assert config.datastore.ilm.indices["hit"].cold == "90d"
        assert config.datastore.ilm.indices["analytic"].warm == "60d"
        assert config.datastore.ilm.indices["analytic"].cold is None

    def test_ilm_disabled_by_default_in_full_config(self):
        yaml_str = """
auth:
  internal:
    enabled: true
datastore:
  hosts:
    - name: elastic
      host: localhost:9200
logging:
  log_level: INFO
system:
  type: development
"""
        data = yaml.safe_load(yaml_str)
        config = Config.model_validate(data)
        assert config.datastore.ilm.enabled is False
        assert config.datastore.ilm.indices == {}

    def test_invalid_ilm_config_rejected(self):
        with pytest.raises(ValidationError):
            ILMConfig(enabled="not_a_bool")  # type: ignore
