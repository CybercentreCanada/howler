"""Unit tests for the add_to_bundle action."""

from unittest.mock import MagicMock, patch

from howler.actions.add_to_bundle import execute, specification
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


@patch("howler.actions.add_to_bundle.bundle_compat_service")
def test_execute_case_not_found_for_bundle(mock_compat):
    """Returns an error report when find_case_for_bundle returns None."""
    mock_compat.find_case_for_bundle.return_value = None

    result = execute("howler.id:*", bundle_id="bundle-001")

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "error"
    assert r["title"] == "Invalid Bundle"


@patch("howler.actions.add_to_bundle.case_service")
@patch("howler.actions.add_to_bundle.datastore")
@patch("howler.actions.add_to_bundle.bundle_compat_service")
def test_execute_no_matching_hits(mock_compat, mock_ds_fn, mock_case_svc):
    """Returns a skipped report when the query returns no matching hits."""
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


@patch("howler.actions.add_to_bundle.case_service")
@patch("howler.actions.add_to_bundle.datastore")
@patch("howler.actions.add_to_bundle.check_hit_limit")
@patch("howler.actions.add_to_bundle.bundle_compat_service")
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


@patch("howler.actions.add_to_bundle.case_service")
@patch("howler.actions.add_to_bundle.datastore")
@patch("howler.actions.add_to_bundle.bundle_compat_service")
def test_execute_not_found_exception(mock_compat, mock_ds_fn, mock_case_svc):
    """Returns an error report when NotFoundException is raised during execution."""
    mock_compat.find_case_for_bundle.side_effect = NotFoundException("Bundle not found")

    result = execute("howler.id:*", bundle_id="bundle-001")

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "error"
    assert r["title"] == "Failed to Execute"
    assert "Bundle not found" in r["message"]


@patch("howler.actions.add_to_bundle.case_service")
@patch("howler.actions.add_to_bundle.datastore")
@patch("howler.actions.add_to_bundle.bundle_compat_service")
def test_execute_adds_hits_successfully(mock_compat, mock_ds_fn, mock_case_svc):
    """Returns a success report when all matching hits are added."""
    mock_case = MagicMock()
    mock_compat.find_case_for_bundle.return_value = mock_case

    mock_ds = MagicMock()
    mock_ds_fn.return_value = mock_ds

    hit1 = MagicMock()
    hit1.howler.id = "hit-001"
    hit1.howler.analytic = "TestAnalytic"

    mock_ds.hit.search.return_value = {"items": [hit1]}

    folder = MagicMock()
    folder.id = "folder-uuid"
    mock_case_svc.get_parent_from_path.return_value = folder

    result = execute("howler.analytic:TestAnalytic", bundle_id="bundle-001")

    assert any(r["outcome"] == "success" for r in result)
    mock_case_svc.append_case_item.assert_called_once()


def test_specification():
    """Verifies the action specification is correctly structured."""
    spec = specification()

    assert spec["id"] == "add_to_bundle"
    assert "title" in spec
    assert "roles" in spec
    assert "steps" in spec
