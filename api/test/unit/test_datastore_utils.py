"""Unit tests for datastore field-selection utilities."""

from howler.datastore.utils import expand_field_patterns, prune_to_paths
from howler.odm import Compound, Keyword, List, model
from howler.odm.base import Model


@model()
class _Item(Model):
    item_type = Keyword()
    value = Keyword()


@model()
class _Document(Model):
    title = Keyword()
    category = Keyword()
    items = List(Compound(_Item))


def test_expand_field_patterns_expands_wildcards_and_keeps_exact_fields():
    expanded = expand_field_patterns(_Document, ["items.*", "title", "__non_doc_raw__"])

    assert expanded == {"items.item_type", "items.value", "title", "__non_doc_raw__"}


def test_expand_field_patterns_omits_unmatched_wildcards():
    expanded = expand_field_patterns(_Document, ["missing.*"])

    assert expanded == set()


def test_expand_field_patterns_omits_unmatched_patterns_when_model_is_provided():
    expanded = expand_field_patterns(_Document, ["items.*", "missing.*"])

    assert expanded == {"items.item_type", "items.value"}


def test_expand_field_patterns_expands_bare_star_by_default():
    expanded = expand_field_patterns(_Document, ["*"])

    assert expanded == set(_Document.flat_fields())


def test_expand_field_patterns_preserves_bare_star_when_requested():
    expanded = expand_field_patterns(_Document, ["*"], preserve_all=True)

    assert expanded == {"*"}


def test_expand_field_patterns_without_model_keeps_patterns_literal():
    expanded = expand_field_patterns(None, ["items.*", "__non_doc_raw__"])

    assert expanded == {"items.*", "__non_doc_raw__"}


def test_prune_to_paths_keeps_selected_subtree():
    value = {
        "title": "Alert",
        "items": [{"item_type": "hit", "value": "hit-1"}],
        "owner": {"id": "user-1", "name": "Analyst"},
    }

    pruned = prune_to_paths(value, {"items"})

    assert pruned == {"items": [{"item_type": "hit", "value": "hit-1"}]}


def test_prune_to_paths_prunes_nested_dicts_and_list_entries():
    value = {
        "title": "Alert",
        "items": [
            {"item_type": "hit", "value": "hit-1"},
            {"item_type": "event", "value": "event-1"},
        ],
        "owner": {"id": "user-1", "name": "Analyst"},
    }

    pruned = prune_to_paths(value, {"items.item_type", "owner.id"})

    assert pruned == {
        "items": [{"item_type": "hit"}, {"item_type": "event"}],
        "owner": {"id": "user-1"},
    }
