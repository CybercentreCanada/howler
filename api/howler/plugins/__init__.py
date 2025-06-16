import importlib
from typing import Optional

from howler.common.logging import get_logger
from howler.config import config as _config  # Python gets BIG mad if we don't alias this
from howler.plugins.config import BasePluginConfig

logger = get_logger(__file__)

PLUGINS: dict[str, Optional[BasePluginConfig]] = {}


def get_plugins() -> list[BasePluginConfig]:
    "Get a set of plugin configurations based on the howler settings."
    for plugin in _config.core.plugins:
        if plugin in PLUGINS:
            continue

        try:
            PLUGINS[plugin] = importlib.import_module(f"{plugin}.config").config
        except (ImportError, ModuleNotFoundError):
            logger.exception("Exception when loading plugin %s", plugin)
            PLUGINS[plugin] = None

    return [plugin for plugin in PLUGINS.values() if plugin]
