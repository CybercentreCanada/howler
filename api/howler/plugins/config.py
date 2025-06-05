import logging
from typing import Any

from pydantic import BaseModel, ImportString, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, YamlConfigSettingsSource

from howler.common.logging import HWL_DATE_FORMAT, HWL_LOG_FORMAT

logger = logging.getLogger("howler.odm.models.config")
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
logger.addHandler(console)


class ODMModules(BaseModel):
    "A set of fields for adding additional fields to Howler's ODM."

    modify_odm: dict[str, ImportString] = {}
    generation: dict[str, ImportString] = {}


class Modules(BaseModel):
    "A list of components exposed for use in Howler by this plugin."

    routes: list[ImportString] = []
    operations: list[ImportString] = []
    token_functions: dict[str, ImportString] = {}

    odm: ODMModules = ODMModules()


class BasePluginConfig(BaseSettings):
    "Configuration File for Plugin"

    name: str
    features: dict[str, bool] = {}

    modules: Modules = Modules()

    @model_validator(mode="before")
    @classmethod
    def initialize_plugin_configuration(cls, data: Any) -> Any:  # noqa: C901
        "Convert a raw yaml config into an object ready for validation by pydantic"
        if not isinstance(data, dict):
            return data

        # Default mutation requires plugin name
        if "name" not in data:
            logger.warning("Name is missing from configuration")
            return data

        plugin_name = data["name"]
        logger.debug("Beginning configuration parsing for plugin %s", plugin_name)

        if "modules" not in data:
            return data

        if "routes" in data["modules"] and isinstance(data["modules"]["routes"], list):
            new_routes: list[str] = []
            for route in data["modules"]["routes"]:
                new_routes.append(f"{plugin_name}.routes.{route}" if "." not in route else route)

            data["modules"]["routes"] = new_routes

        if "operations" in data["modules"] and isinstance(data["modules"]["operations"], list):
            new_operations: list[str] = []
            for operation in data["modules"]["operations"]:
                new_operations.append(f"{plugin_name}.actions.{operation}" if "." not in operation else operation)

            data["modules"]["operations"] = new_operations

        if "token_functions" in data["modules"] and isinstance(data["modules"]["token_functions"], dict):
            for application, value in data["modules"]["token_functions"].items():
                if value == True:  # noqa: E712
                    data["modules"]["token_functions"][application] = f"{plugin_name}.token.{value}:get_token"

        if "odm" not in data["modules"] or not isinstance(data["modules"]["odm"], dict):
            return data

        if "modify_odm" in data["modules"]["odm"] and isinstance(data["modules"]["odm"]["modify_odm"], dict):
            for odm_name, value in data["modules"]["odm"]["modify_odm"].items():
                if data["modules"]["odm"]["modify_odm"][odm_name] == True:  # noqa: E712
                    data["modules"]["odm"]["modify_odm"][odm_name] = f"{plugin_name}.odm.{odm_name}:modify_odm"

        if "generation" in data["modules"]["odm"] and isinstance(data["modules"]["odm"]["generation"], dict):
            for odm_name, value in data["modules"]["odm"]["generation"].items():
                if data["modules"]["odm"]["generation"][odm_name] == True:  # noqa: E712
                    data["modules"]["odm"]["generation"][odm_name] = f"{plugin_name}.odm.{odm_name}:generate"

        return data

    @classmethod
    def settings_customise_sources(
        cls,  # noqa: ANN102
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN002, ANN102
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        "Adds a YamlConfigSettingsSource object at the end of the settings_customize_sources response."
        return (*super().settings_customise_sources(*args, **kwargs), YamlConfigSettingsSource(cls))
