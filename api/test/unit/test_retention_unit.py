from unittest.mock import MagicMock, patch

from howler.cronjobs.retention import _delete_matching_hits
from howler.odm.models.case import CaseItemTypes


@patch("howler.cronjobs.retention.case_service.remove_case_items")
def test_delete_matching_hits_cleans_related_hits_and_case_items(mock_remove_case_items):
    datastore = MagicMock()
    expired_hit = MagicMock()
    expired_hit.howler.id = "expired-hit"
    datastore.hit.stream_search.return_value = iter([expired_hit])

    case = MagicMock()
    hit_item = MagicMock(id="hit-item", type=CaseItemTypes.HIT, value="expired-hit")
    event_item = MagicMock(id="event-item", type=CaseItemTypes.EVENT, value="expired-hit")
    retained_item = MagicMock(id="retained-item", type=CaseItemTypes.HIT, value="retained-hit")
    case.items = [hit_item, event_item, retained_item]
    datastore.case.stream_search.return_value = iter([case])

    _delete_matching_hits(datastore, "event.created:{* TO 2020-01-01}")

    mock_remove_case_items.assert_called_once_with(case, ["hit-item"])
    datastore.hit.update_by_query.assert_called_once()
    update_query, operations = datastore.hit.update_by_query.call_args.args
    assert update_query == "howler.related:(expired-hit)"
    assert len(operations) == 1
    datastore.hit.delete_by_query.assert_called_once_with("event.created:{* TO 2020-01-01}")
    datastore.hit.commit.assert_called_once_with()
