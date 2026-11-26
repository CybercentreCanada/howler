"""The offline contract is a schema for public primitives, not an ingestion validator."""

import json
import os
import subprocess
import sys
from textwrap import dedent
from typing import Annotated, Literal

import pytest
from jsonschema import Draft202012Validator

from build_scripts.model_json_schema import API_DIR, entity_schema
from howler.models import (
    HowlerEmbeddedModel,
    ModelExtensionRegistry,
    any_field,
    construct_partial,
    ip,
    mapping,
    metadata,
    model_extensions,
)
from howler.models.action import Action
from howler.models.case import Case
from howler.models.event import Event
from howler.models.hit import Hit
from howler.models.user import User


@pytest.fixture(scope="module")
def public_schema():
    return entity_schema()


def dereference(schema, prop):
    return schema["$defs"][prop["$ref"].removeprefix("#/$defs/")]


def test_public_schema_matches_serialized_documents_and_projections(public_schema):
    schema = public_schema
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    assert set(schema["properties"]) == {
        "action",
        "analytic",
        "case",
        "dossier",
        "event",
        "hit",
        "overview",
        "template",
        "user",
        "view",
    }
    for ref in schema["properties"].values():
        assert set(ref) == {"$ref"} and ref["$ref"].startswith("#/$defs/")
    hit = Hit.model_validate({"howler.analytic": "Sample", "howler.hash": "a", "host.hostname": "machine"})
    event = Event.model_validate({"howler.hash": "f"})
    case = Case.model_validate({"title": "sample", "summary": "new"})
    validator.validate(
        {
            "hit": hit.as_primitives(),
            "event": event.as_primitives(),
            "case": case.as_primitives(),
            "action": construct_partial(Action, {"name": "one stored field"}).as_primitives(),
        }
    )
    assert not validator.is_valid({"case": {"__index": "event"}})
    assert not validator.is_valid({"case": {}})
    assert not validator.is_valid({"case": {"__index": "case", "overview": None}})
    assert not validator.is_valid({"case": {"__index": "case", "rules": [{"indexes": ["not-an-index"]}]}})

    hit_schema = dereference(schema, schema["properties"]["hit"])
    assert set(hit_schema["required"]) == {"timestamp", "howler", "__index"}
    howler = dereference(schema, hit_schema["properties"]["howler"])
    assert set(howler["required"]) == {"id", "analytic", "assignment", "hash"}
    assert hit_schema["properties"]["classification"]["type"] == "string"
    assert hit_schema["properties"]["timestamp"]["format"] == "date-time"
    assert hit_schema["properties"]["labels"]["additionalProperties"]["type"] == "string"
    assert hit_schema["properties"]["clue"]["$ref"].endswith("/Clue")
    dns = dereference(schema, hit_schema["properties"]["dns"])
    answer = dereference(schema, dns["properties"]["answers"]["items"])
    assert "class" in answer["properties"] and "class_" not in answer["properties"]

    user = dereference(schema, schema["properties"]["user"])
    assert {"meta", "apikeys", "password", "__access_lvl__"}.isdisjoint(user["properties"])
    assert not any(node.get("title") == "ApiKey" for node in schema["$defs"].values())
    assert not validator.is_valid({"user": {"password": "private"}})


def test_default_profile_is_reproducible_in_an_existing_deployment(public_schema, tmp_path, monkeypatch):
    pending = model_extensions.pending(Hit)
    finalized = model_extensions.is_finalized(Hit)
    # Both import-time classification paths must come from the repository. Neither
    # an invalid local deployment nor its feature flags may change the result.
    bad_classification = tmp_path / "classification.yml"
    bad_classification.write_text(": [not valid YAML")
    monkeypatch.setenv("HWL_CONF_FOLDER", str(tmp_path))
    monkeypatch.setenv("HWL_CLASSIFICATION_PATH", str(bad_classification))
    monkeypatch.setenv("HWL_CORE__CLUE__ENABLED", "false")
    monkeypatch.setenv("PYTHONHASHSEED", "917")
    assert json.dumps(entity_schema()) == json.dumps(public_schema)
    assert model_extensions.pending(Hit) == pending
    assert model_extensions.is_finalized(Hit) == finalized
    assert "clue" not in Hit.model_fields


