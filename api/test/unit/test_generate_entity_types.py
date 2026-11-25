import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from build_scripts import generate_api_config_types as config_generator
from build_scripts import generate_classes, model_json_schema
from build_scripts.generate_classes import OUTPUT_DIR, render_entities, sync_output, type_expression
from howler.models.template import Template

LEGACY_HEADER = "/**\n * NOTE: This is an auto-generated file. Don't edit this manually.\n */"


def test_wire_types_follow_schema_and_reuse_local_definitions():
    child = {"$ref": "#/$defs/Child"}
    schema = {
        "properties": {"hit": {"$ref": "#/$defs/ExtendedRecord"}},
        "$defs": {
            "ExtendedRecord": {
                "type": "object",
                "required": ["__index", "wire-name", "classification"],
                "properties": {
                    "__index": {"const": "hit"},
                    "classification": {"type": "string"},
                    "wire-name": {"anyOf": [child, {"type": "null"}]},
                    "groups": {"type": "object", "additionalProperties": {"type": "array", "items": child}},
                    "matrix": {"type": "array", "items": {"type": "array", "items": {"enum": ["a'b", "c"]}}},
                    "flags": {"enum": [True, 1, None]},
                },
            },
            "Child": {
                "type": "object",
                "properties": {"parent": child, "count": {"type": "integer"}, "ratio": {"type": "number"}},
            },
            "Private": {"type": "string"},
        },
    }
    files = render_entities(schema)
    assert files.keys() == {"Hit.d.ts", "Child.d.ts"}
    hit = files["Hit.d.ts"]
    assert hit.count("import type { Child }") == 1
    assert "__index: 'hit';" in hit
    assert "classification: string;" in hit
    assert "'wire-name': Child | null;" in hit
    assert "groups?: { [index: string]: Child[] };" in hit
    assert r"matrix?: (('a\'b' | 'c')[])[];" in hit
    assert "flags?: true | 1 | null;" in hit
    assert "import type" not in files["Child.d.ts"]
    assert "parent?: Child;" in files["Child.d.ts"]
    assert "count?: number;" in files["Child.d.ts"]
    assert "ratio?: number;" in files["Child.d.ts"]


@pytest.mark.parametrize("ref", ["#/$defs/Missing", "https://example.test/Other.json"])
def test_invalid_reference_fails_before_writing(ref):
    with pytest.raises(ValueError, match="(Missing schema definition|local definition reference)"):
        render_entities({"properties": {"hit": {"$ref": ref}}, "$defs": {}})


def test_entity_cannot_overwrite_the_live_config_module():
    with pytest.raises(ValueError, match="conflicting export name"):
        render_entities({"properties": {"api_type": {"$ref": "#/$defs/Other"}}, "$defs": {"Other": True}})


def test_shared_public_roots_export_both_names_from_the_same_definition():
    schema = model_json_schema.entity_schema({"overview": Template, "template": Template})
    assert schema["properties"]["overview"] == schema["properties"]["template"]
    files = render_entities(schema)
    assert files.keys() == {"Overview.d.ts", "Template.d.ts"}
    assert "export interface Template {" in files["Template.d.ts"]
    assert "type?: 'global' | 'personal';" in files["Template.d.ts"]
    assert "export type { Template as Overview } from './Template';" in files["Overview.d.ts"]
    assert files == render_entities({**schema, "properties": dict(reversed(schema["properties"].items()))})


def test_non_null_any_in_public_properties_and_maps_keeps_null_array_elements():
    class Payload(BaseModel):
        value: Any
        by_key: dict[str, Any]
        items: list[Any]

    files = render_entities(model_json_schema.entity_schema({"overview": Payload}))
    overview = files["Overview.d.ts"]
    assert "value?: HowlerJsonValue;" in overview
    assert "by_key?: { [index: string]: HowlerJsonValue };" in overview
    assert "items?: (HowlerJsonValue | null)[];" in overview
    assert (
        "type HowlerJsonValue = boolean | number | string | (HowlerJsonValue | null)[] | "
        "{ [index: string]: HowlerJsonValue };" in files["HowlerJsonValue.d.ts"]
    )
    assert type_expression({"not": {"type": "null"}, "description": "a JSON value"}, {}, set()) == (
        "boolean | number | string | unknown[] | { [index: string]: unknown }"
    )


