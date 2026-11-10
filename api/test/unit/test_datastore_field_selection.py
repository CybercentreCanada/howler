"""Tests for schema-aware stored source selection and projection."""

from types import SimpleNamespace

import pytest

from howler import odm
from howler.datastore.exceptions import SearchException
from howler.datastore.utils import project_stored_fields, select_stored_fields


@odm.model(index=True, store=True)
class _Entry(odm.Model):
    name = odm.Keyword()
    secret = odm.Keyword(store=False)


@odm.model(index=True, store=True)
class _Container(odm.Model):
    labels = odm.Mapping(odm.Keyword())


@odm.model(index=True, store=True)
class _SelectionModel(odm.Model):
    name = odm.Keyword()
    not_stored = odm.Keyword(store=False)
    labels = odm.Mapping(odm.Keyword())
    container = odm.Optional(odm.Compound(_Container))
    entries = odm.List(odm.Compound(_Entry))


def _collection():
    return SimpleNamespace(
        model_class=_SelectionModel,
        stored_fields={name: field for name, field in _SelectionModel.flat_fields().items() if field.store},
    )


def test_mapping_descendant_selects_only_the_requested_dynamic_key():
    collection = _collection()

    assert select_stored_fields({"sample": collection}, "labels.team") == (
        ["labels.team"],
        {"sample": ["labels.team"]},
        False,
    )


def test_nested_mapping_descendant_is_accepted_without_widening_parent():
    collection = _collection()

    source_fields, allowed_by_index, _ = select_stored_fields({"sample": collection}, "container.labels.team")

    assert source_fields == ["container.labels.team"]
    assert allowed_by_index == {"sample": ["container.labels.team"]}


@pytest.mark.parametrize(
    ("selection", "expected"),
    [
        ("labels.*", {"team": "blue", "department": "ops", "team.name": "literal"}),
        ("labels.t*", {"team": "blue", "team.name": "literal"}),
        ("*.team", {"team": "blue"}),
        ("*team", {"team": "blue"}),
        ("labels.team.name", {"team.name": "literal"}),
        ("labels.missing*", None),
    ],
)
def test_mapping_selectors_project_actual_keys_without_widening(selection, expected):
    _, allowed, include_id = select_stored_fields({"sample": _collection()}, selection)
    item = {"__index": "sample", "labels": {"team": "blue", "department": "ops", "team.name": "literal"}}
    expected_item = {"__index": "sample"}
    if expected is not None:
        expected_item["labels"] = expected
    assert project_stored_fields([item], allowed, include_id, fields=selection) == [expected_item]


def test_scalar_descendant_is_not_treated_as_a_mapping_field():
    collection = _collection()

    assert select_stored_fields({"sample": collection}, "name.internal") == ([], {"sample": []}, False)


def test_explicit_non_stored_fields_are_rejected():
    with pytest.raises(SearchException, match="Field 'not_stored' is not stored"):
        select_stored_fields({"sample": _collection()}, "not_stored")


def test_compound_parent_selects_only_stored_descendants_inside_lists():
    collection = _collection()
    source_fields, allowed_by_index, include_id = select_stored_fields({"sample": collection}, "entries")
    item = {
        "__index": "sample",
        "id": "entry-id",
        "entries": [{"name": "allowed", "secret": "filtered"}, {"name": "also allowed", "secret": "filtered"}],
        "name": "not selected",
    }

    assert source_fields == ["entries.name"]
    assert allowed_by_index == {"sample": ["entries.name"]}
    assert include_id is False
    assert project_stored_fields([item], allowed_by_index, include_id, fields="entries") == [
        {"entries": [{"name": "allowed"}, {"name": "also allowed"}], "__index": "sample"}
    ]


@pytest.mark.parametrize("fields", [None, "", [], "*"])
def test_defaults_and_wildcards_select_only_stored_fields(fields):
    collection = _collection()

    source_fields, allowed_by_index, include_id = select_stored_fields({"sample": collection}, fields)

    assert set(source_fields) == set(collection.stored_fields)
    assert "not_stored" not in source_fields
    assert allowed_by_index == {"sample": source_fields}
    assert include_id is (fields == "*")


def test_synthetic_id_is_outside_source_projection():
    collection = _collection()

    assert select_stored_fields({"sample": collection}, "id") == ([], {"sample": []}, True)
    assert project_stored_fields(
        [{"__index": "sample", "id": "doc-id", "name": "not selected"}],
        {"sample": []},
        include_id=True,
        fields="id",
    ) == [{"id": "doc-id", "__index": "sample"}]


def test_projection_preserves_mapping_scope_and_removes_banned_fields_recursively():
    item = {
        "__index": "sample",
        "labels": {"team": "blue", "department": "ops", "__access_lvl__": 5},
        "nested": {"__access_req__": "secret"},
        "__access_grp1__": "secret",
    }

    assert project_stored_fields([item], {"sample": ["labels.team", "nested"]}, include_id=False, fields=None) == [
        {"labels": {"team": "blue"}, "nested": {}, "__index": "sample"}
    ]


def test_unknown_index_and_missing_multi_index_metadata_fail_closed():
    items = [
        {"__index": "unknown", "name": "must not leak"},
        {"name": "metadata missing"},
    ]

    assert project_stored_fields(items, {"sample": ["name"], "other": ["name"]}, include_id=False, fields=None) == [
        {"__index": "unknown"},
        {},
    ]
