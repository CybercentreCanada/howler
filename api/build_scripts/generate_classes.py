import base64
import json
import logging as log
import os
import re
import shutil
import sys
import textwrap
from os import path
from pathlib import Path
from typing import Any, Dict

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

# We'll try and find the howler client and howler-ui paths this way
howler_client_default_path = None
howler_ui_default_path = None
exclude = [
    "node_modules",
    "env",
    "venv",
    "pkg",
    "plugins",
    "snap",
    "build",
    "src",
    "target",
    "master_modules",
]

# Let's walk the user's home directory and find the howler client and howler ui repos
for root, dirs, files in os.walk(os.environ["HOME"]):
    # We've found what we needed, stop iteration
    if howler_client_default_path and howler_ui_default_path:
        break

    # Remove any unnecessary child folders
    dirs[:] = [d for d in dirs if (not d.startswith(".") or d == ".git") and d not in exclude]

    # Found the howler ui! Remove child dirs and continue
    if re.search(r"howler[-_]ui([-_]internal)?$", root) and ".git" in dirs:
        howler_ui_default_path = root
        dirs[:] = []
        continue

    # If this isn't either the howler ui or client, but is a git repo, don't bother checking the child dirs
    if ".git" in dirs:
        dirs[:] = []
        continue

# Where should we place the generated classes?
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
}

