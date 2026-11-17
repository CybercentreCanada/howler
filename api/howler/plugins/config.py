import logging
from typing import Any

from pydantic import BaseModel, ImportString, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, YamlConfigSettingsSource

from howler.common.logging import HWL_DATE_FORMAT, HWL_LOG_FORMAT

logger = logging.getLogger("howler.plugins.config")
logger.setLevel(logging.INFO)
console = logging.StreamHandler()
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(HWL_LOG_FORMAT, HWL_DATE_FORMAT))
logger.addHandler(console)


def _expand_module_map(values: dict[str, Any], namespace: str, function: str) -> dict[str, str]:
    return {
        name: f"{namespace}.{name}:{function.format(name=name)}" if value is True else value
        for name, value in values.items()
        if value is not False
    }


class ODMModules(BaseModel):
    "A set of fields for adding additional fields to Howler's ODM."

    modify_odm: dict[str, str | bool] = {}
    generation: dict[str, ImportString] = {}


class ModelModules(BaseModel):
    """A set of fields for declaring new Pydantic/DSL model extensions for this plugin.

    This is the typed declaration hook for the new ``howler.models.extensions`` startup
    registry, replacing the removed post-definition ``add_namespace``/``remove_namespace``
    mutation pattern. Each entry names a target model (e.g. ``hit``) whose declaration hook
    (conventionally ``declare_{target}_extension``) is called once during datastore startup,
    before the target model is finalized.
    """

    declare_extensions: dict[str, ImportString] = {}


class Modules(BaseModel):
    "A list of components exposed for use in Howler by this plugin."

    routes: list[ImportString] = []
    operations: list[ImportString] = []
    token_functions: dict[str, ImportString] = {}

    odm: ODMModules = ODMModules()
    models: ModelModules = ModelModules()


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
            data["modules"]["token_functions"] = _expand_module_map(
                data["modules"]["token_functions"], f"{plugin_name}.token", "get_token"
            )

        if "odm" in data["modules"] and isinstance(data["modules"]["odm"], dict):
            if "modify_odm" in data["modules"]["odm"] and isinstance(data["modules"]["odm"]["modify_odm"], dict):
                data["modules"]["odm"]["modify_odm"] = {
                    name: value for name, value in data["modules"]["odm"]["modify_odm"].items() if value is not False
                }

            if "generation" in data["modules"]["odm"] and isinstance(data["modules"]["odm"]["generation"], dict):
                data["modules"]["odm"]["generation"] = _expand_module_map(
                    data["modules"]["odm"]["generation"], f"{plugin_name}.odm", "generate"
                )

        if "models" in data["modules"] and isinstance(data["modules"]["models"], dict):
            models_data = data["modules"]["models"]
            if "declare_extensions" in models_data and isinstance(models_data["declare_extensions"], dict):
                models_data["declare_extensions"] = _expand_module_map(
                    models_data["declare_extensions"],
                    f"{plugin_name}.models",
                    "declare_{name}_extension",
                )

        return data

    @classmethod
    def settings_customise_sources(
        cls,  # noqa: ANN102
        *args,  # noqa: ANN002
        **kwargs,  # noqa: ANN002, ANN102
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        "Adds a YamlConfigSettingsSource object at the end of the settings_customize_sources response."
        return (*super().settings_customise_sources(*args, **kwargs), YamlConfigSettingsSource(cls))
