"""Unit tests for ESCollection._expand_fl wildcard expansion."""

from unittest.mock import MagicMock, patch

from howler.datastore.collection import ESCollection
from howler.odm import Compound, Keyword, model
from howler.odm.base import Model


@model()
class _Inner(Model):
    """Simple nested model used for wildcard expansion tests."""

    field_a = Keyword()
    field_b = Keyword()


@model()
class _TestModel(Model):
    """Top-level model used for wildcard expansion tests."""

    id = Keyword()
    prefix_one = Keyword()
    prefix_two = Keyword()
    nested = Compound(_Inner)


def _make_collection():
    """Create an ESCollection backed by the test model without hitting ES."""
    mock_datastore = MagicMock()
    with (
        patch.object(ESCollection, "_ensure_collection"),
        patch.object(ESCollection, "_check_fields"),
    ):
        coll = ESCollection(mock_datastore, "test", model_class=_TestModel)
    return coll


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_expand_fl_no_wildcard_returns_unchanged():
    """Field list without wildcards must pass through unchanged."""
    coll = _make_collection()
    assert coll._expand_fl("id,prefix_one") == "id,prefix_one"


def test_expand_fl_star_expands_prefix():
    """'prefix_*' must expand to all fields whose names start with 'prefix_'."""
    coll = _make_collection()
    result = coll._expand_fl("prefix_*")
    expanded = set(result.split(","))
    assert "prefix_one" in expanded
    assert "prefix_two" in expanded
    assert "id" not in expanded
    assert "nested.field_a" not in expanded


def test_expand_fl_nested_wildcard():
    """'nested.*' must expand to all sub-fields of the nested compound."""
    coll = _make_collection()
    result = coll._expand_fl("nested.*")
    expanded = set(result.split(","))
    assert "nested.field_a" in expanded
    assert "nested.field_b" in expanded
    assert "id" not in expanded
    assert "prefix_one" not in expanded


def test_expand_fl_mixed_wildcard_and_exact():
    """Wildcards and exact names may be combined in the same fl string."""
    coll = _make_collection()
    result = coll._expand_fl("id,prefix_*")
    expanded = set(result.split(","))
    assert "id" in expanded
    assert "prefix_one" in expanded
    assert "prefix_two" in expanded
    assert "nested.field_a" not in expanded


def test_expand_fl_global_wildcard():
    """A bare '*' must be preserved unchanged so that existing 'all fields' semantics are maintained."""
    coll = _make_collection()
    result = coll._expand_fl("*")
    assert result == "*"


def test_expand_fl_unmatched_wildcard_kept_as_is():
    """Wildcard with no matches must be kept in the result list unchanged."""
    coll = _make_collection()
    result = coll._expand_fl("nonexistent.*")
    assert result == "nonexistent.*"


def test_expand_fl_no_model_class_returns_unchanged():
    """Without a model class, _expand_fl must return the original string."""
    mock_datastore = MagicMock()
    with (
        patch.object(ESCollection, "_ensure_collection"),
        patch.object(ESCollection, "_check_fields"),
    ):
        coll = ESCollection(mock_datastore, "test", model_class=None)
    assert coll._expand_fl("prefix_*") == "prefix_*"


def test_expand_fl_multiple_wildcards():
    """Multiple wildcard patterns in a single fl string must all be expanded."""
    coll = _make_collection()
    result = coll._expand_fl("prefix_*,nested.*")
    expanded = set(result.split(","))
    assert "prefix_one" in expanded
    assert "prefix_two" in expanded
    assert "nested.field_a" in expanded
    assert "nested.field_b" in expanded
    assert "id" not in expanded
