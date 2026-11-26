"""Focused tests for generated Elasticsearch mappings and dynamic templates."""

from __future__ import annotations

from typing import Any

import pytest

from howler.models import HowlerEmbeddedModel, HowlerESModel, any_field, keyword, mapping, register_model, schema
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

COLLECTION_TEMPLATE_ORDER = [
    (
        Hit,
        [
            "strings_as_keywords",
            "labels.*_tpl",
            "container.labels.*_tpl",
            "process.env_vars.*_tpl",
            "process.parent.env_vars.*_tpl",
            "process.parent.parent.env_vars.*_tpl",
            "howler.comment.reactions.*_tpl",
        ],
    ),
    (
        Event,
        [
            "strings_as_keywords",
            "labels.*_tpl",
            "container.labels.*_tpl",
            "process.env_vars.*_tpl",
            "process.parent.env_vars.*_tpl",
            "process.parent.parent.env_vars.*_tpl",
            "howler.comment.reactions.*_tpl",
        ],
    ),
    (Case, ["strings_as_keywords", "refuse_all_implicit_mappings"]),
    (Template, ["strings_as_keywords", "refuse_all_implicit_mappings"]),
    (Overview, ["strings_as_keywords", "refuse_all_implicit_mappings"]),
    (Analytic, ["strings_as_keywords", "comment.reactions.*_tpl"]),
    (Action, ["strings_as_keywords", "refuse_all_implicit_mappings"]),
    (User, ["strings_as_keywords", "refuse_all_implicit_mappings"]),
    (View, ["strings_as_keywords", "refuse_all_implicit_mappings"]),
    (Dossier, ["strings_as_keywords", "refuse_all_implicit_mappings"]),
    (
        None,
        [
            "int",
            "ints",
            "long",
            "longs",
            "double",
            "doubles",
            "float",
            "floats",
            "string",
            "strings",
            "text",
            "texts",
            "boolean",
            "booleans",
            "date",
            "date",
        ],
    ),
]


@register_model(index=True, store=True, embedded=True)
class EdgeChild(HowlerEmbeddedModel):
    """Embedded child for recursive template construction."""

    value: keyword()
    label: keyword()


@register_model(index=True, store=True, id_field="key")
class EdgeAnyHost(HowlerESModel):
    """Document containing an arbitrary-value mapping."""

    key: keyword()
    values: mapping(any_field(), index=True, default={})
    plain: keyword()


@register_model(index=True, store=True)
class OrderedSchemaProbe(HowlerESModel):
    """Document with ordered dynamic sources for precedence checks."""

    first: mapping(keyword(), index=True, default={})
    second: mapping(keyword(), index=True, default={})


def test_field_count_and_total_fields_limit() -> None:
    """The schema field limit has a 1500 minimum and scales for large documents."""
    assert schema.total_fields_limit(None) == 1500
    assert schema.total_fields_limit(Hit) == max(1500, schema.flat_field_count(Hit) + 500)
    assert schema.flat_field_count(Hit) < 1000


def test_schema_less_collection_uses_shared_dynamic_templates() -> None:
    """Collections without a model use the default dynamic templates."""
    mappings = schema.document_mapping(None)
    assert mappings["dynamic_templates"] == schema.default_dynamic_templates
    assert mappings["dynamic"] is True


def test_document_mapping_disables_implicit_fields_without_dynamic_sources() -> None:
    """Models without dynamic sources add a rejecting template and remain dynamically configured."""
    mappings = schema.document_mapping(EdgeAnyHost)
    names = [next(iter(template)) for template in mappings["dynamic_templates"]]
    assert "refuse_all_implicit_mappings" in names
    assert mappings["dynamic"] is True


def test_document_mapping_stays_dynamic_when_mapping_templates_exist() -> None:
    """Dynamic mappings remain enabled when a model contributes typed map templates."""
    mappings = schema.document_mapping(Hit)
    names = [next(iter(template)) for template in mappings["dynamic_templates"]]
    assert "refuse_all_implicit_mappings" not in names
    assert mappings["dynamic"] is True


def test_dynamic_template_order_uses_model_field_declaration_order() -> None:
    """Templates for mapping fields follow their declaration order after the shared template."""
    mappings = schema.document_mapping(OrderedSchemaProbe)
    names = [next(iter(template)) for template in mappings["dynamic_templates"]]
    assert names == ["strings_as_keywords", "first.*_tpl", "second.*_tpl"]


