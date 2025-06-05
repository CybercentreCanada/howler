# mypy: ignore-errors
import os
from pathlib import Path

from howler.plugins.config import BasePluginConfig
from pydantic_settings import SettingsConfigDict

APP_NAME = os.environ.get("APP_NAME", "howler")
PLUGIN_NAME = "evidence"

root_path = Path("/etc") / APP_NAME.replace("-dev", "").replace("-stg", "")

config_locations = [
    Path(__file__).parent / "manifest.yml",
    root_path / "conf" / f"{PLUGIN_NAME}.yml",
    Path(os.environ.get("HWL_CONF_FOLDER", root_path)) / f"{PLUGIN_NAME}.yml",
]


class EvidenceConfig(BasePluginConfig):
    "Evidence Plugin Configuration Model"

    model_config = SettingsConfigDict(
        yaml_file=config_locations,
        yaml_file_encoding="utf-8",
        strict=True,
        env_nested_delimiter="__",
        env_prefix=f"{PLUGIN_NAME}_",
    )


config = EvidenceConfig()

if __name__ == "__main__":
    # When executed, the config model will print the default values of the configuration
    import yaml

    print(yaml.safe_dump(EvidenceConfig().model_dump(mode="json")))  # noqa: T201
