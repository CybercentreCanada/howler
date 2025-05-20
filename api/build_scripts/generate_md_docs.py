import importlib
import inspect
import textwrap
from pathlib import Path

import yaml

import howler.odm.base as base
from howler import odm
from howler.odm.models import config

root_dir = Path(__file__).parent.parent
odm_path = root_dir / "howler/odm/models"

MODELS_TO_EXPORT = [
    "howler.odm.models.hit",
    "howler.odm.models.aws",
    "howler.odm.models.azure",
    "howler.odm.models.cbs",
    "howler.odm.models.gcp",
    "howler.odm.models.howler_data",
    *list(
        str(_file.relative_to(root_dir)).replace(".py", "").replace("/", ".")
        for _file in (odm_path / "ecs").rglob("*.py")
        if _file.stem != "__init__"
    ),
]


intro_data = """
    docs/odm/getting_started.md
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

print(textwrap.dedent(intro_data).strip())

print("\n\n")


config_md = config.Config.markdown(url_prefix="#")

print("docs/installation/configuration.md")
for member, obj in inspect.getmembers(
    config, lambda _member: inspect.isclass(_member) and issubclass(_member, odm.Model)
):
    if member == "Config":
        continue

    config_md += obj.markdown(toc_depth=2, url_prefix="#", include_autogen_note=False)

print(config_md)

print("docs/installation/default_configuration.md")
newline = "\n"
print(
    textwrap.dedent(
        f"""
      # Default Configuration

      ??? success "Auto-Generated Documentation"
          This set of documentation is automatically generated from source, and will help ensure any change to functionality will always be documented and available on release.

      Below is the default configuration for Howler. You can use it as a starting point for your installation. For more information, see [Configuration](/howler-docs/installation/configuration).

      ```yaml
      {f"{newline}      ".join(yaml.safe_dump(config.Config(config.DEFAULT_CONFIG).as_primitives()).split(newline))}
      ```


"""  # noqa: E501
    )
)

processed_classes = []

for module_name in MODELS_TO_EXPORT:
    module = importlib.import_module(module_name)

    for export, obj in inspect.getmembers(
        module,
        lambda _member: inspect.isclass(_member) and issubclass(_member, odm.Model),
    ):
        if export not in processed_classes:
            print(f"docs/odm/class/{export.lower()}.md")
            print(obj.markdown())
            processed_classes.append(export)
