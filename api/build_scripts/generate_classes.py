import base64
import copy
import json
import logging as log
import os
import re
import shutil
import sys
import textwrap
from os import path
from pathlib import Path
from typing import get_origin

import requests


def to_pascal_case(snake_str):
    components = snake_str.split("_")
    return "".join(component.title() for component in components)


def to_camel_case(snake_str):
    components = snake_str.split("_")
    return components[0] + "".join(component.title() for component in components[1:])


# Currently set to info. If you're curious for output on the tree structure of the generated classes, set this to
# log.DEBUG instead.
# log.basicConfig(level=log.DEBUG)
log.basicConfig(level=log.INFO)

# In order for this to run, you need to be hosting a development server at this address. There also needs to be
# randomized data added to each of the endpoints we want to pull from, so we can validate the model we create.
API_PATH = "http://localhost:5000/api/v1/"

# Resolve relative to this script, including when it runs in a Git worktree.
HOWLER_UI_PATH = (Path(__file__).parent.parent.parent / "ui").resolve()
TS_GENERATED_PATH = HOWLER_UI_PATH / "src/models/entities/generated"


REQUIRED_FIELDS = [
    "timestamp",
    "howler.id",
    "howler.analytic",
    "howler.assignment",
    "howler.hash",
]

TYPE_TS_MAPPING = {
    "keyword": "string",
    "date": "string",
    "integer": "number",
    "float": "number",
    "ip": "string",
    "boolean": "boolean",
    "text": "string",
    "object": "{ [index: string]: string }",
    "long": "number",
    "double": "number",
    "nested": "object",
}

PYTHON_TS_MAPPING = {"str": "string", "bool": "boolean"}

BASE_TS_TEMPLATE = """/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface {name} {{
{members}
}}
"""

# TypeScript Templates
TS_MEMBER_TEMPLATE = "  {}?: {};"
TS_MEMBER_TEMPLATE_NOTNULL = "  {}: {};"
TS_MEMBER_LIST_TEMPLATE = "  {}?: {}[];"
TS_MEMBER_LIST_TEMPLATE_NOTNULL = "  {}: {}[];"
TS_IMPORT_TEMPLATE = "import type {{ {name} }} from './{name}';"

# These public names predate automatic generation. Keep their namespaces stable
# rather than letting traversal order or random document shape choose an owner.
CLASS_NAMES = {
    "user": "UserUser",
    "hit.event": "ECSEvent",
    "event.event": "ECSEvent",
    "hit.file": "HitFile",
    "hit.organization": "HitOrganization",
    "hit.howler": "Howler",
    "event.howler": "EventHowler",
    "case.enrichments": "Enrichments",
    "case.rules": "Rule",
    "hit.rule": "ECSRule",
    "event.rule": "ECSRule",
    "analytic.comment": "Comment",
    "hit.howler.comment": "HowlerComment",
    "event.howler.comment": "HowlerComment",
}
for _index in ("hit", "event"):
    for _path, _name in {
        "cloud.account": "CloudAccount",
        "source.original": "SourceOriginal",
        "http.response": "HttpResponse",
        "threat.enrichments": "ThreatEnrichment",
        "threat.indicator": "ThreatIndicator",
    }.items():
        CLASS_NAMES[f"{_index}.{_path}"] = _name
CLASS_NAMES.update(
    {
        "event.destination.original": "DestinationOriginal",
        "event.email.attachments": "EmailAttachment",
        "event.email.attachments.file": "AttachmentsFile",
        "event.email.parent": "EmailParent",
        "event.observer.ingress": "ObserverIngress",
        "hit.http.response": "Response",
    }
)
for _field in (
    "cloud",
    "destination",
    "email",
    "file",
    "http",
    "observer",
    "organization",
    "process",
    "source",
    "threat",
    "tls",
):
    CLASS_NAMES[f"event.{_field}"] = "Event" + to_pascal_case(_field)

