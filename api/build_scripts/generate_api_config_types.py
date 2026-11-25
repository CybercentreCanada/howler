"""Generate only ApiType.d.ts from the local development API's /configs response."""

import argparse
import base64
import json
import logging as log
import re
import sys
import textwrap
from io import StringIO
from pathlib import Path

import requests
from pydantic import TypeAdapter

from build_scripts.generate_classes import type_expression
from howler.datastore.types import FieldDescription

# In order for this to run, you need to be hosting a development server at this address.
API_PATH = "http://localhost:5000/api/v1/"

# Resolve relative to this script, including when it runs in a Git worktree.
TS_GENERATED_PATH = Path(__file__).resolve().parents[2] / "ui/src/models/entities/generated"
PYTHON_TS_MAPPING = {"str": "string", "bool": "boolean"}

BASE_TS_TEMPLATE = """/**
 * NOTE: This is an auto-generated file. Don't edit this manually.
 */
export interface {name} {{
{members}
}}
"""
TS_MEMBER_TEMPLATE_NOTNULL = "  {}: {};"
TS_MEMBER_LIST_TEMPLATE_NOTNULL = "  {}: {}[];"


def get_api_response(endpoint):
    """Fail on API errors before interpreting the response as configuration."""
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


def generate_api_config_types(config_req):  # noqa: C901
    """Render in memory so an unexpected response never truncates the previous output."""
    config_req = dict(config_req)
    with StringIO() as file:
        log.info("Step 4.1: Handling 'indexes' key")
        indexes = config_req.pop("indexes")

        # Mapping summaries and ordinary leaves share this datastore wire contract.
        description = TypeAdapter(FieldDescription).json_schema(mode="serialization")
        index_fields = "\n".join(
            TS_MEMBER_TEMPLATE_NOTNULL.format(
                key if key in description["required"] else f"{key}?", type_expression(node, {}, set())
            )
            for key, node in description["properties"].items()
        )

        # First we write the reused type
        file.write("import type { ClassificationDefinition } from 'utils/classificationParser';\n\n")
        file.write(BASE_TS_TEMPLATE.format(name="APIIndex", members=index_fields) + "\n")

        # Then we write the overarching dict containing a key for each index
        file.write(
            BASE_TS_TEMPLATE.format(
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

        file.write(BASE_TS_TEMPLATE.format(name="APILookups", members="\n".join(lookup_members)).strip())

        # The last two are hilariously complex objects, so instead of doing it in a logical way, we just
        # #CHEESEIT instead. We use a bunch of regexes to convert a JSON version of the entry into a TS type.
        log.info("Step 4.3: Handling 'configuration' key")
        # Setting up the basic interface format
        configuration = dict(config_req.pop("configuration"))
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
                """
                export interface ApiType {
                  indexes: APIIndexes;
                  lookups: APILookups;
                  configuration: APIConfiguration;
                  c12nDef: ClassificationDefinition;
                }
                """
            )
        )
        return file.getvalue()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=TS_GENERATED_PATH)
    args = parser.parse_args()
    contents = generate_api_config_types(get_api_response("configs"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "ApiType.d.ts").write_text(contents, encoding="utf-8")
