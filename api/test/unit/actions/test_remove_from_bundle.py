"""Unit tests for the remove_from_bundle action."""

from unittest.mock import MagicMock, patch

from howler.actions.remove_from_bundle import execute, specification
from howler.common.exceptions import NotFoundException

# ---------------------------------------------------------------------------
# Validation – no live datastore required
# ---------------------------------------------------------------------------


def test_execute_missing_bundle_id():
    """Returns an error when bundle_id is not provided."""
    result = execute("howler.id:*")

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "error"
    assert r["title"] == "Invalid Bundle ID"


def test_execute_missing_bundle_id_empty_string():
    """Returns an error when bundle_id is an empty string."""
    result = execute("howler.id:*", bundle_id="")

    assert len(result) == 1
    assert result[0]["outcome"] == "error"
    assert result[0]["title"] == "Invalid Bundle ID"


@patch("howler.actions.remove_from_bundle.bundle_compat_service")
def test_execute_case_not_found_for_bundle(mock_compat):
    """Returns an error report when find_case_for_bundle returns None."""
    mock_compat.find_case_for_bundle.return_value = None

    result = execute("howler.id:*", bundle_id="bundle-001")

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "error"
    assert r["title"] == "Invalid Bundle"


@patch("howler.actions.remove_from_bundle.case_service")
@patch("howler.actions.remove_from_bundle.datastore")
@patch("howler.actions.remove_from_bundle.bundle_compat_service")
def test_execute_no_matching_hits(mock_compat, mock_ds_fn, mock_case_svc):
    """Returns a skipped report when the query matches no hits."""
    mock_case = MagicMock()
    mock_compat.find_case_for_bundle.return_value = mock_case

    mock_ds = MagicMock()
    mock_ds_fn.return_value = mock_ds
    mock_ds.hit.search.return_value = {"items": []}

    result = execute("howler.analytic:NoSuchThing", bundle_id="bundle-001")

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "skipped"
    assert r["title"] == "No Matching Hits"


@patch("howler.actions.remove_from_bundle.case_service")
@patch("howler.actions.remove_from_bundle.datastore")
@patch("howler.actions.remove_from_bundle.check_hit_limit")
@patch("howler.actions.remove_from_bundle.bundle_compat_service")
def test_execute_hit_limit_error_with_user(mock_compat, mock_limit, mock_ds_fn, mock_case_svc):
    """Returns the limit error immediately when the user exceeds the hit limit."""
    mock_case = MagicMock()
    mock_compat.find_case_for_bundle.return_value = mock_case

    limit_error = {
        "query": "howler.id:*",
        "outcome": "error",
        "title": "Hit Limit Exceeded",
        "message": "Too many hits.",
    }
    mock_limit.return_value = limit_error

    user = MagicMock()
    result = execute("howler.id:*", bundle_id="bundle-001", user=user)

    assert result == [limit_error]


@patch("howler.actions.remove_from_bundle.case_service")
@patch("howler.actions.remove_from_bundle.datastore")
@patch("howler.actions.remove_from_bundle.bundle_compat_service")
def test_execute_refreshed_case_not_found(mock_compat, mock_ds_fn, mock_case_svc):
    """Returns an error when the case disappears during refresh (ds.case.get returns None)."""
    mock_case = MagicMock()
    mock_case.case_id = "case-001"
    mock_compat.find_case_for_bundle.return_value = mock_case

    mock_ds = MagicMock()
    mock_ds_fn.return_value = mock_ds

    hit1 = MagicMock()
    hit1.howler.id = "hit-001"
    mock_ds.hit.search.return_value = {"items": [hit1]}

    # The refreshed case is gone
    mock_ds.case.get.return_value = None

    result = execute("howler.id:hit-001", bundle_id="bundle-001")

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "error"
    assert r["title"] == "Case Not Found"


@patch("howler.actions.remove_from_bundle.case_service")
@patch("howler.actions.remove_from_bundle.datastore")
@patch("howler.actions.remove_from_bundle.bundle_compat_service")
def test_execute_no_hits_in_bundle(mock_compat, mock_ds_fn, mock_case_svc):
    """Returns skipped when none of the matching hits are in the bundle."""
    mock_case = MagicMock()
    mock_case.case_id = "case-001"
    mock_compat.find_case_for_bundle.return_value = mock_case

    mock_ds = MagicMock()
    mock_ds_fn.return_value = mock_ds

    hit1 = MagicMock()
    hit1.howler.id = "hit-not-in-bundle"
    mock_ds.hit.search.return_value = {"items": [hit1]}

    refreshed_case = MagicMock()
    refreshed_case.items = []  # no items → hit is not in bundle
    mock_ds.case.get.return_value = refreshed_case

    result = execute("howler.id:hit-not-in-bundle", bundle_id="bundle-001")

    assert any(r["outcome"] == "skipped" for r in result)
    mock_case_svc.remove_case_items.assert_not_called()


@patch("howler.actions.remove_from_bundle.case_service")
@patch("howler.actions.remove_from_bundle.datastore")
@patch("howler.actions.remove_from_bundle.bundle_compat_service")
def test_execute_not_found_exception(mock_compat, mock_ds_fn, mock_case_svc):
    """Returns an error report when NotFoundException is raised during execution."""
    mock_compat.find_case_for_bundle.side_effect = NotFoundException("Bundle not found")

    result = execute("howler.id:*", bundle_id="bundle-001")

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "error"
    assert r["title"] == "Failed to Execute"


@patch("howler.actions.remove_from_bundle.case_service")
@patch("howler.actions.remove_from_bundle.datastore")
@patch("howler.actions.remove_from_bundle.bundle_compat_service")
def test_execute_removes_matching_hits(mock_compat, mock_ds_fn, mock_case_svc):
    """Returns a success report when matching hits are removed from the bundle."""
    mock_case = MagicMock()
    mock_case.case_id = "case-001"
    mock_compat.find_case_for_bundle.return_value = mock_case

    mock_ds = MagicMock()
    mock_ds_fn.return_value = mock_ds

    hit1 = MagicMock()
    hit1.howler.id = "hit-001"
    mock_ds.hit.search.return_value = {"items": [hit1]}

    case_item = MagicMock()
    case_item.value = "hit-001"
    case_item.id = "item-uuid-001"

    refreshed_case = MagicMock()
    refreshed_case.items = [case_item]
    mock_ds.case.get.return_value = refreshed_case

    result = execute("howler.id:hit-001", bundle_id="bundle-001")

    assert any(r["outcome"] == "success" for r in result)
    mock_case_svc.remove_case_items.assert_called_once()


def test_specification():
    """Verifies the action specification is correctly structured."""
    spec = specification()

    assert spec["id"] == "remove_from_bundle"
    assert "title" in spec
    assert "roles" in spec
    assert "steps" in spec
