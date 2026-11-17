from unittest.mock import MagicMock, patch

from howler.models import construct_partial
from howler.models.hit import Hit
from howler.services import overview_service


def test_matching_overviews_uses_analytic_names_from_hit_models():
    hit = construct_partial(Hit, {"howler": {"analytic": "Example Analytic"}})
    storage = MagicMock()
    storage.overview.search.return_value = {"items": [{"overview_id": "overview-1"}]}

    with patch.object(overview_service, "datastore", return_value=storage):
        result = overview_service.get_matching_overviews([hit])

    assert result == [{"overview_id": "overview-1"}]
    storage.overview.search.assert_called_once_with('analytic:("Example Analytic")', as_obj=False)
