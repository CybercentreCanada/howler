import os
from pathlib import Path

from howler.plugins.config import BasePluginConfig
from pydantic_settings import SettingsConfigDict

APP_NAME = os.environ.get("APP_NAME", "howler")
PLUGIN_NAME = "iceberg"

root_path = Path("/etc") / APP_NAME.replace("-dev", "").replace("-stg", "")

config_locations = [
    Path(__file__).parent / "manifest.yml",
    root_path / "conf" / f"{PLUGIN_NAME}.yml",
    Path(os.environ.get("HWL_CONF_FOLDER", root_path)) / f"{PLUGIN_NAME}.yml",
]


class IcebergConfig(BasePluginConfig):
    "Iceberg Plugin Configuration Model"

    name: str = PLUGIN_NAME

    model_config = SettingsConfigDict(
        yaml_file=config_locations,
        yaml_file_encoding="utf-8",
        strict=True,
        env_nested_delimiter="__",
        env_prefix=f"{PLUGIN_NAME.upper()}_",
    )


config = IcebergConfig()

if __name__ == "__main__":
    # When executed, the config model will print the default values of the configuration
    import yaml

    print(yaml.safe_dump(IcebergConfig().model_dump(mode="json")))  # noqa: T201
