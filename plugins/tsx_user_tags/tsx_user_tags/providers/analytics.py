"""Analytics-based tag providers that fetch data from the datastore."""

from typing import Any

from howler.common.loader import datastore
from howler.common.logging import get_logger
from howler.config import cache, redis_persistent
from howler.utils.constants import TESTING

from tsx_user_tags.providers.base import PortfolioProvider, ProductProvider

logger = get_logger(__file__)

# Cache TTL: 2 hours (portfolios/products rarely change)
CACHE_TTL = 2 * 60 * 60

# Shared cache version in Redis. The SimpleCache backend is per-worker, so it
# can't be cleared directly. Instead we fold this version into the memoize key
# and bump it to invalidate every worker at once.
_CACHE_VERSION_KEY = "tsx_user_tags:cache_version"


def _skip_cache(*args: Any, **kwargs: Any) -> bool:
    """Skip cache during testing."""
    return TESTING


def _cache_version() -> str:
    """Return the current cache version from Redis, or "0" if unavailable."""
    try:
        value = redis_persistent.get(_CACHE_VERSION_KEY)
    except Exception:
        logger.exception("Failed to read cache version from Redis, using default")
        return "0"

    if value is None:
        return "0"
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def invalidate_cache() -> int:
    """Bump the shared cache version to invalidate tag caches across all workers.

    Returns:
        The new cache version.
    """
    new_version = redis_persistent.incr(_CACHE_VERSION_KEY)
    logger.info("Invalidated analytics tag cache (version %s)", new_version)
    return int(new_version)


@cache.memoize(CACHE_TTL, unless=_skip_cache)
def _fetch_portfolios(_version: str) -> list[dict[str, str]]:
    """Fetch portfolio data from analytics, cached per version for 2 hours.

    Args:
        _version: Shared cache version, used only to scope the cache key.

    Returns:
        List of {"value": str, "name": str} objects.
    """
    ds = datastore()
    result = ds.analytic.search("*:*", fl="name", rows=10000, as_obj=False)
    items = result.get("items", [])

    unique_names = sorted({item["name"] for item in items if item.get("name") and isinstance(item["name"], str)})

    logger.debug("Fetched %d unique customer names from analytics", len(unique_names))
    return [{"value": name, "name": name} for name in unique_names]


@cache.memoize(CACHE_TTL, unless=_skip_cache)
def _fetch_products(_version: str) -> list[dict[str, str]]:
    """Fetch product data from hit providers, cached per version for 2 hours.

    Args:
        _version: Shared cache version, used only to scope the cache key.

    Returns:
        List of {"value": str, "name": str} objects.
    """
    ds = datastore()
    result = ds.hit.facet("event.provider", mincount=1, rows=1000)

    unique_providers = sorted(result.keys())

    logger.debug("Fetched %d unique event providers from hits", len(unique_providers))
    return [{"value": provider, "name": provider} for provider in unique_providers]


class AnalyticsPortfolioProvider(PortfolioProvider):
    """Portfolio provider that fetches customer names from the analytics datastore.

    Queries the analytic datastore for unique 'name' values and uses them
    directly as both the value key and display name.
    """

    def fetch(self) -> list[dict[str, str]]:
        """Fetch unique customer names from analytics.

        Returns:
            List of {"value": str, "name": str} objects for each customer.
            Returns empty list if datastore is unavailable.
        """
        try:
            return _fetch_portfolios(_cache_version())
        except Exception:
            logger.exception("Failed to fetch customers from analytics, returning empty list")
            return []

    def get_valid_values(self) -> set[str]:
        """Get valid portfolio value keys from analytics.

        Returns:
            Set of valid value strings derived from analytics.
        """
        return {item["value"] for item in self.fetch()}


class AnalyticsProductProvider(ProductProvider):
    """Product provider that fetches event providers from the hit datastore.

    Queries the hit datastore for unique 'event.provider' values and uses
    them directly as both the value key and display name.
    """

    def fetch(self) -> list[dict[str, str]]:
        """Fetch unique event providers from hits.

        Returns:
            List of {"value": str, "name": str} objects for each provider.
            Returns empty list if datastore is unavailable.
        """
        try:
            return _fetch_products(_cache_version())
        except Exception:
            logger.exception("Failed to fetch providers from hits, returning empty list")
            return []

    def get_valid_values(self) -> set[str]:
        """Get valid product value keys from hit providers.

        Returns:
            Set of valid value strings derived from hit event providers.
        """
        return {item["value"] for item in self.fetch()}
