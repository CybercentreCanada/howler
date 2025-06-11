# mypy: ignore-errors
import os
from pathlib import Path
from typing import Optional

from howler.plugins.config import BasePluginConfig
from pydantic import BaseModel, ImportString
from pydantic_settings import SettingsConfigDict

APP_NAME = os.environ.get("APP_NAME", "howler")
PLUGIN_NAME = "sentinel"

root_path = Path("/etc") / APP_NAME.replace("-dev", "").replace("-stg", "")

config_locations = [
    Path(__file__).parent / "manifest.yml",
    root_path / "conf" / f"{PLUGIN_NAME}.yml",
    Path(os.environ.get("HWL_CONF_FOLDER", root_path)) / f"{PLUGIN_NAME}.yml",
]


class ClientCredentials(BaseModel):
    "OAuth2 credentials for client_credential OAuth2 Flow"

    client_id: str
    client_secret: str


class Auth(BaseModel):
    "Configuration for the various authentication methods, both to azure and incoming requests."

    link_key: str = "abcdefghijklmnopqrstuvwxyz1234567890"

    client_credentials: Optional[ClientCredentials] = None

    custom_auth: Optional[ImportString] = None


class Ingestor(BaseModel):
    "Defines necessary data to ingest howler alerts into a specific azure tenancy"

    tenant_id: str
    dce: str
    dcr: str
    table: str


class SentinelConfig(BasePluginConfig):
    "Sentinel Plugin Configuration Model"

    auth: Auth = Auth()

    ingestors: list[Ingestor] = []

    model_config = SettingsConfigDict(
        yaml_file=config_locations,
        yaml_file_encoding="utf-8",
        strict=True,
        env_nested_delimiter="__",
        env_prefix=f"{PLUGIN_NAME.upper()}_",
    )


config = SentinelConfig()

if __name__ == "__main__":
    # When executed, the config model will print the default values of the configuration
    import yaml

    print(yaml.safe_dump(SentinelConfig().model_dump(mode="json")))  # noqa: T201
