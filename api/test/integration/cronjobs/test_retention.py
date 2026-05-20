import pytest

from howler.cronjobs.retention import _find_analytics_with_hits, _remove_analytics_without_hits
from howler.datastore.howler_store import HowlerDatastore
from howler.odm import random_data
from howler.odm.helper import EXAMPLE_ANALYTICS


@pytest.fixture(scope="function")
def expected_analytics():
    return [*EXAMPLE_ANALYTICS, "SecretAnalytic"]


@pytest.fixture(scope="function")
def datastore_connection_with_hits(datastore_connection):
    try:
        random_data.wipe_hits(datastore_connection)
        random_data.wipe_analytics(datastore_connection)
        random_data.create_hits(datastore_connection, hit_count=50)
        random_data.create_analytics(datastore_connection)
        yield datastore_connection
    finally:
        random_data.wipe_hits(datastore_connection)
        random_data.wipe_analytics(datastore_connection)


@pytest.fixture(scope="function")
def datastore_connection_no_hits(datastore_connection_with_hits):
    random_data.wipe_hits(datastore_connection_with_hits)
    yield datastore_connection_with_hits


@pytest.fixture(scope="function")
def datastore_connection_no_extra_analytics(datastore_connection):
    try:
        random_data.wipe_hits(datastore_connection)
        random_data.wipe_analytics(datastore_connection)
        random_data.create_hits(datastore_connection, hit_count=50)
        yield datastore_connection
    finally:
        random_data.wipe_hits(datastore_connection)
        random_data.wipe_analytics(datastore_connection)


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


def test_no_hits_find_analytics_with_hits(datastore_connection_no_hits):
    """Test that if there are no hits the search returns an empty list"""

    matched_analytics = _find_analytics_with_hits(datastore_connection_no_hits)

    assert matched_analytics == []


def test_only_valid_remove_analytics_without_hits(datastore_connection_no_extra_analytics):
    """Test that no analytics removed if all analytics are valid"""

    before_delete = get_analytic_names(datastore_connection_no_extra_analytics)

    _remove_analytics_without_hits(datastore_connection_no_extra_analytics)

    after_delete = get_analytic_names(datastore_connection_no_extra_analytics)
    assert lists_equivalent(after_delete, before_delete)


def test_no_hits_remove_analytics_without_hits(datastore_connection_no_hits):
    """Test that empty hits index clears all analytics"""
    before_delete = get_analytic_names(datastore_connection_no_hits)
    assert len(before_delete) != 0

    _remove_analytics_without_hits(datastore_connection_no_hits)

    analytic_names = get_analytic_names(datastore_connection_no_hits)
    assert analytic_names == []
