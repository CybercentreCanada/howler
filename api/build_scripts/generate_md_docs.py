import argparse
import importlib
import inspect
import textwrap
from pathlib import Path
from types import NoneType
from typing import get_args, get_origin

import yaml
from pydantic import BaseModel
from pydantic_settings import SettingsConfigDict

from howler.config_models import Config
from howler.models import fields as model_fields
from howler.models.assemblyline import AssemblyLine
from howler.models.ecs.event import ECSEvent
from howler.models.ecs.process import ParentProcess
from howler.models.lead import Lead
from howler.models.record import ECSVersion
from howler.models.registry import FieldDefinition, field_metadata, model_annotation, model_registry, unwrap_annotation

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
EXTRA_MODELS = (AssemblyLine, Lead, ParentProcess)
PUBLISHED_NAMES = {ECSEvent: "Event"}


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

for class_name, function_name in sorted(
    {
        "Any": "any_field",
        "Boolean": "boolean",
        "CaseInsensitiveKeyword": "case_insensitive_keyword",
        "Classification": "classification",
        "ClassificationString": "classification_string",
        "Date": "date",
        "EmptyableKeyword": "emptyable_keyword",
        "Enum": "enum",
        "FlattenedListObject": "flattened_list_object",
        "FlattenedObject": "flattened_object",
        "Float": "float_field",
        "IndexText": "index_text",
        "Integer": "integer",
        "Json": "json_field",
        "Keyword": "keyword",
        "List": "list_field",
        "LowerKeyword": "lower_keyword",
        "Mapping": "mapping",
        "Optional": "optional",
        "Text": "text",
        "UUID": "uuid",
        "UpperKeyword": "upper_keyword",
        "ValidatedKeyword": "validated_keyword",
    }.items()
):
    description = inspect.getdoc(getattr(model_fields, function_name)) or ""
    intro_data += f"    | `{class_name}` | {description.splitlines()[0]} |\n"

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
    if check:
        if not path.exists() or path.read_text() != content:
            raise SystemExit(f"Generated documentation is stale: {path}")
    else:
        path.write_text(content)


def _published_name(model: type[BaseModel]) -> str:
    return PUBLISHED_NAMES.get(model, model.__name__)


def _field_type(definition: FieldDefinition) -> str:
    """Format the field using the public ODM documentation vocabulary."""
    child_model = model_annotation(definition.annotation)
    if child_model is not None:
        name = _published_name(child_model)
        link = f"[{name}](/howler/odm/class/{name.lower()})"
        return f"List [{link}]" if definition.metadata and definition.metadata.kind == "List" else link
    annotation = unwrap_annotation(definition.annotation)
    if get_origin(annotation) is list:
        child = get_args(annotation)[0]
        nested_model = model_annotation(child)
        if nested_model is not None:
            name = _published_name(nested_model)
            return f"List [[{name}](/howler/odm/class/{name.lower()})]"
        nested = field_metadata(child)
        return f"List [{nested.kind if nested else 'Any'}]"
    if get_origin(annotation) is dict and definition.metadata and definition.metadata.kind == "Mapping":
        child = get_args(annotation)[1]
        nested = field_metadata(child)
        return f"Mapping [{nested.kind if nested else 'Any'}]"
    return definition.metadata.kind if definition.metadata else "Any"


def _classes_to_export() -> list[type[BaseModel]]:
    """Resolve all published model pages before generating any files."""
    classes: dict[str, type[BaseModel]] = {}
    for module_name in MODELS_TO_EXPORT:
        module = importlib.import_module(module_name)
        for _export, obj in inspect.getmembers(
            module,
            lambda member: inspect.isclass(member) and issubclass(member, BaseModel),
        ):
            if obj.__module__ != module.__name__:
                continue
            name = _published_name(obj).lower()
            if name == "file" and module_name == "howler.models.ecs.email":
                continue  # The published File page is the ECS file, not the email attachment model.
            classes.setdefault(name, obj)
    for obj in (*EXTRA_MODELS, ECSVersion):
        classes.setdefault(_published_name(obj).lower(), obj)
    return [classes[name] for name in sorted(classes)]


def render_model(model: type[BaseModel]) -> str:
    """Render an existing published field table from the Pydantic field registry."""
    content = (
        '??? success "Auto-Generated Documentation"\n'
        "    This set of documentation is automatically generated from source, and will help ensure any change to "
        "functionality will always be documented and available on release.\n\n"
        f"# {_published_name(model)}\n\n> {model_registry.metadata(model).description}\n\n"
        "| Field | Type | Description | Required | Default |\n| :--- | :--- | :--- | :--- | :--- |\n"
    )
    definitions = model_registry.fields(model)
    if model.__name__ == "Hit":
        # The published Hit schema has always presented the required Howler core before ECS.
        definitions = {"timestamp": definitions["timestamp"], "howler": definitions["howler"], **definitions}
    for name, definition in definitions.items():
        metadata = definition.metadata
        kind = _field_type(definition)
        description = definition.description or "None"
        if metadata and metadata.reference:
            description += f'<br><a href="{metadata.reference}">Reference Link</a><br>'
        if metadata and metadata.kind == "Enum":
            values = dict(metadata.options).get("values", ())
            rendered_values = ", ".join('"{}"'.format(v) if v else str(v) for v in sorted(values))
            description += f"<br>Values:<br>`{rendered_values}`"
        optional = not definition.required and definition.default is None
        required = ":material-minus-box-outline: Optional" if optional else ":material-checkbox-marked-outline: Yes"
        if metadata and metadata.deprecated:
            required += f" :material-alert-box-outline: Deprecated - {metadata.deprecated_description}"
        default = f"`{definition.default}`"
        child_model = model_annotation(definition.annotation)
        if child_model and isinstance(definition.default, dict):
            child_name = _published_name(child_model)
            default = f"See [{child_name}](/howler/odm/class/{child_name.lower()}) for more details."
        content += f"| {name} | {kind} | {description} | {required} | {default} |\n"
    return content


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


class DocsConfig(Config):
    model_config = SettingsConfigDict(
        yaml_file=config_locations,
        yaml_file_encoding="utf-8",
        strict=True,
        env_nested_delimiter="__",
        env_prefix="hwl_",
    )


def generate_configuration_docs() -> None:
    """Render configuration pages using the existing settings schema."""
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
    classes = _classes_to_export()
    processed_classes = {_published_name(obj).lower() for obj in classes}
    for obj in classes:
        name = _published_name(obj).lower()
        write_generated(root_dir / f"documentation/docs/odm/class/{name}.md", render_model(obj), check)
    if check:
        # A historical page with no corresponding model in either implementation remains
        # available for old documentation links, but is not generated from the registry.
        published = {path.stem for path in (root_dir / "documentation/docs/odm/class").glob("*.md")}
        published.discard("previousprocess")
        if published != processed_classes:
            raise SystemExit(
                f"Generated class set differs: missing={sorted(processed_classes - published)}, "
                f"stale={sorted(published - processed_classes)}"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Pydantic model documentation")
    parser.add_argument("--check", action="store_true", help="Fail when generated documentation is stale")
    check = parser.parse_args().check
    generate_model_docs(check=check)
