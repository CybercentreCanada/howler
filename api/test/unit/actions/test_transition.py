from unittest.mock import patch

from howler.actions import transition
from howler.odm.models.howler_data import HitStatusTransition
from howler.odm.models.user import User


@patch("howler.actions.transition.hit_service.transition_hits")
@patch("howler.actions.transition.datastore")
def test_execute_transitions_matching_hits_in_bulk(mock_datastore, mock_transition_hits):
    hit_id = "matching-hit"
    hit = {"howler": {"id": hit_id, "status": "in-progress"}}
    mock_datastore.return_value.hit.search.side_effect = [
        {"items": [hit], "total": 1},
        {"total": 0},
    ]
    user = User({"uname": "admin", "name": "Administrator", "password": "password", "type": ["admin"]})

    report = transition.execute(
        query="howler.id:*",
        status="in-progress",
        transition="release",
        user=user,
    )

    mock_transition_hits.assert_called_once_with(
        [hit],
        HitStatusTransition.RELEASE,
        user,
        refresh="wait_for",
    )
    assert report == [
        {
            "query": f"howler.id:({hit_id})",
            "outcome": "success",
            "title": "Transition Executed Successfully",
            "message": "The transition release successfully executed on 1 hits.",
        }
    ]
