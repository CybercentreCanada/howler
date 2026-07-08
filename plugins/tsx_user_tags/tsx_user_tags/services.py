"""Service layer for User Tags plugin.

Provides the TagService class that orchestrates tag providers to fetch
and validate tag values for portfolio, products, and primary disciplines.
"""

from howler.common.logging import get_logger
from opentelemetry import trace

from tsx_user_tags.providers.base import (
    DisciplineProvider,
    PortfolioProvider,
    ProductProvider,
)

logger = get_logger(__file__)
tracer = trace.get_tracer(__name__)


class TagService:
    """Service for fetching and validating tag lists.

    Delegates to provider implementations for each tag type, allowing
    different deployments to use different data sources (static config,
    analytics datastore, external APIs, etc.).
    """

    def __init__(
        self,
        portfolio_provider: PortfolioProvider,
        product_provider: ProductProvider,
        discipline_provider: DisciplineProvider,
    ):
        """Initialize the TagService with providers.

        Args:
            portfolio_provider: Provider for portfolio/customer tag values.
            product_provider: Provider for product tag values.
            discipline_provider: Provider for primary discipline tag values.
        """
        self._portfolios = portfolio_provider
        self._products = product_provider
        self._disciplines = discipline_provider

    @tracer.start_as_current_span("fetch_all")
    def fetch_all(self) -> dict[str, list[dict[str, str]]]:
        """Fetch all available tags from all providers.

        Returns:
            Dictionary with portfolio, products, and primary_disciplines as lists
            of {"value": str, "name": str} objects.
        """
        return {
            "portfolio": self._portfolios.fetch(),
            "products": self._products.fetch(),
            "primary_disciplines": self._disciplines.fetch(),
        }

    @tracer.start_as_current_span("validate_tags")
    def validate_tags(self, tags: dict) -> tuple[bool, list[str]]:
        """Validate user tags against allowed values from providers.

        Checks that all submitted tag values exist in the controlled lists
        provided by each tag provider.

        Args:
            tags: Dictionary containing portfolio, products, and/or
                primary_disciplines lists.

        Returns:
            Tuple of (is_valid, list of error messages).
        """
        errors: list[str] = []
        validators = {
            "portfolio": self._portfolios,
            "products": self._products,
            "primary_disciplines": self._disciplines,
        }

        for key, values in tags.items():
            if key not in validators:
                errors.append(f"Unknown tag type: {key}")
                continue
            valid_values = validators[key].get_valid_values()
            invalid = set(values) - valid_values
            if invalid:
                errors.append(f"Invalid {key} values: {', '.join(sorted(invalid))}")

        return (len(errors) == 0, errors)
