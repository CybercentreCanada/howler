from ctypes import cast
from typing import Any, Generator
from unittest.mock import patch

import pytest

from howler.common.exceptions import InvalidDataException, NotFoundException
from howler.datastore.exceptions import DataStoreException
from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.case import Case, CaseItem
from howler.odm.models.hit import Hit
from howler.odm.models.user import User
from howler.odm.random_data import (
    create_cases,
    create_hits,
    create_observables,
    create_users,
    wipe_cases,
    wipe_hits,
    wipe_observables,
    wipe_users,
)
from howler.services import case_service

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    ds = datastore_connection

    try:
        wipe_users(ds)
        create_users(ds)

        if ds.hit.search("howler.id:*")["total"] < 20:
            wipe_hits(ds)
            create_hits(ds, hit_count=20)

        if ds.observable.search("howler.id:*")["total"] < 10:
            wipe_observables(ds)
            create_observables(ds, observable_count=10)

        create_cases(ds, num_cases=5)

        ds.hit.commit()
        ds.observable.commit()
        ds.case.commit()

        yield ds
    finally:
        wipe_cases(ds)
        wipe_users(ds)
        create_users(ds)


@pytest.fixture
def admin_user(datastore: HowlerDatastore) -> User:
    return datastore.user.get("admin", as_obj=True)


@pytest.fixture
def sample_case(datastore: HowlerDatastore) -> Case:
    """Return one pre-existing case from the datastore."""
    return datastore.case.search("case_id:*", rows=1, as_obj=True)["items"][0]


@pytest.fixture
def sample_hit_id(datastore: HowlerDatastore) -> str:
    return datastore.hit.search("howler.id:*", rows=1, as_obj=True)["items"][0].howler.id


@pytest.fixture
def sample_observable_id(datastore: HowlerDatastore) -> str:
    return datastore.observable.search("howler.id:*", rows=1, as_obj=True)["items"][0].howler.id


@pytest.fixture
def fresh_case(datastore: HowlerDatastore) -> Generator[Case, Any, Any]:
    """Create and return a clean empty case (no items); removed after the test."""
    result = case_service.create_case(
        {"title": "Fresh Test Case", "summary": "Used by individual tests"},
        user="admin",
    )
    case_id = result["case_id"]
    datastore.case.commit()
    yield cast(datastore.case.get(case_id, as_obj=True), Case)
    # Cleanup
    datastore.case.delete(case_id)


# ---------------------------------------------------------------------------
# create_case
# ---------------------------------------------------------------------------


def test_create_case_minimal(datastore: HowlerDatastore):
    result = case_service.create_case({"title": "My Case", "summary": "A summary"}, user="admin")

    assert result["title"] == "My Case"
    assert result["case_id"]
    assert any(log["explanation"] == "Case created" for log in result["log"])

    datastore.case.delete(result["case_id"])


def test_create_case_strips_case_id(datastore: HowlerDatastore):
    result = case_service.create_case(
        {"case_id": "should-be-removed", "title": "T", "summary": "S"},
        user="admin",
    )

    assert result["case_id"] != "should-be-removed"
    datastore.case.delete(result["case_id"])


def test_create_case_defaults_log_user_to_system(datastore: HowlerDatastore):
    result = case_service.create_case({"title": "T", "summary": "S"})

    assert result["log"][0]["user"] == "system"
    datastore.case.delete(result["case_id"])


