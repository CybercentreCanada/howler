import argparse
import importlib
import inspect
import textwrap
from pathlib import Path
from types import NoneType
from typing import get_args, get_origin

import yaml
from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaValue
from pydantic_settings import SettingsConfigDict

from build_scripts.model_json_schema import documentation_schema

root_dir = Path(__file__).parent.parent.parent
model_path = root_dir / "api/howler/models"

MODELS_TO_EXPORT = [
    "howler.models.hit",
    "howler.models.aws",
    "howler.models.azure",
    "howler.models.cbs",
    "howler.models.gcp",
    "howler.models.howler_data",
    *sorted(
        str(_file.relative_to(root_dir / "api")).replace(".py", "").replace("/", ".")
        for _file in (model_path / "ecs").rglob("*.py")
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

for class_name, description in sorted(
    {
        "Any": "A field that can hold any value whatsoever but which is stored as a",
        "Boolean": "A field storing a boolean value.",
        "CaseInsensitiveKeyword": (
            "A field storing a string with a technical interpretation, but is case-insensitive when searching."
        ),
        "Classification": "A field storing access control classification.",
        "ClassificationString": "A field storing the classification as a string only.",
        "Date": "A field storing a datetime value.",
        "EmptyableKeyword": "A keyword which allow to differentiate between empty and None values.",
        "Enum": "A field storing a short string that has predefined list of possible values.",
        "FlattenedListObject": "A field storing a flattened object",
        "FlattenedObject": "A field storing a flattened object",
        "Float": "A field storing a floating point value.",
        "IndexText": "A special field with special processing rules to simplify searching.",
        "Integer": "A field storing an integer value.",
        "Json": "A field storing serializeable structure with their JSON encoded representations.",
        "Keyword": "A field storing a short string with a technical interpretation.",
        "List": "A field storing a sequence of typed elements.",
        "Long": "A field storing a long value. Equivalent to Integer in python, but sets the ES datatype to long.",
        "LowerKeyword": "A field storing a short lowercase string with a technical interpretation.",
        "Mapping": "A field storing a sequence of typed elements.",
        "Text": "A field storing human readable text data.",
        "UUID": "A field storing an auto-generated unique ID if None is provided",
        "UpperKeyword": "A field storing a short uppercase string with a technical interpretation.",
        "ValidatedKeyword": "Keyword field which the values are validated by a regular expression",
    }.items()
):
    intro_data += f"    | `{class_name}` | {description} |\n"

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


def write_generated(path: Path, content: str, check: bool) -> None:
    """Write a generated document, or fail if the committed copy is stale."""
    expected = content.encode("utf-8")
    if path.exists() and path.read_bytes() == expected:
        return
    if check:
        raise SystemExit(f"Generated documentation is stale: {path}")
    path.write_bytes(expected)


def _published_name(name: str) -> str:
    return "Event" if name == "ECSEvent" else name


def documentation_models() -> dict[str, type[BaseModel]]:
    """Resolve all published model pages before generating any files."""
    from howler.models.assemblyline import ALRecord, AssemblyLine, Mitre
    from howler.models.aws import Organization as AWSOrganization
    from howler.models.ecs.elf import Header as ELFHeader
    from howler.models.ecs.process import ParentProcess
    from howler.models.header import Header
    from howler.models.lead import Lead
    from howler.models.localized_label import LocalizedLabel
    from howler.models.log import Log
    from howler.models.record import ECSVersion

    classes: dict[str, type[BaseModel]] = {}
    for module_name in MODELS_TO_EXPORT:
        module = importlib.import_module(module_name)
        for _export, obj in inspect.getmembers(
            module,
            lambda member: inspect.isclass(member) and issubclass(member, BaseModel),
        ):
            if obj.__module__ != module.__name__:
                continue
            if obj is ELFHeader:
                # The public ``header`` page is Howler's outline header, not the ECS ELF header.
                continue
            if obj is AWSOrganization:
                # The published ``organization`` page is the ECS organization field set.
                continue
            name = _published_name(obj.__name__).lower()
            if name == "file" and module_name == "howler.models.ecs.email":
                continue  # The published File page is the ECS file, not the email attachment model.
            classes.setdefault(name, obj)
    for obj in (ALRecord, AssemblyLine, Header, Lead, LocalizedLabel, Log, Mitre, ParentProcess, ECSVersion):
        classes.setdefault(_published_name(obj.__name__).lower(), obj)
    return classes


def _field_type(prop: JsonSchemaValue, definitions: JsonSchemaValue) -> str:
    if "$ref" in prop:
        target = definitions[prop["$ref"].split("/")[-1]]
        if "properties" not in target:
            return prop.get("x-howler-kind", "Any")
        name = _published_name(target["title"])
        return f"[{name}](/howler/odm/class/{name.lower()})"
    if "anyOf" in prop:
        return _field_type(next(branch for branch in prop["anyOf"] if branch.get("type") != "null"), definitions)
    kind = prop.get("x-howler-kind", "Any")
    if kind == "List":
        return f"List [{_field_type(prop['items'], definitions)}]"
    if kind == "Mapping":
        return f"Mapping [{_field_type(prop['additionalProperties'], definitions)}]"
    return kind


def render_model(model: JsonSchemaValue, definitions: JsonSchemaValue) -> str:
    """Render the published ingest field states and defaults, independent of output presence."""
    content = (
        '??? success "Auto-Generated Documentation"\n'
        "    This set of documentation is automatically generated from source, and will help ensure any change to "
        "functionality will always be documented and available on release.\n\n"
        f"# {_published_name(model['title'])}\n\n> {model.get('description')}\n\n"
        "| Field | Type | Description | Required | Default |\n| :--- | :--- | :--- | :--- | :--- |\n"
    )
    linked_table = False
    for name, prop in model["properties"].items():
        kind = _field_type(prop, definitions)
        linked_table |= "](/howler/odm/class/" in kind
        description = prop.get("description", "None")
        if reference := prop.get("x-howler-reference"):
            description += f'<br><a href="{reference}">Reference Link</a><br>'
        if kind == "Enum":
            rendered_values = ", ".join(f'"{v}"' for v in prop["enum"])
            description += f"<br>Values:<br>`{rendered_values}`"
        required = (
            ":material-minus-box-outline: Optional"
            if prop.get("x-howler-optional")
            else ":material-checkbox-marked-outline: Yes"
        )
        if prop.get("deprecated"):
            required += f" :material-alert-box-outline: Deprecated - {prop['x-howler-deprecation']}"
        value = prop.get("x-howler-default")
        default = f"See {kind} for more details." if "$ref" in prop and isinstance(value, dict) else f"`{value}`"
        content += f"| {name} | {kind} | {description} | {required} | {default} |\n"
    # Published leaf tables ended with two blank lines; linked tables did not.
    return content if linked_table else content + "\n\n"


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
            annotation_description = (annotation.__doc__ or "None").replace("\n", " ")
            doc_string = doc_string + (
                "    "
                f"| `{key}` | [`{annotation.__name__}`](#{annotation.__name__.lower()}) | "
                f"{annotation_description} | "
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

config_locations = [
    root_dir / "api" / "build_scripts" / "mappings.yml",
    root_dir / "api" / "test" / "unit" / "config.yml",
]


def generate_configuration_docs() -> None:
    """Render configuration pages using the existing settings schema."""
    from howler.config_models import Config

    class DocsConfig(Config):
        model_config = SettingsConfigDict(
            yaml_file=config_locations,
            yaml_file_encoding="utf-8",
            strict=True,
            env_nested_delimiter="__",
            env_prefix="hwl_",
        )

    (root_dir / "documentation/docs/installation/configuration.md").write_text(preamble + build_docs_for_model(Config))
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


def generate_model_docs(*, check: bool = False) -> None:
    """Regenerate published model tables in stable module and class order."""
    write_generated(
        root_dir / "documentation/docs/odm/getting_started.md", textwrap.dedent(intro_data).strip() + "\n", check
    )
    schema = documentation_schema()
    definitions = schema["$defs"]
    for name, prop in schema["properties"].items():
        model = definitions[prop["$ref"].split("/")[-1]]
        write_generated(root_dir / f"documentation/docs/odm/class/{name}.md", render_model(model, definitions), check)
    if check:
        # A historical page with no corresponding model in either implementation remains
        # available for old documentation links, but is not generated from the registry.
        published = {path.stem for path in (root_dir / "documentation/docs/odm/class").glob("*.md")}
        expected = {*schema["properties"], "previousprocess"}
        if published != expected:
            raise SystemExit(
                f"Generated class set differs: missing={sorted(expected - published)}, "
                f"stale={sorted(published - expected)}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Pydantic model documentation")
    parser.add_argument("--check", action="store_true", help="Fail when generated documentation is stale")
    check = parser.parse_args().check
    generate_model_docs(check=check)
    if not check:
        generate_configuration_docs()
