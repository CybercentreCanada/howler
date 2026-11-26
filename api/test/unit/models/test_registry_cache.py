"""Cached traversal stays isolated across finalized classes, flags and registrations."""

from __future__ import annotations

import operator

import pytest

from howler.datastore.collection import _strip_lists
from howler.models import HowlerEmbeddedModel, HowlerESModel, ModelExtensionRegistry, enum, keyword, mapping
from howler.models.fields import HowlerFieldMetadata
from howler.models.registry import ModelRegistry, annotation_metadata, model_registry


class Child(HowlerEmbeddedModel):
    scalar: keyword()


class Document(HowlerESModel):
    child: Child
    labels: mapping(keyword(), default={})


@pytest.fixture(scope="module")
def derived():
    extensions = ModelExtensionRegistry()
    extensions.declare(Document, "names", list[keyword()], plugin="names")
    return extensions.finalize(Document)


@pytest.mark.parametrize("show_compound", [True, False])
@pytest.mark.parametrize("skip_mappings", [True, False])
def test_cached_traversals_match_cold_results_for_each_concrete_class_and_flags(derived, show_compound, skip_mappings):
    flags = {"show_compound": show_compound, "skip_mappings": skip_mappings}
    for model in (Document, derived):
        expected = {"child.scalar"}
        if not skip_mappings:
            expected.add("labels")
        if show_compound:
            expected.add("child")
        if model is derived:
            expected.add("names")
        view = model_registry.flat_field_view(model, **flags)
        assert set(view) == expected
        assert model_registry.flat_field_view(model, **flags) is view
        with pytest.raises(TypeError):
            operator.delitem(view, "child.scalar")
        model_registry.flat_fields(model, **flags).clear()
        assert set(view) == expected


def test_finalized_extension_list_multiplicity_is_isolated_from_base(derived):
    fields = {"child.scalar": ["s"], "names": ["first", "second"]}
    assert _strip_lists(Document, fields) == {"child": {"scalar": "s"}, "names": "first"}
    assert _strip_lists(derived, fields) == {"child": {"scalar": "s"}, "names": ["first", "second"]}


def test_mutating_an_inspected_default_does_not_change_models_or_cached_views():
    definition = model_registry.flat_field_view(Document)["labels"]
    definition.default["changed"] = "elsewhere"
    assert definition.default == {}
    assert Document.model_fields["labels"].default == {}


def test_nested_enum_options_cannot_mutate_cached_metadata_or_validator():
    class Options(HowlerESModel):
        value: enum([{"tags": ["original"]}])
        labels: mapping(enum([{"tags": ["original"]}]))

    for fields in (model_registry.fields(Options), model_registry.flat_field_view(Options)):
        dict(fields["value"].metadata.options)["values"][0]["tags"].append("changed")
        assert dict(fields["value"].metadata.options)["values"] == ({"tags": ["original"]},)
        # A Mapping's child keeps its constraints in the annotation rather than the parent metadata.
        child = next(
            item for item in annotation_metadata(fields["labels"].annotation) if isinstance(item, HowlerFieldMetadata)
        )
        dict(child.options)["values"][0]["tags"].clear()
    data = {"tags": ["original"]}
    result = Options.model_validate({"value": data, "labels": {"key": data}})
    assert result.value == result.labels["key"] == str(data)


def test_child_reregistration_invalidates_parent_traversals_and_clear_removes_defaults():
    registry = ModelRegistry()
    registry.register(Child, store=True, embedded=True)
    original = registry.flat_field_view(Document)
    assert original["child.scalar"].metadata.store is True

    registry.register(Child, store=False, embedded=True)
    updated = registry.flat_field_view(Document)
    assert updated["child.scalar"].metadata.store is False
    assert original["child.scalar"].metadata.store is True
    assert registry.fields(Child)["scalar"].metadata.store is False

    registry.clear()
    assert registry.flat_field_view(Document)["child.scalar"].metadata.store is None
    assert registry.fields(Child)["scalar"].metadata.store is None


def test_empty_stored_fields_do_not_require_a_schema():
    assert _strip_lists(object, {}) == {}
