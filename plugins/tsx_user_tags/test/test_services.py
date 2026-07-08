"""Unit tests for tsx_user_tags services and providers."""

from unittest.mock import MagicMock, patch

import pytest

from tsx_user_tags.providers.analytics import (
    AnalyticsPortfolioProvider,
    AnalyticsProductProvider,
)
from tsx_user_tags.providers.static import (
    StaticDisciplineProvider,
    StaticPortfolioProvider,
    StaticProductProvider,
)
from tsx_user_tags.services import TagService

# --- Provider fixtures ---


@pytest.fixture()
def static_portfolio_provider():
    """Create a StaticPortfolioProvider with test data."""
    return StaticPortfolioProvider({"acme_corp": "ACME Corp", "widget_inc": "Widget Inc"})


@pytest.fixture()
def static_product_provider():
    """Create a StaticProductProvider with test data."""
    return StaticProductProvider(
        {
            "crowdstrike": "CrowdStrike",
            "elastic": "Elastic",
            "sentinel": "Microsoft Sentinel",
        }
    )


@pytest.fixture()
def static_discipline_provider():
    """Create a StaticDisciplineProvider with test data."""
    return StaticDisciplineProvider(
        {
            "identity": "Identity",
            "malware": "Malware",
            "network": "Network",
        }
    )


def _make_tag_service(portfolio=None, product=None, discipline=None):
    """Helper to build a TagService with optional overrides."""
    return TagService(
        portfolio_provider=portfolio or StaticPortfolioProvider({}),
        product_provider=product or StaticProductProvider({}),
        discipline_provider=discipline or StaticDisciplineProvider({}),
    )


# --- Static Provider Tests ---


class TestStaticPortfolioProvider:
    """Tests for StaticPortfolioProvider."""

    def test_fetch_empty(self):
        """Test fetch returns empty list when no items configured."""
        provider = StaticPortfolioProvider({})
        assert provider.fetch() == []

    def test_fetch_returns_list_format(self, static_portfolio_provider):
        """Test fetch returns list of {value, name} objects."""
        result = static_portfolio_provider.fetch()
        assert len(result) == 2
        assert {"value": "acme_corp", "name": "ACME Corp"} in result
        assert {"value": "widget_inc", "name": "Widget Inc"} in result

    def test_get_valid_values(self, static_portfolio_provider):
        """Test get_valid_values returns set of keys."""
        result = static_portfolio_provider.get_valid_values()
        assert result == {"acme_corp", "widget_inc"}


class TestStaticProductProvider:
    """Tests for StaticProductProvider."""

    def test_fetch_empty(self):
        """Test fetch returns empty list when no items configured."""
        provider = StaticProductProvider({})
        assert provider.fetch() == []

    def test_fetch_returns_list_format(self, static_product_provider):
        """Test fetch returns list of {value, name} objects."""
        result = static_product_provider.fetch()
        assert len(result) == 3
        assert {"value": "crowdstrike", "name": "CrowdStrike"} in result
        assert {"value": "elastic", "name": "Elastic"} in result
        assert {"value": "sentinel", "name": "Microsoft Sentinel"} in result

    def test_get_valid_values(self, static_product_provider):
        """Test get_valid_values returns set of configured keys."""
        result = static_product_provider.get_valid_values()
        assert result == {"crowdstrike", "elastic", "sentinel"}


class TestStaticDisciplineProvider:
    """Tests for StaticDisciplineProvider."""

    def test_fetch_empty(self):
        """Test fetch returns empty list when no items configured."""
        provider = StaticDisciplineProvider({})
        assert provider.fetch() == []

    def test_fetch_returns_list_format(self, static_discipline_provider):
        """Test fetch returns list of {value, name} objects."""
        result = static_discipline_provider.fetch()
        assert len(result) == 3
        assert {"value": "identity", "name": "Identity"} in result
        assert {"value": "malware", "name": "Malware"} in result
        assert {"value": "network", "name": "Network"} in result

    def test_get_valid_values(self, static_discipline_provider):
        """Test get_valid_values returns set of configured keys."""
        result = static_discipline_provider.get_valid_values()
        assert result == {"identity", "malware", "network"}


