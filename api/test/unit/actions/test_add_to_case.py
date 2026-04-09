import pytest

from howler.actions.add_to_case import execute, specification
from howler.common import loader
from howler.common.loader import datastore
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.helper import generate_useful_hit
from howler.odm.models.case import Case
from howler.odm.models.hit import Hit
from howler.odm.random_data import wipe_cases, wipe_hits
from howler.services import case_service


@pytest.fixture(scope="module", autouse=True)
def setup_datastore(datastore_connection: HowlerDatastore):
    try:
        wipe_hits(datastore_connection)
        wipe_cases(datastore_connection)
        datastore_connection.hit.commit()
        datastore_connection.case.commit()

        yield datastore_connection
    finally:
        wipe_hits(datastore_connection)
        wipe_cases(datastore_connection)


# ---------------------------------------------------------------------------
# Validation – no live datastore required
# ---------------------------------------------------------------------------


def test_execute_missing_case_id():
    result = execute("howler.id:*")

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "error"
    assert r["title"] == "Missing Case ID"
    assert "case_id" in r["message"]


def test_execute_missing_case_id_empty_string():
    result = execute("howler.id:*", case_id="")

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "error"
    assert r["title"] == "Missing Case ID"


def test_execute_case_not_found():
    result = execute("howler.id:*", case_id="nonexistent-case-id")

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "error"
    assert r["title"] == "Case Not Found"
    assert "nonexistent-case-id" in r["message"]


# ---------------------------------------------------------------------------
# No matching hits
# ---------------------------------------------------------------------------


def test_execute_no_matching_hits():
    ds = datastore()

    _case = Case({"title": "Test Case", "summary": "For testing"})
    ds.case.save(_case.case_id, _case)
    ds.case.commit()

    result = execute("howler.analytic:ThisAnalyticDoesNotExistAtAll", case_id=_case.case_id)

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "skipped"
    assert r["title"] == "No Matching Hits"

    ds.case.delete(_case.case_id)


# ---------------------------------------------------------------------------
# Happy path – hits added successfully
# ---------------------------------------------------------------------------


def test_execute_adds_hits():
    lookups = loader.get_lookups()
    users = datastore().user.search("uname:*")["items"]

    ds = datastore()

    _case = Case({"title": "Add To Case Test", "summary": "Testing"})
    ds.case.save(_case.case_id, _case)
    ds.case.commit()

    hit: Hit = generate_useful_hit(lookups, [u["uname"] for u in users], prune_hit=False)
    hit.howler.analytic = "TestingAddToCase"
    ds.hit.save(hit.howler.id, hit)
    ds.hit.commit()

    result = execute("howler.analytic:TestingAddToCase", case_id=_case.case_id)

    assert len(result) == 1
    r = result[0]
    assert r["outcome"] == "success"
    assert r["title"] == "Added to Case"
    assert _case.case_id in r["message"]
    assert hit.howler.id in r["query"]

    updated = ds.case.get(_case.case_id)
    assert any(item.value == hit.howler.id for item in updated.items)

    ds.case.delete(_case.case_id)
    ds.hit.delete(hit.howler.id)


def test_execute_default_item_path_uses_analytic_and_id():
    lookups = loader.get_lookups()
    users = datastore().user.search("uname:*")["items"]

    ds = datastore()

    _case = Case({"title": "Path Test Case", "summary": "Testing default path"})
    ds.case.save(_case.case_id, _case)
    ds.case.commit()

    hit: Hit = generate_useful_hit(lookups, [u["uname"] for u in users], prune_hit=False)
    hit.howler.analytic = "TestingDefaultPath"
    ds.hit.save(hit.howler.id, hit)
    ds.hit.commit()

    execute("howler.analytic:TestingDefaultPath", case_id=_case.case_id)

    updated = ds.case.get(_case.case_id)
    item = next(i for i in updated.items if i.value == hit.howler.id)
    expected_path = f"related/{hit.howler.analytic} ({hit.howler.id})"
    assert item.path == expected_path

    ds.case.delete(_case.case_id)
    ds.hit.delete(hit.howler.id)


def test_execute_custom_path():
    lookups = loader.get_lookups()
    users = datastore().user.search("uname:*")["items"]

    ds = datastore()

    _case = Case({"title": "Custom Path Case", "summary": "Testing custom path"})
    ds.case.save(_case.case_id, _case)
    ds.case.commit()

    hit: Hit = generate_useful_hit(lookups, [u["uname"] for u in users], prune_hit=False)
    hit.howler.analytic = "TestingCustomPath"
    ds.hit.save(hit.howler.id, hit)
    ds.hit.commit()

    execute(
        "howler.analytic:TestingCustomPath",
        case_id=_case.case_id,
        path="investigations/q3",
    )

    updated = ds.case.get(_case.case_id)
    item = next(i for i in updated.items if i.value == hit.howler.id)
    assert item.path.startswith("investigations/q3/")

    ds.case.delete(_case.case_id)
    ds.hit.delete(hit.howler.id)


