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
    IP,
    AnyField,
    HowlerEmbeddedModel,
    ModelExtensionRegistry,
    construct_partial,
    mapping,
    metadata,
    model_extensions,
)
from howler.models.action import Action
from howler.models.case import Case
from howler.models.hit import Hit
from howler.models.user import User


@pytest.fixture(scope="module")
def public_schema():
    return entity_schema()


def dereference(schema, prop):
    return schema["$defs"][prop["$ref"].removeprefix("#/$defs/")]


def test_public_schema_and_default_profile(public_schema, tmp_path, monkeypatch):
    schema = public_schema
    validator = Draft202012Validator(schema)
    Draft202012Validator.check_schema(schema)
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
    hit = Hit.model_validate({"howler.analytic": "Sample", "howler.hash": "a"})
    validator.validate(
        {
            "hit": hit.as_primitives(),
            "case": Case.model_validate({"title": "sample", "summary": "new"}).as_primitives(),
            "action": construct_partial(Action, {"name": "one stored field"}).as_primitives(),
        }
    )
    assert not validator.is_valid({"case": {"__index": "event"}})
    hit_schema = dereference(schema, schema["properties"]["hit"])
    assert set(hit_schema["required"]) == {"timestamp", "howler", "__index"}
    timestamp = hit_schema["properties"]["timestamp"]
    assert (
        timestamp["x-howler-default"] == "NOW" and timestamp["x-howler-kind"] == "Date" and "default" not in timestamp
    )
    user = dereference(schema, schema["properties"]["user"])
    assert {"meta", "apikeys", "password", "__access_lvl__"}.isdisjoint(user["properties"])
    pending = model_extensions.pending(Hit), model_extensions.is_finalized(Hit)
    bad = tmp_path / "classification.yml"
    bad.write_text(": [not valid YAML")
    monkeypatch.setenv("HWL_CONF_FOLDER", str(tmp_path))
    monkeypatch.setenv("HWL_CLASSIFICATION_PATH", str(bad))
    monkeypatch.setenv("HWL_CORE__CLUE__ENABLED", "false")
    assert json.dumps(entity_schema()) == json.dumps(schema)
    assert (model_extensions.pending(Hit), model_extensions.is_finalized(Hit)) == pending


def test_offline_schema_generation(tmp_path):
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


def test_schema_for_extension_values_and_literal_nulls():
    registry = ModelExtensionRegistry()
    registry.declare(Case, "payload", Annotated[AnyField | None, metadata(default=None)], plugin="example")
    registry.declare(Case, "values", mapping(AnyField), plugin="example")
    registry.declare(Case, "items_by_key", mapping(list[AnyField]), plugin="example")
    registry.declare(Case, "choices", mapping(Literal["yes", None]), plugin="example")
    registry.declare(Case, "sequences", mapping(list[Literal["yes", None]]), plugin="example")
    model = registry.finalize(Case)
    validator = Draft202012Validator(entity_schema({"case": model}))
    sample = {
        "payload": {"outer": [None, {"inner": {"absent": None, "kept": [None]}}]},
        "values": {"absent": None, "present": False, "nested": {"absent": None}},
        "items_by_key": {"a": [None, 42, [{"absent": None}]]},
        "choices": {"kept": "yes", "omitted": None},
        "sequences": {"key": [None, "yes"]},
    }
    record = construct_partial(model, sample).as_primitives()
    assert record == {
        "__index": "case",
        "payload": {"outer": [None, {"inner": {"kept": [None]}}]},
        "values": {"present": False, "nested": {}},
        "items_by_key": {"a": [None, 42, [{}]]},
        "choices": {"kept": "yes"},
        "sequences": {"key": [None, "yes"]},
    }
    validator.validate({"case": record})
    for bad in (
        {"payload": None},
        {"values": {"absent": None}},
        {"items_by_key": {"a": None}},
        {"payload": {"outer": [None, {"inner": {"absent": None}}]}},
        {"values": {"nested": {"absent": None}}},
        {"items_by_key": {"a": [[{"absent": None}]]}},
        {"choices": {"key": None}},
        {"choices": {"key": "no"}},
        {"sequences": {"key": ["no"]}},
    ):
        assert not validator.is_valid({"case": {"__index": "case", **bad}})
    for value in (False, 1, 0.5, "text", {}, []):
        validator.validate({"case": {"__index": "case", "payload": value, "values": {"a": value}}})


def test_supplied_models_keep_plugin_profile_and_container_null_semantics():
    class PluginData(HowlerEmbeddedModel):
        addresses: list[IP] | None = None
        by_name: mapping(IP, default={})

    extensions = ModelExtensionRegistry()
    extensions.declare(Hit, "extra", Annotated[list[PluginData], metadata(default=[])], plugin="example")
    schema = entity_schema({"hit": extensions.finalize(Hit), "migration": User, "user_avatar": None})
    assert set(schema["properties"]) == {"hit"}
    hit = dereference(schema, schema["properties"]["hit"])
    plugin = dereference(schema, hit["properties"]["extra"]["items"])
    assert "clue" not in hit["properties"] and "extra" not in Hit.model_fields
    assert {child["type"] for child in plugin["properties"]["addresses"]["items"]["anyOf"]} == {"string", "null"}
    assert plugin["properties"]["by_name"]["additionalProperties"]["type"] == "string"
    assert PluginData.model_validate(
        {"addresses": [None], "by_name": {"a": None, "b": "192.0.2.1"}}
    ).as_primitives() == {"addresses": [None], "by_name": {"b": "192.0.2.1"}}


def test_embedded_user_public_policy():
    registry = ModelExtensionRegistry()
    registry.declare(Case, "investigator", User, plugin="example")
    schema = entity_schema({"case": registry.finalize(Case)})
    case = dereference(schema, schema["properties"]["case"])
    user = dereference(schema, case["properties"]["investigator"])
    assert user["title"] == "User" and "uname" in user["properties"]
    assert not {"apikeys", "password"} & user["properties"].keys()
    assert not Draft202012Validator(schema).is_valid({"case": {"__index": "case", "investigator": {"password": "x"}}})