MEMBER_ORDER = {
    "Action": ["action_id", "name", "operations", "owner", "query", "triggers", "admins", "members"],
    "Dossier": ["dossier_id", "leads", "owner", "pivots", "query", "title", "type", "admins", "members"],
    "View": ["owner", "query", "settings", "sort", "span", "title", "type", "view_id", "indexes", "admins", "members"],
    "Pivot": ["format", "icon", "label", "mappings", "value", "group", "description"],
    "Case": [
        "__index",
        "case_id",
        "created",
        "end",
        "enrichments",
        "escalation",
        "indicators",
        "items",
        "overview",
        "participants",
        "rules",
        "status",
        "start",
        "summary",
        "targets",
        "tasks",
        "threats",
        "title",
        "updated",
    ],
    "Item": ["id", "classification", "parent", "name", "type", "value", "visible"],
    "Rule": [
        "rule_id",
        "destination",
        "query",
        "author",
        "enabled",
        "created_at",
        "timeframe",
        "expire_after_resolved",
        "indexes",
    ],
}


def class_name(name, structure):
    """Resolve a stable export name, preserving explicitly assigned legacy names."""
    if "__class_name" in structure:
        return structure["__class_name"]
    if structure.get("__list", False) and name != "antivirus":
        name = re.sub(r"(.+)s$", r"\1", name)
    return to_pascal_case(name)


def member_names(structure):
    """Include the serialized __index discriminator, but exclude generator bookkeeping."""
    return [key for key in structure if key == "__index" or not key.startswith("__")]


def get_api_response(endpoint):
    """Fail on API errors before interpreting the response as configuration or sample data."""
    headers = {"Authorization": f"Basic {base64.b64encode(b'user:devkey:user').decode('utf-8')}"}
    response = requests.get(API_PATH + endpoint, headers=headers, timeout=60)
    if response.status_code == 401:
        log.fatal(
            "User account doesn't exist in Howler!\n"
            "Run poetry run python -m howler.sample_data.random_data from api/ before this script."
        )
        sys.exit(1)
    response.raise_for_status()
    return response.json()["api_response"]


def generate_model_structure(model, index_data, prefix="", parent_list=False):
    """Use live scalar metadata and declared container boundaries, never sample cardinality.

    The public configs endpoint flattens compound boundaries and propagates ``list`` to
    their leaves. The canonical registry supplies only those missing container boundaries
    and dynamic mapping value types; scalar types still come from the API.
    """
    from howler.models.registry import field_metadata, model_annotation, model_registry, unwrap_annotation
    from howler.models.schema import KIND_TYPE_MAPPING, mapping_value_annotation

    structure = {}
    for name, definition in sorted(model_registry.fields(model).items()):
        if name == "apikeys":
            # API keys are redacted and are deliberately absent from the public UI entity.
            continue
        key = f"{prefix}.{name}" if prefix else name
        annotation = unwrap_annotation(definition.annotation)
        is_list = get_origin(annotation) is list
        child_model = model_annotation(annotation)
        if child_model is not None:
            child = generate_model_structure(child_model, index_data, key, parent_list or is_list)
            child["__list"] = is_list
            child["__required"] = any(field == key or field.startswith(key + ".") for field in REQUIRED_FIELDS)
            structure[name] = child
            continue

        is_mapping = get_origin(annotation) is dict
        if is_mapping:
            # A Mapping summary may not exist until a random document populates a key.
            # Its declared value type is invariant even for empty mappings or different keys.
            value_annotation = mapping_value_annotation(definition)
            value_metadata = field_metadata(value_annotation)
            if value_metadata is None:
                raise ValueError(f"Missing mapping value metadata for {key}")
            es_type = KIND_TYPE_MAPPING[value_metadata.kind]
            value_type = TYPE_TS_MAPPING[es_type]
            if get_origin(unwrap_annotation(value_annotation)) is list:
                value_type += "[]"
            ts_type = f"{{ [index: string]: {value_type} }}"
        else:
            metadata = index_data.get(key)
            if metadata is None:
                raise ValueError(f"API configs is missing declared field {key}")
            ts_type = TYPE_TS_MAPPING[metadata["type"]]
            if key in {"settings.display", "rules.indexes"}:
                # Preserve the two literal unions already exposed by the UI baseline.
                values = metadata["values"]
                preferred = ["list", "grid"] if key == "settings.display" else ["hit", "event"]
                ordered_values = [value for value in preferred if value in values] + sorted(
                    set(values) - set(preferred)
                )
                ts_type = " | ".join(repr(value) for value in ordered_values)
            # Only an ancestor array makes the flattened list flag ambiguous.
            leaf_list = is_list if parent_list else metadata["list"]
            if leaf_list:
                ts_type = f"({ts_type})[]" if " | " in ts_type else ts_type + "[]"
        structure[name] = {"__ts_field_type": ts_type, "__required": key in REQUIRED_FIELDS}
    return structure