# --- Analytics Provider Tests ---


class TestAnalyticsPortfolioProvider:
    """Tests for AnalyticsPortfolioProvider."""

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_fetch_returns_list_format(self, mock_datastore):
        """Test fetch returns list of {value, name} objects from analytics."""
        mock_ds = MagicMock()
        mock_ds.analytic.search.return_value = {
            "items": [
                {"name": "ACME Corp"},
                {"name": "Widget Inc"},
                {"name": "Test Company"},
            ]
        }
        mock_datastore.return_value = mock_ds

        provider = AnalyticsPortfolioProvider()
        result = provider.fetch()

        assert len(result) == 3
        # Should be sorted alphabetically by name
        assert result[0] == {"value": "ACME Corp", "name": "ACME Corp"}
        assert result[1] == {"value": "Test Company", "name": "Test Company"}
        assert result[2] == {"value": "Widget Inc", "name": "Widget Inc"}

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_fetch_filters_empty_names(self, mock_datastore):
        """Test fetch filters out empty/None names."""
        mock_ds = MagicMock()
        mock_ds.analytic.search.return_value = {
            "items": [
                {"name": "ACME Corp"},
                {"name": ""},
                {"name": None},
                {"other": "no name field"},
                {"name": "Widget Inc"},
            ]
        }
        mock_datastore.return_value = mock_ds

        provider = AnalyticsPortfolioProvider()
        result = provider.fetch()

        assert len(result) == 2
        assert {"value": "ACME Corp", "name": "ACME Corp"} in result
        assert {"value": "Widget Inc", "name": "Widget Inc"} in result

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_fetch_deduplicates(self, mock_datastore):
        """Test fetch returns unique names only."""
        mock_ds = MagicMock()
        mock_ds.analytic.search.return_value = {
            "items": [
                {"name": "ACME Corp"},
                {"name": "ACME Corp"},
                {"name": "Widget Inc"},
                {"name": "ACME Corp"},
            ]
        }
        mock_datastore.return_value = mock_ds

        provider = AnalyticsPortfolioProvider()
        result = provider.fetch()

        assert len(result) == 2

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_fetch_returns_empty_on_error(self, mock_datastore):
        """Test fetch returns empty list on datastore error."""
        mock_ds = MagicMock()
        mock_ds.analytic.search.side_effect = Exception("Connection failed")
        mock_datastore.return_value = mock_ds

        provider = AnalyticsPortfolioProvider()
        result = provider.fetch()

        assert result == []

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_get_valid_values(self, mock_datastore):
        """Test get_valid_values returns raw analytics names."""
        mock_ds = MagicMock()
        mock_ds.analytic.search.return_value = {"items": [{"name": "ACME Corp"}, {"name": "Widget Inc"}]}
        mock_datastore.return_value = mock_ds

        provider = AnalyticsPortfolioProvider()
        result = provider.get_valid_values()

        assert result == {"ACME Corp", "Widget Inc"}


