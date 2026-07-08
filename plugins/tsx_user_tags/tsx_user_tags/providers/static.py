"""Static tag providers that read from configuration dictionaries."""

from tsx_user_tags.providers.base import (
    DisciplineProvider,
    PortfolioProvider,
    ProductProvider,
)


class StaticPortfolioProvider(PortfolioProvider):
    """Portfolio provider that reads from a static config dictionary.

    Use this when portfolios are a fixed/known list managed in configuration
    rather than dynamically fetched from a data source.
    """

    def __init__(self, items: dict[str, str]):
        """Initialize with a static dictionary.

        Args:
            items: Dictionary mapping value keys to display names.
        """
        self._items = items

    def fetch(self) -> list[dict[str, str]]:
        """Fetch portfolio options from the static config.

        Returns:
            List of {"value": str, "name": str} objects sorted alphabetically by name.
        """
        return sorted(
            [{"value": key, "name": name} for key, name in self._items.items()],
            key=lambda t: t["name"].lower(),
        )

    def get_valid_values(self) -> set[str]:
        """Get valid portfolio value keys.

        Returns:
            Set of valid value strings from the config.
        """
        return set(self._items.keys())


class StaticProductProvider(ProductProvider):
    """Product provider that reads from a static config dictionary."""

    def __init__(self, items: dict[str, str]):
        """Initialize with a static dictionary.

        Args:
            items: Dictionary mapping value keys to display names.
        """
        self._items = items

    def fetch(self) -> list[dict[str, str]]:
        """Fetch product options from the static config.

        Returns:
            List of {"value": str, "name": str} objects sorted alphabetically by name.
        """
        return sorted(
            [{"value": key, "name": name} for key, name in self._items.items()],
            key=lambda t: t["name"].lower(),
        )

    def get_valid_values(self) -> set[str]:
        """Get valid product value keys.

        Returns:
            Set of valid value strings from the config.
        """
        return set(self._items.keys())


class StaticDisciplineProvider(DisciplineProvider):
    """Discipline provider that reads from a static config dictionary."""

    def __init__(self, items: dict[str, str]):
        """Initialize with a static dictionary.

        Args:
            items: Dictionary mapping value keys to display names.
        """
        self._items = items

    def fetch(self) -> list[dict[str, str]]:
        """Fetch discipline options from the static config.

        Returns:
            List of {"value": str, "name": str} objects sorted alphabetically by name.
        """
        return sorted(
            [{"value": key, "name": name} for key, name in self._items.items()],
            key=lambda t: t["name"].lower(),
        )

    def get_valid_values(self) -> set[str]:
        """Get valid discipline value keys.

        Returns:
            Set of valid value strings from the config.
        """
        return set(self._items.keys())
