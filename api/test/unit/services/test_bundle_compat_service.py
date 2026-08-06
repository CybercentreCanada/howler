"""Unit tests for the legacy bundle compatibility service."""

from unittest.mock import MagicMock, patch

from howler.odm.models.case import CaseItemTypes
from howler.services import bundle_compat_service


def test_synthesize_bundle_response_filters_children_for_user():
    case = MagicMock()
    case.case_id = "case-001"
    child = MagicMock(type=CaseItemTypes.HIT, value="restricted-hit")
    case.items = [child]

    root_hit = MagicMock()
    root_hit.howler.id = "root-hit"
    root_hit.as_primitives.return_value = {"howler": {}}
    user = MagicMock()

    with patch.object(
        bundle_compat_service.hit_service,
        "filter_accessible_hits",
        return_value=[],
    ) as filter_hits:
        result = bundle_compat_service.synthesize_bundle_response(case, root_hit, user=user)

    filter_hits.assert_called_once_with(user, ["restricted-hit"])
    assert result["howler"]["hits"] == []
    assert result["howler"]["bundle_size"] == 0


class TestFindCaseForBundle:
    @patch("howler.services.bundle_compat_service.datastore")
    @patch("howler.services.bundle_compat_service.hit_service.get_hit")
    def test_returns_none_without_related_cases(self, mock_get_hit, mock_datastore):
        """An unassociated hit must not generate an empty case-id query."""
        hit = MagicMock()
        hit.howler.related = []
        mock_get_hit.return_value = hit

        result = bundle_compat_service.find_case_for_bundle("hit-id")

        assert result is None
        mock_datastore.assert_not_called()
