"""Unit tests for the legacy bundle compatibility service."""

from unittest.mock import MagicMock, patch

from howler.services import bundle_compat_service


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
