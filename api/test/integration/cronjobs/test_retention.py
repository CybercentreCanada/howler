import pytest

from howler.cronjobs.retention import _find_analytics_with_hits, _remove_analytics_without_hits
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import EXAMPLE_ANALYTICS


@pytest.fixture(scope="function")
def expected_analytics():
    return [*EXAMPLE_ANALYTICS, "SecretAnalytic"]


def lists_equivalent(l1: list[str], l2: list[str]):
    return sorted(s.lower() for s in l1) == sorted(s.lower() for s in l2)


def get_analytic_names(ds: HowlerDatastore):
    search_result = ds.analytic.search("id:*")
    analytic_names = [item["name"] for item in search_result["items"]]
    return analytic_names


def test_find_analytics_with_hits(datastore_connection_with_hits, expected_analytics):
    """Test that the search returns all the analytic names with matching hits"""

    matched_analytics = _find_analytics_with_hits(datastore_connection_with_hits)

    assert lists_equivalent(matched_analytics, expected_analytics)


def test_remove_analytics_without_hits(datastore_connection_with_hits: HowlerDatastore, expected_analytics):
    """Test that only and all analytics with hits remain after running removal"""

    analytic_names = get_analytic_names(datastore_connection_with_hits)
    assert len(analytic_names) > len(expected_analytics)

    _remove_analytics_without_hits(datastore_connection_with_hits)

    analytic_names = get_analytic_names(datastore_connection_with_hits)
    assert lists_equivalent(analytic_names, expected_analytics)