@pytest.mark.parametrize("override", [False, True], ids=["default-directory", "output-dir"])
def test_cli_refuses_unowned_collisions_before_any_writes(tmp_path, monkeypatch, capsys, override):
    output = tmp_path / "generated"
    schema = {"properties": {"fresh": {"$ref": "#/$defs/Fresh"}}, "$defs": {"Fresh": {"type": "string"}}}
    files = render_entities(schema)
    assert sync_output(output, files, check=False)
    (output / "Old.d.ts").write_bytes((output / "Fresh.d.ts").read_bytes())
    schema["$defs"]["Fresh"] = {"type": "object", "properties": {"other": {"$ref": "#/$defs/Shared"}}}
    schema["$defs"]["Shared"] = {"type": "number"}
    (output / "Unrelated.d.ts").write_text(f"{LEGACY_HEADER}\nexport interface Unrelated {{}}\n")
    (output / "Shared.d.ts").write_text((LEGACY_HEADER + "\n" if override else "") + "export type Shared = string;\n")
    (output / "ApiType.d.ts").write_text(f"{LEGACY_HEADER}\nexport interface ApiType {{}}\n")
    snapshot = {p.name: p.read_bytes() for p in output.iterdir()}
    monkeypatch.setattr(generate_classes, "OUTPUT_DIR", tmp_path / "unused" if override else output)
    monkeypatch.setattr(model_json_schema, "entity_schema", lambda: schema)
    args = ["generate_classes.py", *(["--output-dir", str(output)] if override else [])]
    for mode in (["--check"], []):
        monkeypatch.setattr(sys, "argv", args + mode)
        assert generate_classes.main() == 1
        assert f"Unowned declaration: {output / 'Shared.d.ts'}" in capsys.readouterr().err
        assert {p.name: p.read_bytes() for p in output.iterdir()} == snapshot

    (output / "Shared.d.ts").unlink()
    assert generate_classes.main() == 0
    assert not (output / "Old.d.ts").exists()
    assert (output / "Shared.d.ts").read_text().endswith("export type Shared = number;\n")
    for name in ("ApiType.d.ts", "Unrelated.d.ts"):
        assert (output / name).read_bytes() == snapshot[name]


def test_check_detects_real_output_drift_without_writing(tmp_path: Path):
    output = tmp_path / "generated"
    schema = {"properties": {"one": {"$ref": "#/$defs/One"}}, "$defs": {"One": {"type": "string"}}}
    files = render_entities(schema)
    assert not sync_output(output, files, check=True)
    assert not output.exists()
    sync_output(output, files, check=False)
    assert sync_output(output, files, check=True)

    # A previous entity, the separately generated live config, and an unrelated declaration.
    (output / "One.d.ts").rename(output / "Old.d.ts")
    (output / "One.d.ts").write_text(files["One.d.ts"].replace("string;", "boolean;"))
    (output / "ApiType.d.ts").write_text(files["One.d.ts"])
    (output / "Other.d.ts").write_text("user-owned")
    before = {p.name: p.read_bytes() for p in output.iterdir()}
    assert not sync_output(output, files, check=True)
    assert before == {p.name: p.read_bytes() for p in output.iterdir()}
    sync_output(output, files, check=False)
    assert not (output / "Old.d.ts").exists()
    assert (output / "One.d.ts").read_text() == files["One.d.ts"]
    assert (output / "ApiType.d.ts").read_bytes() == before["ApiType.d.ts"]
    assert (output / "Other.d.ts").read_bytes() == before["Other.d.ts"]


def test_live_config_describes_index_metadata_even_when_no_fields_are_populated():
    config = {"indexes": {"hit": {}}, "lookups": {}, "configuration": {"mapping": {}}, "c12nDef": {}}
    result = config_generator.generate_api_config_types(config)
    for member in [
        "deprecated?: boolean",
        "description: string | null",
        "regex: string | null",
        "values: unknown[] | null",
        "deprecated_description: string | null",
    ]:
        assert f"  {member};" in result
    assert "  hit: { [index: string]: APIIndex };" in result
    # Entity --check deliberately ignores ApiType; still verify its shared datastore contract offline.
    boundary = "export interface APIIndexes"
    assert result.split(boundary)[0] == (OUTPUT_DIR / "ApiType.d.ts").read_text().split(boundary)[0]