def generate_structure(config):
    """Generate from metadata; samples are only a check that the API was seeded."""
    from howler.common.loader import datastore

    structure = {}
    for index, index_data in sorted(config["indexes"].items()):
        items = get_api_response("search/" + index + "/?query=*:*")["items"]
        if not items:
            raise ValueError(f"No validation object found for index {index}; seed the API first")
        model = datastore().get_collection(index).schema_model
        structure[index] = generate_model_structure(model, index_data)
        if index in {"hit", "event", "case"}:
            structure[index]["__index"] = {"__ts_field_type": f"'{index}'", "__required": True}
    return structure


def dedupe_objects(names, structure, existing_classes):
    """Deduplicate using immutable type structures, not mutable traversal annotations."""
    if "__ts_field_type" in structure:
        return
    if names:
        signature = copy.deepcopy(structure)
        assigned = CLASS_NAMES.get(".".join(names))
        if assigned is not None:
            structure["__class_name"] = assigned
        candidate = class_name(names[-1], structure)
        if (
            assigned is None
            and len(names) > 1
            and candidate
            in {
                "Hit",
                "Event",
                "Case",
                "Action",
                "Analytic",
                "Dossier",
                "Template",
                "Overview",
                "View",
                "UserUser",
            }
        ):
            candidate = to_pascal_case("_".join(names[-2:]))
        if candidate in existing_classes and existing_classes[candidate] != signature:
            candidate = to_pascal_case("_".join(names[-2:]))
            if candidate in existing_classes and existing_classes[candidate] != signature:
                candidate = to_pascal_case("_".join(names))
        if candidate in existing_classes:
            if existing_classes[candidate] != signature:
                raise ValueError(f"Conflicting generated class {candidate}")
            structure["__class_name"] = candidate
            structure["__skip"] = True
            return
        existing_classes[candidate] = signature
        structure["__class_name"] = candidate
    # Give the alert record first ownership of shared ECS exports.
    priority = {"hit": 0, "event": 1} if not names else {}
    for entry in sorted(member_names(structure), key=lambda key: (priority.get(key, 2), key)):
        dedupe_objects([*names, entry], structure[entry], existing_classes)


def generate_class_member_and_field(name, structure):
    structure_name = class_name(name, structure)

    ts_member_rendered = (
        (TS_MEMBER_LIST_TEMPLATE_NOTNULL if structure.get("__required", False) else TS_MEMBER_LIST_TEMPLATE)
        if structure.get("__list", False)
        else (TS_MEMBER_TEMPLATE_NOTNULL if structure.get("__required", False) else TS_MEMBER_TEMPLATE)
    ).format(name, structure_name)

    ts_import_rendered = TS_IMPORT_TEMPLATE.format(name=structure_name)

    return (
        ts_member_rendered,
        ts_import_rendered,
    )


def generate_primitive_member_and_field(name, structure):
    ts_member_rendered = (
        TS_MEMBER_TEMPLATE_NOTNULL if structure.get("__required", False) else TS_MEMBER_TEMPLATE
    ).format(name, structure["__ts_field_type"])

    return ts_member_rendered, None