class TestAnalyticsProductProvider:
    """Tests for AnalyticsProductProvider."""

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_fetch_returns_sorted_list(self, mock_datastore):
        """Test fetch returns sorted list of event providers."""
        mock_ds = MagicMock()
        mock_ds.hit.facet.return_value = {
            "MSGraphAlertCollector": 16,
            "CrowdStrikeAlertV2": 16,
        }
        mock_datastore.return_value = mock_ds

        provider = AnalyticsProductProvider()
        result = provider.fetch()

        assert len(result) == 2
        assert result[0] == {
            "value": "CrowdStrikeAlertV2",
            "name": "CrowdStrikeAlertV2",
        }
        assert result[1] == {
            "value": "MSGraphAlertCollector",
            "name": "MSGraphAlertCollector",
        }

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_fetch_empty(self, mock_datastore):
        """Test fetch returns empty list when no providers exist."""
        mock_ds = MagicMock()
        mock_ds.hit.facet.return_value = {}
        mock_datastore.return_value = mock_ds

        provider = AnalyticsProductProvider()
        result = provider.fetch()

        assert result == []

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_fetch_returns_empty_on_error(self, mock_datastore):
        """Test fetch returns empty list on datastore error."""
        mock_ds = MagicMock()
        mock_ds.hit.facet.side_effect = Exception("Connection failed")
        mock_datastore.return_value = mock_ds

        provider = AnalyticsProductProvider()
        result = provider.fetch()

        assert result == []

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_get_valid_values(self, mock_datastore):
        """Test get_valid_values returns set of provider keys."""
        mock_ds = MagicMock()
        mock_ds.hit.facet.return_value = {
            "CrowdStrikeAlertV2": 16,
            "MSGraphAlertCollector": 16,
        }
        mock_datastore.return_value = mock_ds

        provider = AnalyticsProductProvider()
        result = provider.get_valid_values()

        assert result == {"CrowdStrikeAlertV2", "MSGraphAlertCollector"}

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_facet_called_with_correct_args(self, mock_datastore):
        """Test that facet is called with correct field and parameters."""
        mock_ds = MagicMock()
        mock_ds.hit.facet.return_value = {}
        mock_datastore.return_value = mock_ds

        provider = AnalyticsProductProvider()
        provider.fetch()

        mock_ds.hit.facet.assert_called_once_with("event.provider", mincount=1, rows=1000)


# --- TagService Tests ---


class TestTagServiceInit:
    """Tests for TagService initialization."""

    def test_init_stores_providers(
        self,
        static_portfolio_provider,
        static_product_provider,
        static_discipline_provider,
    ):
        """Test that TagService stores provider references."""
        service = TagService(
            portfolio_provider=static_portfolio_provider,
            product_provider=static_product_provider,
            discipline_provider=static_discipline_provider,
        )
        assert service._portfolios is static_portfolio_provider
        assert service._products is static_product_provider
        assert service._disciplines is static_discipline_provider


class TestTagServiceFetchAll:
    """Tests for TagService.fetch_all method."""

    def test_fetch_all_returns_combined_response(
        self,
        static_portfolio_provider,
        static_product_provider,
        static_discipline_provider,
    ):
        """Test fetch_all returns all three tag categories."""
        service = TagService(
            portfolio_provider=static_portfolio_provider,
            product_provider=static_product_provider,
            discipline_provider=static_discipline_provider,
        )

        result = service.fetch_all()

        assert "portfolio" in result
        assert "products" in result
        assert "primary_disciplines" in result
        assert len(result["portfolio"]) == 2
        assert len(result["products"]) == 3
        assert len(result["primary_disciplines"]) == 3

    def test_fetch_all_empty_providers(self):
        """Test fetch_all with empty providers returns empty lists."""
        service = _make_tag_service()
        result = service.fetch_all()

        assert result == {
            "portfolio": [],
            "products": [],
            "primary_disciplines": [],
        }

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_fetch_all_with_analytics_provider(self, mock_datastore):
        """Test fetch_all with analytics portfolio provider."""
        mock_ds = MagicMock()
        mock_ds.analytic.search.return_value = {"items": [{"name": "ACME Corp"}]}
        mock_datastore.return_value = mock_ds

        service = TagService(
            portfolio_provider=AnalyticsPortfolioProvider(),
            product_provider=StaticProductProvider({"crowdstrike": "CrowdStrike"}),
            discipline_provider=StaticDisciplineProvider({"identity": "Identity"}),
        )

        result = service.fetch_all()

        assert result["portfolio"] == [{"value": "ACME Corp", "name": "ACME Corp"}]
        assert result["products"] == [{"value": "crowdstrike", "name": "CrowdStrike"}]
        assert result["primary_disciplines"] == [{"value": "identity", "name": "Identity"}]