def test_create_case_raises_on_empty_input():
    with pytest.raises(InvalidDataException):
        case_service.create_case({})

    with pytest.raises(InvalidDataException):
        case_service.create_case(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# update_case
# ---------------------------------------------------------------------------


def test_update_case_scalar_field(fresh_case: Case, admin_user: User, datastore: HowlerDatastore):
    case_service.update_case(fresh_case.case_id, {"title": "Updated Title"}, admin_user)
    datastore.case.commit()

    updated = datastore.case.get_if_exists(fresh_case.case_id, as_obj=True)
    assert updated.title == "Updated Title"
    assert any("title" in log.get("key", "") for log in updated.log)


def test_update_case_list_field_logs_diff(fresh_case: Case, admin_user: User, datastore: HowlerDatastore):
    case_service.update_case(fresh_case.case_id, {"targets": ["host-a", "host-b"]}, admin_user)
    datastore.case.commit()

    updated = datastore.case.get_if_exists(fresh_case.case_id, as_obj=True)
    assert set(updated.targets) == {"host-a", "host-b"}

    case_service.update_case(fresh_case.case_id, {"targets": ["host-a"]}, admin_user)
    datastore.case.commit()

    updated = datastore.case.get_if_exists(fresh_case.case_id, as_obj=True)
    log_explanations = [log.get("explanation", "") for log in updated.log]
    assert any("removed" in e for e in log_explanations)


def test_update_case_raises_on_immutable_fields(fresh_case: Case, admin_user: User):
    for field in ("case_id", "created", "updated"):
        with pytest.raises(InvalidDataException, match="immutable"):
            case_service.update_case(fresh_case.case_id, {field: "x"}, admin_user)


def test_update_case_raises_on_empty_update(fresh_case: Case, admin_user: User):
    with pytest.raises(InvalidDataException):
        case_service.update_case(fresh_case.case_id, {}, admin_user)


def test_update_case_raises_not_found(admin_user: User):
    with pytest.raises(NotFoundException):
        case_service.update_case("nonexistent-case-id", {"title": "x"}, admin_user)


# ---------------------------------------------------------------------------
# append_case_item / append_hit
# ---------------------------------------------------------------------------


def test_append_hit_adds_item_and_backreference(fresh_case: Case, sample_hit_id: str, datastore: HowlerDatastore):
    case_service.append_case_item(fresh_case.case_id, item_type="hit", item_value=sample_hit_id)
    datastore.case.commit()
    datastore.hit.commit()

    updated_case = datastore.case.get_if_exists(fresh_case.case_id, as_obj=True)
    hit = datastore.hit.get_if_exists(sample_hit_id, as_obj=True)

    assert any(i["value"] == sample_hit_id for i in updated_case.items)
    assert fresh_case.case_id in hit.howler.related


def test_append_hit_sets_default_path(fresh_case: Case, sample_hit_id: str, datastore: HowlerDatastore):
    case_service.append_case_item(fresh_case.case_id, item_type="hit", item_value=sample_hit_id)
    datastore.case.commit()

    updated_case = datastore.case.get_if_exists(fresh_case.case_id, as_obj=True)
    item = next(i for i in updated_case.items if i["value"] == sample_hit_id)
    assert item["path"].startswith("alerts/")


def test_append_hit_duplicate_raises(fresh_case: Case, sample_hit_id: str):
    case_service.append_case_item(fresh_case.case_id, item_type="hit", item_value=sample_hit_id)

    with pytest.raises(InvalidDataException):
        case_service.append_case_item(fresh_case.case_id, item_type="hit", item_value=sample_hit_id)


def test_append_hit_missing_case_raises(sample_hit_id: str):
    with pytest.raises(NotFoundException):
        case_service.append_case_item("nonexistent-case", item_type="hit", item_value=sample_hit_id)


def test_append_hit_missing_hit_raises(fresh_case: Case):
    with pytest.raises(NotFoundException):
        case_service.append_case_item(fresh_case.case_id, item_type="hit", item_value="nonexistent-hit-id")


# ---------------------------------------------------------------------------
# append_case_item / append_observable
# ---------------------------------------------------------------------------


def test_append_observable_adds_item_and_backreference(
    fresh_case: Case, sample_observable_id: str, datastore: HowlerDatastore
):
    case_service.append_case_item(fresh_case.case_id, item_type="observable", item_value=sample_observable_id)
    datastore.case.commit()
    datastore.observable.commit()

    updated_case = datastore.case.get_if_exists(fresh_case.case_id, as_obj=True)
    observable = datastore.observable.get_if_exists(sample_observable_id, as_obj=True)

    assert any(i["value"] == sample_observable_id for i in updated_case.items)
    assert fresh_case.case_id in observable.howler.related


def test_append_observable_duplicate_raises(fresh_case: Case, sample_observable_id: str):
    case_service.append_case_item(fresh_case.case_id, item_type="observable", item_value=sample_observable_id)

    with pytest.raises(InvalidDataException):
        case_service.append_case_item(fresh_case.case_id, item_type="observable", item_value=sample_observable_id)


def test_append_observable_missing_raises(fresh_case: Case):
    with pytest.raises(NotFoundException):
        case_service.append_case_item(fresh_case.case_id, item_type="observable", item_value="nonexistent-obs-id")


# ---------------------------------------------------------------------------
# append_case_item / append_case (nested case reference)
# ---------------------------------------------------------------------------


def test_append_case_reference(datastore: HowlerDatastore):
    parent = case_service.create_case({"title": "Parent", "summary": "P"}, user="admin")
    child = case_service.create_case({"title": "Child", "summary": "C"}, user="admin")
    datastore.case.commit()

    try:
        case_service.append_case_item(parent["case_id"], item_type="case", item_value=child["case_id"])
        datastore.case.commit()

        updated = datastore.case.get_if_exists(parent["case_id"], as_obj=True)
        assert any(i["value"] == child["case_id"] for i in updated.items)
        item = next(i for i in updated.items if i["value"] == child["case_id"])
        assert child["case_id"] in item["path"]
    finally:
        datastore.case.delete(parent["case_id"])
        datastore.case.delete(child["case_id"])


def test_append_case_duplicate_raises(datastore: HowlerDatastore):
    parent = case_service.create_case({"title": "P", "summary": "P"}, user="admin")
    child = case_service.create_case({"title": "C", "summary": "C"}, user="admin")
    datastore.case.commit()

    try:
        case_service.append_case_item(parent["case_id"], item_type="case", item_value=child["case_id"])

        with pytest.raises(InvalidDataException):
            case_service.append_case_item(parent["case_id"], item_type="case", item_value=child["case_id"])
    finally:
        datastore.case.delete(parent["case_id"])
        datastore.case.delete(child["case_id"])


# ---------------------------------------------------------------------------
# append_case_item validation
# ---------------------------------------------------------------------------


def test_append_case_item_requires_type_and_value(fresh_case: Case):
    with pytest.raises(InvalidDataException):
        case_service.append_case_item(fresh_case.case_id, item_type="hit")

    with pytest.raises(InvalidDataException):
        case_service.append_case_item(fresh_case.case_id, item_value="some-id")


def test_append_case_item_invalid_type_raises(fresh_case: Case):
    with pytest.raises(InvalidDataException):
        case_service.append_case_item(fresh_case.case_id, item_type="unicorn", item_value="some-id")


@pytest.mark.parametrize("item_type", ["table", "lead", "reference"])
def test_append_not_implemented_types_raise(fresh_case: Case, item_type: str):
    item = CaseItem({"type": item_type, "value": "x", "path": "misc/"})
    with pytest.raises(NotImplementedError):
        case_service.append_case_item(fresh_case.case_id, item=item)


# ---------------------------------------------------------------------------
# remove_case_item
# ---------------------------------------------------------------------------


def test_remove_hit_item_clears_backreference(fresh_case: Case, sample_hit_id: str, datastore: HowlerDatastore):
    case_service.append_case_item(fresh_case.case_id, item_type="hit", item_value=sample_hit_id)
    datastore.case.commit()
    datastore.hit.commit()

    case_service.remove_case_item(fresh_case.case_id, sample_hit_id)
    datastore.case.commit()
    datastore.hit.commit()

    updated_case = datastore.case.get_if_exists(fresh_case.case_id, as_obj=True)
    hit = datastore.hit.get_if_exists(sample_hit_id, as_obj=True)

    assert not any(i["value"] == sample_hit_id for i in updated_case.items)
    assert fresh_case.case_id not in hit.howler.related


def test_remove_observable_item_clears_backreference(
    fresh_case: Case, sample_observable_id: str, datastore: HowlerDatastore
):
    case_service.append_case_item(fresh_case.case_id, item_type="observable", item_value=sample_observable_id)
    datastore.case.commit()
    datastore.observable.commit()

    case_service.remove_case_item(fresh_case.case_id, sample_observable_id)
    datastore.case.commit()
    datastore.observable.commit()

    updated_case = datastore.case.get_if_exists(fresh_case.case_id, as_obj=True)
    observable = datastore.observable.get_if_exists(sample_observable_id, as_obj=True)

    assert not any(i["value"] == sample_observable_id for i in updated_case.items)
    assert fresh_case.case_id not in observable.howler.related


def test_remove_case_item_raises_not_found_for_missing_case():
    with pytest.raises(NotFoundException):
        case_service.remove_case_item("nonexistent-case", "some-value")


def test_remove_case_item_raises_not_found_for_missing_item(fresh_case: Case):
    with pytest.raises(NotFoundException):
        case_service.remove_case_item(fresh_case.case_id, "nonexistent-item-value")


# ---------------------------------------------------------------------------
# hide_cases
# ---------------------------------------------------------------------------


def test_hide_cases_marks_case_invisible(datastore: HowlerDatastore):
    case = case_service.create_case({"title": "Hide Me", "summary": "S"}, user="admin")
    datastore.case.commit()

    case_service.hide_cases({case["case_id"]}, user="admin")
    datastore.case.commit()

    hidden = datastore.case.get_if_exists(case["case_id"], as_obj=True)
    assert hidden.visible is False
    datastore.case.delete(case["case_id"])


def test_hide_cases_marks_references_invisible(datastore: HowlerDatastore):
    parent = case_service.create_case({"title": "Parent", "summary": "P"}, user="admin")
    child = case_service.create_case({"title": "Child", "summary": "C"}, user="admin")
    datastore.case.commit()

    case_service.append_case_item(parent["case_id"], item_type="case", item_value=child["case_id"])
    datastore.case.commit()

    case_service.hide_cases({child["case_id"]}, user="admin")
    datastore.case.commit()

    parent_updated = datastore.case.get_if_exists(parent["case_id"], as_obj=True)
    ref_items = [i for i in parent_updated.items if i["value"] == child["case_id"]]
    assert all(not i["visible"] for i in ref_items)

    datastore.case.delete(parent["case_id"])
    datastore.case.delete(child["case_id"])


# ---------------------------------------------------------------------------
# delete_cases
# ---------------------------------------------------------------------------


def test_delete_cases_removes_from_store(datastore: HowlerDatastore):
    case = case_service.create_case({"title": "Delete Me", "summary": "S"}, user="admin")
    datastore.case.commit()

    case_service.delete_cases({case["case_id"]})
    datastore.case.commit()

    assert datastore.case.get_if_exists(case["case_id"]) is None


def test_delete_cases_removes_references_from_other_cases(datastore: HowlerDatastore):
    parent = case_service.create_case({"title": "P", "summary": "P"}, user="admin")
    child = case_service.create_case({"title": "C", "summary": "C"}, user="admin")
    datastore.case.commit()

    case_service.append_case_item(parent["case_id"], item_type="case", item_value=child["case_id"])
    datastore.case.commit()

    case_service.delete_cases({child["case_id"]})
    datastore.case.commit()

    parent_updated = datastore.case.get_if_exists(parent["case_id"], as_obj=True)
    assert not any(i["value"] == child["case_id"] for i in parent_updated.items)

    datastore.case.delete(parent["case_id"])


# ---------------------------------------------------------------------------
# _collect_indicators_from_related
# ---------------------------------------------------------------------------


def test_collect_indicators_from_related_none():
    assert case_service._collect_indicators_from_related(None) == set()


def test_collect_indicators_from_related_values():
    from howler.odm.models.ecs.related import Related

    related = Related(
        {
            "hash": ["abc123"],
            "hosts": ["host-a", "host-b"],
            "ip": ["1.2.3.4"],
            "user": [],
        }
    )

    result = case_service._collect_indicators_from_related(related)
    assert "abc123" in result
    assert "host-a" in result
    assert "host-b" in result
    assert "1.2.3.4" in result


# ---------------------------------------------------------------------------
# _sync_case_metadata
# ---------------------------------------------------------------------------


def test_sync_case_metadata_updates_targets_threats_indicators(
    fresh_case: Case, sample_hit_id: str, datastore: HowlerDatastore
):
    # Set up outline data on the hit so sync has something to find
    hit: Hit = datastore.hit.get_if_exists(sample_hit_id, as_obj=True)
    if hit.howler.outline is None:
        from howler.odm.models.howler_data import Header

        hit.howler.outline = Header(
            {"threat": "evil.example.com", "target": "workstation-01", "indicators": ["hash-abc"]}
        )
        datastore.hit.save(sample_hit_id, hit)
        datastore.hit.commit()

    case_service.append_case_item(fresh_case.case_id, item_type="hit", item_value=sample_hit_id)
    datastore.case.commit()

    updated = datastore.case.get_if_exists(fresh_case.case_id, as_obj=True)
    assert "evil.example.com" in updated.threats
    assert "workstation-01" in updated.targets
    assert "hash-abc" in updated.indicators


def test_sync_case_metadata_noop_on_missing_case():
    # Should not raise even when the case doesn't exist
    case_service._sync_case_metadata("nonexistent-case-id")


def test_sync_case_metadata_clears_after_remove(fresh_case: Case, sample_hit_id: str, datastore: HowlerDatastore):
    hit: Hit = datastore.hit.get_if_exists(sample_hit_id, as_obj=True)
    if hit.howler.outline is None:
        from howler.odm.models.howler_data import Header

        hit.howler.outline = Header({"threat": "evil.example.com", "target": "host-01"})
        datastore.hit.save(sample_hit_id, hit)
        datastore.hit.commit()

    case_service.append_case_item(fresh_case.case_id, item_type="hit", item_value=sample_hit_id)
    datastore.case.commit()

    case_service.remove_case_item(fresh_case.case_id, sample_hit_id)
    datastore.case.commit()

    updated = datastore.case.get_if_exists(fresh_case.case_id, as_obj=True)
    assert updated.targets == []
    assert updated.threats == []


# ---------------------------------------------------------------------------
# _add_backreference / remove_backreference
# ---------------------------------------------------------------------------


def test_add_backreference_raises_on_none_object():
    with pytest.raises(InvalidDataException):
        case_service._add_backreference(None, "case-id")


def test_add_backreference_raises_on_empty_case_id(datastore: HowlerDatastore):
    hit: Hit = datastore.hit.search("howler.id:*", rows=1, as_obj=True)["items"][0]
    with pytest.raises(InvalidDataException):
        case_service._add_backreference(hit, "")


def test_add_backreference_is_idempotent(datastore: HowlerDatastore):
    hit: Hit = datastore.hit.search("howler.id:*", rows=1, as_obj=True)["items"][0]
    hit.howler.related = []

    case_service._add_backreference(hit, "case-abc")
    hit_reload = datastore.hit.get_if_exists(hit.howler.id, as_obj=True)
    case_service._add_backreference(hit_reload, "case-abc")

    hit_final = datastore.hit.get_if_exists(hit.howler.id, as_obj=True)
    assert hit_final.howler.related.count("case-abc") == 1


def test_remove_backreference_raises_on_none_object():
    with pytest.raises(InvalidDataException):
        case_service.remove_backreference(None, "case-id")


def test_remove_backreference_noop_when_not_present(datastore: HowlerDatastore):
    hit: Hit = datastore.hit.search("howler.id:*", rows=1, as_obj=True)["items"][0]
    original_related = list(hit.howler.related)

    # Should not raise and should not change related list
    case_service.remove_backreference(hit, "case-that-was-never-added")

    hit_reload = datastore.hit.get_if_exists(hit.howler.id, as_obj=True)
    assert set(hit_reload.howler.related) == set(original_related)


# ---------------------------------------------------------------------------
# save failure path
# ---------------------------------------------------------------------------


def test_append_hit_raises_on_save_failure(fresh_case: Case, sample_hit_id: str):
    with patch("howler.services.case_service.datastore") as mock_ds:
        real_ds = case_service.datastore()

        def side_effect():
            return real_ds

        mock_ds.side_effect = side_effect

        # First call (get_if_exists) returns the real case; second save() returns False
        mock_case_store = mock_ds.return_value.case
        mock_case_store.get_if_exists.return_value = real_ds.case.get_if_exists(fresh_case.case_id, as_obj=True)
        mock_case_store.save.return_value = False

        with pytest.raises(DataStoreException):
            case_service.append_hit(
                fresh_case.case_id,
                CaseItem({"type": "hit", "value": sample_hit_id, "path": "related/"}),
            )