def generate_class(name, structure):
    # This is one of those special case leaves, a duplicate class. No writing, just generate the reference
    if structure.get("__skip", False):
        return generate_class_member_and_field(name, structure)

    if "__ts_field_type" in structure:
        return generate_primitive_member_and_field(name, structure)
    else:
        # Generate the references for this class
        structure_name = class_name(name, structure)
        order = MEMBER_ORDER.get(structure_name, [])
        members = sorted(
            member_names(structure), key=lambda key: (order.index(key) if key in order else len(order), key)
        )
        values = [generate_class(obj, structure[obj]) for obj in members]

        # Generate the file name
        file_name = "{}/{}.d.ts".format(TS_GENERATED_PATH, structure_name)
        if not path.exists(file_name):
            with open(
                file_name,
                "w",
            ) as file:
                file_contents = "\n".join(
                    sorted({x[1] for x in values if x[1]}, key=lambda value: (value.casefold(), value))
                )

                if file_contents:
                    file_contents += "\n\n"

                file_contents += BASE_TS_TEMPLATE.format(
                    name=structure_name,
                    members="\n".join([x[0] for x in values]),
                )

                # Write the templated file using the generated references!
                file.write(file_contents)

        # Return the reference the parent generated class can use
        return generate_class_member_and_field(name, structure)