def test_execute_custom_title_template():
    lookups = loader.get_lookups()
    users = datastore().user.search("uname:*")["items"]

    ds = datastore()

    _case = Case({"title": "Template Test Case", "summary": "Testing custom template"})
    ds.case.save(_case.case_id, _case)
    ds.case.commit()

    hit: Hit = generate_useful_hit(lookups, [u["uname"] for u in users], prune_hit=False)
    hit.howler.analytic = "TestingTitleTemplate"
    ds.hit.save(hit.howler.id, hit)
    ds.hit.commit()

    execute(
        "howler.analytic:TestingTitleTemplate",
        case_id=_case.case_id,
        path="",
        title_template="Alert: {{howler.analytic}}",
    )

    updated = ds.case.get(_case.case_id)
    item = next(i for i in updated.items if i.value == hit.howler.id)
    assert item.path == f"Alert: {hit.howler.analytic}"

    ds.case.delete(_case.case_id)
    ds.hit.delete(hit.howler.id)


# ---------------------------------------------------------------------------
# Duplicate hits are skipped, not errored
# ---------------------------------------------------------------------------


def test_execute_duplicate_hit_reported_as_skipped():
    lookups = loader.get_lookups()
    users = datastore().user.search("uname:*")["items"]

    ds = datastore()

    _case = Case({"title": "Duplicate Test Case", "summary": "Testing duplicates"})
    ds.case.save(_case.case_id, _case)
    ds.case.commit()

    hit: Hit = generate_useful_hit(lookups, [u["uname"] for u in users], prune_hit=False)
    hit.howler.analytic = "TestingDuplicate"
    ds.hit.save(hit.howler.id, hit)
    ds.hit.commit()

    # First call – should succeed
    result = execute("howler.analytic:TestingDuplicate", case_id=_case.case_id)
    assert result[0]["outcome"] == "success"

    # Second call – hit already in case, should be skipped
    result = execute("howler.analytic:TestingDuplicate", case_id=_case.case_id)
    assert any(r["outcome"] == "skipped" for r in result)
    assert not any(r["outcome"] == "error" for r in result)

    ds.case.delete(_case.case_id)
    ds.hit.delete(hit.howler.id)


# ---------------------------------------------------------------------------
# Mixed results – some added, some skipped
# ---------------------------------------------------------------------------


def test_execute_mixed_results():
    lookups = loader.get_lookups()
    users = datastore().user.search("uname:*")["items"]

    ds = datastore()

    _case = Case({"title": "Mixed Results Case", "summary": "Testing mixed"})
    ds.case.save(_case.case_id, _case)
    ds.case.commit()

    hit_new: Hit = generate_useful_hit(lookups, [u["uname"] for u in users], prune_hit=False)
    hit_new.howler.analytic = "TestingMixed"
    ds.hit.save(hit_new.howler.id, hit_new)

    hit_existing: Hit = generate_useful_hit(lookups, [u["uname"] for u in users], prune_hit=False)
    hit_existing.howler.analytic = "TestingMixed"
    ds.hit.save(hit_existing.howler.id, hit_existing)

    ds.hit.commit()

    # Pre-add hit_existing so the second execute sees it as a duplicate
    case_service.append_case_item(_case.case_id, item_type="hit", item_value=hit_existing.howler.id)

    result = execute("howler.analytic:TestingMixed", case_id=_case.case_id)

    outcomes = {r["outcome"] for r in result}
    assert "success" in outcomes
    assert "skipped" in outcomes

    ds.case.delete(_case.case_id)
    ds.hit.delete(hit_new.howler.id)
    ds.hit.delete(hit_existing.howler.id)


# ---------------------------------------------------------------------------
# Specification
# ---------------------------------------------------------------------------


def test_specification():
    spec = specification()

    assert spec["id"] == "add_to_case"
    assert spec["title"] == "Add to Case"
    assert "roles" in spec
    assert "automation_basic" in spec["roles"]
    assert "triggers" in spec
    assert "steps" in spec
    steps = spec["steps"]
    assert isinstance(steps, list)
    assert len(steps) == 1
    step: dict = steps[0]  # type: ignore[assignment]
    assert isinstance(step, dict)
    args = step["args"]
    assert "case_id" in args
    assert "path" in args
    assert "title_template" in args
