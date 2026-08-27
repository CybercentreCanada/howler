"""Deterministic normalized-contract comparisons for the new model schema builder.

Compares complete generated index contracts (settings, mappings/properties, dynamic templates,
ILM composable templates) for every one of the 11 Howler collections against the frozen legacy
ODM contract fixture (``odm_contract_inventory.json``), plus focused unit tests for the
recursive dynamic-template builder's edge cases (compound/list-in-mapping) that are not
exercised by any of today's real top-level models.

The comparison includes dynamic-template order because Elasticsearch applies the first matching
template. Generation follows canonical registry field order rather than the DSL mapping tree's
process-dependent iteration order.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from howler import odm
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


@odm.model()
class LegacyEdgeChild(odm.Model):
    """Legacy counterpart of ``EdgeChild`` for differential dynamic-template comparison."""

    value = odm.Keyword()
    label = odm.Keyword()


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


def test_flat_field_count_matches_legacy_total_fields_heuristic() -> None:
    """``total_fields_limit`` reproduces ``max(1500, flat field count + 500)``."""
    assert schema.total_fields_limit(None) == 1500
    assert schema.total_fields_limit(Hit) == max(1500, schema.flat_field_count(Hit) + 500)
    # Hit has hundreds of ECS fields but stays under the 1500 default floor today.
    assert schema.flat_field_count(Hit) < 1000


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


def _legacy_dynamic_templates_for(legacy_field) -> list[dict[str, Any]]:
    from howler.datastore.support.build import build_templates

    return build_templates("edge_case.*", legacy_field, nested_template=False, index=True)


class TestDynamicTemplateRecursionEdgeCases:
    """Compound/list-in-mapping combinations not exercised by any real top-level model today.

    These verify the recursive ``schema._dynamic_templates`` helper against the legacy
    ``build_templates`` algorithm directly (rather than a real registered model), since no
    current Howler model nests a ``Compound`` or ``List`` inside an *indexed* ``Mapping``
    dynamic-key value.
    """

    def test_mapping_of_compound_matches_legacy_recursion(self) -> None:
        new_templates = schema._dynamic_templates(
            "edge_case.*", compound(EdgeChild), inherited_index=True, nested_template=False
        )
        legacy_field = odm.Mapping(odm.Compound(LegacyEdgeChild), index=True)
        legacy_field.apply_defaults(index=True, store=True)
        legacy_templates = _legacy_dynamic_templates_for(legacy_field)

        key = lambda templates: sorted(next(iter(t)) for t in templates)  # noqa: E731
        assert key(new_templates) == key(legacy_templates)
        new_by_key = {next(iter(t)): t[next(iter(t))] for t in new_templates}
        legacy_by_key = {next(iter(t)): t[next(iter(t))] for t in legacy_templates}
        assert new_by_key == legacy_by_key

    def test_mapping_of_list_matches_legacy_recursion(self) -> None:
        new_templates = schema._dynamic_templates(
            "edge_case.*", list[keyword()], inherited_index=True, nested_template=False
        )
        legacy_field = odm.Mapping(odm.List(odm.Keyword()), index=True)
        legacy_templates = _legacy_dynamic_templates_for(legacy_field)
        assert new_templates == legacy_templates
        assert new_templates == [{"nested_edge_case.*": {"match": "edge_case.*", "mapping": {"type": "nested"}}}]

    def test_mapping_of_mapping_matches_legacy_recursion(self) -> None:
        new_templates = schema._dynamic_templates(
            "edge_case.*", mapping(keyword()), inherited_index=True, nested_template=False
        )
        legacy_templates = _legacy_dynamic_templates_for(odm.Mapping(odm.Keyword()))
        assert new_templates == legacy_templates
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