def generate_api_config_types(config_req):  # noqa: C901
    ts_file_name = TS_GENERATED_PATH / "ApiType.d.ts"
    with open(ts_file_name, "w") as file:
        # We handle each field slightly differently. First up is the indexes!
        # This is quite trivial as it is simply a dict of dicts of the same object, repeated.
        # We simply drill down two levels to the dicts for the first entry in the index, and replicate it for all
        # the known indexes
        log.info("Step 4.1: Handling 'indexes' key")
        indexes = config_req.pop("indexes")

        # A Mapping summary lacks some flags; nullable regex/values also vary by
        # the first field. Describe the metadata contract, not one arbitrary leaf.
        index_fields = "\n".join(
            TS_MEMBER_TEMPLATE_NOTNULL.format(key, ts_type)
            for key, ts_type in {
                "default": "boolean",
                "indexed": "boolean",
                "list": "boolean",
                "stored": "boolean",
                "deprecated": "boolean",
                "type": "string",
                "description": "string",
                "regex": "string",
                "values": "string[]",
                "deprecated_description": "string",
            }.items()
        )

        # First we write the reused type
        file.write("import type { ClassificationDefinition } from 'utils/classificationParser';\n\n")
        file.write(BASE_TS_TEMPLATE.format(imports="", name="APIIndex", members=index_fields) + "\n")

        # Then we write the overarching dict containing a key for each index
        file.write(
            BASE_TS_TEMPLATE.format(
                imports="",
                name="APIIndexes",
                members="\n".join(
                    TS_MEMBER_TEMPLATE_NOTNULL.format(key, "{ [index: string]: APIIndex }") for key in sorted(indexes)
                ),
            )
            + "\n"
        )

        # Lookups is next. This requires some slightly more touch and go formatting as there's no unified format for our
        # lookups. They can be a list of strings, a dict of lists of strings, or a dict of dicts with the same keys.
        # We handle each of these cases
        log.info("Step 4.2: Handling 'lookups' key")
        lookups = config_req.pop("lookups")
        lookup_members = []
        lookup_order = [
            "howler.status",
            "howler.scrutiny",
            "howler.escalation",
            "howler.assessment",
            "case.escalation",
            "transitions",
            "techniques",
            "tactics",
            "icons",
            "roles",
        ]
        for lookup_name in sorted(
            lookups, key=lambda key: (lookup_order.index(key) if key in lookup_order else len(lookup_order), key)
        ):
            lookup_data = lookups[lookup_name]
            if lookup_name == "roles":
                lookup_data = sorted(lookup_data, key=lambda value: (value != "admin", value))
            # "simple" list format (i.e. ["one", "two"])
            if isinstance(lookup_data, list):
                sub_type = type(lookup_data[0]).__name__ if lookup_data else "str"

                # If there's only a few values in the lookup, we create an enum style list instead
                if lookup_data and len(lookup_data) < 12 and sub_type == "str":
                    compact = len(lookup_data) <= 5 or lookup_name == "roles"
                    quoted_values = [
                        json.dumps(value) if lookup_name == "case.escalation" else repr(value) for value in lookup_data
                    ]
                    lookup_members.append(
                        TS_MEMBER_TEMPLATE_NOTNULL.format(
                            f"'{lookup_name}'" if "." in lookup_name else lookup_name,
                            "["
                            + ("" if compact else "\n    ")
                            + (", " if compact else ",\n    ").join(quoted_values)
                            + ("" if compact else "\n  ")
                            + "]",
                        )
                    )
                    continue
                else:
                    lookup_members.append(
                        TS_MEMBER_LIST_TEMPLATE_NOTNULL.format(
                            f"'{lookup_name}'" if "." in lookup_name else lookup_name,
                            PYTHON_TS_MAPPING[sub_type],
                        )
                    )
                    continue

            # Dict is next
            elif isinstance(lookup_data, dict):
                entry = lookup_data[min(lookup_data)]

                # Dict of lists
                if isinstance(entry, list):
                    sub_type = type(entry[0]).__name__ if entry else "str"
                    lookup_members.append(
                        TS_MEMBER_TEMPLATE_NOTNULL.format(
                            f"'{lookup_name}'" if "." in lookup_name else lookup_name,
                            f"{{ [index: string]: {PYTHON_TS_MAPPING[sub_type]}[] }}",
                        )
                    )
                    continue

                # Dict of dicts (we reuse the logic from the indexes, basically)
                elif isinstance(entry, dict):
                    fields = [f"{k}: {PYTHON_TS_MAPPING[type(v).__name__]};" for k, v in sorted(entry.items())]

                    lookup_members.append(
                        TS_MEMBER_TEMPLATE_NOTNULL.format(
                            f"'{lookup_name}'" if "." in lookup_name else lookup_name,
                            f"{{ [index: string]: {{ {' '.join(fields)[:-1]} }} }}",
                        )
                    )
                    continue

            # We've missed some logic! This is just a check in case we change the formatting of the config in an
            # unexpected way in the future.
            log.warning("Missing logic for key %s: %s", lookup_name, lookup_data)

        file.write(BASE_TS_TEMPLATE.format(imports="", name="APILookups", members="\n".join(lookup_members)).strip())

        # The last two are hilariously complex objects, so instead of doing it in a logical way, we just
        # #CHEESEIT instead. We use a bunch of regexes to convert a JSON version of the entry into a TS type.
        step = 3
        for key in ["configuration"]:
            log.info("Step 4.%s: Handling '%s' key", step, key)
            step += 1

            # Setting up the basic interface format
            configuration = config_req.pop(key)
            configuration.pop("mapping")
            # Follow the stable public layout, independent of Flask's JSON key ordering.
            orders = {
                "": ["auth", "system", "ui", "features", "clue"],
                "auth": [
                    "allow_apikeys",
                    "allow_extended_apikeys",
                    "max_apikey_duration_amount",
                    "max_apikey_duration_unit",
                    "oauth_providers",
                    "internal",
                ],
                "system": ["type", "version", "branch", "commit", "retention"],
                "system.retention": ["enabled", "limit_unit", "limit_amount"],
                "features": ["clue", "notebook"],
            }

            def ordered(data, prefix=""):
                if not isinstance(data, dict):
                    return data
                order = orders.get(prefix, [])
                return {
                    k: ordered(v, f"{prefix}.{k}" if prefix else k)
                    for k, v in sorted(
                        data.items(),
                        key=lambda item: (order.index(item[0]) if item[0] in order else len(order), item[0]),
                    )
                }

            config_type = "export interface APIConfiguration extends APIMappings " + json.dumps(
                ordered(configuration), indent=2
            )

            # |    "key":| -> |    key:|
            config_type = re.sub(r'^( +)"(\w+)":', r"\1\2:", config_type, flags=re.MULTILINE)

            # true or false -> boolean;
            config_type = re.sub(r"(true|false),?", "boolean;", config_type, flags=re.MULTILINE)

            # array of strings -> string[];
            config_type = re.sub(r'\[(\s+".+",?\s+)+],?', "string[];", config_type, flags=re.MULTILINE)

            # |    key: "value"| -> |    key: string;|
            config_type = re.sub(r': ".+?",?', ": string;", config_type)
            config_type = re.sub(r": \d+,?", ": number;", config_type)

            # In order to handle cases where there's a list of complex objects, we make the assumption that all children
            # have the same keys. We then do two things:
            # 1. We remove every entry in the array except the last one
            # 2. We convert the entry from a formatted dict into a single line of key: type entries. Example:
            #
            # | [{              |
            # |   key: string;  |
            # |   key2: string; | -> | { key: string; key2: string; key3: string }[] |
            # |   key3: string; |
            # | }]              |
            def fix_whitespace(match_obj):
                lines = match_obj.group(2).split("\n")
                return f"{{{' '.join(line.strip() for line in lines)}}}[]"

            config_type = re.sub(r"\[\s+({([\s\S]+?)},?\s+)+]", fix_whitespace, config_type)

            # We can hardcode a few types here:
            config_type = re.sub(
                r"max_apikey_duration_amount: null.+",
                r"max_apikey_duration_amount?: number;",
                config_type,
            )
            config_type = re.sub(
                r"max_apikey_duration_unit: null.+",
                r"max_apikey_duration_unit?: 'seconds' | 'minutes' | 'hours' | 'days' | 'weeks' | 'months' | 'years';",
                config_type,
            )

            config_type = re.sub(
                r"apps: \[\],?",
                "apps: { alt: string; name: string; img_d: string; img_l: string; route: "
                "string; classification: string }[];",
                config_type,
            )
            config_type = re.sub(r"status_checks: \[\],?", "status_checks: string[];", config_type)
            config_type = re.sub(r"(    notebook: boolean;)", r"\1\n    [feature: string]: boolean;", config_type)

            # Finally, we convert any null values into unknown types.
            config_type = re.sub(r"(.+): null.+", r"\1?: unknown;", config_type)

            # We clean up a few remaining awkward bits
            config_type = config_type.replace('"', "'")
            config_type = config_type.replace("},", "};")
            config_type = config_type.replace("}\n", "};\n")
            config_type = config_type.replace("[],", "[];")

            # All done!
            file.write("\n\n" + config_type)

        # Deployment markings are data, not property names in a static type. The
        # UI already uses this generic definition; retain the old export name.
        config_req.pop("c12nDef")
        file.write("\n\nexport interface APIC12Ndef extends ClassificationDefinition {}\n")
        file.write("\nexport interface APIMappings {\n  mapping: { [index: string]: string };\n}\n")

        # We'll check for any keys we missed and throw a warning so we know what the problem is in the future
        leftover_keys = list(config_req.keys())
        if len(leftover_keys) > 0:
            log.warning("Missing handling for config key(s) %s", ", ".join(leftover_keys))

        # Write the final section of the new type
        file.write(
            textwrap.dedent(
                f"""
                export interface ApiType {{
                  indexes: API{to_pascal_case("indexes")};
                  lookups: API{to_pascal_case("lookups")};
                  configuration: API{to_pascal_case("configuration")};
                  c12nDef: ClassificationDefinition;
                }}
                """
            )
        )


def run():
    log.info("Step 1: Generate and validate type structure")
    config = get_api_response("configs")
    structure = generate_structure(config)

    log.info("Step 2: Deduplicate objects")
    dedupe_objects([], structure, {})

    log.info("Step 3: Generate classes")

    # We don't want to keep any of the old files, they're in git anyway
    if TS_GENERATED_PATH and path.exists(TS_GENERATED_PATH):
        log.info("Step 3.1: Remove old files")
        shutil.rmtree(TS_GENERATED_PATH)

    if TS_GENERATED_PATH and not path.exists(TS_GENERATED_PATH):
        os.mkdir(TS_GENERATED_PATH)

    for root in structure.keys():
        generate_class(root, structure[root])

    # Retain this historically exported duplicate even though no current entity
    # references it. Its contents are derived from the canonical generated type.
    indicator = TS_GENERATED_PATH / "Indicator.d.ts"
    (TS_GENERATED_PATH / "EnrichmentsIndicator.d.ts").write_text(
        indicator.read_text().replace("export interface Indicator {", "export interface EnrichmentsIndicator {"),
        encoding="utf-8",
    )

    log.info("Step 4: Generate API configs")
    generate_api_config_types(config)


if __name__ == "__main__":
    run()