def test_parent_import_and_both_fixture_workers_run_with_sockets_blocked(tmp_path):
    # sitecustomize installs the same guard before imports in the parent and both
    # child interpreters. Block DNS as well as sockets: RedisCluster resolves its
    # startup nodes while constructing the client, not just when querying it.
    (tmp_path / "sitecustomize.py").write_text(
        dedent("""\
        import sys
        def offline(event, args):
            if event == 'socket.__new__':
                raise OSError('sockets disabled in schema generation test')
            if event.startswith(('socket.get', 'socket.connect')):
                raise AssertionError(f'network access during schema generation: {event}')
        sys.addaudithook(offline)
    """)
    )
    parent = dedent("""\
        import os, sys
        assert 'sitecustomize' in sys.modules
        from build_scripts.model_json_schema import entity_schema
        assert 'howler.models' not in sys.modules and 'howler.config' not in sys.modules
        assert 'hit' in entity_schema()['properties']
        assert 'hwl_core' in os.environ and 'howler.config' not in sys.modules
    """)
    cluster = {"host": "must-not-resolve.invalid", "port": 6379, "is_cluster": True}
    env = {
        **os.environ,
        "hwl_core": json.dumps({"redis": {"persistent": cluster, "nonpersistent": cluster}}),
        "HwL_DaTaStOrE": "invalid JSON if read by Pydantic Settings",
        "PYTHONPATH": os.pathsep.join([str(tmp_path), str(API_DIR), os.environ.get("PYTHONPATH", "")]),
    }
    subprocess.run([sys.executable, "-c", parent], cwd=API_DIR, env=env, check=True, timeout=90)


def test_public_policy_follows_embedded_model_identity_without_its_root():
    registry = ModelExtensionRegistry()
    registry.declare(Case, "investigator", User, plugin="example")
    schema = entity_schema({"case": registry.finalize(Case)})
    case = dereference(schema, schema["properties"]["case"])
    investigator = dereference(schema, case["properties"]["investigator"])
    assert investigator["title"] == "User" and "uname" in investigator["properties"]
    assert not {"apikeys", "password"} & investigator["properties"].keys()
    assert not any(node.get("title") == "ApiKey" for node in schema["$defs"].values())
    assert not Draft202012Validator(schema).is_valid({"case": {"__index": "case", "investigator": {"password": "x"}}})

    registry.declare(Action, "source_case", Case, plugin="example")
    extended_action = registry.finalize(Action)
    schema = entity_schema({"action": extended_action})
    action = dereference(schema, schema["properties"]["action"])
    source = dereference(schema, action["properties"]["source_case"])
    assert source["title"] == "Case" and source["required"] == ["__index"]
    record = construct_partial(extended_action, {"source_case": {"title": "projected"}}).as_primitives()
    assert record == {"source_case": {"title": "projected", "__index": "case"}}
    validator = Draft202012Validator(schema)
    validator.validate({"action": record})
    assert not validator.is_valid({"action": {"source_case": {"__index": "hit"}}})


