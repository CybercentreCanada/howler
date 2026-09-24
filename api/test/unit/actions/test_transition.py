from types import SimpleNamespace
from unittest.mock import patch

from howler.actions import transition
from howler.datastore.exceptions import VersionConflictException
from howler.models.user import User


@patch("howler.actions.transition.hit_service.transition_hit", side_effect=VersionConflictException("conflict"))
@patch("howler.actions.transition.datastore")
@patch("howler.actions.datastore")
def test_execute_reports_concurrent_update_as_error(mock_limit_datastore, mock_datastore, mock_transition_hit):
    hit_id = "concurrently-updated-hit"
    mock_datastore.return_value.hit.search.side_effect = [
        {"items": [SimpleNamespace(howler=SimpleNamespace(id=hit_id))], "total": 1},
        {"total": 0},
    ]
    mock_limit_datastore.return_value.hit.search.return_value = {"total": 1}
    user = User.validate_howler({"uname": "admin", "name": "Administrator", "password": "password", "type": ["admin"]})

    report = transition.execute(
        query="howler.id:*",
        status="in-progress",
        transition="release",
        user=user,
    )

    assert mock_transition_hit.call_count == transition.MAX_VERSION_CONFLICT_ATTEMPTS
    mock_datastore.return_value.hit.commit.assert_called_once()
    assert report == [
        {
            "query": f"howler.id:{hit_id}",
            "outcome": "error",
            "title": "Version Conflict",
            "message": "The hit was modified while this transition was running.",
        }
    ]


@patch("howler.actions.transition.hit_service.transition_hit", side_effect=[VersionConflictException("conflict"), None])
@patch("howler.actions.transition.datastore")
@patch("howler.actions.datastore")
def test_execute_retries_concurrent_update(mock_limit_datastore, mock_datastore, mock_transition_hit):
    hit_id = "concurrently-updated-hit"
    mock_datastore.return_value.hit.search.side_effect = [
        {"items": [SimpleNamespace(howler=SimpleNamespace(id=hit_id))], "total": 1},
        {"total": 0},
    ]
    mock_limit_datastore.return_value.hit.search.return_value = {"total": 1}
    user = User.validate_howler({"uname": "admin", "name": "Administrator", "password": "password", "type": ["admin"]})

    report = transition.execute(
        query="howler.id:*",
        status="in-progress",
        transition="release",
        user=user,
    )

    assert mock_transition_hit.call_count == 2
    assert report[0]["outcome"] == "success"
