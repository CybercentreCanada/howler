# mypy: ignore-errors
import os
from pathlib import Path

from howler import config as howler_config
from howler.plugins.config import BasePluginConfig
from pydantic_settings import SettingsConfigDict

from tsx_user_status.constants import KEY_PREFIX, SHIFT_KEY_PREFIX
from tsx_user_status.services import UserStatusService

APP_NAME = os.environ.get("APP_NAME", "howler")
PLUGIN_NAME = "tsx_user_status"

root_path = Path("/etc") / APP_NAME.replace("-dev", "").replace("-stg", "")

config_locations = [
    Path(__file__).parent / "manifest.yml",
    root_path / "conf" / f"{PLUGIN_NAME}.yml",
    Path(os.environ.get("HWL_CONF_FOLDER", root_path)) / f"{PLUGIN_NAME}.yml",
]


class TSXUserStatusPluginConfig(BasePluginConfig):
    """tsx_user_status Plugin Configuration Model.

    Attributes:
        key_prefix: Redis key prefix for per-user status values. Defaults to
            ``"tsx_user_status:status"``.
        shift_key_prefix: Redis key prefix for per-user schedule/team values.
            Defaults to ``"tsx_user_status:shift"``.
        schedules_account: Azure Storage account name for the schedules blob.
        schedules_container: Container name within the schedules storage account.
        schedules_blob: Blob name containing schedule data.
        schedules_key: Access key for the schedules storage account.
        schedules_cache_key: Redis key under which the cached schedules JSON
            payload is stored. Defaults to ``"tsx_user_status:schedules"``.
        schedules_cache_ttl: TTL (in seconds) for the cached schedules in Redis.
            Defaults to 18000 (5 hours).
    """

    key_prefix: str = KEY_PREFIX
    shift_key_prefix: str = SHIFT_KEY_PREFIX
    schedules_account: str = ""
    schedules_container: str = ""
    schedules_blob: str = ""
    schedules_key: str = ""
    schedules_cache_key: str = "tsx_user_status:schedules"
    schedules_cache_ttl: int = 18000

    model_config = SettingsConfigDict(
        yaml_file=config_locations,
        yaml_file_encoding="utf-8",
        strict=True,
        env_nested_delimiter="__",
        env_prefix=f"{PLUGIN_NAME.upper()}_",
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


config = TSXUserStatusPluginConfig()
status_service = UserStatusService(howler_config.redis_persistent)
