import uuid

import pytest

from howler.datastore.howler_store import HowlerDatastore
from howler.odm.models.dossier import Dossier
from howler.services import dossier_service


@pytest.fixture(scope="module")
def datastore(datastore_connection):
    yield datastore_connection


@pytest.fixture
def group_dossiers(datastore: HowlerDatastore):
    created_ids = []

    def create(groups: list[str], owner: str = "admin", dossier_type: str = "global") -> Dossier:
        dossier = Dossier(
            {
                "title": f"Pivot group integration test {uuid.uuid4().hex}",
                "query": "howler.id:*",
                "type": dossier_type,
                "owner": owner,
                "pivots": [
                    {
                        "group": group,
                        "label": {"en": group, "fr": group},
                        "value": group,
                        "format": "link",
                    }
                    for group in groups
                ],
            }
        )
        datastore.dossier.save(dossier.dossier_id, dossier)
        created_ids.append(dossier.dossier_id)
        return dossier

    yield create

    for dossier_id in created_ids:
        datastore.dossier.delete(dossier_id)
    datastore.dossier.commit()


def test_get_pivot_groups_filters_prefix_deduplicates_sorts_and_caps(datastore, group_dossiers):
    prefix = f"integration-pivot-{uuid.uuid4().hex}"
    matching_groups = [f"{prefix}/alpha-{index:02}" for index in range(dossier_service.MAX_GROUP_SUGGESTIONS + 2)]
    additional_groups = [f"{prefix}/dns", f"{prefix}/DHCP"]

    group_dossiers(matching_groups)
    group_dossiers([matching_groups[0], *additional_groups, f"{prefix}-other/user"])
    datastore.dossier.commit()

    results = dossier_service.get_pivot_groups(f"{prefix.upper()}/", username="analyst")

    expected_groups = sorted({*matching_groups, *additional_groups})[: dossier_service.MAX_GROUP_SUGGESTIONS]
    assert results == expected_groups
    assert len(results) == dossier_service.MAX_GROUP_SUGGESTIONS


def test_get_pivot_groups_scopes_search_to_visible_dossiers(datastore, group_dossiers):
    prefix = f"integration-visible-{uuid.uuid4().hex}"
    global_group = f"{prefix}/global"
    own_group = f"{prefix}/own"
    other_group = f"{prefix}/other"

    group_dossiers([global_group])
    group_dossiers([own_group], owner="analyst", dossier_type="personal")
    group_dossiers([other_group], owner="other", dossier_type="personal")
    datastore.dossier.commit()

    assert dossier_service.get_pivot_groups(prefix, username="analyst") == sorted([global_group, own_group])


def test_get_pivot_groups_escapes_username_in_visibility_query(datastore, group_dossiers):
    prefix = f"integration-escaped-{uuid.uuid4().hex}"
    global_group = f"{prefix}/global"
    other_group = f"{prefix}/other"

    group_dossiers([global_group])
    group_dossiers([other_group], owner="other", dossier_type="personal")
    datastore.dossier.commit()

    assert dossier_service.get_pivot_groups(prefix, username="analyst) OR owner:(other") == [global_group]


def test_get_pivot_groups_handles_missing_pivots(datastore, group_dossiers):
    prefix = f"integration-missing-{uuid.uuid4().hex}"
    group = f"{prefix}/dns"

    group_dossiers([])
    group_dossiers([group])
    datastore.dossier.commit()

    assert dossier_service.get_pivot_groups(prefix, username="analyst") == [group]


def test_get_pivot_groups_pages_before_capping(datastore, group_dossiers):
    prefix = f"integration-pagination-{uuid.uuid4().hex}"
    groups_before_match = [f"{prefix}/other-{index:03}" for index in range(dossier_service.GROUP_SUGGESTION_PAGE_SIZE)]
    matching_groups = [f"{prefix}/target/alpha", f"{prefix}/target/zulu"]

    group_dossiers([*groups_before_match, *matching_groups])
    datastore.dossier.commit()

    assert dossier_service.get_pivot_groups(f"{prefix}/target", username="analyst") == sorted(matching_groups)


def test_get_pivot_groups_stops_after_the_page_limit(datastore, group_dossiers):
    prefix = f"integration-page-limit-{uuid.uuid4().hex}"
    groups_before_match = [
        f"{prefix}/other-{index:03}"
        for index in range(dossier_service.GROUP_SUGGESTION_PAGE_SIZE * dossier_service.MAX_GROUP_SUGGESTION_PAGES)
    ]
    group_dossiers([*groups_before_match, f"{prefix}/target"])
    datastore.dossier.commit()

    assert dossier_service.get_pivot_groups(f"{prefix}/target", username="analyst") == []
