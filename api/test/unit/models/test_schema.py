"""Frozen-contract comparisons for the new model schema builder.

Compares complete generated index contracts (settings, mappings/properties, dynamic templates,
ILM composable templates) for every one of the 11 Howler collections against the frozen legacy
ODM contract fixture (``odm_contract_inventory.json``), plus focused unit tests for the
recursive dynamic-template builder's edge cases (compound/list-in-mapping) that are not
exercised by any of today's real top-level models.

Elasticsearch applies the first matching dynamic template, so this suite compares that sequence
exactly. Mapping properties and settings are JSON objects, so their key order is intentionally
normalized and is not treated as a storage contract.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from howler.models import (
    HowlerEmbeddedModel,
    HowlerESModel,
    any_field,
    compound,
    keyword,
    mapping,
    register_model,
    schema,
)
from howler.models.action import Action
from howler.models.analytic import Analytic
from howler.models.case import Case
from howler.models.dossier import Dossier
from howler.models.event import Event
from howler.models.hit import Hit
from howler.models.overview import Overview
from howler.models.template import Template
from howler.models.user import User
from howler.models.view import View
from test.unit.models._goldens import TEMPLATE_ORDER_GOLDEN_PATH, template_order_golden

CONTRACT_PATH = Path(__file__).parents[1] / "odm/fixtures/odm_contract_inventory.json"
FIXTURE: dict[str, Any] = json.loads(CONTRACT_PATH.read_text())

COLLECTION_MODELS: dict[str, Any] = {
    "hit": Hit,
    "event": Event,
    "case": Case,
    "template": Template,
    "overview": Overview,
    "analytic": Analytic,
    "action": Action,
    "user": User,
    "view": View,
    "dossier": Dossier,
    "user_avatar": None,
}
ILM_ENABLED = {"hit", "event", "case"}
TEMPLATE_ORDER = template_order_golden()
TEMPLATE_ORDER_GOLDEN_SHA256 = "e930ab5613d4d319e272e23a5db9846eec9604ebad45293a3b24fd5faf3a26b3"
SYNTHETIC_ACCESS_FIELDS = {"__access_lvl__", "__access_req__", "__access_grp1__", "__access_grp2__"}


# Module-level (not test-method-local) ad hoc models for the recursion edge-case tests below:
# with ``from __future__ import annotations`` active, a class body's annotations are deferred
# strings that must later resolve against the class's *module* globals, so a class nested inside
# a test function (whose annotation helpers are only local names) can intermittently fail to
# resolve under pytest depending on collection/import order, even though it is fine when run as
# a standalone script. See ``test_extensions.py`` for the same established convention.
@register_model(index=True, store=True, embedded=True)
class EdgeChild(HowlerEmbeddedModel):
    """Embedded model used only to test Compound-inside-Mapping dynamic template recursion."""

    value: keyword()
    label: keyword()


@register_model(index=True, store=True, id_field="key")
class EdgeAnyHost(HowlerESModel):
    """Top-level model used only to test that Mapping-of-Any is always disabled."""

    key: keyword()
    values: mapping(any_field(), index=True, default={})
    plain: keyword()


def _normalize(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, default=str))


@pytest.mark.parametrize("name", sorted(COLLECTION_MODELS))
def test_generated_mapping_matches_legacy_contract(name: str) -> None:
    """The generated properties/dynamic-templates/dynamic-strictness match the legacy fixture."""
    fixture_index = FIXTURE["collections"][name]["legacy_index"]
    mappings = schema.document_mapping(COLLECTION_MODELS[name])
    assert _normalize(mappings) == _normalize(fixture_index["mappings"])


@pytest.mark.parametrize("name", sorted(COLLECTION_MODELS))
def test_generated_settings_match_legacy_contract(name: str) -> None:
    """Shard/replica settings and the total-fields limit match the legacy fixture."""
    fixture_index = FIXTURE["collections"][name]["legacy_index"]
    settings = schema.index_settings(COLLECTION_MODELS[name], shards=1, replicas=0)
    assert _normalize(settings) == _normalize(fixture_index["settings"])


@pytest.mark.parametrize("name", sorted(ILM_ENABLED))
def test_generated_ilm_template_matches_legacy_contract(name: str) -> None:
    """The ILM composable template payload (settings + mappings + lifecycle) matches legacy."""
    fixture_ilm = FIXTURE["collections"][name]["ilm_template"]
    index_name = f"howler-{name}"
    body = schema.ilm_template_body(
        COLLECTION_MODELS[name],
        shards=1,
        replicas=0,
        policy_name=f"{index_name}_policy",
        rollover_alias=index_name,
    )
    assert body["mappings"] == schema.document_mapping(COLLECTION_MODELS[name])
    assert _normalize(body["mappings"]) == _normalize(fixture_ilm["template"]["mappings"])
    assert _normalize(body["settings"]) == _normalize(fixture_ilm["template"]["settings"])
    assert fixture_ilm["index_patterns"] == [f"{index_name}-*"]


@pytest.mark.parametrize("name", sorted(set(COLLECTION_MODELS) - {"user_avatar"}))
def test_dynamic_template_order_matches_legacy_contract(name: str) -> None:
    """Generated template precedence exactly follows the frozen legacy contract."""
    actual = schema.document_mapping(COLLECTION_MODELS[name])["dynamic_templates"]
    expected = FIXTURE["collections"][name]["legacy_index"]["mappings"]["dynamic_templates"]
    assert [next(iter(template)) for template in actual] == [next(iter(template)) for template in expected]
    assert [next(iter(template)) for template in actual] == TEMPLATE_ORDER["collections"][name][
        "dynamic_template_order"
    ]


def _property_paths(properties: dict[str, Any], prefix: str = "") -> set[str]:
    paths: set[str] = set()
    for name, definition in properties.items():
        if not prefix and name in SYNTHETIC_ACCESS_FIELDS:
            # The Pydantic collection overlays these generated ACL fields after its declared
            # model properties. Their values are checked elsewhere; field presence is independent
            # of dictionary insertion order.
            continue
        path = f"{prefix}.{name}" if prefix else name
        paths.add(path)
        children = definition.get("properties") if isinstance(definition, dict) else None
        if isinstance(children, dict):
            paths.update(_property_paths(children, path))
    return paths


@pytest.mark.parametrize("name", sorted(COLLECTION_MODELS))
def test_generated_mapping_properties_match_frozen_paths_order_insensitive(name: str) -> None:
    """Mapping property coverage is compared as JSON object content, without key-order parity."""
    actual = _property_paths(schema.document_mapping(COLLECTION_MODELS[name])["properties"])
    legacy_mapping = FIXTURE["collections"][name]["legacy_index"]["mappings"]["properties"]
    expected = _property_paths(legacy_mapping) - SYNTHETIC_ACCESS_FIELDS
    assert actual == expected


def test_flat_field_count_matches_legacy_total_fields_heuristic() -> None:
    """``total_fields_limit`` reproduces ``max(1500, flat field count + 500)``."""
    assert schema.total_fields_limit(None) == 1500
    assert schema.total_fields_limit(Hit) == max(1500, schema.flat_field_count(Hit) + 500)
    # Hit has hundreds of ECS fields but stays under the 1500 default floor today.
    assert schema.flat_field_count(Hit) < 1000


def test_dynamic_template_order_fixture_has_pinned_capture_provenance() -> None:
    assert TEMPLATE_ORDER["fixture_version"] == 1
    assert TEMPLATE_ORDER["capture"]["source_head"] == "3071fc4ea45d4b2dd44a7ee1646095426097d061"
    assert hashlib.sha256(TEMPLATE_ORDER_GOLDEN_PATH.read_bytes()).hexdigest() == TEMPLATE_ORDER_GOLDEN_SHA256


def test_schema_less_collection_uses_default_dynamic_templates() -> None:
    """A ``None`` schema model (e.g. ``user_avatar``) uses the shared default dynamic templates."""
    mappings = schema.document_mapping(None)
    assert mappings["dynamic_templates"] == schema.default_dynamic_templates
    assert mappings["dynamic"] is True


def test_document_mapping_forces_strict_when_no_dynamic_templates() -> None:
    """A model with no Mapping/FlattenedObject fields still gets ``refuse_all_implicit_mappings``.

    ``mappings["dynamic"]`` is intentionally left as the stub's ``True`` here, not overridden to
    ``"strict"``: ``strings_as_keywords`` is unconditionally inserted before the legacy
    ``if not dynamic_templates`` check runs, so that check can never actually fire in the
    (pre-existing, unrelated to this migration) legacy implementation either — verified directly
    against the frozen fixture, where every collection's ``dynamic`` is ``True``. This module
    intentionally reproduces that exact (dead-code) behavior rather than "fixing" it.
    """
    mappings = schema.document_mapping(Action)
    keys = [next(iter(template)) for template in mappings["dynamic_templates"]]
    assert "refuse_all_implicit_mappings" in keys
    assert mappings["dynamic"] is True


def test_document_mapping_stays_dynamic_true_when_templates_exist() -> None:
    """A model with an indexed Mapping field (e.g. Hit's ``labels``) never gets ``refuse_all``."""
    mappings = schema.document_mapping(Hit)
    keys = [next(iter(template)) for template in mappings["dynamic_templates"]]
    assert "refuse_all_implicit_mappings" not in keys
    assert mappings["dynamic"] is True


class TestDynamicTemplateRecursionEdgeCases:
    """Compound/list-in-mapping combinations not exercised by any real top-level model today.

    These verify the recursive ``schema._dynamic_templates`` helper against frozen expected
    output captured from the legacy ``build_templates`` algorithm, since no current Howler model
    nests a ``Compound`` or ``List`` inside an *indexed* ``Mapping`` dynamic-key value.
    """

    def test_mapping_of_compound_matches_frozen_legacy_recursion(self) -> None:
        new_templates = schema._dynamic_templates(
            "edge_case.*", compound(EdgeChild), inherited_index=True, nested_template=False
        )
        assert new_templates == [
            {
                "edge_case.*.value_tpl": {
                    "path_match": "edge_case.*.value",
                    "mapping": {"type": "keyword", "index": True},
                }
            },
            {
                "edge_case.*.label_tpl": {
                    "path_match": "edge_case.*.label",
                    "mapping": {"type": "keyword", "index": True},
                }
            },
        ]

    def test_mapping_of_list_matches_frozen_legacy_recursion(self) -> None:
        new_templates = schema._dynamic_templates(
            "edge_case.*", list[keyword()], inherited_index=True, nested_template=False
        )
        assert new_templates == [{"nested_edge_case.*": {"match": "edge_case.*", "mapping": {"type": "nested"}}}]

    def test_mapping_of_mapping_matches_frozen_legacy_recursion(self) -> None:
        new_templates = schema._dynamic_templates(
            "edge_case.*", mapping(keyword()), inherited_index=True, nested_template=False
        )
        assert new_templates == [{"nested_edge_case.*": {"match": "edge_case.*", "mapping": {"type": "nested"}}}]

    def test_mapping_of_any_is_disabled_regardless_of_index(self) -> None:
        properties, dynamic_sources = schema.build_properties(EdgeAnyHost)
        assert properties["values"] == schema.DISABLED_OBJECT_MAPPING
        assert "values" not in dynamic_sources


def test_id_and_text_properties_are_always_overlaid() -> None:
    """The synthetic ``id``/``__text__`` properties are added regardless of the model."""
    for model_type in (Hit, None):
        mappings = schema.document_mapping(model_type)
        assert mappings["properties"]["id"] == {"store": True, "doc_values": True, "type": "keyword"}
        assert mappings["properties"]["__text__"] == {"store": False, "type": "text"}
