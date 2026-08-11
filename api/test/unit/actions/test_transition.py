from types import SimpleNamespace
from unittest.mock import patch

from howler.actions import transition
from howler.datastore.exceptions import VersionConflictException
from howler.odm.models.user import User


@patch("howler.actions.transition.hit_service.transition_hit", side_effect=VersionConflictException("conflict"))
@patch("howler.actions.transition.datastore")
def test_execute_reports_concurrent_update_as_error(mock_datastore, mock_transition_hit):
    hit_id = "concurrently-updated-hit"
    mock_datastore.return_value.hit.search.side_effect = [
        {"items": [SimpleNamespace(howler=SimpleNamespace(id=hit_id))], "total": 1},
        {"total": 0},
    ]
    user = User({"uname": "admin", "name": "Administrator", "password": "password", "type": ["admin"]})

    report = transition.execute(
        query="howler.id:*",
        status="in-progress",
        transition="release",
        user=user,
    )

    mock_transition_hit.assert_called_once()
    mock_datastore.return_value.hit.commit.assert_called_once()
    assert report == [
        {
            "query": f"howler.id:{hit_id}",
            "outcome": "error",
            "title": "Version Conflict",
            "message": "The hit was modified while this transition was running.",
        }
    ]