def test_any_output_omits_null_properties_and_mapping_values_but_retains_null_array_items():
    registry = ModelExtensionRegistry()
    registry.declare(Case, "payload", any_field(optional=True), plugin="example")
    registry.declare(Case, "values", mapping(any_field()), plugin="example")
    registry.declare(Case, "items_by_key", mapping(list[any_field()]), plugin="example")
    model = registry.finalize(Case)
    schema = entity_schema({"case": model})
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    sample = {
        "payload": {"outer": [None, {"inner": {"absent": None, "kept": [None]}}]},
        "values": {"absent": None, "present": False, "nested": {"absent": None}},
        "items_by_key": {"a": [None, 42, [{"absent": None}]]},
    }
    serialized = construct_partial(model, sample).as_primitives()
    assert serialized == {
        "__index": "case",
        "payload": {"outer": [None, {"inner": {"kept": [None]}}]},
        "values": {"present": False, "nested": {}},
        "items_by_key": {"a": [None, 42, [{}]]},
    }
    validator.validate({"case": serialized})
    for bad_field in (
        {"payload": None},
        {"values": {"absent": None}},
        {"items_by_key": {"a": None}},
        {"payload": {"outer": [None, {"inner": {"absent": None}}]}},
        {"values": {"nested": {"absent": None}}},
        {"items_by_key": {"a": [[{"absent": None}]]}},
    ):
        assert not validator.is_valid({"case": {"__index": "case", **bad_field}})
    for value in (False, 1, 0.5, "text", {}, []):
        validator.validate({"case": {"__index": "case", "payload": value, "values": {"a": value}}})


def test_literal_mapping_values_drop_only_null():
    registry = ModelExtensionRegistry()
    registry.declare(Case, "choices", mapping(Literal["yes", None]), plugin="example")
    registry.declare(Case, "sequences", mapping(list[Literal["yes", None]]), plugin="example")
    model = registry.finalize(Case)
    schema = entity_schema({"case": model})
    validator = Draft202012Validator(schema)
    sample = {"choices": {"kept": "yes", "omitted": None}, "sequences": {"key": [None, "yes"]}}
    record = construct_partial(model, sample).as_primitives()
    assert record == {"__index": "case", "choices": {"kept": "yes"}, "sequences": {"key": [None, "yes"]}}
    validator.validate({"case": record})
    for invalid in [None, "no"]:
        assert not validator.is_valid({"case": {"__index": "case", "choices": {"key": invalid}}})
    assert not validator.is_valid({"case": {"__index": "case", "sequences": {"key": ["no"]}}})


def test_supplied_models_keep_exact_plugin_profile_and_container_null_semantics():
    class PluginData(HowlerEmbeddedModel):
        addresses: list[ip()] | None = None
        by_name: mapping(ip(), default={})

    extensions = ModelExtensionRegistry()
    extensions.declare(Hit, "extra", Annotated[list[PluginData], metadata(default=[])], plugin="example")
    finalized = extensions.finalize(Hit)
    schema = entity_schema({"hit": finalized, "migration": User, "user_avatar": None})
    assert set(schema["properties"]) == {"hit"}
    hit = dereference(schema, schema["properties"]["hit"])
    assert "clue" not in hit["properties"]
    plugin = dereference(schema, hit["properties"]["extra"]["items"])
    addresses = plugin["properties"]["addresses"]
    assert addresses["type"] == "array"
    assert {child["type"] for child in addresses["items"]["anyOf"]} == {"string", "null"}
    by_name = plugin["properties"]["by_name"]["additionalProperties"]
    assert by_name["type"] == "string" and "anyOf" not in by_name
    data = PluginData.model_validate({"addresses": [None], "by_name": {"a": None, "b": "192.0.2.1"}})
    assert data.as_primitives() == {"addresses": [None], "by_name": {"b": "192.0.2.1"}}
    assert "extra" not in Hit.model_fields


def test_schema_exposes_input_metadata_separately_from_output(public_schema):
    hit = dereference(public_schema, public_schema["properties"]["hit"])
    timestamp = hit["properties"]["timestamp"]
    assert timestamp["x-howler-default"] == "NOW" and "default" not in timestamp
    assert timestamp["x-howler-reference"].endswith("ecs-base.html")
    assert timestamp["x-howler-kind"] == "Date"
    howler = dereference(public_schema, hit["properties"]["howler"])
    optional_score = howler["properties"]["score"]
    assert optional_score["x-howler-optional"] and optional_score["x-howler-default"] == 0
    assert optional_score["type"] == "number" and "score" not in howler["required"]
