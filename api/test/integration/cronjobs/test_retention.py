from datetime import datetime

import pytest

from howler.cronjobs import retention as retention_cronjob
from howler.cronjobs.retention import _execute_rules, _find_analytics_with_hits, _remove_analytics_without_hits
from howler.datastore.howler_store import HowlerDatastore
from howler.odm import random_data
from howler.odm.helper import EXAMPLE_ANALYTICS
from howler.odm.models.analytic import Analytic
from howler.odm.models.config import RetentionRule
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


@pytest.fixture(scope="function")
def retention_rule_factory():
    def _build_rule(
        name: str = "test-retention-rule",
        *,
        enabled: bool = True,
        query: str = "howler.id:*",
        limit_unit: str = "days",
        limit_amount: int = 36500,
    ) -> RetentionRule:
        return RetentionRule(
            name=name,
            enabled=enabled,
            query=query,
            limit_unit=limit_unit,
            limit_amount=limit_amount,
        )

    return _build_rule


def lists_equivalent(l1: list[str], l2: list[str]):
    return sorted(s.lower() for s in l1) == sorted(s.lower() for s in l2)


def get_analytic_names(ds: HowlerDatastore):
    search_result = ds.analytic.search("id:*")
    analytic_names = [item["name"] for item in search_result["items"]]
    return analytic_names


def get_hit_count(ds: HowlerDatastore) -> int:
    return ds.hit.search("howler.id:*", rows=0, track_total_hits=True)["total"]


def set_all_hit_created(ds: HowlerDatastore, created_at: str) -> None:
    hits = ds.hit.search("howler.id:*", rows=1000)["items"]

    for hit in hits:
        hit.event.created = created_at
        hit.timestamp = created_at
        ds.hit.save(hit.howler.id, hit)

    ds.hit.commit()


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


def test_execute_rules_deletes_matching_hits(
    datastore_connection_no_extra_analytics: HowlerDatastore, monkeypatch, retention_rule_factory
):
    ds = datastore_connection_no_extra_analytics
    set_all_hit_created(ds, "1900-01-01T00:00:00Z")
    rule = retention_rule_factory(query="howler.id:*", limit_amount=36500)
    monkeypatch.setattr(retention_cronjob.config.system.retention, "rules", [rule])
    before_count = get_hit_count(ds)

    assert before_count > 0

    _execute_rules(ds)

    after_count = get_hit_count(ds)
    assert after_count == 0


def test_execute_rules_preserves_non_matching_hits(
    datastore_connection_no_extra_analytics: HowlerDatastore, monkeypatch, retention_rule_factory
):
    ds = datastore_connection_no_extra_analytics
    rule = retention_rule_factory(query="howler.analytic:NonExistentAnalytic99999")
    monkeypatch.setattr(retention_cronjob.config.system.retention, "rules", [rule])
    before_count = get_hit_count(ds)

    _execute_rules(ds)

    after_count = get_hit_count(ds)
    assert after_count == before_count


def test_execute_rules_preserves_recent_hits(
    datastore_connection_no_extra_analytics: HowlerDatastore, monkeypatch, retention_rule_factory
):
    ds = datastore_connection_no_extra_analytics
    set_all_hit_created(ds, f"{datetime.now().isoformat()}Z")
    rule = retention_rule_factory(query="howler.id:*", limit_amount=0)
    monkeypatch.setattr(retention_cronjob.config.system.retention, "rules", [rule])
    before_count = get_hit_count(ds)

    _execute_rules(ds)

    after_count = get_hit_count(ds)
    assert after_count == before_count


def test_execute_rules_skips_disabled_rule(
    datastore_connection_no_extra_analytics: HowlerDatastore, monkeypatch, retention_rule_factory
):
    ds = datastore_connection_no_extra_analytics
    set_all_hit_created(ds, "1900-01-01T00:00:00Z")
    rule = retention_rule_factory(enabled=False, query="howler.id:*", limit_amount=36500)
    monkeypatch.setattr(retention_cronjob.config.system.retention, "rules", [rule])
    before_count = get_hit_count(ds)

    _execute_rules(ds)

    after_count = get_hit_count(ds)
    assert after_count == before_count


def test_execute_rules_no_rules_is_noop(datastore_connection_no_extra_analytics: HowlerDatastore, monkeypatch):
    ds = datastore_connection_no_extra_analytics
    monkeypatch.setattr(retention_cronjob.config.system.retention, "rules", [])
    before_count = get_hit_count(ds)

    _execute_rules(ds)

    after_count = get_hit_count(ds)
    assert after_count == before_count


def test_execute_rules_continues_after_bad_rule(
    datastore_connection_no_extra_analytics: HowlerDatastore, monkeypatch, retention_rule_factory
):
    ds = datastore_connection_no_extra_analytics
    set_all_hit_created(ds, "1900-01-01T00:00:00Z")
    rules = [
        retention_rule_factory(name="bad-rule", query="howler.id:*", limit_amount=36500),
        retention_rule_factory(name="good-rule", query="howler.id:*", limit_amount=36500),
    ]
    monkeypatch.setattr(retention_cronjob.config.system.retention, "rules", rules)

    original_delete_by_query = ds.hit.delete_by_query
    call_state = {"count": 0}

    def flaky_delete_by_query(query: str, *args, **kwargs):
        call_state["count"] += 1

        if call_state["count"] == 1:
            raise Exception("simulated delete failure")

        return original_delete_by_query(query, *args, **kwargs)

    monkeypatch.setattr(ds.hit, "delete_by_query", flaky_delete_by_query)
    before_count = get_hit_count(ds)

    assert before_count > 0

    _execute_rules(ds)

    after_count = get_hit_count(ds)
    assert call_state["count"] == 2
    assert after_count == 0
