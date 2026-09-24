"""Analytics generated from registered Hit models retain the stored contract."""

from unittest.mock import MagicMock, patch

from howler.models import construct_partial
from howler.models.hit import Hit
from howler.models.user import User
from howler.services import analytic_service


def test_save_from_pydantic_hits_uses_typed_analytic():
    hit = construct_partial(Hit, {"howler": {"analytic": "New Analytic", "detection": "New Detection"}})
    user = User.validate_howler({"uname": "analyst", "name": "Analyst", "password": "hash"})
    storage = MagicMock()
    storage.analytic.search.return_value = {"items": []}

    with patch.object(analytic_service, "datastore", return_value=storage):
        analytic_service.save_from_hits([hit], user)

    plan = storage.analytic.get_bulk_plan.return_value
    action_id, analytic = plan.add_index_operation.call_args.args
    assert action_id == analytic.analytic_id
    assert analytic.name == "New Analytic"
    assert analytic.owner == "analyst"
    assert analytic.detections == ["New Detection"]
    assert analytic.triage_settings.valid_assessments


def test_matching_analytics_accepts_pydantic_hits():
    hit = construct_partial(Hit, {"howler": {"analytic": "New Analytic"}})
    storage = MagicMock()
    storage.analytic.search.return_value = {"items": []}

    with patch.object(analytic_service, "datastore", return_value=storage):
        assert analytic_service.get_matching_analytics([hit]) == []

    assert storage.analytic.search.call_args.args[0] == 'name:("New Analytic")'