def test_model_mapping_has_expected_hit_and_case_field_types() -> None:
    """Representative Hit and Case fields map to their intended Elasticsearch types."""
    hit_properties = schema.document_mapping(Hit)["properties"]
    case_properties = schema.document_mapping(Case)["properties"]

    assert hit_properties["howler.analytic"]["type"] == "keyword"
    assert hit_properties["howler.analytic"]["normalizer"] == "lowercase_normalizer"
    assert hit_properties["source.ip"]["type"] == "ip"
    assert hit_properties["file.hash.md5"]["normalizer"] == "lowercase_normalizer"
    assert case_properties["title"]["type"] == "text"
    assert case_properties["escalation"]["type"] == "keyword"
    assert case_properties["classification"]["type"] == "keyword"


@pytest.mark.parametrize(("model_type", "expected_names"), COLLECTION_TEMPLATE_ORDER)
def test_collection_dynamic_template_order_is_stable(model_type: Any, expected_names: list[str]) -> None:
    """Collection dynamic templates retain the precedence required by their mappings."""
    actual = schema.document_mapping(model_type)["dynamic_templates"]
    assert [next(iter(template)) for template in actual] == expected_names


def test_index_settings_include_shared_analysis_and_collection_limits() -> None:
    """Index settings include the shared normalizer and configured shard, replica, and field limits."""
    settings = schema.index_settings(Hit, shards=1, replicas=0)

    assert settings["analysis"]["normalizer"]["lowercase_normalizer"] == {
        "type": "custom",
        "char_filter": [],
        "filter": ["lowercase"],
    }
    assert settings["index"]["number_of_shards"] == 1
    assert settings["index"]["number_of_replicas"] == 0
    assert settings["index"]["mapping"]["total_fields"]["limit"] == schema.total_fields_limit(Hit)


def test_searchable_user_and_record_fields_copy_to_full_text_property() -> None:
    """User search fields and record/case classifications feed the full-text field."""
    user_properties = schema.document_mapping(User)["properties"]
    hit_properties = schema.document_mapping(Hit)["properties"]
    case_properties = schema.document_mapping(Case)["properties"]

    assert [user_properties[name]["copy_to"] for name in ("name", "uname", "email")] == ["__text__"] * 3
    assert hit_properties["classification"]["copy_to"] == "__text__"
    assert case_properties["classification"]["copy_to"] == "__text__"


def test_ilm_template_reuses_document_mapping() -> None:
    """An ILM template embeds the same mapping generated for an index."""
    body = schema.ilm_template_body(
        Hit,
        shards=1,
        replicas=0,
        policy_name="howler-hit-policy",
        rollover_alias="howler-hit",
    )

    assert body["mappings"] == schema.document_mapping(Hit)
    assert body["settings"]["index"]["lifecycle.name"] == "howler-hit-policy"
    assert body["settings"]["index"]["lifecycle.rollover_alias"] == "howler-hit"


def test_mapping_of_compound_recurses_into_declared_children() -> None:
    """A compound dynamic value gets one leaf template for each declared child field."""
    templates = schema._dynamic_templates("edge_case.*", EdgeChild, inherited_index=True, nested_template=False)
    assert templates == [
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


@pytest.mark.parametrize(
    "annotation",
    [list[keyword()], mapping(keyword())],
)
def test_nested_dynamic_containers_use_nested_templates(annotation: Any) -> None:
    """List and mapping values are represented by a nested template at their dynamic path."""
    assert schema._dynamic_templates("edge_case.*", annotation, inherited_index=True, nested_template=False) == [
        {"nested_edge_case.*": {"match": "edge_case.*", "mapping": {"type": "nested"}}}
    ]


def test_mapping_of_arbitrary_values_is_disabled() -> None:
    """A mapping of arbitrary values has no indexed dynamic source."""
    properties, dynamic_sources = schema.build_properties(EdgeAnyHost)
    assert properties["values"] == schema.DISABLED_OBJECT_MAPPING
    assert "values" not in dynamic_sources


def test_identifier_and_search_text_properties_are_always_added() -> None:
    """Synthetic document ID and full-text properties are present in every mapping."""
    for model_type in (Hit, None):
        properties = schema.document_mapping(model_type)["properties"]
        assert properties["id"] == {"store": True, "doc_values": True, "type": "keyword"}
        assert properties["__text__"] == {"store": False, "type": "text"}
