from __future__ import annotations

import pytest

from howler.models import AnyField, HowlerESModel, Keyword, mapping, register_model, schema
from howler.models.case import Case
from howler.models.hit import Hit


@register_model(index=True, store=True)
class Ordered(HowlerESModel):
    first: mapping(Keyword, index=True, default={})
    second: mapping(Keyword, index=True, default={})
    arbitrary: mapping(AnyField, index=True, default={})


def test_dynamic_template_order_and_disabled_arbitrary_values():
    mappings = schema.document_mapping(Ordered)
    assert [next(iter(template)) for template in mappings["dynamic_templates"]] == [
        "strings_as_keywords",
        "first.*_tpl",
        "second.*_tpl",
    ]
    assert mappings["properties"]["arbitrary"] == schema.DISABLED_OBJECT_MAPPING
    case = schema.document_mapping(Case)
    assert [next(iter(template)) for template in case["dynamic_templates"]] == [
        "strings_as_keywords",
        "refuse_all_implicit_mappings",
    ]
    assert schema.document_mapping(None)["dynamic_templates"] == schema.default_dynamic_templates


@pytest.mark.parametrize("annotation", [list[Keyword], mapping(Keyword)])
def test_nested_dynamic_containers(annotation):
    assert schema._dynamic_templates("edge_case.*", annotation, inherited_index=True, nested_template=False) == [
        {"nested_edge_case.*": {"match": "edge_case.*", "mapping": {"type": "nested"}}}
    ]


def test_ilm_template_uses_document_mapping():
    body = schema.ilm_template_body(Hit, shards=1, replicas=0, policy_name="policy", rollover_alias="hits")
    assert body["mappings"] == schema.document_mapping(Hit)
    assert body["settings"]["index"]["lifecycle.name"] == "policy"
    assert body["settings"]["index"]["lifecycle.rollover_alias"] == "hits"
