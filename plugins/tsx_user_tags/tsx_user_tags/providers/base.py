"""Abstract base classes for tag providers."""

from abc import ABC, abstractmethod


class PortfolioProvider(ABC):
    """Abstract provider for portfolio/customer tag values.

    Implement this class to supply portfolio options from any data source
    (e.g., analytics datastore, static config, external API).
    """

    @abstractmethod
    def fetch(self) -> list[dict[str, str]]:
        """Fetch all available portfolio options.

        Returns:
            List of {"value": str, "name": str} objects.
        """

    @abstractmethod
    def get_valid_values(self) -> set[str]:
        """Get the set of valid portfolio value keys for validation.

        Returns:
            Set of valid value strings.
        """


class ProductProvider(ABC):
    """Abstract provider for product tag values.

    Implement this class to supply product options from any data source.
    """

    @abstractmethod
    def fetch(self) -> list[dict[str, str]]:
        """Fetch all available product options.

        Returns:
            List of {"value": str, "name": str} objects.
        """

    @abstractmethod
    def get_valid_values(self) -> set[str]:
        """Get the set of valid product value keys for validation.

        Returns:
            Set of valid value strings.
        """


class DisciplineProvider(ABC):
    """Abstract provider for primary discipline tag values.

    Implement this class to supply discipline options from any data source.
    """

    @abstractmethod
    def fetch(self) -> list[dict[str, str]]:
        """Fetch all available discipline options.

        Returns:
            List of {"value": str, "name": str} objects.
        """

    @abstractmethod
    def get_valid_values(self) -> set[str]:
        """Get the set of valid discipline value keys for validation.

        Returns:
            Set of valid value strings.
        """
