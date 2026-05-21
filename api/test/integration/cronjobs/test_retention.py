import pytest

from howler.cronjobs.retention import _find_analytics_with_hits, _remove_analytics_without_hits
from howler.datastore.howler_store import HowlerDatastore
from howler.odm import random_data
from howler.odm.helper import EXAMPLE_ANALYTICS
from howler.odm.models.analytic import Analytic
from howler.odm.randomizer import random_model_obj


@pytest.fixture(scope="function")
def expected_analytics():
    return [*EXAMPLE_ANALYTICS, "SecretAnalytic"]


@pytest.fixture(scope="function")
def orphan_analytic_names():
    return [f"OrphanAnalytic{i}" for i in range(10)]


@pytest.fixture(scope="function")
def rule_analytic_name():
    return "RuleAnalytic"


@pytest.fixture(scope="function")
def rule_analytic(rule_analytic_name):
    a: Analytic = random_model_obj(Analytic)
    a.rule = "some rule"
    a.rule_type = "lucene"
    a.detections = ["Rule"]
    a.name = rule_analytic_name
    return a


@pytest.fixture(scope="function")
def orphan_analytics(orphan_analytic_names):
    analytics = []
    for name in orphan_analytic_names:
        a: Analytic = random_model_obj(Analytic)
        a.rule = None
        a.rule_type = None
        a.name = name
        analytics.append(a)
    return analytics


@pytest.fixture(scope="function")
def datastore_connection_with_hits(datastore_connection, orphan_analytics):
    try:
        random_data.wipe_hits(datastore_connection)
        random_data.wipe_analytics(datastore_connection)
        random_data.create_hits(datastore_connection, hit_count=50)
        for analytic in orphan_analytics:
            datastore_connection.analytic.save(analytic.analytic_id, analytic)
        datastore_connection.analytic.commit()
        yield datastore_connection
    finally:
        random_data.wipe_hits(datastore_connection)
        random_data.wipe_analytics(datastore_connection)


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


@pytest.fixture(scope="function")
def datastore_connection_with_rule_analytics(datastore_connection_with_hits, rule_analytic):
    try:
        datastore_connection_with_hits.analytic.save(rule_analytic.analytic_id, rule_analytic)
        datastore_connection_with_hits.analytic.commit()
        yield datastore_connection_with_hits
    finally:
        datastore_connection_with_hits.analytic.delete(rule_analytic.analytic_id)
        datastore_connection_with_hits.analytic.commit()


@pytest.fixture(scope="function")
def datastore_connection_no_hits(datastore_connection_with_rule_analytics):
    random_data.wipe_hits(datastore_connection_with_rule_analytics)
    yield datastore_connection_with_rule_analytics


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
    assert len(analytic_names) > len(expected_analytics), "Test setup failure: not enough analytics without hits"

    _remove_analytics_without_hits(datastore_connection_with_hits)

    analytic_names = get_analytic_names(datastore_connection_with_hits)
    assert lists_equivalent(analytic_names, expected_analytics)


def test_remove_analytics_without_hits_does_not_remove_rule_analytics(
    datastore_connection_with_rule_analytics, expected_analytics, rule_analytic_name
):
    """Test that analytics with rules are not removed even if they have no hits"""

    expected_analytics_with_rule = expected_analytics + [rule_analytic_name]

    analytic_names = get_analytic_names(datastore_connection_with_rule_analytics)
    assert len(analytic_names) > len(expected_analytics_with_rule), (
        "Test setup failure: not enough analytics without hits"
    )

    _remove_analytics_without_hits(datastore_connection_with_rule_analytics)

    analytic_names = get_analytic_names(datastore_connection_with_rule_analytics)
    assert lists_equivalent(analytic_names, expected_analytics_with_rule)


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


def test_no_hits_remove_analytics_without_hits(datastore_connection_no_hits, rule_analytic_name):
    """Test that empty hits index clears all analytics except rule analytics"""
    before_delete = get_analytic_names(datastore_connection_no_hits)
    assert len(before_delete) != 0, "Test setup failure: there should be analytics to delete"

    _remove_analytics_without_hits(datastore_connection_no_hits)

    analytic_names = get_analytic_names(datastore_connection_no_hits)
    assert analytic_names == [rule_analytic_name]


def test_too_many_analytics_does_not_run_cleanup(monkeypatch, datastore_connection):
    """Test that if the analytics aggregation fails, the cleanup does not run and no analytics are deleted"""

    # simulate large number of analytics
    monkeypatch.setattr(datastore_connection.analytic, "count", lambda *args, **kwargs: {"count": 65537})

    before_delete = get_analytic_names(datastore_connection)

    with pytest.warns(UserWarning, match="size argument higher than the maximum allowed"):
        _remove_analytics_without_hits(datastore_connection)

    after_delete = get_analytic_names(datastore_connection)
    assert lists_equivalent(after_delete, before_delete)
