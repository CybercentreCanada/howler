import importlib
import inspect
import textwrap
from pathlib import Path
from types import NoneType
from typing import get_args, get_origin

import yaml
from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict

import howler.odm.base as base
from howler import odm
from howler.odm.models.config import Config

root_dir = Path(__file__).parent.parent.parent
odm_path = root_dir / "api/howler/odm/models"

MODELS_TO_EXPORT = [
    "howler.odm.models.hit",
    "howler.odm.models.aws",
    "howler.odm.models.azure",
    "howler.odm.models.cbs",
    "howler.odm.models.gcp",
    "howler.odm.models.howler_data",
    *list(
        str(_file.relative_to(root_dir / "api")).replace(".py", "").replace("/", ".")
        for _file in (odm_path / "ecs").rglob("*.py")
        if _file.stem != "__init__"
    ),
]


intro_data = """
    # Howler ODM Documentation

    ??? success "Auto-Generated Documentation"
        This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

    This section of the site is useful for deciding what fields to place your raw data in when ingesting into Howler.

    ## Basic Field Types

    Here is a table of the basic types of fields in our data models and what they're used for:

    |Name|Description|
    |:---|:----------|
"""  # noqa: E501

for class_name, _class in inspect.getmembers(
    base,
    lambda _member: inspect.isclass(_member) and issubclass(_member, base._Field),
):
    if not _class.__doc__:
        continue

    newline = "\n"
    intro_data += f"    | `{class_name}` | {_class.__doc__.strip().split(newline)[0]} |\n"

intro_data += """
    ## Field States

    In each table, there will be a "Required" column with different states about the field's status:

    |State|Description|
    |:---|:----------|
    |:material-checkbox-marked-outline: Yes|This field is required to be set in the model|
    |:material-minus-box-outline: Optional|This field isn't required to be set in the model|
    |:material-alert-box-outline: Deprecated|This field has been deprecated in the model. See field's description for more details.|

    __Note__: Fields that are ":material-alert-box-outline: Deprecated" that are still shown in the docs will still work as expected but you're encouraged to update your configuration as soon as possible to avoid future deployment issues.
    """  # noqa: E501

(root_dir / "documentation/docs/odm/getting_started.md").write_text(textwrap.dedent(intro_data).strip() + "\n")


def get_type_name(annotation):
    """Extract the type name from an annotation, handling Optional types."""
    if annotation is None:
        return "None"

    # Check if it's a Union type (including Optional which is Union[T, None])
    origin = get_origin(annotation)
    if origin is not None:  # This handles Union, Optional, etc.
        if NoneType in get_args(annotation):
            return " | ".join(get_type_name(arg) for arg in get_args(annotation) if arg is not NoneType)
        return f"{origin.__name__}[{', '.join(get_type_name(arg) for arg in get_args(annotation))}]"

    # Return the type name
    if hasattr(annotation, "__name__"):
        return annotation.__name__

    return str(annotation)


def build_docs_for_model(model: type[BaseModel], parent_key: str | None = None):
    doc_string = f"""
    # {model.__name__}

    {(model.__doc__ or "No description provided.").strip()}

    | Field | Type | Description | Required | Default |
    | :--- | :--- | :--- | :--- | :--- |\n"""

    submodels: dict[str, type[BaseModel]] = {}
    for key, fieldinfo in model.model_fields.items():
        # Get the actual type, handling Optional
        annotation = fieldinfo.annotation

        # Check if the actual type is a BaseModel subclass
        if annotation and inspect.isclass(annotation) and issubclass(annotation, BaseModel):
            doc_string = doc_string + (
                "    "
                f"| `{key}` | [`{annotation.__name__}`](#{annotation.__name__.lower()}) | "
                f"{(annotation.__doc__ or "None").replace("\n", " ")} | "
                f":material-checkbox-marked-outline: Yes | See [{annotation.__name__}]"
                f"(#{annotation.__name__.lower()}) for details. |\n"
            )
            submodels[key if parent_key is None else f"{parent_key}.{key}"] = annotation
        else:
            type_name = get_type_name(annotation)

            required_text: str
            if get_origin(annotation) is not None and NoneType in get_args(annotation):
                required_text = ":material-minus-box-outline: Optional"
            else:
                required_text = ":material-checkbox-marked-outline: Yes"
            doc_string = doc_string + (
                f"    | `{key}` | `{type_name}` | {fieldinfo.description} | {required_text} | `{fieldinfo.default}`\n"
            )

            if get_origin(annotation) is not None:
                for arg in get_args(annotation):
                    if arg and inspect.isclass(arg) and issubclass(arg, BaseModel):
                        submodels[key if parent_key is None else f"{parent_key}.{key}"] = arg

    doc_string = doc_string + "\n"

    doc_string = textwrap.dedent(doc_string)

    for key, annotation in submodels.items():
        doc_string = doc_string + build_docs_for_model(annotation, key)

    return doc_string


preamble = """??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality
    will always be documented and available on release.
"""

(root_dir / "documentation/docs/installation/configuration.md").write_text(preamble + build_docs_for_model(Config))

config_locations = [
    root_dir / "api" / "build_scripts" / "mappings.yml",
    root_dir / "api" / "test" / "unit" / "config.yml",
]


class DocsConfig(Config):
    model_config = SettingsConfigDict(
        yaml_file=config_locations,
        yaml_file_encoding="utf-8",
        strict=True,
        env_nested_delimiter="__",
        env_prefix="hwl_",
    )


(root_dir / "documentation/docs/installation/default_configuration.md").write_text(
    f"""
# Default Configuration

??? success "Auto-Generated Documentation"
    This set of documentation is automatically generated from source, and will help ensure any change to functionality
    will always be documented and available on release.

Below is the default configuration for Howler when unit tests are run. You can use it as a starting point for your
installation. For more information, see [Configuration](/howler/installation/configuration).

```yaml
{yaml.safe_dump(DocsConfig().model_dump(mode="json")).strip()}
```
"""  # noqa: E501
)

processed_classes = []

for module_name in MODELS_TO_EXPORT:
    module = importlib.import_module(module_name)

    for export, obj in inspect.getmembers(
        module,
        lambda _member: inspect.isclass(_member) and issubclass(_member, odm.Model),
    ):
        if export not in processed_classes:
            (root_dir / f"documentation/docs/odm/class/{export.lower()}.md").write_text(obj.markdown())
            processed_classes.append(export)