class TestTagServiceValidateTags:
    """Tests for TagService.validate_tags method."""

    def test_validate_tags_all_valid(self):
        """Test validate_tags returns success for all valid tags."""
        service = TagService(
            portfolio_provider=StaticPortfolioProvider({"acme_corp": "ACME Corp"}),
            product_provider=StaticProductProvider({"crowdstrike": "CrowdStrike"}),
            discipline_provider=StaticDisciplineProvider({"malware": "Malware"}),
        )

        tags = {
            "portfolio": ["acme_corp"],
            "products": ["crowdstrike"],
            "primary_disciplines": ["malware"],
        }
        is_valid, errors = service.validate_tags(tags)

        assert is_valid is True
        assert errors == []

    def test_validate_tags_invalid_portfolio(self):
        """Test validate_tags detects invalid portfolio values."""
        service = TagService(
            portfolio_provider=StaticPortfolioProvider({"acme_corp": "ACME Corp"}),
            product_provider=StaticProductProvider({}),
            discipline_provider=StaticDisciplineProvider({}),
        )

        tags = {"portfolio": ["acme_corp", "invalid_company"]}
        is_valid, errors = service.validate_tags(tags)

        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid portfolio values: invalid_company" in errors[0]

    def test_validate_tags_invalid_product(self):
        """Test validate_tags detects invalid product values."""
        service = _make_tag_service(product=StaticProductProvider({"crowdstrike": "CrowdStrike"}))

        tags = {"products": ["crowdstrike", "unknown_product"]}
        is_valid, errors = service.validate_tags(tags)

        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid products values: unknown_product" in errors[0]

    def test_validate_tags_invalid_discipline(self):
        """Test validate_tags detects invalid discipline values."""
        service = _make_tag_service(discipline=StaticDisciplineProvider({"malware": "Malware"}))

        tags = {"primary_disciplines": ["malware", "unknown_discipline"]}
        is_valid, errors = service.validate_tags(tags)

        assert is_valid is False
        assert len(errors) == 1
        assert "Invalid primary_disciplines values: unknown_discipline" in errors[0]

    def test_validate_tags_multiple_errors(self):
        """Test validate_tags collects all validation errors."""
        service = _make_tag_service()

        tags = {
            "portfolio": ["invalid_portfolio"],
            "products": ["invalid_product"],
            "primary_disciplines": ["invalid_discipline"],
        }
        is_valid, errors = service.validate_tags(tags)

        assert is_valid is False
        assert len(errors) == 3

    def test_validate_tags_empty_tags(self):
        """Test validate_tags returns success for empty tags dict."""
        service = _make_tag_service()
        is_valid, errors = service.validate_tags({})

        assert is_valid is True
        assert errors == []

    def test_validate_tags_partial_update(self):
        """Test validate_tags only validates present keys."""
        service = _make_tag_service(product=StaticProductProvider({"crowdstrike": "CrowdStrike"}))

        tags = {"products": ["crowdstrike"]}
        is_valid, errors = service.validate_tags(tags)

        assert is_valid is True
        assert errors == []

    def test_validate_tags_empty_list_is_valid(self):
        """Test validate_tags accepts empty lists as valid."""
        service = _make_tag_service()

        tags = {
            "portfolio": [],
            "products": [],
            "primary_disciplines": [],
        }
        is_valid, errors = service.validate_tags(tags)

        assert is_valid is True
        assert errors == []

    def test_validate_tags_unknown_tag_type(self):
        """Test validate_tags rejects unknown tag types."""
        service = _make_tag_service()

        tags = {"unknown_type": ["some_value"]}
        is_valid, errors = service.validate_tags(tags)

        assert is_valid is False
        assert len(errors) == 1
        assert "Unknown tag type: unknown_type" in errors[0]

    @patch("tsx_user_tags.providers.analytics.datastore")
    def test_validate_tags_with_analytics_provider(self, mock_datastore):
        """Test validate_tags works with analytics portfolio provider."""
        mock_ds = MagicMock()
        mock_ds.analytic.search.return_value = {"items": [{"name": "ACME Corp"}, {"name": "Widget Inc"}]}
        mock_datastore.return_value = mock_ds

        service = TagService(
            portfolio_provider=AnalyticsPortfolioProvider(),
            product_provider=StaticProductProvider({}),
            discipline_provider=StaticDisciplineProvider({}),
        )

        tags = {"portfolio": ["ACME Corp", "invalid_one"]}
        is_valid, errors = service.validate_tags(tags)

        assert is_valid is False
        assert "Invalid portfolio values: invalid_one" in errors[0]