# This mapping mirrors the above - we use it for type validation on the dummy data.
TYPE_PYTHON_MAPPING = {
    "keyword": str,
    "date": str,
    "integer": int,
    "float": float,
    "ip": str,
    "boolean": bool,
    "text": str,
    "long": int,
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


def generate_structure():  # noqa: C901
    """Step 1: Generate the type structure based on the ES indexes, and validate it on an example object"""
    headers = {"Authorization": f"Basic {base64.b64encode(b'user:devkey:user').decode('utf-8')}"}
    config_req = requests.get(API_PATH + "configs", headers=headers)
    indexes: Dict[str, Dict[str, dict]] = config_req.json()["api_response"]["indexes"]

    # This object will actually contain the links between our various generated classes, as well as any primitives
    # in each class.
    structure: dict[str, Any] = dict()
    for index, index_data in indexes.items():
        validation_req = requests.get(API_PATH + "search/" + index + "/?query=*:*", headers=headers)

        if validation_req.status_code == 401:
            log.fatal(
                "User account doesn't exist in Howler!\n"
                + "Run howler/odm/random_data.py in howler-api before this script."
            )
            sys.exit(1)

        if validation_req.status_code == 400:
            log.fatal(f"400 when pulling validation data! Response: {validation_req.json()}")
            sys.exit(1)

        validation_list = validation_req.json()["api_response"]["items"]

        if len(validation_list) == 0:
            log.critical(f"No validation object found for index {index}, aborting")
            sys.exit(1)

        validation_obj = next(
            obj
            for obj in validation_list
            if index in ["user", "template", "overview", "analytic", "view", "action", "dossier"]
            or obj.get("agent", {}).get("id", False)
        )
        log.debug("  Processing %s", index)

        structure[index] = dict()
        for key in index_data.keys():
            if key[:-1].endswith("key_") and not key.endswith("a"):
                continue

            # The indexes returned by the API are flattened. In order to rebuild the tree, we need to unflatten them.
            # The keys are in the form:
            #
            # key1.key2.key3
            # key1.key2.key4
            # key1.key5.key6
            #
            # So we split them up and build the tree from there.
            fields = [part for part in key.split(sep=".") if not part.startswith("key_")]
            required = key in REQUIRED_FIELDS

            # We hava two parts to keep track of - where we are in the tree we are building, and where we are in
            # the validation object. The goal is to keep these in sync so we can easily compare the two and resolve
            # any discrepancies.
            current = structure[index]
            current_validation = validation_obj

            indent = "    "

            # Process the intermediate nodes. The leaves of the tree are special cased.
            while len(fields) > 1:
                # Starting at the top, and working our way downward.
                current_field = fields.pop(0)

                if current.get(current_field, None) is None:
                    # If we haven't initialized this node yet, we'll do so now
                    current[current_field] = dict()
                    log.debug(f"{indent}{current_field}:")

                # Descend down the tree we're creating, and the validation object.
                current = current[current_field]
                current["__required"] = required or current.get("__required", False)
                current_validation = current_validation.get(current_field, None)

                # The index information returned by the server doesn't actually tell us if intermediate nodes in the
                # tree are arrays, so we need to check that ourselves.
                if isinstance(current_validation, list):
                    # We also need to descend into the array, so we can continue validating the types.
                    current_validation = current_validation[0]

                    # We'll annotate the structure we are generating with some private context info. Anything starting
                    # with __ we know we can safely ignore later!
                    current["__list"] = True

                indent = indent + "  "

            # We've now arrived at the leaf! Time to figure out the types of the primitives, and check that they match
            # the example object we fetched earlier.
            current_field = fields[0]

            # The specification will tell us if the primitive keys are of type list, BUT this can lead to trouble if any
            # of the parent nodes are list as well, as this will be set to true in that case too. So we'll need to
            # verify this using the validation object.
            is_list = index_data[key]["list"]
            is_dict = False
            try:
                if isinstance(current_validation, list):
                    current_value = current_validation[0].get(current_field)
                else:
                    try:
                        current_value = current_validation.get(current_field)
                    except Exception:
                        log.info("\tMissing value at %s.%s, setting to None.", index, key)
                        current_value = None

                if isinstance(current_value, list):
                    # Even though the specification claimed the type isn't list, it actually is. We'll reflect that in
                    # the generated class.
                    is_list = True
                    try:
                        current_value = current_value[0]
                    except IndexError:
                        current_value = TYPE_PYTHON_MAPPING[index_data[key]["type"]]()
                else:
                    # Even though the specification claimed the type is list, it actually isn't. We'll reflect that in
                    # the generated class.
                    is_list = False

                if isinstance(current_value, dict):
                    is_dict = True
                    current_value = current_value.get("key_a", None)

                # Verify the claimed type in the specification matches the type of the validation object.
                python_type: type = str
                try:
                    python_type = TYPE_PYTHON_MAPPING[index_data[key]["type"]]
                except KeyError:
                    # apikeys currently doesn't work, but we shouldn't really care about them, so we can skip
                    if key == "apikeys":
                        continue

                if current_value is not None:
                    assert isinstance(
                        current_value,
                        python_type,
                    ), (
                        f"Type {key} does not match: {type(current_value)}, "
                        f"{python_type} from {index_data[key]['type']}"
                    )
            except KeyError as e:
                # We have to special case dossier models, since they have up to five defined fields but often only the
                # first few are actually set. We can safely ignore KeyErrors from them if they aren't set.
                if not current_field.startswith("key_"):
                    raise e

            # Get the corresponding Typescript type, and make it an array if necessary
            ts_field_type = TYPE_TS_MAPPING[index_data[key]["type"]]

            if is_dict and index_data[key]["type"] != "object":
                ts_field_type = f"{{ [index: string]: {ts_field_type} }}"

            if is_list:
                ts_field_type = f"{ts_field_type}[]"

            # We're done processing this leaf! Onto the next
            current[current_field] = {
                **index_data[key],
                "__ts_field_type": ts_field_type,
                "__required": key in REQUIRED_FIELDS,
            }
            log.debug(f"{indent}{current_field}: ts:{ts_field_type}")

    return structure


def dedupe_objects(names, structure, existing_classes):
    """Step 2: Look for any duplicate classes and remove them, preserving the reference"""
    # This is a primitive type definition, we don't want to mess with this stuff
    if len(names) > 0 and "__ts_field_type" in structure:
        return None

    if len(names) > 0:
        # If we have two models with the same name but different types, one will need to be renamed
        # This can likely be made more efficient and remove duplicate classes that *don't* share a name, but for now we
        # just want to avoid conflicts!
        if names[-1] in existing_classes:
            # We need to pop this property if it exists, so equality checks work
            existing_names = existing_classes[names[-1]].pop("__name")

            # Luckily, we are working with pretty basic types so a simple == will check deep equality correctly.
            if existing_classes[names[-1]] == structure:
                log.debug("Model Match: %s and %s" % (".".join(names), existing_names))

                # If a class doesn't need to be generated (since it's a duplicate) we simply skip the rest of the
                # tree, basically making it a leaf (but a special case leaf!)
                structure["__skip"] = True
            else:
                # We'll name the class after its parent. This is sufficient for now - if we get further conflicts down
                # the road, we can just add the parent's parent, or make this a bit smarter ;)
                try:
                    structure["__class_name"] = names[-2] + "_" + names[-1]
                except IndexError:
                    structure["__class_name"] = names[0] + "_" + names[0]

            # Add the property back, if it exists
            existing_classes[names[-1]]["__name"] = existing_names
        else:
            # No class of this name exists yet, so add it
            existing_classes[names[-1]] = {**structure, "__name": ".".join(names)}

    for entry in list(structure.keys()):
        # Ignore any private fields
        if entry.startswith("__"):
            continue

        # RECURSION TIME BABY
        dedupe_objects([*names, entry], structure[entry], existing_classes)


def generate_class_member_and_field(name, structure):
    structure_name = structure.get("__class_name", name)
    if structure.get("__list", False) and structure_name.lower() not in ["antivirus"]:
        structure_name = re.sub(r"(.+)s$", r"\1", structure_name)

    ts_member_rendered = (
        (TS_MEMBER_LIST_TEMPLATE_NOTNULL if structure.get("__required", False) else TS_MEMBER_LIST_TEMPLATE)
        if structure.get("__list", False)
        else (TS_MEMBER_TEMPLATE_NOTNULL if structure.get("__required", False) else TS_MEMBER_TEMPLATE)
    ).format(name, to_pascal_case(structure_name))

    ts_import_rendered = TS_IMPORT_TEMPLATE.format(name=to_pascal_case(structure_name))

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
        values = [generate_class(obj, structure[obj]) for obj in structure.keys() if not obj.startswith("__")]

        structure_name = structure.get("__class_name", name)
        if structure.get("__list", False) and structure_name.lower() not in ["antivirus"]:
            structure_name = re.sub(r"(.+)s$", r"\1", structure_name)

        # Generate the file name
        file_name = "{}/{}.d.ts".format(TS_GENERATED_PATH, to_pascal_case(structure_name))
        if not path.exists(file_name):
            with open(
                file_name,
                "w",
            ) as file:
                file_contents = "\n".join(sorted([x[1] for x in values if x[1]]))

                if file_contents:
                    file_contents += "\n\n"

                file_contents += BASE_TS_TEMPLATE.format(
                    name=to_pascal_case(structure_name),
                    members="\n".join([x[0] for x in values]),
                )

                # Write the templated file using the generated references!
                file.write(file_contents)

        # Return the reference the parent generated class can use
        return generate_class_member_and_field(name, structure)


def generate_api_config_types():
    headers = {"Authorization": f"Basic {base64.b64encode(b'user:devkey:user').decode('utf-8')}"}
    config_req = requests.get(API_PATH + "configs", headers=headers).json()["api_response"]

    ts_file_name = TS_GENERATED_PATH / "ApiType.d.ts"
    with open(ts_file_name, "w") as file:
        # We handle each field slightly differently. First up is the indexes!
        # This is quite trivial as it is simply a dict of dicts of the same object, repeated.
        # We simply drill down two levels to the dicts for the first entry in the index, and replicate it for all
        # the known indexes
        log.info("Step 4.1: Handling 'indexes' key")
        indexes = config_req.pop("indexes")

        index_fields = "\n".join(
            [
                TS_MEMBER_TEMPLATE_NOTNULL.format(k, PYTHON_TS_MAPPING.get(type(v).__name__, "string"))
                for k, v in indexes["hit"][next(key for key in indexes["hit"].keys())].items()
            ]
        )

        # First we write the reused type
        file.write(BASE_TS_TEMPLATE.format(imports="", name="APIIndex", members=index_fields) + "\n")

        # Then we write the overarching dict containing a key for each index
        file.write(
            BASE_TS_TEMPLATE.format(
                imports="",
                name="APIIndexes",
                members="\n".join(
                    TS_MEMBER_TEMPLATE_NOTNULL.format(key, "{ [index: string]: APIIndex }") for key in indexes.keys()
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
        for lookup_name, lookup_data in lookups.items():
            # "simple" list format (i.e. ["one", "two"])
            if isinstance(lookup_data, list):
                sub_type = type(lookup_data[0]).__name__

                # If there's only a few values in the lookup, we create an enum style list instead
                if len(lookup_data) < 12 and sub_type == "str":
                    lookup_members.append(
                        TS_MEMBER_TEMPLATE_NOTNULL.format(
                            f"'{lookup_name}'" if "." in lookup_name else lookup_name,
                            "["
                            + ("" if len(lookup_data) <= 5 else "\n    ")
                            + (", " if len(lookup_data) <= 5 else ",\n    ").join(f"'{val}'" for val in lookup_data)
                            + ("" if len(lookup_data) <= 5 else "\n  ")
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
                entry = lookup_data[next(key for key in lookup_data.keys())]

                # Dict of lists
                if isinstance(entry, list):
                    sub_type = type(entry[0]).__name__
                    lookup_members.append(
                        TS_MEMBER_TEMPLATE_NOTNULL.format(
                            f"'{lookup_name}'" if "." in lookup_name else lookup_name,
                            f"{{ [index: string]: {PYTHON_TS_MAPPING[sub_type]}[] }}",
                        )
                    )
                    continue

                # Dict of dicts (we reuse the logic from the indexes, basically)
                elif isinstance(entry, dict):
                    fields = [f"{k}: {PYTHON_TS_MAPPING[type(v).__name__]};" for k, v in entry.items()]

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
        for key in ["configuration", "c12nDef"]:
            log.info("Step 4.%s: Handling '%s' key", step, key)
            step += 1

            # Setting up the basic interface format
            config_type = f"export interface API{to_pascal_case(key)} " + json.dumps(config_req.pop(key), indent=2)

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
                return f'{{{" ".join(line.strip() for line in lines)}}}[]'

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

            config_type = config_type.replace(
                "apps: [],",
                "apps: { alt: string; name: string; img_d: string; img_l: string; route: "
                "string; classification: string }[];",
            )

            # Finally, we convert any null values into unknown types.
            config_type = re.sub(r"(.+): null.+", r"\1?: unknown;", config_type)

            # We clean up a few remaining awkward bits
            config_type = config_type.replace('"', "'")
            config_type = config_type.replace("},", "};")
            config_type = config_type.replace("}\n", "};\n")
            config_type = config_type.replace("[],", "[];")

            # All done!
            file.write("\n\n" + config_type)

        # We'll check for any keys we missed and throw a warning so we know what the problem is in the future
        leftover_keys = list(config_req.keys())
        if len(leftover_keys) > 0:
            log.warning("Missing handling for config key(s) %s", ", ".join(leftover_keys))

        # Write the final section of the new type
        file.write(
            "\n"
            + textwrap.dedent(
                f"""
                export interface ApiType {{
                  indexes: API{to_pascal_case('indexes')};
                  lookups: API{to_pascal_case('lookups')};
                  configuration: API{to_pascal_case('configuration')};
                  c12nDef: API{to_pascal_case('c12nDef')};
                }}
                """
            )
        )


def run():
    log.info("Step 1: Generate and validate type structure")
    structure = generate_structure()

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

    log.info("Step 4: Generate API configs")
    generate_api_config_types()


if __name__ == "__main__":
    run()
